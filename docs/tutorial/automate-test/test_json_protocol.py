"""测试 JSON 协议：直接通过管道与 Delphi exe 通信。"""
import os, sys, json, time, subprocess, ctypes
from ctypes import wintypes

PIPE_NAME = r'\\.\pipe\daofy_auto'

_k32 = ctypes.windll.kernel32

_CreateFile = _k32.CreateFileW
_CreateFile.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
_CreateFile.restype = wintypes.HANDLE

_WriteFile = _k32.WriteFile
_WriteFile.argtypes = [wintypes.HANDLE, wintypes.LPCVOID, wintypes.DWORD, wintypes.PDWORD, wintypes.LPVOID]
_WriteFile.restype = wintypes.BOOL

_ReadFile = _k32.ReadFile
_ReadFile.argtypes = [wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD, wintypes.PDWORD, wintypes.LPVOID]
_ReadFile.restype = wintypes.BOOL

_CloseHandle = _k32.CloseHandle
_CloseHandle.argtypes = [wintypes.HANDLE]
_CloseHandle.restype = wintypes.BOOL

_SetNPHState = _k32.SetNamedPipeHandleState
_SetNPHState.argtypes = [wintypes.HANDLE, wintypes.LPDWORD, wintypes.LPVOID, wintypes.LPVOID]
_SetNPHState.restype = wintypes.BOOL

_WaitNP = _k32.WaitNamedPipeW
_WaitNP.argtypes = [wintypes.LPCWSTR, wintypes.DWORD]
_WaitNP.restype = wintypes.BOOL

_GetLastError = _k32.GetLastError
_GetLastError.restype = wintypes.DWORD

def send_req(req, max_retries=3, delay=0.5):
    """发送 JSON 请求到 Delphi 命名管道，带重试。支持 ERROR_MORE_DATA 循环读取。"""
    ERROR_MORE_DATA = 234
    for attempt in range(max_retries):
        if not _WaitNP(PIPE_NAME, 5000):
            err = _GetLastError()
            if attempt < max_retries - 1:
                time.sleep(delay)
                continue
            return None, None, f'pipe_unavailable ({err})'
        handle = _CreateFile(
            PIPE_NAME, 0x80000000|0x40000000, 0, None, 3, 0, None
        )
        if handle == wintypes.HANDLE(-1).value:
            err = _GetLastError()
            if attempt < max_retries - 1:
                time.sleep(delay)
                continue
            return None, None, f'pipe_open ({err})'
        try:
            mode = wintypes.DWORD(2)
            _SetNPHState(handle, ctypes.byref(mode), None, None)
            b = (json.dumps(req, ensure_ascii=False) + '\0').encode('utf-8')
            written = wintypes.DWORD(0)
            if not _WriteFile(handle, b, len(b), ctypes.byref(written), None):
                return None, None, f'write_failed ({_GetLastError()})'
            # 循环读取，处理 ERROR_MORE_DATA
            chunks = []
            while True:
                buf = ctypes.create_string_buffer(65536)
                read = wintypes.DWORD(0)
                ok = _ReadFile(handle, buf, 65536, ctypes.byref(read), None)
                if ok:
                    chunks.append(buf.raw[:read.value])
                    break
                err_code = _GetLastError()
                if err_code == ERROR_MORE_DATA:
                    chunks.append(buf.raw[:read.value])
                    continue
                return None, None, f'read_failed ({err_code})'
            raw = b''.join(chunks)
            text = raw.decode('utf-8', errors='replace').strip()
            try:
                return json.loads(text), raw, None
            except json.JSONDecodeError:
                return text, raw, None
        finally:
            _CloseHandle(handle)
    return None, None, 'max_retries_exceeded'

def test():
    app = r'C:\user\daofy-agent\daofy\docs\tutorial\automate-test\Win32\Debug\AutoTest.exe'
    snap = r'C:\user\daofy-agent\daofy\docs\tutorial\automate-test\snapshots'

    # Start
    proc = subprocess.Popen([app], cwd=os.path.dirname(app))
    time.sleep(1.5)

    # snapdir
    r, raw, err = send_req({'reqId': 'init', 'cmd': 'snapdir', 'target': snap})
    print(f'snapdir: {r}  err={err}')

    # 1. goto
    r, raw, err = send_req({'reqId': '001', 'cmd': 'goto', 'target': 'TForm1'})
    print(f'goto: {r}')
    assert r and r.get('status') in ('ok',), f'goto failed: {r}'

    # 2. wait before type to avoid race
    r, raw, err = send_req({'reqId': '002', 'cmd': 'wait', 'ms': '300'})
    print(f'wait: {r} err={err}')

    # 3. type
    r, raw, err = send_req({'reqId': '003', 'cmd': 'type', 'target': 'EditName', 'value': 'JSON测试'})
    print(f'type: r={r} err={err}')
    assert r and r.get('status') == 'ok', f'type failed: r={r} err={err}'

    # 4. rget - debug raw bytes
    r, raw, err = send_req({'reqId': '004', 'cmd': 'rget', 'target': 'EditName', 'prop': 'Text'})
    print(f'rget Text: parsed={r} err={err}')
    if raw:
        # print hex of the entire response
        print(f'  raw ({len(raw)} bytes): {raw.hex()}')
        # try decoding piece by piece to find corruption
        for encoding in ['utf-8', 'utf-16-le', 'gbk', 'cp1252']:
            try:
                decoded = raw.strip().decode(encoding, errors='replace')
                print(f'  decode as {encoding}: {decoded[:80]!r}')
            except:
                pass
    assert r and r.get('status') == 'ok', f'rget failed: r={r} err={err}'
    print(f'  data: {r.get("data")!r}')

    # 5. rset
    r, raw, err = send_req({'reqId': '005', 'cmd': 'rset', 'target': 'EditName', 'prop': 'Text', 'value': 'RTTI设置成功'})
    print(f'rset: r={r} err={err}')
    assert r and r.get('status') == 'ok', f'rset failed: r={r} err={err}'
    print(f'  rset OK, verifying...')

    # 6. rget verify
    r, raw, err = send_req({'reqId': '006', 'cmd': 'rget', 'target': 'EditName', 'prop': 'Text'})
    print(f'rget verify: parsed={r} err={err}')
    assert r and r.get('status') == 'ok', f'rget verify failed: r={r} err={err}'
    print(f'  data: {r.get("data")!r}')

    # 7. rget BtnHello.Caption
    r, raw, err = send_req({'reqId': '007', 'cmd': 'rget', 'target': 'BtnHello', 'prop': 'Caption'})
    print(f'rget BtnHello.Caption: r={r} err={err}')
    assert r and r.get('status') == 'ok', f'rget BtnHello failed: r={r} err={err}'

    # 8. rinspect (同步，返回 JSON 数据)
    r, raw, err = send_req({'reqId': '008', 'cmd': 'rinspect', 'target': 'EditName'})
    print(f'rinspect: r={r} err={err}')
    assert r and r.get('status') == 'ok', f'rinspect failed: r={r} err={err}'
    assert 'EditName' in json.dumps(r.get('data', '')), f'rinspect no EditName: {r}'

    # 9. TreeView nested RTTI: Items.Count (6 total nodes)
    r, raw, err = send_req({'reqId': '009', 'cmd': 'rget', 'target': 'TreeView1', 'prop': 'Items.Count'})
    print(f'rget TreeView1.Items.Count: r={r}')
    assert r and r.get('status') == 'ok', f'Items.Count failed: {r}'
    assert r.get('data') == '6', f'Items.Count expected 6, got {r.get("data")!r}'

    # 10. TreeView Selected (initially nil -> "(empty)")
    r, raw, err = send_req({'reqId': '010', 'cmd': 'rget', 'target': 'TreeView1', 'prop': 'Selected'})
    print(f'rget TreeView1.Selected (nil): r={r}')
    assert r and r.get('status') == 'ok', f'Selected nil failed: {r}'
    assert r.get('data') == '(empty)', f'Selected expected (empty), got {r.get("data")!r}'

    # 11. click TreeView1 to select first node, then read Selected.Text
    r, raw, err = send_req({'reqId': '011', 'cmd': 'click', 'target': 'TreeView1@5,5'})
    print(f'click TreeView1: r={r}')
    assert r and r.get('status') == 'ack', f'click TreeView1 failed: {r}'
    time.sleep(0.5)

    r, raw, err = send_req({'reqId': '012', 'cmd': 'rget', 'target': 'TreeView1', 'prop': 'Selected.Text'})
    print(f'rget TreeView1.Selected.Text: r={r}')
    assert r and r.get('status') == 'ok', f'Selected.Text failed: {r}'
    assert r.get('data') == 'Root1', f'Selected.Text expected Root1, got {r.get("data")!r}'

    # 13. error case: unknown cmd
    r, raw, err = send_req({'reqId': '013', 'cmd': 'nonexistent'})
    print(f'unknown cmd: r={r} err={err}')
    assert r and r.get('status') == 'err', f'unknown cmd should err: r={r} err={err}'

    # 14. exit
    r, raw, err = send_req({'reqId': '999', 'cmd': 'exit'})
    print(f'exit: r={r} err={err}')

    time.sleep(0.5)
    proc.kill()
    print('\n=== ALL TESTS PASSED ===')

if __name__ == '__main__':
    test()
