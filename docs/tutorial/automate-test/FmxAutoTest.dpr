program FmxAutoTest;

uses
  FMX.Forms,
  Fmx.DaofyAutomation in '..\..\..\tools\auto\Fmx.DaofyAutomation.pas',
  DaofyAutomation.Base in '..\..\..\tools\auto\DaofyAutomation.Base.pas',
  FmxMainForm in 'FmxMainForm.pas' {FmxMainForm};

begin
  Fmx.DaofyAutomation.AutoStart;
  Application.Initialize;
  Application.CreateForm(TFmxMainForm, MainForm);
  Application.Run;
  Fmx.DaofyAutomation.AutoStop;
end.
