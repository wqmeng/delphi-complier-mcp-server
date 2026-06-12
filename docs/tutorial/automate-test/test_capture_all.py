"""测试三个框架的截图功能：VCL / FMX 2D / FMX 3D"""
import os, json, time, subprocess, ctypes
from ctypes import wintypes

PIPE_NAME = r'\\.\pipe\daofy_auto'
_k32 = ctypes.windll.kernel32
_CreateFile = _k32.CreateFileW
_CreateFile.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
_CreateFile.restype = wintypes.HANDLE
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
            raw = b''.join(chunks)
            return json.loads(raw.decode('utf-8').strip()), None
        finally:
            _CloseHandle(h)
    return None, 'retry'

SNAPSHOTS = r'C:\user\daofy-agent\daofy\docs\tutorial\automate-test\snapshots'
EXE_DIR = r'C:\user\daofy-agent\daofy\docs\tutorial\automate-test\Win32\Debug'
os.makedirs(SNAPSHOTS, exist_ok=True)

def test_framework(name, exe, form_name, extra_script=None):
    print(f"\n{'='*50}")
    print(f"测试: {name}")
    print(f"{'='*50}")

    proc = subprocess.Popen([exe], cwd=EXE_DIR)
    time.sleep(1)

    send({'reqId':'init','cmd':'snapdir','target':SNAPSHOTS})
    time.sleep(0.2)

    tests = [
        (f'{name}_goto', {'reqId':'g','cmd':'goto','target':form_name}),
        (f'{name}_main', {'reqId':'c1','cmd':'capture','target':f'{name}_main'}),
    ]
    if extra_script:
        tests.extend(extra_script)

    for label, req in tests:
        r, e = send(req)
        status = r.get('status','') if r else 'noconn'
        if status in ('ok','ack'):
            print(f'  PASS {label}: {status}')
        else:
            print(f'  FAIL {label}: status={status} data={r}')

    send({'reqId':'e','cmd':'exit'})
    time.sleep(0.5)
    try: proc.kill()
    except: pass
    return name

# ── 1. VCL ──
test_framework('VCL',
    os.path.join(EXE_DIR, 'AutoTest.exe'),
    'TForm1',
    extra_script=[
        ('VCL_click_msgbox', {'reqId':'m','cmd':'click','target':'BtnMsgBox'}),
        ('VCL_wait', {'reqId':'w','cmd':'wait','ms':'500'}),
        ('VCL_msgbox', {'reqId':'c2','cmd':'capture','target':'VCL_msgbox'}),
        ('VCL_msgclick', {'reqId':'mc','cmd':'msgclick','target':'ok'}),
        ('VCL_wait_close', {'reqId':'w2','cmd':'wait','ms':'500'}),
    ])

# ── 2. FMX 2D ──
test_framework('FMX2D',
    os.path.join(EXE_DIR, 'FmxAutoTest.exe'),
    'TFmxMainForm',
    extra_script=[
        ('FMX2D_click_msgbox', {'reqId':'m','cmd':'click','target':'BtnMsgBox'}),
        ('FMX2D_wait', {'reqId':'w','cmd':'wait','ms':'500'}),
        ('FMX2D_msgbox', {'reqId':'c2','cmd':'capture','target':'FMX2D_msgbox'}),
        ('FMX2D_msgclick', {'reqId':'mc','cmd':'msgclick','target':'ok'}),
        ('FMX2D_wait_close', {'reqId':'w2','cmd':'wait','ms':'1500'}),
    ])

# ── 3. FMX 3D ──
test_framework('FMX3D',
    os.path.join(EXE_DIR, 'Fmx3DTest.exe'),
    'TFmx3DMainForm',
    extra_script=[
        ('FMX3D_click_msgbox', {'reqId':'m','cmd':'click','target':'BtnMsgBox'}),
        ('FMX3D_wait', {'reqId':'w','cmd':'wait','ms':'500'}),
        ('FMX3D_msgbox', {'reqId':'c2','cmd':'capture','target':'FMX3D_msgbox'}),
        ('FMX3D_msgclick', {'reqId':'mc','cmd':'msgclick','target':'ok'}),
        ('FMX3D_wait_close', {'reqId':'w2','cmd':'wait','ms':'1500'}),
    ])

# ── 结果 ──
print(f"\n{'='*50}")
print("截图文件:")
import glob
for f in sorted(glob.glob(os.path.join(SNAPSHOTS, 'VCL_*.jpg')) + glob.glob(os.path.join(SNAPSHOTS, 'FMX2D_*.jpg')) + glob.glob(os.path.join(SNAPSHOTS, 'FMX3D_*.jpg'))):
    size = os.path.getsize(f)
    print(f'  {os.path.basename(f)}: {size:>6} bytes')
print(f"{'='*50}")
