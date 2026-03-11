# Delphi 知识库 - 快速开始指南

## 🚀 30 秒快速开始

### 1. 启动 MCP Server

确保已安装 delphi_mcp_server,然后启动 MCP Server:

```bash
cd delphi_mcp_server
python src/server.py
```

### 2. 配置 AI 助手

在你的 AI 助手配置文件中添加 delphi_mcp_server:

**Claude Desktop**:
```json
{
  "mcpServers": {
    "delphi-kb": {
      "command": "python",
      "args": ["C:\\path\\to\\delphi_mcp_server\\src\\server.py"]
    }
  }
}
```

**CodeArts Agent**:
```json
{
  "mcp": {
    "servers": {
      "delphi-kb": {
        "enabled": true,
        "type": "stdio",
        "command": "python",
        "args": ["C:\\path\\to\\delphi_mcp_server\\src\\server.py"]
      }
    }
  }
}
```

### 3. 构建知识库

首次使用时,让智能体构建知识库:

```
你: 请构建 Delphi 知识库
```

### 4. 开始使用

现在你可以让智能体帮你查找 Delphi 代码:

```
你: 请搜索 TButton 类
你: 我需要创建一个按钮
你: 查找文件流相关的类
```

## 💡 常用命令

### 构建知识库

```
请构建 Delphi 知识库
请使用 Delphi 11 版本构建知识库
请强制重建知识库
```

### 精确搜索

```
请搜索 TButton 类
请查找 Create 函数
请搜索 TComponent 类
```

### 语义搜索

```
我需要创建一个按钮
如何处理网络请求
查找文件流相关的类
我需要一个处理字符串的函数
```

### 查看信息

```
请查看知识库统计信息
请列出已安装的 Delphi 版本
```

## 📊 知识库性能

- **构建时间**: ~92 秒 (首次)
- **加载时间**: 65ms
- **精确查询**: 0.31ms
- **语义查询**: 154ms
- **数据大小**: 111 MB

## 🎯 使用技巧

### 1. 使用自然语言查询

不要只搜索类名,用自然语言描述你的需求:

❌ 不好:
```
搜索 button
```

✅ 好:
```
我需要创建一个按钮
我需要一个可以点击的组件
```

### 2. 结合精确搜索和语义搜索

先精确搜索,再用语义搜索补充:

```
你: 请搜索 TButton 类

智能体: [显示 TButton 的详细信息]

你: 还有哪些相关的组件?

智能体: [使用语义搜索查找相关组件]
```

### 3. 查看统计信息

定期查看知识库统计信息,了解知识库的规模:

```
你: 请查看知识库统计信息
```

## ❓ 常见问题

### Q: 首次构建时间很长,正常吗?

A: 是的,首次构建需要扫描所有 Delphi 源码文件(约 3000 个文件),构建时间约 92 秒。构建完成后,后续使用会非常快。

### Q: 知识库占用多少磁盘空间?

A: 约 111 MB,包含所有类和函数的向量数据。

### Q: 支持哪些 Delphi 版本?

A: 支持 Delphi 2005 到 Delphi 13 的所有版本,会自动检测已安装的版本。

### Q: 知识库更新频率?

A: 知识库基于 Delphi 源码构建,只有当 Delphi 源码更新时才需要重建。可以使用 `force_rebuild` 参数强制重建。

### Q: 语义搜索准确吗?

A: 语义搜索使用 TF-IDF 向量相似度计算,对于功能描述性查询效果很好。对于精确类名,建议使用精确搜索。

## 📞 获取帮助

如果遇到问题:

1. 检查是否已安装 Delphi 编译器
2. 检查是否有读取 Delphi 源码目录的权限
3. 查看知识库构建日志
4. 运行测试: `python tests/test_knowledge_base.py`

## 🎉 开始使用

现在你已经准备好使用 Delphi 知识库了!让智能体帮助你更高效地开发 Delphi 应用吧!

```
你: 我需要开发一个文件上传功能

智能体: 根据您的需求,我找到了几个相关的组件:
       1. TIdFTP - Indy 的 FTP 客户端,适合文件传输
       2. THTTPClient - HTTP 客户端,适合通过 HTTP 上传文件
       3. TFileStream - 文件流,用于本地文件操作

       如果需要通过 FTP 上传,可以使用 TIdFTP 组件...
```

祝开发愉快!🚀
