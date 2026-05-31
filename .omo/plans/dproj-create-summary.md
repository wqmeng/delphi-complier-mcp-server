# Delphi .dproj 创建工具 — 状态总结

## Goal
创建并完善 Delphi .dproj 项目文件创建/配置管理工具，使其输出与 Delphi IDE 原生格式一致，能被 IDE 直接打开而不被重写

## Constraints & Preferences
- 所有修改自动备份到 `__history` 目录
- 复用 `DprojParser` 只读能力，扩展写能力
- 正确 MSBuild 命名空间处理
- 输出 .dproj 必须能被 Delphi IDE 直接打开
- Cfg_1/Cfg_2 按 configs 列表顺序动态分配

## Done
- **重写 `_handle_create` 为完整 IDE 兼容格式**
- **PropertyGroup 继承链**：Base → Base_{platform} → Cfg_1 → Cfg_1_{platform} → Cfg_2 → Cfg_2_{platform} → '$(Base)'!='' → '$(Base_{platform})'!='' → '$(Cfg_1)'!='' → '$(Cfg_2)'!=''
- **BuildConfiguration 映射条目**
- **DelphiCompile** 使用 `$(MainSource)` 变量
- **ProjectExtensions** 完整骨架
- **3 个 Import**
- **5 种项目类型**：Application / Console / Library / Package
- **多平台支持**：迭代 platforms 列表，为每个平台生成完整继承链
- **BT_BuildType**：Base_{platform} PG 中生成 Debug/Release，Cfg_1/Cfg_2 PG 中根据配置名自动判断
- **DCC_ConsoleTarget**：Console 应用的 Base_{platform} PG 中生成
- **GenPackage + RuntimeOnlyPackage + GenDll**：Package 项目的 '$(Base)'!='' PG 中生成
- **Package ProjectExtensions**：Borland.Personality + Source + ProjectFileVersion
- **对比 6 个三方库验证**：Skia4Delphi VCL/FMX/Console D13, EurekaLogCore Studio28, VirtualTreesR XE8, DDetours Console
- **差异汇总**：105/130 项检查通过 → 25 项已修复，0 项剩余
- pyright: 0 errors / 0 warnings / 0 infos
- pytest: 32/32 passed

## Key Decisions
- Cfg_1/Cfg_2 按 configs 列表顺序分配，不假设 Debug/Release 顺序
- 每个配置的编译属性（BT_BuildType, DCC_Define, DCC_Optimize 等）根据配置名自动判断（debug-like / release-like / neutral）
- Package 项目生成完整平台继承链（参考 GR32_R.dproj）
- DCC_DCCCompiler 仅 Console/Library 类型生成（新 Delphi 趋向省略此字段）
- ProjectExtensions 保留最小骨架（IDE 自动填充 Deployment 等细节）
- ProjectFileVersion 在所有类型（包括 Package）中生成

## Verified Against
| 项目 | 类型 | 版本 | 关键确认 |
|------|------|------|---------|
| Skia4Delphi VCL | Application | D13 (20.3) | PropertyGroup 层次结构、BuildConfiguration、BT_BuildType |
| Skia4Delphi FMX | Application | D13 (20.3) | FMX 8 平台扩展、ProjectExtensions 结构 |
| Skia4Delphi Console | Console | D13 (20.3) | DCC_ConsoleTarget、FrameworkType=None |
| EurekaLogCore | Package (VCL) | Studio28 (19.5) | GenPackage/RuntimeOnlyPackage/GenDll、包签名元素 |
| VirtualTreesR | Package (VCL) | XE8 (17.2) | 旧版 DCC_DCCCompiler、Cfg_1=Release Cfg_2=Debug |
| DDetours Test | Console | 10.3 (18.7) | 多平台继承链、BuildConfiguration 顺序可变 |

## Next Steps
- 可选的 `add_config`/`remove_config`/`set` 增加 Cfg_N 编号分配逻辑
