"""
Delphi MCP Server 主程序

版权所有 (C) 吉林省左右软件开发有限公司
Copyright (C) Equilibrium Software Development Co., Ltd, Jilin

提供 MCP 协议服务,注册所有工具并启动服务器
"""

import asyncio
import sys
import os
from pathlib import Path

# 设置环境变量以确保正确的编码
os.environ['PYTHONIOENCODING'] = 'utf-8'
os.environ['PYTHONUTF8'] = '1'

# 重新配置标准错误输出流编码
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from mcp.server import Server
from mcp.server.stdio import stdio_server

from src.services.config_manager import ConfigManager
from src.services.compiler_service import CompilerService
from src.services.knowledge_base import DelphiKnowledgeBaseService
from src.tools import compile_project, compile_file, get_args, config, environment
from src.tools import knowledge_base as kb_tools
from src.tools import project_knowledge_base as project_kb_tools
from src.tools import help_knowledge_base as help_kb_tools
from src.utils.logger import init_default_logger, get_logger
from src.__version__ import __version__, __copyright__

# 初始化日志
logger = init_default_logger()


async def run_server():
    """运行 MCP Server"""
    logger.info(f"启动 Delphi MCP Server v{__version__}")
    logger.info(f"{__copyright__}")

    # 初始化配置管理器
    config_manager = ConfigManager()
    logger.info("配置管理器初始化完成")

    # 初始化编译服务
    compiler_service = CompilerService(config_manager)
    logger.info("编译服务初始化完成")

    # 初始化知识库服务
    kb_service = DelphiKnowledgeBaseService()
    logger.info("知识库服务初始化完成")

    # 设置工具的服务实例
    compile_project.set_compiler_service(compiler_service)
    compile_file.set_compiler_service(compiler_service)
    get_args.set_compiler_service(compiler_service)
    config.set_config_manager(config_manager)
    environment.set_config_manager(config_manager)
    kb_tools.set_knowledge_base_service(kb_service)
    logger.info("工具服务实例设置完成")

    # 创建 MCP Server 实例
    server = Server("delphi-mcp-server")
    logger.info("MCP Server 实例创建完成")

    # 注册工具
    @server.list_tools()
    async def list_tools():
        """列出所有可用工具"""
        from mcp.types import Tool
        return [
            Tool(
                name="compile_project",
                description="编译 Delphi 工程",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "project_path": {"type": "string", "description": "项目文件路径(.dproj 或 .dpr)"},
                        "target_platform": {"type": "string", "enum": ["win32", "win64"], "default": "win32", "description": "目标平台: win32(32位) 或 win64(64位)"},
                        "output_path": {"type": "string", "description": "输出路径，编译生成的可执行文件存放目录"},
                        "compiler_version": {"type": "string", "description": "编译器版本名称，使用 set_compiler_config 配置的编译器名称"},
                        "timeout": {"type": "integer", "default": 600, "description": "编译超时时间(秒)，默认600秒"},
                        "conditional_defines": {"type": "array", "items": {"type": "string"}, "description": "条件编译定义符号列表，如 ['DEBUG', 'TRACE']"},
                        "unit_search_paths": {"type": "array", "items": {"type": "string"}, "description": "单元文件搜索路径列表"},
                        "resource_search_paths": {"type": "array", "items": {"type": "string"}, "description": "资源文件搜索路径列表"},
                        "optimization_enabled": {"type": "boolean", "default": True, "description": "是否启用编译优化"},
                        "debug_info_enabled": {"type": "boolean", "default": False, "description": "是否生成调试信息"},
                        "warning_level": {"type": "integer", "default": 2, "description": "警告级别(0-4)，数值越大警告越严格"},
                        "disabled_warnings": {"type": "array", "items": {"type": "string"}, "description": "禁用的警告编号列表，如 ['W1000', 'W1001']"},
                        "output_type": {"type": "string", "enum": ["console", "gui", "dll"], "default": "gui", "description": "输出类型: console(控制台程序), gui(GUI程序), dll(动态链接库)"},
                        "runtime_library": {"type": "string", "enum": ["static", "dynamic"], "default": "static", "description": "运行时库链接方式: static(静态链接), dynamic(动态链接)"},
                        "build_configuration": {"type": "string", "description": "构建配置名称，如 'Debug' 或 'Release'"}
                    },
                    "required": ["project_path"]
                }
            ),
            Tool(
                name="compile_file",
                description="编译单个 Delphi 单元文件(仅语法检查)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "单元文件路径(.pas)"},
                        "unit_search_paths": {"type": "array", "items": {"type": "string"}, "description": "单元文件搜索路径列表"},
                        "warning_level": {"type": "integer", "default": 2, "description": "警告级别(0-4)，数值越大警告越严格"},
                        "disabled_warnings": {"type": "array", "items": {"type": "string"}, "description": "禁用的警告编号列表，如 ['W1000', 'W1001']"}
                    },
                    "required": ["file_path"]
                }
            ),
            Tool(
                name="get_compiler_args",
                description="获取编译器命令行参数(不执行编译)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "project_path": {"type": "string", "description": "项目文件路径(.dproj 或 .dpr)"},
                        "target_platform": {"type": "string", "enum": ["win32", "win64"], "default": "win32", "description": "目标平台: win32(32位) 或 win64(64位)"},
                        "output_path": {"type": "string", "description": "输出路径，编译生成的可执行文件存放目录"},
                        "compiler_version": {"type": "string", "description": "编译器版本名称，使用 set_compiler_config 配置的编译器名称"},
                        "conditional_defines": {"type": "array", "items": {"type": "string"}, "description": "条件编译定义符号列表，如 ['DEBUG', 'TRACE']"},
                        "unit_search_paths": {"type": "array", "items": {"type": "string"}, "description": "单元文件搜索路径列表"},
                        "resource_search_paths": {"type": "array", "items": {"type": "string"}, "description": "资源文件搜索路径列表"},
                        "optimization_enabled": {"type": "boolean", "default": True, "description": "是否启用编译优化"},
                        "debug_info_enabled": {"type": "boolean", "default": False, "description": "是否生成调试信息"},
                        "warning_level": {"type": "integer", "default": 2, "description": "警告级别(0-4)，数值越大警告越严格"},
                        "disabled_warnings": {"type": "array", "items": {"type": "string"}, "description": "禁用的警告编号列表，如 ['W1000', 'W1001']"},
                        "output_type": {"type": "string", "enum": ["console", "gui", "dll"], "default": "gui", "description": "输出类型: console(控制台程序), gui(GUI程序), dll(动态链接库)"},
                        "runtime_library": {"type": "string", "enum": ["static", "dynamic"], "default": "static", "description": "运行时库链接方式: static(静态链接), dynamic(动态链接)"},
                        "build_configuration": {"type": "string", "description": "构建配置名称，如 'Debug' 或 'Release'"}
                    },
                    "required": ["project_path"]
                }
            ),
            Tool(
                name="set_compiler_config",
                description="配置 Delphi 编译器",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "编译器版本名称，用于标识不同的编译器配置"},
                        "path": {"type": "string", "description": "编译器可执行文件路径，如 'C:\\Program Files\\Embarcadero\\RAD Studio\\bin\\dcc32.exe'"},
                        "is_default": {"type": "boolean", "default": False, "description": "是否设为默认编译器"},
                        "version": {"type": "string", "description": "编译器版本号，如 '10.4' 或 '11.0'"}
                    },
                    "required": ["name", "path"]
                }
            ),
            Tool(
                name="check_environment",
                description="检查编译器环境状态",
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            ),
            Tool(
                name="build_knowledge_base",
                description="构建 Delphi 源码知识库 (支持语义搜索)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "version": {"type": "string", "description": "Delphi 版本 (可选),默认使用最新版本"},
                        "force_rebuild": {"type": "boolean", "default": False, "description": "是否强制重建知识库"}
                    },
                    "required": []
                }
            ),
            Tool(
                name="search_class",
                description="搜索 Delphi 类定义",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "class_name": {"type": "string", "description": "类名,如 'TButton'"}
                    },
                    "required": ["class_name"]
                }
            ),
            Tool(
                name="search_function",
                description="搜索 Delphi 函数/过程定义",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "function_name": {"type": "string", "description": "函数名,如 'Create'"}
                    },
                    "required": ["function_name"]
                }
            ),
            Tool(
                name="semantic_search",
                description="语义搜索 Delphi 代码 (支持自然语言查询)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "搜索查询,如 'create button' 或 'network http request'"},
                        "top_k": {"type": "integer", "default": 10, "description": "返回结果数量"}
                    },
                    "required": ["query"]
                }
            ),
            Tool(
                name="get_knowledge_base_stats",
                description="获取知识库统计信息",
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            ),
            Tool(
                name="list_delphi_versions",
                description="列出已安装的 Delphi 版本",
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            ),
            # 项目知识库工具
            Tool(
                name="init_project_knowledge_base",
                description="初始化项目知识库 (从 .dproj 读取三方库路径并构建知识库)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "project_path": {"type": "string", "description": "项目文件路径 (.dproj 或 .dpr)"},
                        "build_thirdparty": {"type": "boolean", "default": True, "description": "是否构建三方库知识库"},
                        "build_project": {"type": "boolean", "default": True, "description": "是否构建项目源码知识库"},
                        "force_rebuild": {"type": "boolean", "default": False, "description": "是否强制重建"}
                    },
                    "required": ["project_path"]
                }
            ),
            Tool(
                name="search_project_class",
                description="在项目中搜索类定义 (支持搜索项目源码和三方库)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "project_path": {"type": "string", "description": "项目文件路径 (.dproj 或 .dpr)"},
                        "class_name": {"type": "string", "description": "类名"},
                        "search_in": {"type": "string", "enum": ["project", "thirdparty", "all"], "default": "all", "description": "搜索范围: project(项目源码), thirdparty(三方库), all(全部)"}
                    },
                    "required": ["project_path", "class_name"]
                }
            ),
            Tool(
                name="search_project_function",
                description="在项目中搜索函数定义 (支持搜索项目源码和三方库)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "project_path": {"type": "string", "description": "项目文件路径 (.dproj 或 .dpr)"},
                        "function_name": {"type": "string", "description": "函数名"},
                        "search_in": {"type": "string", "enum": ["project", "thirdparty", "all"], "default": "all", "description": "搜索范围: project(项目源码), thirdparty(三方库), all(全部)"}
                    },
                    "required": ["project_path", "function_name"]
                }
            ),
            Tool(
                name="semantic_search_project",
                description="在项目中进行语义搜索 (支持自然语言查询,自动检测源码变动并更新)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "project_path": {"type": "string", "description": "项目文件路径 (.dproj 或 .dpr)"},
                        "query": {"type": "string", "description": "搜索查询,如 'create button' 或 'network http request'"},
                        "top_k": {"type": "integer", "default": 10, "description": "返回结果数量"},
                        "search_in": {"type": "string", "enum": ["project", "thirdparty", "all"], "default": "all", "description": "搜索范围: project(项目源码), thirdparty(三方库), all(全部)"}
                    },
                    "required": ["project_path", "query"]
                }
            ),
            Tool(
                name="get_project_kb_stats",
                description="获取项目知识库统计信息",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "project_path": {"type": "string", "description": "项目文件路径 (.dproj 或 .dpr)"}
                    },
                    "required": ["project_path"]
                }
            ),
            Tool(
                name="get_thirdparty_paths",
                description="获取项目的三方库路径 (从 .dproj 文件中提取)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "project_path": {"type": "string", "description": "项目文件路径 (.dproj 或 .dpr)"}
                    },
                    "required": ["project_path"]
                }
            ),
            # 帮助文档知识库工具
            Tool(
                name="build_help_knowledge_base",
                description="构建 Delphi 帮助文档知识库 (从 CHM 文件提取)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "force_rebuild": {"type": "boolean", "default": False, "description": "是否强制重建"}
                    },
                    "required": []
                }
            ),
            Tool(
                name="search_help",
                description="搜索 Delphi 帮助文档",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "搜索查询"},
                        "top_k": {"type": "integer", "default": 10, "description": "返回结果数量"}
                    },
                    "required": ["query"]
                }
            ),
            Tool(
                name="get_help_kb_stats",
                description="获取帮助文档知识库统计信息",
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            )
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict):
        """调用工具"""
        logger.info(f"调用工具: {name}")

        try:
            if name == "compile_project":
                result = await compile_project.compile_project(**arguments)
            elif name == "compile_file":
                result = await compile_file.compile_file(**arguments)
            elif name == "get_compiler_args":
                result = await get_args.get_compiler_args(**arguments)
            elif name == "set_compiler_config":
                result = await config.set_compiler_config(**arguments)
            elif name == "check_environment":
                result = await environment.check_environment()
            elif name == "build_knowledge_base":
                result = await kb_tools.build_knowledge_base(arguments)
            elif name == "search_class":
                result = await kb_tools.search_class(arguments)
            elif name == "search_function":
                result = await kb_tools.search_function(arguments)
            elif name == "semantic_search":
                result = await kb_tools.semantic_search(arguments)
            elif name == "get_knowledge_base_stats":
                result = await kb_tools.get_knowledge_base_stats(arguments)
            elif name == "list_delphi_versions":
                result = await kb_tools.list_delphi_versions(arguments)
            # 项目知识库工具
            elif name == "init_project_knowledge_base":
                result = await project_kb_tools.init_project_knowledge_base(arguments)
            elif name == "search_project_class":
                result = await project_kb_tools.search_project_class(arguments)
            elif name == "search_project_function":
                result = await project_kb_tools.search_project_function(arguments)
            elif name == "semantic_search_project":
                result = await project_kb_tools.semantic_search_project(arguments)
            elif name == "get_project_kb_stats":
                result = await project_kb_tools.get_project_kb_stats(arguments)
            elif name == "get_thirdparty_paths":
                result = await project_kb_tools.get_thirdparty_paths(arguments)
            # 帮助文档知识库工具
            elif name == "build_help_knowledge_base":
                result = await help_kb_tools.build_help_knowledge_base(arguments)
            elif name == "search_help":
                result = await help_kb_tools.search_help(arguments)
            elif name == "get_help_kb_stats":
                result = await help_kb_tools.get_help_kb_stats(arguments)
            else:
                raise ValueError(f"未知工具: {name}")

            return {"content": [{"type": "text", "text": str(result)}]}

        except Exception as e:
            logger.error(f"工具调用失败: {str(e)}", exc_info=True)
            return {"content": [{"type": "text", "text": f"错误: {str(e)}"}], "isError": True}

    # 启动服务器
    logger.info("MCP Server 启动中...")
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


def main():
    """主函数"""
    try:
        asyncio.run(run_server())
    except KeyboardInterrupt:
        logger.info("服务器已停止")
    except Exception as e:
        logger.error(f"服务器运行失败: {str(e)}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
