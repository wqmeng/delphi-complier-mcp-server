unit FmxMainForm;

{===============================================================================
  FMX 自动化测试主窗体（纯代码创建，不需要 .fmx 文件）
===============================================================================}
interface

uses
  System.SysUtils, System.Classes,
  FMX.Forms, FMX.Controls, FMX.StdCtrls, FMX.Edit, FMX.Types, FMX.Dialogs,
  System.UITypes,
  Fmx.DaofyAutomation;

type
  TFmxMainForm = class(TForm)
  private
    FBtnMsgBox: TButton;
    FBtnHello: TButton;
    FBtnExit: TButton;
    FEditName: TEdit;
    procedure DoBtnMsgBoxClick(Sender: TObject);
    procedure DoBtnHelloClick(Sender: TObject);
    procedure DoBtnExitClick(Sender: TObject);
  public
    constructor Create(AOwner: TComponent); override;
  end;

var
  MainForm: TFmxMainForm;

implementation

// 纯代码创建窗体，不需要 .fmx 文件

constructor TFmxMainForm.Create(AOwner: TComponent);

  function AddBtn(const AName, ACaption: string; X, Y, W, H: Single;
    AClick: TNotifyEvent): TButton;
  begin
    Result := TButton.Create(Self);
    Result.Parent := Self;
    Result.Name := AName;
    Result.Text := ACaption;
    Result.Position.X := X;
    Result.Position.Y := Y;
    Result.Width := W;
    Result.Height := H;
    Result.OnClick := AClick;
  end;

begin
  inherited CreateNew(AOwner);

  Caption := 'FMX Automation Test';
  ClientWidth := 660;
  ClientHeight := 380;

  FBtnMsgBox := AddBtn('BtnMsgBox', 'Show Message', 200, 50, 120, 30,
    DoBtnMsgBoxClick);

  FBtnHello := AddBtn('BtnHello', 'Say Hello', 50, 50, 120, 30,
    DoBtnHelloClick);

  FBtnExit := AddBtn('BtnExit', 'Exit', 200, 140, 120, 30,
    DoBtnExitClick);

  FEditName := TEdit.Create(Self);
  FEditName.Parent := Self;
  FEditName.Name := 'EditName';
  FEditName.Position.X := 50;
  FEditName.Position.Y := 100;
  FEditName.Width := 200;
  FEditName.Text := 'Daofy';
end;

procedure TFmxMainForm.DoBtnMsgBoxClick(Sender: TObject);
begin
  AutoCapture('fmx_before_msgbox');
  MessageDlg('This is a test message.', TMsgDlgType.mtInformation,
    [TMsgDlgBtn.mbOK], 0);
  AutoCapture('fmx_after_msgbox');
end;

procedure TFmxMainForm.DoBtnHelloClick(Sender: TObject);
var LName: string;
begin
  AutoCapture('fmx_before_hello');
  LName := Trim(FEditName.Text);
  if LName = '' then LName := 'World';
  FBtnHello.Text := 'Hello, ' + LName + '!';
  AutoCapture('fmx_after_hello');
end;

procedure TFmxMainForm.DoBtnExitClick(Sender: TObject);
begin
  Close;
end;

end.
