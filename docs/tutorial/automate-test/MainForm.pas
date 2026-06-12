unit MainForm;

interface

uses
  Winapi.Windows, Winapi.Messages, System.SysUtils, System.Variants,
  System.Classes, Vcl.Graphics, Vcl.Controls, Vcl.Forms, Vcl.Dialogs,
  Vcl.StdCtrls, Vcl.Menus, Vcl.ExtCtrls, Vcl.ExtDlgs, Vcl.ComCtrls, Vcl.DaofyAutomation;

type
  TForm1 = class(TForm)
    BtnHello: TButton;
    EditName: TEdit;
    BtnClear: TButton;
    BtnMsgBox: TButton;
    BtnExit: TButton;
    BtnCoord: TButton;
    PanelHover: TPanel;
    PopupMenu1: TPopupMenu;
    MenuCopy: TMenuItem;
    MenuPaste: TMenuItem;
    MenuSep1: TMenuItem;
    MenuProperties: TMenuItem;
    BtnOpenPic: TButton;
    OpenPictureDialog1: TOpenPictureDialog;
    TreeView1: TTreeView;
    procedure FormCreate(Sender: TObject);
    procedure BtnHelloClick(Sender: TObject);
    procedure BtnClearClick(Sender: TObject);
    procedure BtnMsgBoxClick(Sender: TObject);
    procedure BtnExitClick(Sender: TObject);
    procedure BtnCoordClick(Sender: TObject);
    procedure BtnOpenPicClick(Sender: TObject);
    procedure MenuCopyClick(Sender: TObject);
    procedure MenuPasteClick(Sender: TObject);
    procedure MenuPropertiesClick(Sender: TObject);
  private
  public
  end;

var Form1: TForm1;

implementation
{$R *.dfm}

procedure TForm1.FormCreate(Sender: TObject);
begin
  with TreeView1.Items do begin
    var R1 := AddChild(nil, 'Root1');
    AddChild(R1, 'Child1');
    var R1C2 := AddChild(R1, 'Child2');
    AddChild(R1C2, 'Grandchild1');
    var R2 := AddChild(nil, 'Root2');
    AddChild(R2, 'Child3');
  end;
end;

procedure TForm1.BtnHelloClick(Sender: TObject);
var LName: string;
begin AutoCapture('before_hello'); LName := Trim(EditName.Text); if LName = '' then LName := 'World'; BtnHello.Caption := 'Hello, ' + LName + '!'; AutoCapture('after_hello'); end;

procedure TForm1.BtnClearClick(Sender: TObject);
begin EditName.Text := ''; BtnHello.Caption := 'Say Hello'; AutoCapture('after_clear'); end;

procedure TForm1.BtnMsgBoxClick(Sender: TObject);
begin AutoCapture('before_msgbox'); MessageBox(Handle, 'This is a test message.', 'DaofyAuto Test', MB_OK or MB_ICONINFORMATION); AutoCapture('after_msgbox'); end;

procedure TForm1.BtnExitClick(Sender: TObject); begin Close; end;

procedure TForm1.BtnCoordClick(Sender: TObject);
begin AutoCapture('coord_click'); BtnCoord.Caption := 'Clicked!'; MessageBox(Handle, 'BtnCoord clicked via coordinate!', 'DaofyAuto', MB_OK); end;

procedure TForm1.BtnOpenPicClick(Sender: TObject);
begin AutoCapture('before_opendlg'); OpenPictureDialog1.Execute; AutoCapture('after_opendlg'); end;

procedure TForm1.MenuCopyClick(Sender: TObject);
begin if EditName.SelLength > 0 then EditName.CopyToClipboard; AutoCapture('menu_copy'); end;

procedure TForm1.MenuPasteClick(Sender: TObject);
begin EditName.PasteFromClipboard; AutoCapture('menu_paste'); end;

procedure TForm1.MenuPropertiesClick(Sender: TObject);
begin MessageBox(Handle, 'Properties dialog', 'DaofyAuto', MB_OK); AutoCapture('menu_properties'); end;

end.