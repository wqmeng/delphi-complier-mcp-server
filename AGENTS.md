# AGENTS.md - Agent Coding Guidelines

Delphi MCP Server — Python 3.10-3.14, Windows, pytest.

## Quick Command Reference

| Action | Command |
|--------|---------|
| Install deps | `pip install -r requirements.txt && pip install -e ".[dev]"` |
| Run all tests | `pytest` (or `python tests/run_all_tests.py` for basic) |
| Run one test | `pytest tests/test_validator.py -v` |
| Lint/type | `mypy src/` |
| Environment | Always set `$env:PYTHONIOENCODING='utf-8'` on Windows |
| Run server | `python src/server.py` |

## Project Structure

```
src/
├── server.py              # MCP entry point
├── tools/                 # MCP tool implementations
├── services/              # Business logic
│   ├── compiler_service.py, config_manager.py, process_manager.py, args_generator.py
│   └── knowledge_base/    # KB modules (schema, smart_cache, project, thirdparty, scan, embedding, async_task_manager)
├── models/                # Pydantic/dataclass models
└── utils/                 # Utilities (delphi_env, dproj_parser, validator, logger)
```

## Agent 编码工作流（优先级顺序）

### 编译 Delphi 前

```
① check_environment(action="check")       → 确认编译器
② get_coding_rules(project_path=...)       → 获取编码规则
③ delphi_kb(query=...)                     → 搜索 API 定义（下面详述）
④ 写代码 → compile_project → format_delphi
```

### 知识库搜索（先猜精确名，再模糊搜）

| 优先级 | 方式 | 示例 |
|--------|------|------|
| 1 | 猜精确类名 → `search_by_name` | `TStringList` |
| 2 | 猜函数名 → `search_type="function"` | `Create` |
| 3 | 多关键字尝试 | `TJSONObject`→`TJsonSerializer` |
| 4 | `search_type="reference"` 查引用 | 评估修改影响 |
| 5 | `search_type="semantic"` 兜底 | 中文需求 |

**`project_path` 规则**：`kb_type="project"` 时必须传；`kb_type="all"` 时可选（不传则只搜 delphi+thirdparty）；`delphi`/`thirdparty`/`document` 不需要。

**典型错误**：`delphi_kb(query="帮我找分割函数", search_type="semantic")` → 应改为 `delphi_kb(query="Split", search_type="function")`。

**搜索**：单元名（如 `System.DateUtils`）自动回退到文件路径匹配；`search_type="function"` 同时匹配 FF+FP。

```
需要写代码
  → 引用已有类型/函数? → 猜类名/函数名 → delphi_kb 精确搜索 → 看定义/继承链 → 生成代码
  → 否则 → 直接生成代码
  → compile_project 验证
```

### 知识库范围

| kb_type | 目标 | project_path |
|---------|------|-------------|
| `project` | 项目自有代码 | **必须传** |
| `delphi` | VCL/FMX/RTL 官方 | 不需要 |
| `thirdparty` | 三方组件 | 不需要 |
| `document` | Delphi 帮助文档 | 不需要 |

### Entity Kind Codes

`TC`=class `TR`=record `TI`=interface `TE`=enum `TS`=set `TY`=type alias `FF`=function `FP`=procedure `CC`=const `CR`=resourcestring `KS`=string literal `TH`=helper

## Code Style (Python)

- **类型**: 全部用 type hints
- **导入顺序**: stdlib → third-party → local (每组空格分隔, 内部字母序)
- **命名**: `snake_case` 函数/变量, `PascalCase` 类, `UPPER_SNAKE` 常量, `_前缀` 私有
- **文档**: Google-style docstring, 公共函数必须有
- **异常**: 用具体异常类型, 不要 `except Exception: pass`
- **测试**: `test_*.py`, `test_` 前缀函数, pytest fixture, `unittest.mock` 打桩

## Agent 操作硬规则

### 脚本执行
- ❌ 绝不用 `python -c "..."`（PowerShell 引号转义必炸）
- ✅ 始终用 `write` 创建 `.py` 文件 → `bash` 执行 `python script.py` → `Remove-Item script.py` 清理

### 字符串格式化
- ❌ f-string 内嵌字典 `f'{d["key"]}'`（引号冲突）
- ✅ 用 `.format()` 或 `%`

### Python 陷阱
- **不要在函数内局部 `import`**：函数内任何地方出现 `from X import Y` 会使 `Y` 在整个函数作用域成为局部变量。放在头部的引用也会 `UnboundLocalError`。始终写在模块顶部。
- **`if x:` vs `if x is not None:`**：0、`""`、`[]` 都是 False。数字可选参数用 `Optional[int]` 并用 `is not None` 判断。
- **`$()` 宏展开**：注册表变量键名（`SKIADIR`）不含 `$()` 前缀，加入 `macros` 字典时必须 `macros[f'$({k})'] = v`。用 `update(dict)` 会导致 `str.replace('SKIADIR', ...)` 错误匹配 `$(SKIADIR)` → 路径残缺。

### 多进程 Worker
- **Worker 内部禁用 `print()`**：MCP 环境下 stdout 是 JSON-RPC 通信管道，worker print 破坏协议边界，构建从 8s 飙到 172s
- Worker 标准模式：
  ```python
  def worker(args):
      import io, sys
      sys.stdout = sys.stderr = io.StringIO()
      try:
          ...  # 实际工作
          return result
      except:
          return None  # 错误通过返回值传递
  ```

### 数据库
- **DDL 统一**：所有建表语句集中在 `schema.py`，各 Builder 调 `create_source_tables()`/`create_document_tables()`
- **同一 DB 文件所有连接用相同 journal 模式**：本项目统一使用 WAL（`PRAGMA journal_mode=WAL`），切换模式需要独占锁，运行中若有其他连接会 locked
- 修改表结构后 `grep` 全项目旧表名/列名的所有 INSERT/DELETE/SELECT/ALTER 引用

### 编译
- `shell=True` 执行编译事件前记录 `logger.warning`（命令来自 `.dproj` 文件）
- 长轮询 ≤30 秒（MCP 请求通道约 60s 超时），超时后切换短轮询

## 发布打包流程

### 创建 Release 包

```powershell
$env:PYTHONIOENCODING='utf-8'
$7z="$src\tools\7z\7z.exe"
$src="C:\User\delphi-complier-mcp-server"
$ver="v2026.05.14"  # 替换为当前版本
$out="$src\releases\delphi-mcp-server-$ver"

# 从 git 索引取文件（自动排除 .gitignore 内容）
git ls-files | Where-Object {
    $_ -notmatch '^\.arts/' -and
    $_ -notmatch '^\.coverage$' -and
    $_ -notmatch '^config/history\.json$' -and
    $_ -notmatch '^src/config/compilers\.json$' -and
    $_ -notmatch '^\.gitignore$'
} | ForEach-Object {
    $target = Join-Path "$out" "$_"
    $dir = Split-Path $target -Parent
    if (!(Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
    Copy-Item (Join-Path $src $_) $target -Force
}

# 打包三种格式
& $7z a -ttar "$src\releases\delphi-mcp-server-$ver.tar" "$out\*" -bb0 -bsp0
& $7z a -t7z "$src\releases\delphi-mcp-server-$ver.7z" "$src\releases\delphi-mcp-server-$ver.tar" -mx=9 -m0=LZMA2 -bb0 -bsp0
& $7z a -tzip "$src\releases\delphi-mcp-server-$ver.zip" "$out\*" -mx=9 -bb0 -bsp0
Remove-Item "$out" -Recurse -Force
```

**自动包含**：`tools/pasfmt/cli/pasfmt.exe` 等工具文件由 `git ls-files` 自动纳入（已在版本控制中），无需手动处理。

### 发布步骤

1. 运行打包脚本 → 生成 `.7z` / `.tar` / `.zip`
2. 创建 GitHub Release：
   ```bash
   gh release create v2026.05.14 --title "v2026.05.14" --notes-file release_notes.md
   ```
3. 附加包文件到 Release（通过 Web UI 或 `gh release upload`）

## 重构 Checklist

```
[ ] DDL 统一为 schema 模块
[ ] grep 旧表名/列名所有 CRUD 引用
[ ] 删除废弃方法后验证无外部调用
[ ] 检查局部 import 作用域问题
[ ] 同一 DB 的 journal 模式一致
[ ] 0 值用 is not None 判断
[ ] 构建结束时记录 metadata(时间+用时)
[ ] 强制重建用 DELETE FROM (不逐行)
[ ] 全量测试 + KB 构建验证
[ ] MCP 工具超时说明准确
[ ] 多进程 worker 禁用 print()
```
