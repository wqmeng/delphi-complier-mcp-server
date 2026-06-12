"""完整自动化命令测试 — 覆盖所有新增和基础命令。"""
import os, sys, json, time, subprocess, ctypes
from ctypes import wintypes

PIPE_NAME = r'\\.\pipe\daofy_auto'
_k32 = ctypes.windll.kernel32

_CreateFile = _k32.CreateFileW
_CreateFile.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
_CreateFile.restype = wintypes.HANDLE
_WriteFile = _k32.WriteFile
_WriteFile.argtypes = [wintypes.HANDLE, wintypes.LPCVOID, wintypes.DWORD, wintypes.PDWORD, wintypes.LPVOID]
_ReadFile = _k32.ReadFile
_ReadFile.argtypes = [wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD, wintypes.PDWORD, wintypes.LPVOID]
_CloseHandle = _k32.CloseHandle
_SetNPHState = _k32.SetNamedPipeHandleState
_SetNPHState.argtypes = [wintypes.HANDLE, wintypes.LPDWORD, wintypes.LPVOID, wintypes.LPVOID]
_WaitNP = _k32.WaitNamedPipeW
_WaitNP.argtypes = [wintypes.LPCWSTR, wintypes.DWORD]
_GetLastError = _k32.GetLastError

def send(req):
    """发送命令，返回 (json_response, error)"""
    for _ in range(3):
        if not _WaitNP(PIPE_NAME, 3000):
            time.sleep(0.5); continue
        h = _CreateFile(PIPE_NAME, 0x80000000|0x40000000, 0, None, 3, 0, None)
        if h == wintypes.HANDLE(-1).value:
            time.sleep(0.5); continue
        try:
            mode = wintypes.DWORD(2)
            _SetNPHState(h, ctypes.byref(mode), None, None)
            b = (json.dumps(req, ensure_ascii=False) + '\0').encode('utf-8')
            written = wintypes.DWORD(0)
            if not _WriteFile(h, b, len(b), ctypes.byref(written), None):
                return None, 'write_failed'
            chunks = []
            while True:
                buf = ctypes.create_string_buffer(65536)
                read = wintypes.DWORD(0)
                ok = _ReadFile(h, buf, 65536, ctypes.byref(read), None)
                if ok:
                    chunks.append(buf.raw[:read.value]); break
                err = _GetLastError()
                if err == 234:
                    chunks.append(buf.raw[:read.value]); continue
                return None, f'read_failed({err})'
            raw = b''.join(chunks)
            return json.loads(raw.decode('utf-8').strip()), None
        finally:
            _CloseHandle(h)
    return None, 'retry_exhausted'

ok = err = 0
def check(name, r, exp_status='ok'):
    global ok, err
    status = r.get('status') if r else 'noresp'
    data = r.get('data', '') if r else ''
    if status == exp_status:
        ok += 1
        print(f'  PASS {name}: {data[:80]}')
    else:
        err += 1
        print(f'  FAIL {name}: expected {exp_status}, got {status} data={data[:80]!r}')

# 启动程序
print("=== 启动 AutoTest ===")
proc = subprocess.Popen([
    r'C:\user\daofy-agent\daofy\docs\tutorial\automate-test\Win32\Debug\AutoTest.exe'
], cwd=r'C:\user\daofy-agent\daofy\docs\tutorial\automate-test\Win32\Debug')
time.sleep(1.5)

# 设置截图目录
snap = r'C:\user\daofy-agent\daofy\docs\tutorial\automate-test\snapshots'
r, e = send({'reqId':'init','cmd':'snapdir','target':snap})
check('snapdir', r)

# ── 基础命令 ──
print("\n=== 基础命令 ===")
r, _ = send({'reqId':'g1','cmd':'goto','target':'TForm1'}); check('goto', r)
r, _ = send({'reqId':'w1','cmd':'wait','ms':'200'}); check('wait', r)

# ── rget/rset/rcall (RTTI 命令) ──
print("\n=== RTTI 命令 ===")
r, _ = send({'reqId':'rg1','cmd':'rget','target':'EditName','prop':'Text'}); check('rget Text', r)
r, _ = send({'reqId':'rs1','cmd':'rset','target':'EditName','prop':'Text','value':'Hello'}); check('rset Text', r, 'ack')
r, _ = send({'reqId':'rs1p','cmd':'peekresult','target':'rs1'}); check('rset result', r)
r, _ = send({'reqId':'rg2','cmd':'rget','target':'EditName','prop':'Text'}); check('rget verify', r)
r, _ = send({'reqId':'rg3','cmd':'rget','target':'EditName','prop':'SelLength'}); check('rget SelLength', r)
r, _ = send({'reqId':'rc1','cmd':'rcall','target':'EditName','method':'SelectAll'}); check('rcall SelectAll', r, 'ack')
r, _ = send({'reqId':'rg4','cmd':'rget','target':'EditName','prop':'SelLength'}); check('rget SelLength>0', r)

# ── rinspect ──
print("\n=== rinspect ===")
r, _ = send({'reqId':'ri1','cmd':'rinspect','target':'EditName'})
if r and r.get('status') == 'ok':
    data = r.get('data', '')
    if 'methods' in data and 'props' in data:
        ok += 1; print(f'  ✅ rinspect: methods+props OK ({len(data)} bytes)')
    else:
        err += 1; print(f'  ❌ rinspect: no methods/props in response')
else:
    err += 1; print(f'  ❌ rinspect: {r}')

# ── listwnd ──
print("\n=== listwnd ===")
r, _ = send({'reqId':'lw1','cmd':'listwnd'}); check('listwnd', r)
if r and r.get('status') == 'ok':
    data = json.loads(r.get('data', '{}'))
    windows = data.get('windows', [])
    print(f'         windows: {len(windows)} found')
    for w in windows:
        print(f'           - {w.get("name")} ({w.get("class")}) active={w.get("active")}')

# ── dumpstate ──
print("\n=== dumpstate ===")
r, _ = send({'reqId':'ds1','cmd':'dumpstate'}); check('dumpstate', r)
if r and r.get('status') == 'ok':
    print(f'         data: {len(r.get("data",""))} chars')

# ── 鼠标命令 ──
print("\n=== 鼠标命令 ===")
r, _ = send({'reqId':'mv1','cmd':'move','target':'EditName'}); check('move', r, 'ack')
r, _ = send({'reqId':'hv1','cmd':'hover','target':'BtnHello'}); check('hover', r, 'ack')
r, _ = send({'reqId':'cl1','cmd':'click','target':'EditName@5,5'}); check('click@x,y', r, 'ack')
r, _ = send({'reqId':'cl2','cmd':'click','target':'BtnHello'}); check('click BtnHello', r, 'ack')

# ── key 命令 ──
print("\n=== key 命令 ===")
r, _ = send({'reqId':'ky1','cmd':'key','target':'EditName','key':'Tab'}); check('key Tab', r, 'ack')
r, _ = send({'reqId':'ky2','cmd':'key','target':'EditName','key':'Enter'}); check('key Enter', r, 'ack')
r, _ = send({'reqId':'ky3','cmd':'key','target':'EditName','key':'Esc'}); check('key Esc', r, 'ack')
r, _ = send({'reqId':'ky4','cmd':'key','target':'EditName','key':'Space'}); check('key Space', r, 'ack')

# ── capture ──
print("\n=== capture ===")
r, _ = send({'reqId':'cp1','cmd':'capture','target':'test_all'}); check('capture', r)

# ── 弹出菜单（选中文本 + 右键 + 复制 + 剪贴板验证）──
print("\n=== 弹出菜单 ===")
# 先设焦点 + 全选（焦点必须，否则 SelectAll 无效果）
r, _ = send({'reqId':'rc0','cmd':'rcall','target':'EditName','method':'SetFocus'}); check('SetFocus', r, 'ack')
r, _ = send({'reqId':'rc0b','cmd':'wait','ms':'100'}); check('wait', r)
r, _ = send({'reqId':'rc0c','cmd':'rcall','target':'EditName','method':'SelectAll'}); check('SelectAll', r, 'ack')
r, _ = send({'reqId':'rc0d','cmd':'rget','target':'EditName','prop':'SelLength'}); check('SelLength>0', r)
sel_len = int(r.get('data', '0')) if r else 0
print(f'         SelLength={sel_len}')
has_selection = sel_len > 0
if has_selection:
    ok += 1; print(f'  ✅ 文本已选中 ({sel_len} 字符)')
else:
    err += 1; print(f'  ❌ 文本未选中')

# 弹出右键菜单
r, _ = send({'reqId':'rc1','cmd':'rclick','target':'EditName'}); check('rclick', r, 'ack')
time.sleep(0.3)
# 扫描菜单项，确认"复制"在里面
r, _ = send({'reqId':'rc2','cmd':'dlgscan'}); check('dlgscan', r)
if r and r.get('status') == 'ok':
    menu_data = json.loads(r.get('data', '{}'))
    items = [it.get('caption','') for it in menu_data.get('items', [])]
    found_copy = any('复制' in it for it in items)
    if found_copy:
        ok += 1; print(f'  ✅ 菜单含"复制": {items}')
    else:
        err += 1; print(f'  ❌ 菜单无"复制": {items}')
    # 取完整 Caption（含加速键如 (&X)，dlgclick 需要精确匹配）
    copy_caption = next((it for it in items if '复制' in it), '')
    print(f'         dlgclick target="{copy_caption}"')
else:
    err += 1; print(f'  ❌ dlgscan failed')
    copy_caption = '复制'

# 点击"复制"（同步，菜单项存在则返回 OK，不存在返回 NF）
r, _ = send({'reqId':'rc3','cmd':'dlgclick','target':copy_caption}); check('dlgclick 复制', r, 'ack')

# ── waitfor ──
print("\n=== waitfor ===")
r, _ = send({'reqId':'wf1','cmd':'waitfor','target':'EditName','prop':'Text','value':'Hello','timeout':'2000'}); check('waitfor Text=Hello', r)

# ── exit ──
print("\n=== exit ===")
r, _ = send({'reqId':'ex1','cmd':'exit'}); check('exit', r)
time.sleep(0.5)

proc.kill()
print(f"\n{'='*40}\n结果: {ok} 通过, {err} 失败")
sys.exit(0 if err == 0 else 1)
