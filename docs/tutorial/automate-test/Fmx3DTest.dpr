program Fmx3DTest;

uses
  FMX.Forms,
  Fmx.DaofyAutomation in '..\..\..\tools\auto\Fmx.DaofyAutomation.pas',
  DaofyAutomation.Base in '..\..\..\tools\auto\DaofyAutomation.Base.pas',
  Fmx3DMainForm in 'Fmx3DMainForm.pas' {Fmx3DMainForm};

begin
  Fmx.DaofyAutomation.AutoStart;
  Application.Initialize;
  Application.CreateForm(TFmx3DMainForm, Main3DForm);
  Application.Run;
  Fmx.DaofyAutomation.AutoStop;
end.
