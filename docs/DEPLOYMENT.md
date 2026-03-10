# 部署文档

本文档说明如何在生产环境中部署和使用 Delphi MCP Server。

## 目录

1. [系统要求](#系统要求)
2. [安装部署](#安装部署)
3. [Claude Desktop 配置](#claude-desktop-配置)
4. [其他 MCP 客户端配置](#其他-mcp-客户端配置)
5. [日志与监控](#日志与监控)
6. [故障排查](#故障排查)
7. [性能优化](#性能优化)

## 系统要求

### 硬件要求

- CPU: 双核及以上
- 内存: 2GB 及以上
- 磁盘: 100MB 可用空间(不包括 Delphi 编译器)

### 软件要求

- 操作系统: Windows 10/11 或 Windows Server 2016+
- Python: 3.10 或更高版本
- Delphi 编译器: Delphi 10.4 Sydney 或更高版本

## 安装部署

### 方式一: 从源码安装

1. **下载源码**

```bash
git clone <repository-url>
cd delphi_mcp_server
```

2. **创建虚拟环境**

```bash
python -m venv venv
```

3. **激活虚拟环境**

Windows:
```bash
venv\Scripts\activate
```

4. **安装依赖**

```bash
pip install -r requirements.txt
```

5. **配置编译器**

编辑 `config/compilers.json` 文件,添加 Delphi 编译器配置:

```json
{
  "compilers": [
    {
      "name": "Delphi 11",
      "path": "C:\\Program Files (x86)\\Embarcadero\\Studio\\22.0\\bin\\dcc64.exe",
      "is_default": true,
      "version": "11.0"
    }
  ],
  "default_compiler": "Delphi 11"
}
```

### 方式二: 使用 pip 安装(待发布)

```bash
pip install delphi-mcp-server
```

## Claude Desktop 配置

### 1. 找到配置文件

Claude Desktop 配置文件位置:

- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`

### 2. 添加 MCP Server 配置

在配置文件中添加以下内容:

```json
{
  "mcpServers": {
    "delphi-compiler": {
      "command": "python",
      "args": ["C:\\path\\to\\delphi_mcp_server\\src\\server.py"],
      "env": {
        "PYTHONUNBUFFERED": "1"
      }
    }
  }
}
```

**注意**:
- 将 `C:\\path\\to\\delphi_mcp_server` 替换为实际的项目路径
- 如果使用虚拟环境,需要指定虚拟环境中的 Python 解释器路径

### 3. 使用虚拟环境的 Python

如果使用虚拟环境,配置如下:

```json
{
  "mcpServers": {
    "delphi-compiler": {
      "command": "C:\\path\\to\\delphi_mcp_server\\venv\\Scripts\\python.exe",
      "args": ["C:\\path\\to\\delphi_mcp_server\\src\\server.py"]
    }
  }
}
```

### 4. 重启 Claude Desktop

保存配置文件后,重启 Claude Desktop 使配置生效。

## 其他 MCP 客户端配置

### Cursor IDE

在 Cursor IDE 的设置中添加 MCP Server 配置:

```json
{
  "mcp.servers": {
    "delphi-compiler": {
      "command": "python",
      "args": ["C:\\path\\to\\delphi_mcp_server\\src\\server.py"]
    }
  }
}
```

### 自定义 MCP 客户端

如果使用自定义 MCP 客户端,需要:

1. 启动 MCP Server 进程
2. 通过标准输入/输出与 Server 通信
3. 使用 MCP 协议进行消息交换

示例启动命令:

```bash
python C:\path\to\delphi_mcp_server\src\server.py
```

## 日志与监控

### 日志文件位置

日志文件默认保存在 `logs/delphi_mcp.log`。

### 日志级别

可以在 `src/utils/logger.py` 中修改日志级别:

```python
logger = setup_logger(level=logging.DEBUG)  # DEBUG, INFO, WARNING, ERROR
```

### 日志内容

日志包含以下信息:

- 编译请求接收
- 编译器进程启动
- 编译完成/失败/超时
- 配置变更
- 错误和异常

### 监控建议

1. **日志轮转**: 使用日志轮转工具(如 logrotate)管理日志文件大小
2. **错误告警**: 监控日志中的 ERROR 级别消息
3. **性能监控**: 监控编译耗时,识别性能瓶颈

## 故障排查

### 1. MCP Server 无法启动

**症状**: Claude Desktop 提示无法连接到 MCP Server

**排查步骤**:

1. 检查 Python 是否正确安装:
   ```bash
   python --version
   ```

2. 检查依赖是否安装:
   ```bash
   pip list | grep mcp
   ```

3. 手动启动 Server 测试:
   ```bash
   python src/server.py
   ```

4. 查看 Claude Desktop 日志:
   - Windows: `%APPDATA%\Claude\logs\`
   - macOS: `~/Library/Logs/Claude/`

### 2. 编译器未找到

**症状**: 提示"编译器配置不存在"或"编译器文件不存在"

**排查步骤**:

1. 检查配置文件:
   ```bash
   cat config/compilers.json
   ```

2. 检查编译器路径是否存在:
   ```bash
   dir "C:\Program Files (x86)\Embarcadero\Studio\22.0\bin\dcc64.exe"
   ```

3. 使用 `set_compiler_config` 工具重新配置

### 3. 编译超时

**症状**: 编译过程超时

**排查步骤**:

1. 检查项目大小和复杂度
2. 增加 timeout 参数值
3. 检查系统资源使用情况
4. 检查编译器是否卡住

### 4. 权限错误

**症状**: 提示"无权限写入输出路径"

**排查步骤**:

1. 检查输出目录权限
2. 以管理员身份运行
3. 修改输出目录位置

## 性能优化

### 1. 使用 SSD

将项目和编译器放在 SSD 上可以显著提高编译速度。

### 2. 增加内存

确保系统有足够的内存,避免编译过程中使用虚拟内存。

### 3. 并发编译

系统支持并发编译,可以同时编译多个项目。

### 4. 编译器缓存

Delphi 编译器会缓存编译结果,避免重复编译未修改的单元。

### 5. 禁用不必要的功能

在 Release 编译时,可以禁用调试信息和优化选项以提高编译速度。

## 安全建议

1. **路径验证**: 系统已内置路径验证,禁止访问项目目录外的文件
2. **参数校验**: 所有编译参数都经过安全校验,防止命令注入
3. **权限控制**: 确保 MCP Server 进程只有必要的文件访问权限
4. **日志审计**: 定期检查日志,发现异常行为

## 备份与恢复

### 备份配置

定期备份以下文件:

- `config/compilers.json` - 编译器配置
- `config/history.json` - 编译历史

### 恢复配置

1. 停止 MCP Server
2. 恢复配置文件
3. 重启 MCP Server

## 更新与升级

### 更新依赖

```bash
pip install --upgrade -r requirements.txt
```

### 更新代码

```bash
git pull
pip install -r requirements.txt
```

### 版本兼容性

- Python 3.10+ 兼容
- MCP SDK 0.9.0+ 兼容
- Delphi 10.4+ 兼容

## 技术支持

如遇问题,请:

1. 查看本文档的故障排查章节
2. 查看日志文件
3. 提交 Issue 到项目仓库
