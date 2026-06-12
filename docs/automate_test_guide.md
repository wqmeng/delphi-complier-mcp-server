# 道飞自动化测试指南

大模型驱动的 Delphi 自动化测试框架。

## 架构概览

```
┌─────────────────────────────────────────────────────────────┐
│                     大模型 (LLM)                             │
│  分析需求 → 规划步骤 → 验证结果 → 生成报告                   │
└──────────┬──────────────────────────────────────┬──────────┘
           │ automate_delphi 工具                    │ delphi_file / ...
           ▼                                        ▼
┌──────────────────────┐              ┌──────────────────────┐
│    Python 服务层       │              │   辅助工具            │
│  automation_service   │              │   rget / rset /       │
│  ─ 进程池管理          │              │   delphi_kb 等        │
│  ─ 管道通信            │              │                      │
│  ─ ERROR_MORE_DATA    │              └──────────────────────┘
│    循环读取             │
└──────────┬────────────┘
           │ 命名管道 \\.\pipe\daofy_auto
           ▼
┌─────────────────────────────────────────────────────────────┐
│                   Delphi 程序 (AUT)                          │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  DaofyAutomation 单元 (链接到被测程序)                │   │
│  │  ─ 管道线程 + JSON 协议                              │   │
│  │  ─ Vcl.DaofyAutomation / Fmx.DaofyAutomation         │   │
│  │  ─ RTTI 操作 (rget/rset/rcall/rinspect)              │   │
│  │  ─ 截图 (2D PaintTo / 3D GPU / 对话框 BitBlt)       │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## 快速开始

### 1. 在目标 Delphi 程序中接入自动化单元

找到 `.dpr` 文件，在 `uses` 中添加对应框架的自动化单元：

```pascal
program MyApp;

uses
  Vcl.Forms,                              // VCL 项目
  // 或 FMX.Forms,                        // FMX 项目
  Vcl.DaofyAutomation in 'path\to\tools\auto\Vcl.DaofyAutomation.pas',
  DaofyAutomation.Base in 'path\to\tools\auto\DaofyAutomation.Base.pas',
  // 或 Fmx.DaofyAutomation  (FMX 项目)
  MainForm in 'MainForm.pas';

begin
  Vcl.DaofyAutomation.AutoStart;          // 启动自动化管道线程
  Application.Initialize;
  Application.CreateForm(TMainForm, MainForm);
  Application.Run;
  Vcl.DaofyAutomation.AutoStop;
end.
```

调用 `AutoStart` 后，被测程序会在后台创建命名管道 `\\.\pipe\daofy_auto`，等待外部命令。

### 2. 基础自动化调用

```json
{
  "app_path": "C:\\MyApp\\Win32\\Debug\\MyApp.exe",
  "keep_alive": true,
  "script": [
    {"cmd": "goto", "target": "TMainForm"},
    {"cmd": "capture", "target": "screenshot_01"},
    {"cmd": "click", "target": "BtnLogin"},
    {"cmd": "waitfor", "target": "StatusBar", "prop": "Caption", "value": "登录成功", "timeout": "5000"},
    {"cmd": "capture", "target": "screenshot_02"},
    {"cmd": "exit"}
  ]
}
```

---

## 命令参考

### 导航
```json
{"cmd": "goto", "target": "TMainForm"}
```
激活指定类名或 Name 的窗体。

### 鼠标操作
```json
{"cmd": "click", "target": "BtnSave"}                  // RTTI 点击
{"cmd": "click", "target": "ListBox1@5,5"}             // 坐标点击（相对控件）
{"cmd": "rclick", "target": "EditName"}                // 右键弹出菜单
{"cmd": "dblclick", "target": "ListItem1"}             // 双击
{"cmd": "hover", "target": "Panel1"}                   // 悬停
{"cmd": "move", "target": "BtnSave"}                   // 移动鼠标到控件中心
{"cmd": "move", "x": "500", "y": "300"}                // 移动鼠标到屏幕坐标
{"cmd": "drag", "source": "Slider1", "target": "TrackBar1"}  // 拖拽到目标控件
{"cmd": "drag", "source": "Header1", "x": "500", "y": "300"} // 拖拽到坐标
```

### 键盘操作
```json
{"cmd": "type", "target": "EditName", "value": "张三"}        // 输入文本
{"cmd": "key", "target": "EditName", "key": "Tab"}            // 按键
{"cmd": "key", "key": "Enter"}
{"cmd": "key", "key": "Esc"}
{"cmd": "key", "key": "F5"}
```
支持的键名：`Tab`, `Enter`, `Esc`, `Back`, `Del`, `Home`, `End`,
`Up`, `Down`, `Left`, `Right`, `Space`, `F1`~`F12`, 单字符。

### 等待
```json
{"cmd": "wait", "ms": "2000"}                                          // 固定等待
{"cmd": "waitfor", "target": "BtnSave", "prop": "Enabled",            // 等条件满足
                  "value": "True", "timeout": "5000", "interval": "100"}
```
`timeout` 默认 5000ms，`interval` 默认 100ms。支持嵌套属性：
```json
{"cmd": "waitfor", "target": "ListBox1", "prop": "Items.Count", "value": "10", "timeout": "3000"}
```

### 截图
```json
{"cmd": "capture", "target": "test_001"}
```
截图保存到 `snapshots_dir/{target}.jpg`。内部自动选择最佳方式：

| 场景 | 方式 |
|------|------|
| MessageBox/TaskDialog 弹窗 | `FindWindowW('#32770')` → GDI BitBlt → JPEG |
| FMX 模态对话框 | `TFmxFormState.Modal` 检测 → PaintTo |
| FMX 3D 窗体 | `TContext3D.CopyToBitmap` GPU readback |
| FMX 2D 窗体 | `TCustomForm.PaintTo(Canvas)` |
| VCL 窗体 | `GetWindowDC` + GDI BitBlt |

### 窗口枚举
```json
{"cmd": "listwnd"}
```
返回所有窗口的 name/class/caption/active 状态：
```json
{"status": "ok", "data": "{\"windows\":[{\"name\":\"Form1\",\"class\":\"TForm1\",\"caption\":\"MyApp\",\"active\":\"true\"}]}"}
```

### 全量控件树
```json
{"cmd": "dumpstate"}
```
通过管道返回完整控件树 JSON（含所有控件的属性），不再写文件。

### 弹出菜单
```json
{"cmd": "dlgscan"}           // 扫描弹出菜单项
{"cmd": "dlgclick", "target": "复制"}  // 点击菜单项
```

### MessageBox / 对话框
```json
{"cmd": "msgscan"}                              // 扫描弹窗
{"cmd": "msgclick", "target": "ok"}             // 点按钮（支持 TaskDialog）
{"cmd": "msgclose", "target": "DaofyAuto"}      // 关闭弹窗（按标题匹配）
{"cmd": "dlgfile", "path": "C:\\test.txt", "target": "open"}   // 文件对话框
{"cmd": "dlgfile", "target": "cancel"}          // 取消文件对话框
```

### RTTI 操作
```json
{"cmd": "rget", "target": "EditName", "prop": "Text"}                        // 读属性
{"cmd": "rget", "target": "ListBox1", "prop": "Items.Count"}                 // 嵌套属性
{"cmd": "rset", "target": "EditName", "prop": "Text", "value": "Hello"}      // 写属性
{"cmd": "rcall", "target": "EditName", "method": "Clear"}                    // 调用无参方法
{"cmd": "rcall", "target": "ListBox1", "method": "Items.Add",               // 调用带参方法
         "params": ["Hello"]}
{"cmd": "rcall", "target": "Form1", "method": "Close"}                      // 关闭窗体
{"cmd": "rinspect", "target": "EditName"}                                    // 检视成员列表
```

### 进程管理
```json
{"cmd": "snapdir", "target": "D:\\screenshots\\"}    // 设置截图目录
{"cmd": "exit"}                                        // 退出程序
```

---

## 进程复用模式

**问题**：每次调用 `automate_delphi` 都要启动 exe、等管道初始化、执行、退出——重复开销大。

**解决**：`keep_alive=true` 让进程常驻：

```
# 第一次：启动并保持
automate_delphi(app_path="MyApp.exe", script=[goto, capture], keep_alive=true)
→ 返回 process_reused:false, process_alive:true

# 第二次：复用已有进程
automate_delphi(app_path="MyApp.exe", script=[click, capture])
→ 返回 process_reused:true, process_alive:true

# 最后：发送 exit 终止
automate_delphi(app_path="MyApp.exe", script=[exit])
→ 返回 process_alive:false
```

进程池自动管理：
- 同一 `app_path` 自动复用
- **5 分钟无调用**自动 `kill()`
- 进程崩溃后下次调用自动重启
- 返回 `process_reused` / `process_alive` 字段让 AI 感知状态

---

## 自动化测试流程模板

### 基本流程
```
1. 启动程序（keep_alive=true）
2. goto 激活目标窗体
3. listwnd / dumpstate 了解当前界面结构
4. 执行测试操作（click / type / key / rcall）
5. 截图或 rget 验证结果
6. `waitfor` 等待异步操作完成
7. 重复 4-6 直到测试结束
8. exit 退出
```

### 实际示例

```python
# 模拟用户登录
脚本 = [
    {"cmd": "goto", "target": "TLoginForm"},
    {"cmd": "type", "target": "EditUser", "value": "admin"},
    {"cmd": "key", "target": "EditPwd", "key": "Tab"},
    {"cmd": "type", "target": "EditPwd", "value": "123456"},
    {"cmd": "click", "target": "BtnLogin"},
    {"cmd": "waitfor", "target": "StatusBar", "prop": "Caption",
     "value": "登录成功", "timeout": "5000"},
    {"cmd": "capture", "target": "login_result"},
]

# 验证列表加载
脚本2 = [
    {"cmd": "waitfor", "target": "ListView1", "prop": "Items.Count",
     "value": "10", "timeout": "5000"},
    {"cmd": "rget", "target": "ListView1", "prop": "Items[0].Caption"},
]
```

---

## 各框架差异说明

| 特性 | VCL | FMX 2D | FMX 3D |
|------|-----|--------|--------|
| 截图 | GDI BitBlt | PaintTo | CopyToBitmap |
| 控件查找 | FindChildControl | FindComponent | FindComponent |
| 右键菜单 | TPopupMenu | TPopupMenu(手动扫) | TPopupMenu(手动扫) |
| 点击 | SendMessage BM_CLICK | RTTI Click / OnClick | RTTI Click / OnClick |
| 坐标点击 @x,y | SendMessage WM_LBUTTONDOWN | FormToHWND + SendMessage | FormToHWND + SendMessage |
| 类型转换接口 | 通用 | 通用 | 通用 |

---

## 调试技巧

1. **先 `listwnd` 再操作**：查看当前有哪些窗体可用，确认窗体名
2. **`rinspect` 了解控件**：查看控件有哪些方法和属性
3. **`dumpstate` 获取全量状态**：排查控件属性值
4. **`capture` 直观验证**：截图确认界面状态
5. **`rget` 断言**：AI 自行比较预期值
6. **`waitfor` 替代固定 wait**：减少等待时间，提高稳定性
7. **进程残留**：检查 `process_alive` 字段，定期 exit

---

## 常见问题

**Q: `waitfor` 一直超时返回 TIMEOUT？**  
A: 检查 `prop` 属性名是否正确，先用 `rget` 确认。

**Q: `msgclick` 关不掉弹窗？**  
A: FMX 的 MessageDlg 在 Windows 上创建 TaskDialog（`#32770`），`msgclick` 找的是 `#32770` 类窗口。确认弹窗类型。

**Q: FMX exe 启动时报找不到文件？**  
A: FMX 运行时 DLL 需要能被进程找到。确保 PATH 环境变量包含 FMX 运行时目录，或使用静态链接。

**Q: `click` 点了但没反应？**  
A: 检查目标控件名是否正确，先用 `rinspect` 查看控件是否有 `Click` 方法或 `OnClick` 事件。

**Q: FileNotFoundError 启动失败？**  
A: FMX 项目需确保 Win32\Debug\ 目录下有 FMX 依赖的 DLL（如 `fmx260.bpl`）。可以试试用 VCL 测试项目验证基础功能。
