"""验证：右键菜单 → 点击菜单项 → 弹出 MessageBox → 截图 → msgclick 关闭"""
import os, sys, json, time, subprocess, ctypes
from ctypes import wintypes

PIPE_NAME = r'\\.\pipe\daofy_auto'
_k32 = ctypes.windll.kernel32
_CreateFile = _k32.CreateFileW
_CreateFile.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
_WriteFile = _k32.WriteFile
_ReadFile = _k32.ReadFile
_CloseHandle = _k32.CloseHandle
_SetNPHState = _k32.SetNamedPipeHandleState
_WaitNP = _k32.WaitNamedPipeW
_GetLastError = _k32.GetLastError

def send(req):
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
            return json.loads(b''.join(chunks).decode('utf-8').strip()), None
        finally:
            _CloseHandle(h)
    return None, 'retry'

snap = r'C:\user\daofy-agent\daofy\docs\tutorial\automate-test\snapshots'
exe = r'C:\user\daofy-agent\daofy\docs\tutorial\automate-test\Win32\Debug\AutoTest.exe'
proc = subprocess.Popen([exe], cwd=os.path.dirname(exe))
time.sleep(1.5)

ok = err = 0
def check(name, r, exp='ok'):
    global ok, err
    s = r.get('status','') if r else 'noresp'
    d = r.get('data','') if r else ''
    if s == exp:
        ok += 1; print(f'  PASS {name}: {d[:60]}')
    else:
        err += 1; print(f'  FAIL {name}: expect {exp} got {s} data={d[:60]!r}')

send({'reqId':'init','cmd':'snapdir','target':snap})

print("=== 1. 激活窗体 ===")
r, _ = send({'reqId':'g','cmd':'goto','target':'TForm1'}); check('goto', r)

print("\n=== 2. 截主窗体 ===")
r, _ = send({'reqId':'c1','cmd':'capture','target':'dlgtest_before'}); check('capture main', r)

print("\n=== 3. 右键弹出菜单 ===")
r, _ = send({'reqId':'rc','cmd':'rclick','target':'EditName'}); check('rclick', r, 'ack')
time.sleep(0.3)

print("\n=== 4. 扫描菜单 ===")
r, _ = send({'reqId':'ds','cmd':'dlgscan'}); check('dlgscan', r)
if r and r.get('status') == 'ok':
    items = json.loads(r.get('data','{}')).get('items',[])
    captions = [it.get('caption','') for it in items]
    print(f'         菜单项: {captions}')

print("\n=== 5. 点击[属性(&Z)] — 会弹出 MessageBox（异步，返回 ack）===")
r, _ = send({'reqId':'dc','cmd':'dlgclick','target':'属性(&Z)'})
check('dlgclick 属性', r, 'ack')
time.sleep(0.5)
# 如果返回 OK，说明菜单点击成功，MessageBox 已弹出

print("\n=== 6. 截图 MessageBox ===")
r, _ = send({'reqId':'c2','cmd':'capture','target':'dlgtest_msgbox'}); check('capture msgbox', r)

print("\n=== 7. msgclick 关闭弹窗 ===")
r, _ = send({'reqId':'mc','cmd':'msgclick','target':'ok'}); check('msgclick', r, 'ack')
time.sleep(0.5)

print("\n=== 8. 截图关闭后状态 ===")
r, _ = send({'reqId':'c3','cmd':'capture','target':'dlgtest_after'}); check('capture after', r)

print("\n=== 9. 退出 ===")
r, _ = send({'reqId':'ex','cmd':'exit'}); check('exit', r)
time.sleep(0.5)
proc.kill()

print(f"\n{'='*40}")
print(f'结果: {ok} 通过, {err} 失败')
import glob
for f in sorted(glob.glob(os.path.join(snap, 'dlgtest_*.jpg'))):
    sz = os.path.getsize(f)
    print(f'  {os.path.basename(f)}: {sz} bytes')
