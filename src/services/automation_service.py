r"""
自动化截图服务 — 驱动 Delphi 程序执行流程并截图。

通信方式：命名管道 \\.\pipe\daofy_auto（Delphi server -> Python client）
使用 ctypes 直接调用 Windows API，零外部依赖。

协议：JSON 请求/响应 (REST-style)
  请求: {"reqId":"step_0","cmd":"goto","target":"TForm1"}
  响应: {"reqId":"step_0","status":"ok","data":"OK"}
  (async 命令: click/rclick/msgclick/dlgclick/hover/rinspect 返回 ACK，
   rinspect 结果写入 FSSDir\_async_{reqId}.json 文件)

进程池复用：
  通过 keep_alive 参数让 Delphi 进程常驻，后续调用直接复用。
  进程超过 PROCESS_KEEPALIVE_TIMEOUT 未被使用会自动清理。
"""

import os
import json
import time
import subprocess
import ctypes
from ctypes import wintypes
from pathlib import Path
from threading import Lock

PROJECT_ROOT = Path(__file__).parent.parent.parent
DEFAULT_SNAPSHOTS_DIR = PROJECT_ROOT / 'docs' / 'copyright' / 'snapshots'
PIPE_NAME = r'\\.\pipe\daofy_auto'

# ── 进程池 ──
_process_pool: dict[str, dict] = {}
_pool_lock = Lock()
PROCESS_KEEPALIVE_TIMEOUT = 300  # 5 分钟无使用则自动清理

# ── Windows API ──
GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
OPEN_EXISTING = 3
PIPE_READMODE_MESSAGE = 2
INVALID_HANDLE_VALUE = wintypes.HANDLE(-1).value
PIPE_TIMEOUT_MS = 5000

_k32 = ctypes.windll.kernel32

_CreateFile = _k32.CreateFileW
_CreateFile.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                        wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD,
                        wintypes.HANDLE]
_CreateFile.restype = wintypes.HANDLE

_WriteFile = _k32.WriteFile
_WriteFile.argtypes = [wintypes.HANDLE, wintypes.LPCVOID, wintypes.DWORD,
                       wintypes.PDWORD, wintypes.LPVOID]
_WriteFile.restype = wintypes.BOOL

_ReadFile = _k32.ReadFile
_ReadFile.argtypes = [wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD,
                      wintypes.PDWORD, wintypes.LPVOID]
_ReadFile.restype = wintypes.BOOL

_CloseHandle = _k32.CloseHandle
_CloseHandle.argtypes = [wintypes.HANDLE]
_CloseHandle.restype = wintypes.BOOL

_SetNPHState = _k32.SetNamedPipeHandleState
_SetNPHState.argtypes = [wintypes.HANDLE, wintypes.LPDWORD,
                         wintypes.LPVOID, wintypes.LPVOID]
_SetNPHState.restype = wintypes.BOOL

_WaitNP = _k32.WaitNamedPipeW
_WaitNP.argtypes = [wintypes.LPCWSTR, wintypes.DWORD]
_WaitNP.restype = wintypes.BOOL

_GetLastError = _k32.GetLastError
_GetLastError.restype = wintypes.DWORD


def _send_command(cmd: str, timeout_ms: int = PIPE_TIMEOUT_MS) -> str:
    """发送命令到 Delphi 命名管道。"""
    if not _WaitNP(PIPE_NAME, timeout_ms):
        return f'ERR:pipe_unavailable (err={_GetLastError()})'

    handle = _CreateFile(
        PIPE_NAME, GENERIC_READ | GENERIC_WRITE, 0,
        None, OPEN_EXISTING, 0, None,
    )
    if handle == INVALID_HANDLE_VALUE:
        return f'ERR:pipe_open (err={_GetLastError()})'

    try:
        mode = wintypes.DWORD(PIPE_READMODE_MESSAGE)
        _SetNPHState(handle, ctypes.byref(mode), None, None)

        cmd_bytes = cmd.encode('utf-8') + b'\0'
        written = wintypes.DWORD(0)
        if not _WriteFile(handle, cmd_bytes, len(cmd_bytes),
                          ctypes.byref(written), None):
            return f'ERR:write_failed (err={_GetLastError()})'

        # 循环读取，处理 ERROR_MORE_DATA（管道消息 > 64KB 时分批到达）
        BUF_SIZE = 65536
        chunks = []
        while True:
            buf = ctypes.create_string_buffer(BUF_SIZE)
            read = wintypes.DWORD(0)
            ok = _ReadFile(handle, buf, BUF_SIZE, ctypes.byref(read), None)
            if ok:
                chunks.append(buf.raw[:read.value])
                break
            # 获取错误码
            err = _GetLastError()
            if err == 234:  # ERROR_MORE_DATA
                chunks.append(buf.raw[:read.value])
                continue
            return f'ERR:read_failed (err={err})'
        return b''.join(chunks).decode('utf-8', errors='replace').strip()
    finally:
        _CloseHandle(handle)


def _wait_for_pipe(timeout: float = 10.0) -> bool:
    """等待 Delphi 程序创建管道。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _WaitNP(PIPE_NAME, 200):
            return True
        time.sleep(0.2)
    return False


# ── 进程池管理 ──

def _cleanup_stale_processes():
    """清理超时未用的进程。"""
    now = time.time()
    with _pool_lock:
        stale = [k for k, v in _process_pool.items()
                 if now - v['last_used'] > PROCESS_KEEPALIVE_TIMEOUT]
        for key in stale:
            entry = _process_pool.pop(key)
            try:
                entry['proc'].kill()
            except Exception:
                pass


def _ensure_process(app_path: str, wait_for_pipe: float) -> tuple[bool, str]:
    """确保 app_path 对应的进程在运行。返回 (是否新建, 错误信息)。"""
    _cleanup_stale_processes()

    with _pool_lock:
        if app_path in _process_pool:
            entry = _process_pool[app_path]
            if entry['proc'].poll() is None:
                entry['last_used'] = time.time()
                return False, ''  # 复用已有进程
            # 进程已死，移除
            del _process_pool[app_path]

    # 启动新进程
    try:
        proc = subprocess.Popen(
            [app_path],
            cwd=os.path.dirname(app_path) or None,
        )
    except Exception as e:
        return True, f'启动失败: {e}'

    if not _wait_for_pipe(wait_for_pipe):
        try:
            proc.kill()
        except Exception:
            pass
        return True, f'Delphi 程序未在 {wait_for_pipe}s 内创建管道'

    with _pool_lock:
        _process_pool[app_path] = {
            'proc': proc,
            'last_used': time.time(),
        }
    return True, ''


def _kill_process(app_path: str):
    """强制终止指定进程。"""
    with _pool_lock:
        entry = _process_pool.pop(app_path, None)
    if entry:
        try:
            entry['proc'].kill()
        except Exception:
            pass


def execute_script(app_path: str, script,
                   snapshots_dir: str = '',
                   wait_for_pipe: float = 10.0,
                   keep_alive: bool = False) -> dict:
    """执行自动化脚本。

    支持进程池复用：同一个 app_path 在 keep_alive=True 后保持运行，
    后续调用直接复用已有进程。

    Args:
        app_path: Delphi exe 路径
        script: JSON 脚本（文件路径 / JSON 字符串 / list）
        snapshots_dir: 截图输出目录（默认 docs/copyright/snapshots）
        wait_for_pipe: 等待管道超时秒数
        keep_alive: True=执行完后保持进程运行供后续复用

    Returns:
        dict 执行结果，包含 process_reused 指示是否复用了已有进程。
    """
    if not snapshots_dir:
        snapshots_dir = str(DEFAULT_SNAPSHOTS_DIR)
    Path(snapshots_dir).mkdir(parents=True, exist_ok=True)

    # 解析脚本
    if isinstance(script, str):
        script = script.strip()
        steps = json.loads(open(script, 'r', encoding='utf-8')) if os.path.isfile(script) else json.loads(script)
    elif isinstance(script, list):
        steps = script
    else:
        return {'status': 'error', 'message': 'script 须为文件路径、JSON 字符串或列表'}

    # 获取或创建进程
    is_new, err = _ensure_process(app_path, wait_for_pipe)
    if err:
        return {'status': 'error', 'message': err}

    # 新建进程时需要设置截图目录
    if is_new:
        _send_command(json.dumps(
            {"reqId": "init", "cmd": "snapdir", "target": snapshots_dir},
            ensure_ascii=False))
        time.sleep(0.2)

    results = []
    success = True
    req_index = 0

    for step in steps:
        cmd = step.get('cmd', '')
        target = step.get('target', step.get('name', ''))
        ms = step.get('ms', step.get('wait', 500))
        capture_name = step.get('capture', '')
        req_id = f'step_{req_index}'
        req_index += 1

        # 构造 JSON 请求
        req = {'reqId': req_id, 'cmd': cmd}
        if target:
            req['target'] = target

        if cmd == 'type':
            req['value'] = step.get('text', step.get('value', target))
        elif cmd == 'wait':
            req['ms'] = str(ms)
        elif cmd in ('rget',):
            parts = target.split('.', 1)
            req['target'] = parts[0]
            if len(parts) > 1:
                req['prop'] = parts[1]
            else:
                req['prop'] = step.get('prop', '')
        elif cmd in ('rset',):
            parts = target.split('.', 1)
            req['target'] = parts[0]
            req['prop'] = parts[1] if len(parts) > 1 else step.get('prop', '')
            req['value'] = step.get('value', step.get('text', ''))
        elif cmd == 'rcall':
            req['method'] = step.get('method', target)
            params_val = step.get('params')
            if params_val is not None:
                req['params'] = json.dumps(params_val, ensure_ascii=False)
        elif cmd == 'move':
            if target:
                req['target'] = target
            x_val = step.get('x')
            y_val = step.get('y')
            if x_val is not None:
                req['x'] = str(x_val)
            if y_val is not None:
                req['y'] = str(y_val)
        elif cmd == 'capture':
            if not target:
                req['target'] = step.get('name', '')
        elif cmd == 'dumpstate':
            req['target'] = step.get('name', target)
        elif cmd == 'waitfor':
            req['prop'] = step.get('prop', '')
            req['value'] = str(step.get('value', ''))
            timeout_val = step.get('timeout', 5000)
            interval_val = step.get('interval', 100)
            req['timeout'] = str(timeout_val)
            req['interval'] = str(interval_val)
        elif cmd == 'key':
            req['key'] = step.get('key', target)
            if target:
                req['target'] = target
        elif cmd == 'drag':
            req['source'] = step.get('source', target)
            tgt = step.get('target', '')
            if tgt:
                req['target'] = tgt
            x_val = step.get('x')
            y_val = step.get('y')
            if x_val is not None:
                req['x'] = str(x_val)
            if y_val is not None:
                req['y'] = str(y_val)
        elif cmd == 'dlgfile':
            path_val = step.get('path', '')
            if path_val:
                req['path'] = path_val

        cmd_str = json.dumps(req, ensure_ascii=False)
        resp_raw = _send_command(cmd_str)

        # 解析 JSON 响应
        try:
            resp_json = json.loads(resp_raw) if resp_raw else {}
            resp_status = resp_json.get('status', 'err')
        except json.JSONDecodeError:
            resp_json = {'status': 'err', 'data': resp_raw}
            resp_status = 'err'

        ok = resp_status in ('ok', 'ack')

        # dumpstate/dlgscan 返回的就是 JSON 字符串，存到响应的 state 字段
        if cmd in ('dumpstate', 'dlgscan') and ok and resp_json.get('data'):
            try:
                parsed = json.loads(resp_json['data'])
                resp_json['state'] = parsed
            except (json.JSONDecodeError, TypeError):
                pass

        if capture_name and cmd != 'capture':
            _send_command(json.dumps({"reqId": f"cap_{req_id}", "cmd": "capture", "target": capture_name}, ensure_ascii=False))
            results.append({
                'step': step, 'command': cmd_str,
                'capture': capture_name, 'status': 'ok',
            })
        else:
            results.append({
                'step': step, 'command': cmd_str,
                'response': resp_json, 'status': 'ok' if ok else 'error',
            })

        if not ok:
            success = False
        time.sleep(0.3)

    # keep_alive=False：确保进程退出（脚本没 exit 则自动发送）
    if not keep_alive:
        has_exit = any(s.get('cmd') == 'exit' for s in steps)
        if not has_exit:
            _send_command(json.dumps(
                {"reqId": "auto_exit", "cmd": "exit"}, ensure_ascii=False))
            time.sleep(0.5)
        # 给进程一点时间退出，从池中移除
        time.sleep(0.5)
        with _pool_lock:
            _process_pool.pop(app_path, None)

    return {
        'status': 'ok' if success else 'partial',
        'app_path': app_path,
        'snapshots_dir': snapshots_dir,
        'steps_total': len(steps),
        'process_reused': not is_new,
        'process_alive': app_path in _process_pool,
        'results': results,
    }
