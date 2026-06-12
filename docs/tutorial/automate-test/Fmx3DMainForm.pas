unit Fmx3DMainForm;

interface

uses
  System.SysUtils, System.Classes, System.UITypes,
  FMX.Forms3D, FMX.Controls3D, FMX.Objects3D, FMX.Types3D,
  FMX.Controls, FMX.StdCtrls, FMX.Types, FMX.Dialogs, FMX.DialogService,
  Fmx.DaofyAutomation;

type
  TFmx3DMainForm = class(TForm3D)
  private
    FCube: TCube;
    FLight: TLight;
    FTimer: TTimer;
    FBtnMsgBox: TButton;
    procedure DoBtnMsgBoxClick(Sender: TObject);
    procedure DoTimerTick(Sender: TObject);
  public
    constructor Create(AOwner: TComponent); override;
  end;

var
  Main3DForm: TFmx3DMainForm;

implementation

{$WARN SYMBOL_DEPRECATED OFF}

constructor TFmx3DMainForm.Create(AOwner: TComponent);

  function AddBtn(const AName, ACaption: string; AClick: TNotifyEvent): TButton;
  begin
    Result := TButton.Create(Self);
    Result.Parent := Self;
    Result.Name := AName;
    Result.Text := ACaption;
    Result.Width := 120;
    Result.Height := 30;
    Result.Position.X := 20;
    Result.Position.Y := 20;
    Result.OnClick := AClick;
  end;

begin
  inherited CreateNew(AOwner);
  Width := 660;
  Height := 480;

  // 3D 场景：旋转立方体
  FCube := TCube.Create(Self);
  FCube.Parent := Self;
  FCube.Width := 2;
  FCube.Height := 2;
  FCube.Depth := 2;
  FCube.Position.X := 0;
  FCube.Position.Y := 0;
  FCube.Position.Z := 0;
  FCube.RotationAngle.X := 30;
  FCube.RotationAngle.Y := 45;

  // 光源
  FLight := TLight.Create(Self);
  FLight.Parent := Self;
  FLight.Position.X := 5;
  FLight.Position.Y := 5;
  FLight.Position.Z := -5;

  // 定时器驱动旋转动画
  FTimer := TTimer.Create(Self);
  FTimer.Interval := 30;
  FTimer.OnTimer := DoTimerTick;
  FTimer.Enabled := True;

  // 按钮
  FBtnMsgBox := AddBtn('BtnMsgBox', 'Show Message', DoBtnMsgBoxClick);
end;

procedure TFmx3DMainForm.DoTimerTick(Sender: TObject);
begin
  FCube.RotationAngle.Y := FCube.RotationAngle.Y + 1;
end;

procedure TFmx3DMainForm.DoBtnMsgBoxClick(Sender: TObject);
begin
  AutoCapture('fmx3d_before');
  MessageDlg('3D Form Test Message', TMsgDlgType.mtInformation,
    [TMsgDlgBtn.mbOK], 0);
  AutoCapture('fmx3d_after');
end;

end.
