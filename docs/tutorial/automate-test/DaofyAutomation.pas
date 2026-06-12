unit DaofyAutomation;

interface

uses
  Winapi.Windows, Winapi.Messages,
  System.SysUtils, System.Classes, System.Rtti, System.TypInfo,
  System.Generics.Collections, System.JSON;

procedure AutoStart(const APipeName: string = '\\.\pipe\daofy_auto');
procedure AutoStop;
procedure AutoCapture(const AName: string);
procedure SetScreenshotDir(const ADir: string);

implementation

uses Vcl.Forms, Vcl.Controls, Vcl.Graphics, Vcl.Imaging.Jpeg, Vcl.Menus;

const
  WM_DAOFY_CMD = WM_USER + $200;
  MAX_PIPE = 4096; BM_CLICK = $00F5; JPG_Q = 80;

type
  TAutomationProcessor = class(TThread)
  private
    class var FCurrent: TAutomationProcessor;
    FMsgWnd: HWND;
    FPipeName: string;
    FSSDir: string;
    FLastResp: string;
    class function GetCurrent: TAutomationProcessor; static;
    // JSON 协议
    function GetReqId(const Req: string): string;
    function GetCmd(const Req: string): string;
    function IsAsyncCmd(const Cmd: string): Boolean;
    function GetJSONStr(const J: TJSONObject; const K, Def: string): string;
    function ExecCmd(const AReq: string): string;
    procedure WndProc(var Msg: TMessage);
    // 工具
    procedure WriteJSON(Obj: TJSONObject); overload;
    function WriteResp(const ReqId, Status, Data: string): string;
    procedure WriteAsyncJSON(const ReqId: string; Obj: TJSONObject);
    function TakeShot(const AFile: string): string;
    function DoCap(const AName: string): string;
    function DoDump: string;
    function DoDlgScan: string;
    function DoDlgClick(const Param: string): string;
    function DoMsgScan: string;
    function DoMsgClick(const Param: string): string;
    function BtnID(const S: string): Integer;
    function FindClick(Items: TMenuItem; const Cap: string): string;
    function IsX(const N: string): Boolean;
    function IsSK(K: TTypeKind): Boolean;
    function P2J(const Prop: TRttiProperty; Obj: TObject): TJSONValue;
    function DTree(Ctrl: TControl): TJSONObject;
    // RTTI 命令
    function DoRGet(const ReqId, Target, Prop: string): string;
    function DoRSet(const ReqId, Target, Prop, Val: string): string;
    function DoRInsp(const ReqId, Target: string): string;
  protected
    procedure Execute; override;
  public
    class property Current: TAutomationProcessor read GetCurrent;
    constructor Create(const APipeName: string);
    destructor Destroy; override;
    procedure SetSSDir(const D: string);
    procedure DoCapPub(const AName: string);
  end;

// ═ WndProc（stdcall 静态函数，可被 SendMessage 跨线程调用）═

function WP(hWnd: HWND; Msg: UINT; w: WPARAM; l: LPARAM): LRESULT; stdcall;
var P: PWideChar; Cmd: string;
begin
  Result := 0;
  if (Msg = WM_DAOFY_CMD) and (TAutomationProcessor.Current <> nil) then begin
    P := PWideChar(w);
    if P <> nil then begin
      Cmd := string(P);
      TAutomationProcessor.Current.ExecCmd(Cmd);
      GlobalFree(Winapi.Windows.HGLOBAL(w));
    end;
  end else
    Result := DefWindowProc(hWnd, Msg, w, l);
end;

// ═ 全局接口 ═

procedure AutoStart(const APipeName: string);
begin
  // GetCurrent 惰性创建并启动线程（构造函数中 inherited Create(False) 已调用 Start）
  TAutomationProcessor.Current.SetSSDir('');
end;

procedure AutoStop;
begin
  if TAutomationProcessor.Current <> nil then
    TAutomationProcessor.Current.Terminate;
end;

procedure AutoCapture(const AName: string);
begin
  if TAutomationProcessor.Current <> nil then
    TAutomationProcessor.Current.DoCapPub(AName);
end;

procedure SetScreenshotDir(const ADir: string);
begin
  TAutomationProcessor.Current.SetSSDir(ADir);
  ForceDirectories(ADir);
end;

// ═══════════════════════════════════════════════════════
// TAutomationProcessor
// ═══════════════════════════════════════════════════════

class function TAutomationProcessor.GetCurrent: TAutomationProcessor;
begin
  // 惰性创建单例
  if FCurrent = nil then
    FCurrent := TAutomationProcessor.Create('\\.\pipe\daofy_auto');
  Result := FCurrent;
end;

constructor TAutomationProcessor.Create(const APipeName: string);
begin
  inherited Create(False);
  FPipeName := APipeName;
  // 在主线程上下文创建隐藏窗口（因为是构造时创建，此时在主线程）
  FMsgWnd := AllocateHWnd(WndProc);
  FreeOnTerminate := False;
end;

destructor TAutomationProcessor.Destroy;
begin
  Terminate;
  WaitFor;
  if FMsgWnd <> 0 then begin DeallocateHWnd(FMsgWnd); FMsgWnd := 0; end;
  inherited;
end;

procedure TAutomationProcessor.SetSSDir(const D: string);
begin FSSDir := D; end;

procedure TAutomationProcessor.DoCapPub(const AName: string);
begin DoCap(AName); end;

// ── 管道线程（TAutomationProcessor 就是 TThread）─

procedure TAutomationProcessor.Execute;
var
  h: THandle;
  Buf: array[0..MAX_PIPE-1] of AnsiChar;
  Br, Bw: DWORD;
  Req, Resp, ReqId, Cmd: string;
  R: TBytes;
begin
  while not Terminated do begin
    h := CreateNamedPipe(PChar(FPipeName), PIPE_ACCESS_DUPLEX,
      PIPE_TYPE_MESSAGE or PIPE_READMODE_MESSAGE or PIPE_WAIT,
      PIPE_UNLIMITED_INSTANCES, MAX_PIPE, MAX_PIPE, 100, nil);
    if h = INVALID_HANDLE_VALUE then begin Sleep(500); Continue; end;
    if not ConnectNamedPipe(h, nil) and (GetLastError <> ERROR_PIPE_CONNECTED) then
      begin CloseHandle(h); Sleep(500); Continue; end;
    while not Terminated do begin
      FillChar(Buf, SizeOf(Buf), 0);
      if not ReadFile(h, Buf, SizeOf(Buf)-1, Br, nil) then Break;
      if Br > 0 then begin
        Req := Trim(string(UTF8ToString(Buf)));
        if Req = '' then Continue;
        ReqId := GetReqId(Req);
        Cmd := GetCmd(Req);
        if Cmd = '' then begin
          Resp := WriteResp(ReqId, 'err', 'no cmd');
        end else if IsAsyncCmd(Cmd) then begin
          // 异步：PostMessage，不阻塞管道线程，立即返回 ACK
          var P := PWideChar(GlobalAlloc(GMEM_FIXED, (Length(Req)+1)*SizeOf(WideChar)));
          if P <> nil then begin
            Move(PWideChar(Req)^, P^, (Length(Req)+1)*SizeOf(WideChar));
            PostMessage(FMsgWnd, WM_DAOFY_CMD, WPARAM(P), 0);
          end;
          Resp := WriteResp(ReqId, 'ack', '');
        end else begin
          // 同步：SendMessage 到主线程，等待执行完成
          var P := PWideChar(GlobalAlloc(GMEM_FIXED, (Length(Req)+1)*SizeOf(WideChar)));
          if P <> nil then begin
            Move(PWideChar(Req)^, P^, (Length(Req)+1)*SizeOf(WideChar));
            SendMessage(FMsgWnd, WM_DAOFY_CMD, WPARAM(P), 0);
          end;
          Resp := FLastResp;
        end;
        R := TEncoding.UTF8.GetBytes(Resp + #10);
        WriteFile(h, R[0], Length(R), Bw, nil);
      end;
    end;
    CloseHandle(h);
  end;
end;

// ── WndProc（AllocateHWnd 回调，运行在主线程）─

// ── WndProc（AllocateHWnd 回调，运行在主线程）─

procedure TAutomationProcessor.WndProc(var Msg: TMessage);
begin
  if Msg.Msg = WM_DAOFY_CMD then begin
    var P := PWideChar(Msg.WParam);
    if P <> nil then begin
      FLastResp := ExecCmd(string(P));
      GlobalFree(Winapi.Windows.HGLOBAL(Msg.WParam));
    end;
    Msg.Result := 0;
  end else
    Msg.Result := DefWindowProc(FMsgWnd, Msg.Msg, Msg.WParam, Msg.LParam);
end;

// ── ExecCmd：所有命令的统一入口 ──

// ── ExecCmd：JSON 请求分发器，运行在主线程 ──

function TAutomationProcessor.ExecCmd(const AReq: string): string;
var J: TJSONObject; Cmd, ReqId, Target: string;
  I, WaitMs: Integer; Ch, hWnd: Winapi.Windows.HWND;
  WC: TWinControl; Buf: array[0..255] of Char; R: TRect;
  V: TJSONValue;
begin
  try
    V := TJSONObject.ParseJSONValue(AReq);
    if V = nil then Exit(WriteResp('', 'err', 'invalid JSON'));
    if not (V is TJSONObject) then begin V.Free; Exit(WriteResp('', 'err', 'not a JSON object')); end;
    J := V as TJSONObject;
    try
      ReqId := GetJSONStr(J, 'reqId', '');
      Cmd   := LowerCase(GetJSONStr(J, 'cmd', ''));
      Target := GetJSONStr(J, 'target', '');

      if Cmd = '' then
        Result := WriteResp(ReqId, 'err', 'no cmd')

      else if Cmd = 'goto' then begin
        for I := 0 to Screen.FormCount - 1 do
          if SameText(Screen.Forms[I].ClassName, Target) or SameText(Screen.Forms[I].Name, Target) then
            begin Screen.Forms[I].Show; Screen.Forms[I].BringToFront; Screen.Forms[I].SetFocus; Break; end;
        Result := WriteResp(ReqId, 'ok', 'OK'); end

      else if Cmd = 'click' then begin
        var AtPos := Pos('@', Target);
        var CtrlName := Target;
        if AtPos > 0 then begin
          var CoordStr := Copy(Target, AtPos+1, MaxInt);
          CtrlName := Copy(Target, 1, AtPos-1);
          var CommaPos := Pos(',', CoordStr);
          if CommaPos > 0 then begin
            var CX := StrToIntDef(Trim(Copy(CoordStr, 1, CommaPos-1)), 0);
            var CY := StrToIntDef(Trim(Copy(CoordStr, CommaPos+1, MaxInt)), 0);
            if Screen.ActiveForm <> nil then begin
              WC := Screen.ActiveForm.FindChildControl(CtrlName) as TWinControl;
              if WC <> nil then begin Ch := WC.Handle;
                SendMessage(Ch, WM_LBUTTONDOWN, MK_LBUTTON, MakeLParam(CX, CY));
                SendMessage(Ch, WM_LBUTTONUP, 0, MakeLParam(CX, CY));
              end;
            end;
          end;
        end else begin
          if Screen.ActiveForm <> nil then begin
            WC := Screen.ActiveForm.FindChildControl(CtrlName) as TWinControl;
            if WC <> nil then begin Ch := WC.Handle; SendMessage(Ch, BM_CLICK, 0, 0); end; end;
        end;
        Result := WriteResp(ReqId, 'ok', 'OK'); end

      else if Cmd = 'dblclick' then begin
        var AtPos2 := Pos('@', Target);
        var CtrlName2 := Target;
        if AtPos2 > 0 then begin
          var CoordStr2 := Copy(Target, AtPos2+1, MaxInt);
          CtrlName2 := Copy(Target, 1, AtPos2-1);
          var CommaPos2 := Pos(',', CoordStr2);
          if CommaPos2 > 0 then begin
            var CX2 := StrToIntDef(Trim(Copy(CoordStr2, 1, CommaPos2-1)), 0);
            var CY2 := StrToIntDef(Trim(Copy(CoordStr2, CommaPos2+1, MaxInt)), 0);
            if Screen.ActiveForm <> nil then begin
              WC := Screen.ActiveForm.FindChildControl(CtrlName2) as TWinControl;
              if WC <> nil then begin Ch := WC.Handle;
                SendMessage(Ch, WM_LBUTTONDBLCLK, MK_LBUTTON, MakeLParam(CX2, CY2));
              end;
            end;
          end;
        end else begin
          if Screen.ActiveForm <> nil then begin
            WC := Screen.ActiveForm.FindChildControl(CtrlName2) as TWinControl;
            if WC <> nil then begin Ch := WC.Handle;
              GetWindowRect(Ch, R);
              SendMessage(Ch, WM_LBUTTONDBLCLK, MK_LBUTTON,
                MakeLParam(R.Width div 2, R.Height div 2));
            end;
          end;
        end;
        Result := WriteResp(ReqId, 'ok', 'OK'); end

      else if Cmd = 'rclick' then begin
        if Screen.ActiveForm <> nil then begin
          WC := Screen.ActiveForm.FindChildControl(Target) as TWinControl;
          if WC <> nil then begin Ch := WC.Handle; GetWindowRect(Ch, R);
            if Screen.ActiveForm.PopupMenu <> nil then
              Screen.ActiveForm.PopupMenu.Popup(R.Left+(R.Width div 2), R.Top+(R.Height div 2)); end; end;
        Result := WriteResp(ReqId, 'ok', 'OK'); end

      else if Cmd = 'hover' then begin
        if Screen.ActiveForm <> nil then begin
          WC := Screen.ActiveForm.FindChildControl(Target) as TWinControl;
          if WC <> nil then begin Ch := WC.Handle;
            SendMessage(Ch, WM_MOUSEMOVE, 0, MakeLParam(WC.Width div 2, WC.Height div 2)); end; end;
        Result := WriteResp(ReqId, 'ok', 'OK'); end

      else if Cmd = 'type' then begin
        var VStr := GetJSONStr(J, 'value', '');
        if (Target <> '') and (Screen.ActiveForm <> nil) then begin
          WC := Screen.ActiveForm.FindChildControl(Target) as TWinControl;
          if WC <> nil then begin Ch := WC.Handle;
            SetWindowText(Ch, PChar(VStr)); end; end;
        Result := WriteResp(ReqId, 'ok', 'OK'); end

      else if Cmd = 'wait' then begin
        WaitMs := StrToIntDef(GetJSONStr(J, 'ms', '500'), 500);
        if WaitMs > 10000 then WaitMs := 10000; Sleep(WaitMs);
        Result := WriteResp(ReqId, 'ok', 'OK'); end

      else if Cmd = 'capture' then begin
        DoCap(Target);
        Result := WriteResp(ReqId, 'ok', 'captured'); end

      else if Cmd = 'dlgscan' then begin
        DoDlgScan;
        Result := WriteResp(ReqId, 'ok', 'scanned'); end

      else if Cmd = 'dlgclick' then begin
        Result := WriteResp(ReqId, 'ok', DoDlgClick(Target)); end

      else if Cmd = 'msgscan' then begin
        DoMsgScan;
        Result := WriteResp(ReqId, 'ok', 'scanned'); end

      else if Cmd = 'msgclick' then begin
        Result := WriteResp(ReqId, 'ok', DoMsgClick(Target)); end

      else if Cmd = 'msgclose' then begin
        hWnd := FindWindowW('#32770', nil);
        while hWnd <> 0 do begin GetWindowTextW(hWnd, Buf, 256);
          if (Target = '') or (Pos(Target, string(Buf)) > 0) then
            begin SendMessage(hWnd, WM_CLOSE, 0, 0); Break; end;
          hWnd := GetNextWindow(hWnd, GW_HWNDNEXT); end;
        Result := WriteResp(ReqId, 'ok', 'OK'); end

      else if Cmd = 'snapdir' then begin
        FSSDir := Target; ForceDirectories(FSSDir);
        Result := WriteResp(ReqId, 'ok', 'OK'); end

      else if Cmd = 'dumpstate' then begin
        DoDump;
        Result := WriteResp(ReqId, 'ok', 'dumped'); end

      else if Cmd = 'exit' then begin
        Application.Terminate;
        Result := WriteResp(ReqId, 'ok', 'bye'); end

      // RTTI 命令（同步）
      else if Cmd = 'rget' then begin
        var Prop := GetJSONStr(J, 'prop', '');
        Result := DoRGet(ReqId, Target, Prop); end

      else if Cmd = 'rset' then begin
        var Prop := GetJSONStr(J, 'prop', '');
        var Val := GetJSONStr(J, 'value', '');
        Result := DoRSet(ReqId, Target, Prop, Val); end

      // rinspect 异步：ExecCmd 被 PostMessage 调用，结果写文件
      else if Cmd = 'rinspect' then begin
        DoRInsp(ReqId, Target);
        Result := ''; end

      else
        Result := WriteResp(ReqId, 'err', 'unknown cmd: ' + Cmd);

    finally J.Free; end;
  except
    on E: Exception do
      Result := WriteResp('', 'err', E.Message);
  end;
end;

// ── 工具 ──


procedure TAutomationProcessor.WriteJSON(Obj: TJSONObject);
var F: string; Raw: TBytes; SS: TFileStream;
begin if (FSSDir = '') or (Obj = nil) then Exit;
  F := FSSDir + '\_formstate.json';
  Raw := TEncoding.UTF8.GetBytes(Obj.ToJSON);
  SS := TFileStream.Create(F, fmCreate);
  try SS.Write(Raw[0], Length(Raw)); finally SS.Free; end;
end;

// ── 截图 ──

function TAutomationProcessor.TakeShot(const AFile: string): string;
var hWin: Winapi.Windows.HWND; DC, MemDC: HDC; Bmp: TBitmap; Jpg: TJPEGImage;
  Old: HGDIOBJ; R: TRect;
begin
  Result := 'NO_WIN';
  hWin := FindWindowW('#32770', nil);
  if hWin = 0 then
    if Screen.ActiveForm <> nil then hWin := Screen.ActiveForm.Handle
    else hWin := GetTopWindow(0);
  if hWin = 0 then Exit;
  GetWindowRect(hWin, R);
  if (R.Width <= 0) or (R.Height <= 0) then begin Result := 'ZERO'; Exit; end;
  DC := GetWindowDC(hWin); if DC = 0 then begin Result := 'NODC'; Exit; end;
  try MemDC := CreateCompatibleDC(DC); if MemDC = 0 then begin Result := 'NOMC'; Exit; end;
    try Bmp := TBitmap.Create; try Bmp.PixelFormat := pf24bit;
      Bmp.Width := R.Width; Bmp.Height := R.Height;
      Old := SelectObject(MemDC, Bmp.Handle);
      BitBlt(MemDC, 0, 0, R.Width, R.Height, DC, 0, 0, SRCCOPY);
      SelectObject(MemDC, Old);
      Jpg := TJPEGImage.Create;
      try Jpg.Assign(Bmp); Jpg.CompressionQuality := JPG_Q; Jpg.Compress;
        ForceDirectories(ExtractFilePath(AFile)); Jpg.SaveToFile(AFile); Result := 'OK';
        finally Jpg.Free; end;
    finally Bmp.Free; end; finally DeleteDC(MemDC); end;
  finally ReleaseDC(hWin, DC); end;
end;

function TAutomationProcessor.DoCap(const AName: string): string;
begin if FSSDir = '' then Exit('NODIR');
  Result := TakeShot(FSSDir + '\' + AName + '.jpg'); end;

// ── RTTI ──

function TAutomationProcessor.IsX(const N: string): Boolean;
const X: array of string = ['Action','Align','AlignWithMargins','Anchors',
  'BiDiMode','BorderSpacing','Brush','Canvas','ClientHeight','ClientWidth',
  'Color','Constraints','Cursor','CustomHint','Font','Handle','Height',
  'HelpContext','HelpKeyword','HelpType','Hint','ImeMode','ImeName',
  'Left','Top','Width','Margins','Name','Owner','Padding','Parent',
  'ParentBackground','ParentBiDiMode','ParentColor','ParentCtl3D',
  'ParentCustomHint','ParentDoubleBuffered','ParentFont','ParentShowHint',
  'PopupMenu','ScrollBar','Showing','StyleElements','TabOrder','Tag',
  'Touch','WindowHandle','WindowProc',
  'OnActivate','OnClick','OnChange','OnClose','OnCreate','OnDblClick',
  'OnDeactivate','OnDestroy','OnEnter','OnExit','OnKeyDown','OnKeyPress',
  'OnKeyUp','OnMouseActivate','OnMouseDown','OnMouseEnter','OnMouseLeave',
  'OnMouseMove','OnMouseUp','OnResize','OnShow'];
var S: string;
begin for S in X do if SameText(S, N) then Exit(True); Result := False; end;

function TAutomationProcessor.IsSK(K: TTypeKind): Boolean;
begin Result := K in [tkString,tkUString,tkWString,tkLString,tkChar,tkWChar,
  tkInteger,tkInt64,tkEnumeration,tkFloat]; end;

function TAutomationProcessor.P2J(const Prop: TRttiProperty; Obj: TObject): TJSONValue;
var V: TValue;
begin
  if not Prop.IsReadable then Exit(TJSONNull.Create);
  V := Prop.GetValue(Obj);
  case V.Kind of
    tkString,tkUString,tkWString,tkLString: Result := TJSONString.Create(V.AsString);
    tkChar,tkWChar: Result := TJSONString.Create(string(V.AsString));
    tkInteger,tkInt64: Result := TJSONNumber.Create(V.AsInteger);
    tkEnumeration: if SameText(Prop.PropertyType.Name, 'Boolean') then
      Result := TJSONBool.Create(V.AsBoolean)
    else Result := TJSONString.Create(GetEnumName(Prop.PropertyType.Handle, V.AsOrdinal));
    tkFloat: Result := TJSONNumber.Create(V.AsExtended);
  else Result := TJSONNull.Create; end;
end;

function TAutomationProcessor.DTree(Ctrl: TControl): TJSONObject;
var Ctx: TRttiContext; Prop: TRttiProperty; Seen: TDictionary<string, Boolean>;
  I: Integer; W: TWinControl; Props: TJSONObject; Children: TJSONArray;
begin
  Result := TJSONObject.Create;
  Result.AddPair('name', Ctrl.Name);
  Result.AddPair('class', Ctrl.ClassName);
  Props := TJSONObject.Create;
  Seen := TDictionary<string, Boolean>.Create;
  try Ctx := TRttiContext.Create; try for Prop in Ctx.GetType(Ctrl.ClassType).GetProperties do
    if not IsX(Prop.Name) and IsSK(Prop.PropertyType.TypeKind)
      and not Seen.ContainsKey(Prop.Name) then begin
      Seen.Add(Prop.Name, True);
      Props.AddPair(Prop.Name, P2J(Prop, Ctrl)); end;
  finally Ctx.Free; end; finally Seen.Free; end;
  Result.AddPair('props', Props);
  if Ctrl is TWinControl then begin
    W := TWinControl(Ctrl);
    if W.ControlCount > 0 then begin
      Children := TJSONArray.Create;
      for I := 0 to W.ControlCount - 1 do
        Children.AddElement(DTree(W.Controls[I]));
      Result.AddPair('children', Children);
    end;
  end;
end;

function TAutomationProcessor.DoDump: string;
var I: Integer; F: TForm; Ctx: TRttiContext; Prop: TRttiProperty;
  Seen: TDictionary<string, Boolean>;
  Root: TJSONObject; Props: TJSONObject; Controls: TJSONArray;
begin if FSSDir = '' then Exit('NODIR');
  F := Screen.ActiveForm; if F = nil then begin if Screen.FormCount > 0 then F := Screen.Forms[0] else Exit; end;
  Root := TJSONObject.Create; Seen := TDictionary<string, Boolean>.Create;
  try
    Root.AddPair('form', F.Name);
    Root.AddPair('class', F.ClassName);
    Root.AddPair('caption', F.Caption);
    Props := TJSONObject.Create;
    Ctx := TRttiContext.Create; try for Prop in Ctx.GetType(F.ClassType).GetProperties do
      if not IsX(Prop.Name) and IsSK(Prop.PropertyType.TypeKind)
        and (Prop.Name <> 'Caption') and not Seen.ContainsKey(Prop.Name) then begin
        Seen.Add(Prop.Name, True);
        Props.AddPair(Prop.Name, P2J(Prop, F)); end;
    finally Ctx.Free; end;
    Root.AddPair('props', Props);
    Controls := TJSONArray.Create;
    for I := 0 to F.ControlCount - 1 do
      Controls.AddElement(DTree(F.Controls[I]));
    Root.AddPair('controls', Controls);
    WriteJSON(Root); Result := 'OK';
  finally Seen.Free; Root.Free; end;
end;

function TAutomationProcessor.DoDlgScan: string;
var F: TForm; PM: TPopupMenu; Root: TJSONObject; Items: TJSONArray;
  II: Integer; It: TMenuItem;
begin if FSSDir = '' then Exit('NODIR');
  F := Screen.ActiveForm; if F = nil then Exit('NOF');
  PM := F.PopupMenu; if PM = nil then Exit('NOP');
  Root := TJSONObject.Create;
  try
    Root.AddPair('type', 'popup');
    Root.AddPair('menu', PM.Name);
    Items := TJSONArray.Create;
    for II := 0 to PM.Items.Count - 1 do begin
      It := PM.Items[II];
      var ItemObj := TJSONObject.Create;
      ItemObj.AddPair('name', It.Name);
      ItemObj.AddPair('caption', It.Caption);
      ItemObj.AddPair('enabled', TJSONBool.Create(It.Enabled));
      ItemObj.AddPair('visible', TJSONBool.Create(It.Visible));
      ItemObj.AddPair('checked', TJSONBool.Create(It.Checked));
      Items.AddElement(ItemObj); end;
    Root.AddPair('items', Items);
    WriteJSON(Root); Result := 'OK';
  finally Root.Free; end;
end;

function TAutomationProcessor.FindClick(Items: TMenuItem; const Cap: string): string;
var I: Integer;
begin for I := 0 to Items.Count - 1 do begin
  if SameText(Items[I].Caption, Cap) then begin Items[I].Click; Exit('OK'); end;
  if Items[I].Count > 0 then if FindClick(Items[I], Cap) = 'OK' then Exit('OK'); end;
  Result := 'NF'; end;

function TAutomationProcessor.DoDlgClick(const Param: string): string;
var F: TForm; PM: TPopupMenu;
begin F := Screen.ActiveForm; if F = nil then Exit('NOF');
  PM := F.PopupMenu; if PM = nil then Exit('NOP');
  Result := FindClick(PM.Items, Param); end;

function TAutomationProcessor.BtnID(const S: string): Integer;
begin
  if LowerCase(S) = 'ok' then Exit(1); if LowerCase(S) = 'cancel' then Exit(2);
  if LowerCase(S) = 'abort' then Exit(3); if LowerCase(S) = 'retry' then Exit(4);
  if LowerCase(S) = 'ignore' then Exit(5); if LowerCase(S) = 'yes' then Exit(6);
  if LowerCase(S) = 'no' then Exit(7); Result := -1; end;

function TAutomationProcessor.DoMsgScan: string;
var Root: TJSONObject; Buttons: TJSONArray;
  hDlg, hSt, hBtn: Winapi.Windows.HWND; Buf: array[0..511] of Char;
begin if FSSDir = '' then Exit('NODIR');
  hDlg := FindWindowW('#32770', nil); if hDlg = 0 then Exit('NOD');
  Root := TJSONObject.Create;
  try
    FillChar(Buf, SizeOf(Buf), 0); GetWindowTextW(hDlg, Buf, 512);
    Root.AddPair('title', string(Buf));
    Root.AddPair('type', 'msgbox');
    Root.AddPair('hWnd', IntToStr(hDlg));
    hSt := FindWindowExW(hDlg, 0, 'Static', nil);
    if hSt <> 0 then begin FillChar(Buf, SizeOf(Buf), 0); GetWindowTextW(hSt, Buf, 512);
      Root.AddPair('text', string(Buf)); end
    else Root.AddPair('text', '');
    Buttons := TJSONArray.Create;
    hBtn := FindWindowExW(hDlg, 0, 'Button', nil);
    while hBtn <> 0 do begin FillChar(Buf, SizeOf(Buf), 0); GetWindowTextW(hBtn, Buf, 512);
      if string(Buf) <> '' then
        Buttons.AddElement(TJSONString.Create(string(Buf)));
      hBtn := FindWindowExW(hDlg, hBtn, 'Button', nil); end;
    Root.AddPair('buttons', Buttons);
    WriteJSON(Root); Result := 'OK';
  finally Root.Free; end;
end;

function TAutomationProcessor.DoMsgClick(const Param: string): string;
var hDlg, hBtn: Winapi.Windows.HWND; Buf: array[0..255] of Char; ID: Integer;
begin
  hDlg := FindWindowW('#32770', nil); if hDlg = 0 then Exit('NOD');
  ID := BtnID(Param);
  if ID > 0 then begin SendMessage(hDlg, WM_COMMAND, ID, 0); Exit('OK'); end;
  hBtn := FindWindowExW(hDlg, 0, 'Button', nil);
  while hBtn <> 0 do begin FillChar(Buf, SizeOf(Buf), 0); GetWindowTextW(hBtn, Buf, 255);
    if LowerCase(string(Buf)) = LowerCase(Param) then
      begin SendMessage(hBtn, BM_CLICK, 0, 0); Exit('OK'); end;
    hBtn := FindWindowExW(hDlg, hBtn, 'Button', nil); end;
  Result := 'NF';
end;

// ══════════════════════════════════════════════════════════════
// 协议辅助
// ══════════════════════════════════════════════════════════════

function TAutomationProcessor.GetJSONStr(const J: TJSONObject; const K, Def: string): string;
var V: TJSONValue;
begin
  V := J.Values[K];
  if V <> nil then Result := V.Value else Result := Def;
end;

function TAutomationProcessor.WriteResp(const ReqId, Status, Data: string): string;
var J: TJSONObject;
begin
  J := TJSONObject.Create;
  try
    J.AddPair('reqId', ReqId);
    J.AddPair('status', Status);
    J.AddPair('data', Data);
    Result := J.ToJSON;
  finally J.Free; end;
end;

procedure TAutomationProcessor.WriteAsyncJSON(const ReqId: string; Obj: TJSONObject);
var F: string; Raw: TBytes; SS: TFileStream;
begin
  if FSSDir = '' then Exit;
  F := FSSDir + '\_async_' + ReqId + '.json';
  Raw := TEncoding.UTF8.GetBytes(Obj.ToJSON);
  SS := TFileStream.Create(F, fmCreate);
  try SS.Write(Raw[0], Length(Raw)); finally SS.Free; end;
end;

function TAutomationProcessor.GetReqId(const Req: string): string;
var V: TJSONValue;
begin
  V := TJSONObject.ParseJSONValue(Req);
  if V is TJSONObject then
    Result := GetJSONStr(V as TJSONObject, 'reqId', '')
  else
    Result := '';
  V.Free;
end;

function TAutomationProcessor.GetCmd(const Req: string): string;
var V: TJSONValue;
begin
  V := TJSONObject.ParseJSONValue(Req);
  if V is TJSONObject then
    Result := LowerCase(GetJSONStr(V as TJSONObject, 'cmd', ''))
  else
    Result := '';
  V.Free;
end;

function TAutomationProcessor.IsAsyncCmd(const Cmd: string): Boolean;
begin
  Result := (Cmd = 'click') or (Cmd = 'dblclick') or (Cmd = 'rclick') or
            (Cmd = 'msgclick') or (Cmd = 'dlgclick') or (Cmd = 'hover') or
            (Cmd = 'rinspect');
end;

// ══════════════════════════════════════════════════════════════
// RTTI 命令
// ══════════════════════════════════════════════════════════════

function TAutomationProcessor.DoRGet(const ReqId, Target, Prop: string): string;
var Ctrl: TControl; Ctx: TRttiContext; Pr: TRttiProperty; V: TValue; Obj: TObject;
  Parts: TArray<string>; i: Integer;
begin
  try
    if Screen.ActiveForm = nil then Exit(WriteResp(ReqId, 'err', 'no active form'));
    Ctrl := Screen.ActiveForm.FindChildControl(Target);
    if Ctrl = nil then Exit(WriteResp(ReqId, 'err', 'NF:'+Target));
    Parts := Prop.Split(['.']);
    if Length(Parts) = 0 then Exit(WriteResp(ReqId, 'err', 'no property'));
    Ctx := TRttiContext.Create;
    try
      // First segment: control property
      Pr := Ctx.GetType(Ctrl.ClassType).GetProperty(Parts[0]);
      if Pr = nil then Exit(WriteResp(ReqId, 'err', 'NP:'+Parts[0]));
      if not Pr.IsReadable then Exit(WriteResp(ReqId, 'err', 'NR:'+Parts[0]));
      V := Pr.GetValue(Ctrl);
      // Nested segments: traverse object chain
      for i := 1 to High(Parts) do begin
        if V.Kind <> tkClass then Exit(WriteResp(ReqId, 'err', 'not an object: '+Parts[i]));
        Obj := V.AsObject;
        if Obj = nil then Exit(WriteResp(ReqId, 'err', 'nil: '+Parts[i]));
        Pr := Ctx.GetType(Obj.ClassType).GetProperty(Parts[i]);
        if Pr = nil then Exit(WriteResp(ReqId, 'err', 'NP:'+Parts[i]));
        if not Pr.IsReadable then Exit(WriteResp(ReqId, 'err', 'NR:'+Parts[i]));
        V := Pr.GetValue(Obj);
      end;
      Result := WriteResp(ReqId, 'ok', V.ToString);
    finally Ctx.Free; end;
  except
    on E: Exception do Result := WriteResp(ReqId, 'err', E.Message);
  end;
end;

function TAutomationProcessor.DoRSet(const ReqId, Target, Prop, Val: string): string;
var Ctrl: TControl; Ctx: TRttiContext; Pr: TRttiProperty;
begin
  try
    if Screen.ActiveForm = nil then Exit(WriteResp(ReqId, 'err', 'no active form'));
    Ctrl := Screen.ActiveForm.FindChildControl(Target);
    if Ctrl = nil then Exit(WriteResp(ReqId, 'err', 'NF:'+Target));
    Ctx := TRttiContext.Create;
    try
      Pr := Ctx.GetType(Ctrl.ClassType).GetProperty(Prop);
      if Pr = nil then Exit(WriteResp(ReqId, 'err', 'NP:'+Prop));
      if not Pr.IsWritable then Exit(WriteResp(ReqId, 'err', 'NW:'+Prop));
      case Pr.PropertyType.TypeKind of
        tkString, tkUString, tkWString, tkLString:
          Pr.SetValue(Ctrl, Val);
        tkInteger, tkInt64:
          Pr.SetValue(Ctrl, StrToIntDef(Val, 0));
        tkFloat:
          Pr.SetValue(Ctrl, StrToFloatDef(Val, 0));
        tkEnumeration:
          if SameText(Pr.PropertyType.Name, 'Boolean') then
            Pr.SetValue(Ctrl, SameText(Val, 'true'))
          else
            Pr.SetValue(Ctrl, TValue.FromOrdinal(Pr.PropertyType.Handle,
              GetEnumValue(Pr.PropertyType.Handle, Val)));
      else
        Exit(WriteResp(ReqId, 'err', 'unsupported type'));
      end;
      Result := WriteResp(ReqId, 'ok', 'OK');
    finally Ctx.Free; end;
  except
    on E: Exception do Result := WriteResp(ReqId, 'err', E.Message);
  end;
end;

function TAutomationProcessor.DoRInsp(const ReqId, Target: string): string;
var Ctrl: TControl; Ctx: TRttiContext; Ty: TRttiType;
  M: TRttiMethod; PR: TRttiProperty;
  Root: TJSONObject; Methods: TJSONArray; Props: TJSONArray; JE: TJSONObject;
begin
  try
    if FSSDir = '' then Exit;
    if Screen.ActiveForm = nil then begin
      JE := TJSONObject.Create; JE.AddPair('status','err'); JE.AddPair('data','NA');
      WriteAsyncJSON(ReqId, JE); JE.Free; Exit; end;
    Ctrl := Screen.ActiveForm.FindChildControl(Target);
    if Ctrl = nil then begin
      JE := TJSONObject.Create; JE.AddPair('status','err'); JE.AddPair('data','NF');
      WriteAsyncJSON(ReqId, JE); JE.Free; Exit; end;
    Root := TJSONObject.Create;
    try
      Ctx := TRttiContext.Create; Ty := Ctx.GetType(Ctrl.ClassType);
      try
        Root.AddPair('name', Ctrl.Name);
        Root.AddPair('class', Ctrl.ClassName);
        Methods := TJSONArray.Create;
        for M in Ty.GetMethods do
          if (M.Visibility=mvPublic) and (M.MethodKind=mkProcedure)
            and (Length(M.GetParameters)=0) then
            Methods.AddElement(TJSONString.Create(M.Name));
        Root.AddPair('methods', Methods);
        Props := TJSONArray.Create;
        for PR in Ty.GetProperties do
          if PR.IsReadable and PR.IsWritable then begin
            var PObj := TJSONObject.Create;
            PObj.AddPair('name', PR.Name);
            PObj.AddPair('type', PR.PropertyType.Name);
            Props.AddElement(PObj); end;
        Root.AddPair('props', Props);
        WriteAsyncJSON(ReqId, Root);
      finally Ctx.Free; end;
    finally Root.Free; end;
    Result := WriteResp(ReqId, 'ok', 'OK');
  except
    on E: Exception do begin
      JE := TJSONObject.Create; JE.AddPair('status','err'); JE.AddPair('data',E.Message);
      WriteAsyncJSON(ReqId, JE); JE.Free;
      Result := WriteResp(ReqId, 'err', E.Message);
    end;
  end;
 end;

end.
