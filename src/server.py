"""
Daofy 主程序

版权所有 (C) 吉林省左右软件开发有限公司
Copyright (C) Equilibrium Software Development Co., Ltd, Jilin
Update & Mod By Crystalxp (黑夜杀手 QQ:281309196)

提供 MCP 协议服务,注册所有工具并启动服务器
"""

import asyncio
import sys
import os
import winreg
from pathlib import Path
from typing import Any, Optional
import io

os.environ['PYTHONIOENCODING'] = 'utf-8'
os.environ['PYTHONUTF8'] = '1'

# 保护: 子进程(multiprocessing spawn) 的 stdout 已经 pipe,
# TextIOWrapper 可能失败。失败时跳过不影响子进程通信。
if __name__ != '__mp_main__':
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=False)
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace', line_buffering=False)
    except Exception:
        pass

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# ============================================================
# multiprocessing 子进程保护
# Windows spawn模式下,子进程会重新导入 __main__ 模块(即本文件),
# 导致所有服务模块被重新导入(885个模块),启动极慢。
# 检测到是子进程时,跳过所有服务导入,只保留必要的模块。
# ============================================================
_is_multiprocessing_child = __name__ == '__mp_main__'

if _is_multiprocessing_child:
    # 子进程不需要任何MCP服务,直接跳过
    # ProcessPoolExecutor的worker只需要能pickle/unpickle函数即可
    pass
else:

    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import CallToolResult, TextContent

    from src.services.config_manager import ConfigManager
    from src.services.compiler_service import CompilerService
    from src.services.knowledge_base import DelphiKnowledgeBaseService
    from src.services.knowledge_base.thirdparty_knowledge_base import ThirdPartyKnowledgeBase
    from src.tools.compile_project import set_compiler_service as sp1, compile_project
    from src.tools.compile_file import set_compiler_service as sp2, compile_file
    from src.tools.get_args import set_compiler_service as sp3, get_compiler_args
    from src.tools.config import set_config_manager, search_compilers
    from src.tools.environment import check_environment, set_config_manager as scm, set_thirdparty_kb_service as stks
    from src.tools.knowledge_base import (
        set_delphi_kb_service,
        set_thirdparty_kb_service,
        search_knowledge,
        build_unified_knowledge_base,
        get_unified_knowledge_stats
    )
    from src.tools.read_source_file import set_knowledge_base_services, read_source_file
    from src.tools import knowledge_base as kb_tools
    from src.tools import thirdparty_knowledge_base as thirdparty_kb_tools
    from src.tools import async_tasks as async_tools
    from src.tools import pasfmt
    from src.tools.install_package import install_package, list_installed_packages, set_compiler_service as sip
    from src.tools import document_kb_tools as doc_tools
    from src.tools.code_hosting import code_hosting
    from src.tools import file_tool
    from src.tools import dfm_utils as dfm_utils_mod
    from src.utils.logger import init_default_logger, get_logger, log_api_call
    from src.__version__ import __version__, __copyright__

    # 初始化日志
    logger = init_default_logger()


def _auto_detect_delphi_help_dir() -> Optional[str]:
    """自动检测最新安装的 Delphi 帮助文档目录"""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"SOFTWARE\Embarcadero\BDS")
        versions = []
        i = 0
        while True:
            try:
                versions.append(winreg.EnumKey(key, i))
                i += 1
            except OSError:
                break
        winreg.CloseKey(key)

        versions.sort(key=lambda x: float(x) if x.replace('.', '').isdigit() else 0, reverse=True)
        for ver in versions:
            try:
                vk = winreg.OpenKey(winreg.HKEY_CURRENT_USER, rf"SOFTWARE\Embarcadero\BDS\{ver}")
                root_dir = winreg.QueryValueEx(vk, "RootDir")[0]
                winreg.CloseKey(vk)
                help_dir = Path(root_dir) / "Help" / "Doc"
                if help_dir.exists():
                    logger.info(f"自动检测到 Delphi 帮助目录 (版本 {ver}): {help_dir}")
                    return str(help_dir)
            except Exception:
                logger.debug("读取注册表版本键失败", exc_info=True)
                continue
    except Exception:
        logger.debug("打开注册表 BDS 键失败", exc_info=True)

    # 注册表失败，尝试默认路径（版本号与注册表一致：37.0=Delphi13, 23.0=Delphi12, 22.0=Delphi11...）
    for ver in ["37.0", "23.0", "22.0", "21.0", "20.0", "19.0", "18.0", "17.0", "16.0", "15.0", "14.0", "12.0", "11.0", "10.0", "9.0", "8.0", "7.0", "6.0", "5.0", "4.0", "3.0"]:
        path = rf"C:\Program Files (x86)\Embarcadero\Studio\{ver}\Help\Doc"
        if Path(path).exists():
            logger.info(f"使用默认帮助目录: {path}")
            return path
    return None


def _get_smart_hint(name: str, result: Any, arguments: dict) -> Optional[str]:
    """
    智能提示：根据工具名和返回结果，生成下一步建议。

    Args:
        name: 工具名
        result: 工具返回结果（dict 或 CallToolResult）
        arguments: 调用参数

    Returns:
        建议文本，无建议时返回 None
    """
    if name == "compile_project":
        proj_path = arguments.get("project_path", "")
        is_pas = proj_path.lower().endswith('.pas')
        if isinstance(result, CallToolResult):
            is_error = result.isError
        elif isinstance(result, dict):
            is_error = (
                result.get('status') == 'failed'
                or result.get('success') is False
                or 'error' in result
            )
        else:
            is_error = False

        if is_error:
            if is_pas:
                return ("✨ 提示：编译失败。试试：\n"
                        "  check_environment(action='detect') — 重新检测编译器\n"
                        "  compile_project(..., get_args_only=True) — 预览编译参数")
            return ("✨ 提示：编译失败。试试：\n"
                    "  check_environment(action='detect') — 重新检测编译器\n"
                    "  check_environment(action='check') — 检查编译环境\n"
                    "  compile_project(..., get_args_only=True) — 预览编译参数")
        elif not is_pas and not arguments.get("get_args_only"):
            return ("✨ 提示：建议用 file_tool(action='format', file_path=...) "
                    "统一格式化代码风格")

    elif name == "delphi_kb":
        action = arguments.get("action", "search")
        if action == "search":
            if isinstance(result, dict):
                results = result.get('results') or result.get('data') or []
                if isinstance(results, list) and len(results) > 0:
                    return ("✨ 提示：找到目标后，可用 "
                            'file_tool(action="read", file_path="...") 读取完整源码定义')
        elif action == "stats":
            return ("✨ 提示：如果知识库数据过期，"
                    "可用 delphi_kb(action='build', kb_type='project') 重建")

    elif name == "get_coding_rules":
        # 仅在 section=None（默认模式）时提示
        section = arguments.get("section")
        if section is None or section == "":
            return ("✨ 提示：使用 section 参数按需获取对应章节：\n"
                    '   get_coding_rules(section="writing")  — 写代码前看编码规则\n'
                    '   get_coding_rules(section="review")   — 编译后看审核表\n'
                    '   get_coding_rules(section="safety")   — 安全敏感操作')

    elif name == "check_environment":
        action = arguments.get("action", "check")
        if action == "detect" or action == "check":
            if isinstance(result, dict):
                compilers = result.get('compilers') or result.get('data')
                if compilers and len(compilers) > 0:
                    return ("✨ 提示：环境已就绪，"
                            "可用 compile_project 开始编译验证")
                else:
                    return ("✨ 提示：未检测到编译器，"
                            "请检查 Delphi 是否已安装，"
                            "或用 check_environment(action='detect', search_path=...) 指定自定义路径")

    elif name == "install_package":
        if isinstance(result, CallToolResult):
            is_error = result.isError
        elif isinstance(result, dict):
            is_error = (
                result.get('status') == 'failed'
                or result.get('success') is False
                or 'error' in result
            )
        else:
            is_error = False
        if not is_error:
            return ("✨ 提示：安装完成，"
                    "可用 list_installed_packages 验证组件已注册到 IDE")

    return None


async def run_server():
    """运行 MCP Server"""
    logger.info(f"启动 Daofy v{__version__}")
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

    # 初始化第三方库知识库服务
    thirdparty_kb_service = ThirdPartyKnowledgeBase()
    thirdparty_kb_tools.set_thirdparty_knowledge_base_service(thirdparty_kb_service)
    logger.info("第三方库知识库服务初始化完成")

    # 设置工具的服务实例
    sp1(compiler_service)
    sp2(compiler_service)
    sp3(compiler_service)
    sip(compiler_service)
    scm(config_manager)
    set_config_manager(config_manager)
    stks(thirdparty_kb_service)
    set_knowledge_base_services(kb_service, thirdparty_kb_service)
    set_delphi_kb_service(kb_service)
    # 项目 KB 服务由 project_path 参数动态创建,不在启动时初始化
    # set_project_kb_service(kb_service)  # kb_service 是 Delphi RTL KB,不适合作为项目 KB
    set_thirdparty_kb_service(thirdparty_kb_service)

    # 设置 DFM 工具编译器路径
    newest = config_manager.get_newest_compiler()
    if newest and newest.path:
        dfm_utils_mod.set_compiler_path(newest.path)
        logger.info(f"DFM 工具编译器路径已设置: {newest.path}")
    else:
        logger.warning("未找到可用编译器，DFM 转换功能将不可用")

    logger.info("工具服务实例设置完成")

    # 创建 MCP Server 实例
    server = Server("delphi-mcp-server")
    logger.info("MCP Server 实例创建完成")

    # ============================================================
    # MCP 工具注册
    # 所有工具必须同时在 list_tools() 和 call_tool() 中注册
    # ============================================================
    @server.list_tools()
    async def list_tools():
        """列出所有可用工具"""
        from mcp.types import Tool
        return [
            # ===== 编译/检查 — 构建 Delphi ⭐⭐⭐ =====
            Tool(
                name="compile_project",
                description="【优先级 ⭐⭐⭐】编译/检查 — 构建 Delphi\n"
                            "【触发词】编译、构建、生成exe、语法检查、编译报错、build、compile、msbuild、dcc32、\n"
                            "           检查语法、编译验证、编译项目、dproj编译\n"
                            "【Delphi 文件触发】看到 .dproj/.dpr/.dpk/.pas 文件时优先编译\n"
                            "❌ 不得用 bash/cmd 运行 dcc32/msbuild（绕过 MSBuild/事件/依赖）\n"
                            "✅ 编译 .dproj/.dpr/.dpk 或检查 .pas 语法必须用此\n"
                            "【协作链】get_coding_rules→file_tool→compile→失败→check_environment\n"
                            "【降级】MSBuild 不可用→dcc32；get_args_only 预览参数\n"
                            "【示例】\n"
                            '   compile_project(build_configuration="Release")  # "编译Release版本"\n'
                            '   compile_project(target_platform="win64")        # "生成64位exe"\n'
                            '   compile_project(project_path="unit.pas")        # "检查语法"\n'
                            '   compile_project(get_args_only=True)             # "只看参数不执行"',
                inputSchema={
                    "type": "object",
                    "properties": {
                        "project_path": {"type": "string", "description": "[必需] 项目文件(.dproj/.dpr/.dpk)或 .pas 文件路径"},
                        "target_platform": {"type": "string", "enum": ["win32", "win64", "osx64", "osxarm64", "iosdevice64", "iosdevice", "iossimulator", "android", "android64", "linux64"], "default": "win32", "description": "目标平台: win32/win64/osx64/android 等"},
                        "build_configuration": {"type": "string", "default": "Debug", "description": "构建配置: Debug（调试）或 Release（发布）"},
                        "output_path": {"type": "string", "description": "编译输出目录（可选，默认是项目目录）"},
                        "compiler_version": {"type": "string", "description": "编译器版本（可选，不传时自动检测最新安装的版本）"},
                        "conditional_defines": {"type": "array", "items": {"type": "string"}, "description": "条件编译符号列表，如 [\"DEBUG\", \"USE_MYLIB\"]"},
                        "unit_search_paths": {"type": "array", "items": {"type": "string"}, "description": "额外单元搜索路径列表，系统会自动从.dproj和Delphi默认路径获取"},
                        "resource_search_paths": {"type": "array", "items": {"type": "string"}, "description": "资源搜索路径列表"},
                        "optimization_enabled": {"type": "boolean", "default": True, "description": "是否启用编译器优化"},
                        "debug_info_enabled": {"type": "boolean", "default": True, "description": "是否生成调试信息（含行号信息）"},
                        "warning_level": {"type": "integer", "default": 2, "description": "警告级别(0-4)，越高越严格"},
                        "disabled_warnings": {"type": "array", "items": {"type": "string"}, "description": "要禁用的编译器警告编号列表，如 [\"W1000\"]"},
                        "output_type": {"type": "string", "default": "gui", "enum": ["console", "gui", "dll"], "description": "输出类型: console=控制台程序, gui=窗口程序, dll=动态库"},
                        "runtime_library": {"type": "string", "default": "static", "enum": ["static", "dynamic"], "description": "运行时库链接方式: static=静态链接, dynamic=动态链接"},
                        "timeout": {"type": "integer", "default": 600, "description": "编译超时秒数（默认600秒，即10分钟）"},
                        "install_if_design_package": {"type": "boolean", "default": True, "description": "设计期包是否自动安装到IDE（仅.dpk有效）"},
                        "get_args_only": {"type": "boolean", "default": False, "description": "true=仅显示编译参数不实际编译，用于调试编译选项"}
                    },
                    "required": ["project_path"]
                }
            ),

            # ===== 知识库搜索/管理 ⭐⭐⭐ =====
            Tool(
                name="delphi_kb",
                description="【优先级 ⭐⭐⭐】知识库搜索/管理 — 查 Delphi API、项目代码、文档\n"
                            "【触发词】搜索类、搜索函数、查API、查定义、知识库、构建知识库、KB、语义搜索\n"
                            "【Delphi 文件触发】写 .pas 代码前应先搜索 KB 查 API 定义(TODO先调用 delphi_kb 搜索类/函数)\n"
                            "【协作链】写代码前→delphi_kb查API→file_tool(read)看定义→写代码→compile\n"
                            "【action 说明】\n"
                            '  action="search"    默认 — 搜索类/函数/文档, kb_type=all/delphi/project/thirdparty/document\n'
                            '                    search_type=function/procedure/class/record/semantic/reference\n'
                            '  action="stats"     查看知识库统计(文件数、类数、函数数、末次构建时间)\n'
                            '  action="build"     构建/更新知识库（支持异步 async_mode=true）\n'
                            '  action="scan"      扫描目录添加文档(kb_type=document)\n'
                            '  action="web"       添加网页文档(kb_type=document)\n'
                            '  action="read"      读取文档内容(url/doc_id)或源码文件(file_path)\n'
                            "【示例】\n"
                            '   delphi_kb(query="TStringList")           — 搜索类\n'
                            '   delphi_kb(query="Create", search_type="function") — 搜索函数\n'
                            '   delphi_kb(action="stats")                — 查看统计\n'
                            '   delphi_kb(action="build", kb_type="project") — 构建项目知识库',
                inputSchema={
                    "type": "object",
                    "properties": {
                        "action": {"type": "string", "enum": ["search", "stats", "build", "scan", "web", "read", "build_embedding"], "default": "search", "description": "操作类型: search=搜索, stats=统计, build=构建, scan=扫描文档, web=添加网页, read=读取, build_embedding=构建向量"},
                        "query": {"type": "string", "description": "搜索关键词（action=search时需要）"},
                        "kb_type": {"type": "string", "enum": ["all", "delphi", "project", "thirdparty", "document"], "default": "all", "description": "知识库类型"},
                        "search_type": {"type": "string", "enum": ["function", "procedure", "class", "record", "interface", "enum", "type", "const", "property", "method", "field", "event", "semantic", "reference", "all"], "description": "搜索类型（action=search 时生效）"},
                        "top_k": {"type": "integer", "default": 200, "description": "最大返回结果数（默认200，最大500）"},
                        "project_path": {"type": "string", "description": "项目路径（搜索project/thirdparty知识库时需要，不传则自动检测目录下的.dproj）"},
                        "version": {"type": "string", "description": "Delphi版本（构建知识库时使用）"},
                        "async_mode": {"type": "boolean", "default": True, "description": "是否异步执行（build操作时生效，默认true）"},
                        "force_rebuild": {"type": "boolean", "default": False, "description": "是否强制重建（build操作时生效）"},
                        "incremental": {"type": "boolean", "default": False, "description": "是否增量更新（build操作时生效）"},
                        "build_thirdparty": {"type": "boolean", "default": True, "description": "构建项目KB时是否同时构建第三方库KB"},
                        "build_project": {"type": "boolean", "default": True, "description": "是否构建项目KB"},
                        "directory": {"type": "string", "description": "扫描目录（action=scan时使用，或build document时可以不传自动检测Delphi帮助目录）"},
                        "extensions": {"type": "array", "items": {"type": "string"}, "description": "文件扩展名过滤（action=scan/build时使用，如[\".chm\"]）"},
                        "content_type": {"type": "string", "description": "文档类型过滤（action=search kb_type=document时使用）"},
                        "url": {"type": "string", "description": "网页URL（action=web时使用）或文档URL（action=read时使用）"},
                        "doc_id": {"type": "string", "description": "文档ID（action=read时使用，与url二选一）"},
                        "file_path": {"type": "string", "description": "文件路径（action=read时使用）"},
                        "offset": {"type": "integer", "default": 0, "description": "读取偏移量（action=read时使用）"},
                        "limit": {"type": "integer", "default": 5000, "description": "读取字节数限制（action=read时使用）"},
                        "max_pages": {"type": "integer", "default": 100, "description": "最大抓取页数（build document KB时使用）"},
                        "max_depth": {"type": "integer", "default": 3, "description": "最大抓取深度（build document KB时使用）"},
                        "domain_filter": {"type": "string", "description": "域名过滤（build document KB时使用）"},
                        "url_pattern": {"type": "string", "description": "URL模式过滤（build document KB时使用）"},
                        "exclude_dirs": {"type": "array", "items": {"type": "string"}, "description": "排除目录列表（build document KB时使用）"},
                        "max_workers": {"type": "integer", "description": "最大工作进程数（action=scan时使用）"},
                        "show_progress": {"type": "boolean", "default": True, "description": "是否显示进度"},
                    }
                }
            ),

            # ===== 文件操作 — 读/写/格式化/备份管理 ⭐⭐⭐ =====
            Tool(
                name="file_tool",
                description="【优先级 ⭐⭐⭐】读写文件 / 格式化 / 备份管理 — .pas/.dfm/.dproj 等 Delphi 文件\n"
                            "【触发词】修改代码、编辑文件、写入代码、新建文件、改代码、替换内容、覆盖文件、读文件、查看源码、打开文件、cat文件、\n"
                            "           格式化代码、整理代码、排版、代码风格、自动格式化、恢复备份、备份文件、历史版本、\n"
                            "           查看备份、还原文件、回退修改、修改前备份、差异对比、diff\n"
                            "【Delphi 文件触发】操作 .pas/.dfm/.dproj/.dpk/.fmx/.inc 文件时必须用此，\n"
                            "【严禁】使用 edit/write/bash echo 直接修改 .pas/.dfm 文件（会绕过备份机制）\n"
                            "\n"
                            "四种工作模式(action)，每种只使用自己的参数：\n"
                            "\n"
                            "═══ action=\"read\" — 读文件 / 查源码 ═══\n"
                            '  file_tool(action="read", file_path="Unit1.pas", start_line=1)\n'
                            '  file_tool(action="read", search_type="class", type_name="TForm1")   # 搜类定义位置\n'
                            '  file_tool(action="read", search_type="function", function_name="Create")  # 搜函数\n'
                            "  ⭐ DFM 自动转文本：二进制 DFM 读成文本，无需手动转换\n"
                            "\n"
                            "═══ action=\"write\" — 写文件 / 改代码 / 替换内容 ═══\n"
                            '  file_tool(action="write", file_path="src/Unit1.pas", content="...", backup=True)\n'
                            "  ⭐ 自动备份到 __history（backup=True 默认）\n"
                            "  ⭐ 自动识别并保持原始编码（UTF-8/GBK/UTF-16），不乱码\n"
                            "  ⭐ DFM 二进制自动转换：写入文本后自动转回二进制格式\n"
                            '  📌 写入后自动格式化: format_after_write=True\n'
                            "\n"
                            "═══ action=\"format\" — 格式化 / 整理代码 ═══\n"
                            '  file_tool(action="format", file_path="src/Unit1.pas")\n'
                            "  使用 pasfmt 格式化 .pas/.dfm 代码（自动备份）\n"
                            '  file_tool(action="format", file_path="Unit1.pas", check_only=True)   # 仅检查不修改\n'
                            '  file_tool(action="format", format_action="code", code="procedure...")  # 格式化代码段\n'
                            "\n"
                            "═══ action=\"backup\" — 备份管理 / 历史版本 / 恢复 ═══\n"
                            '  file_tool(action="backup", file_path="src/Unit1.pas")             # 手动创建备份\n'
                            '  file_tool(action="backup", backup_action="list", file_path="Unit1.pas")  # 列出所有版本\n'
                            '  file_tool(action="backup", backup_action="restore", file_path="Unit1.pas", version=3)  # 恢复\n'
                            "\n"
                            "【协作链】get_coding_rules→file_tool(read)→file_tool(write)→file_tool(format)→compile_project",
                inputSchema={
                    "type": "object",
                    "properties": {
                        # ---- 全局参数 ----
                        "action": {"type": "string", "enum": ["read", "write", "format", "backup"], "default": "read", "description": "操作类型: read=读文件, write=写文件(自动备份), format=格式化, backup=备份管理"},

                        # ---- 所有 action 共用 ----
                        "file_path": {"type": "string", "description": "目标文件路径，支持 .pas/.dfm/.dproj/.dpk/.fmx/.inc"},

                        # ---- read 参数 ----
                        "search_type": {"type": "string", "enum": ["path", "class", "function", "record"], "description": "读取模式: path=按路径, class=按类名定位, function=按函数名定位, record=按record名定位"},
                        "type_name": {"type": "string", "description": "类名/接口名/枚举名（search_type=class时使用，如 'TForm1'）"},
                        "class_name": {"type": "string", "description": "类名（与type_name二选一，兼容旧版）"},
                        "record_name": {"type": "string", "description": "Record 类型名（search_type=record时使用）"},
                        "function_name": {"type": "string", "description": "函数/过程名（search_type=function时使用，如 'Create'）"},
                        "start_line": {"type": "integer", "default": 1, "description": "起始行号（从1开始），读大文件时分段使用"},
                        "max_lines": {"type": "integer", "default": 500, "description": "最大返回行数，读大文件时建议用此参数分段"},
                        "search_in": {"type": "string", "enum": ["all", "delphi", "thirdparty"], "default": "all", "description": "搜索范围: all=所有知识库, delphi=官方源码, thirdparty=第三方库"},
                        "project_path": {"type": "string", "description": "项目文件路径(可选)，用于在项目知识库中查找 .pas"},
                        "end_line": {"type": "integer", "description": "结束行号，不传则到文件末尾"},

                        # ---- write 参数 ----
                        "content": {"type": "string", "description": "写入的完整文件内容（action=write时必需）"},
                        "encoding": {"type": "string", "default": "auto", "description": "写入编码: auto=自动检测保持原始编码, 也可指定 utf-8/gbk/utf-16"},
                        "format_after_write": {"type": "boolean", "default": False, "description": "写入后自动调用 pasfmt 格式化代码"},
                        "backup": {"type": "boolean", "default": True, "description": "写入前自动备份原文件到 __history 目录（建议保持默认 true）"},

                        # ---- format 参数 ----
                        "format_action": {"type": "string", "enum": ["file", "code", "check"], "default": "file", "description": "格式化子操作: file=格式化文件, code=格式化代码段, check=仅检查格式"},
                        "code": {"type": "string", "description": "待格式化的代码文本（format_action=code时使用）"},
                        "config_path": {"type": "string", "description": "pasfmt 配置文件路径（可选，高级用法）"},
                        "uses_style": {"type": "string", "enum": ["compact", "pasfmt_default"], "description": "uses子句风格: compact=合并为一行, pasfmt_default=每行一个"},
                        "check_only": {"type": "boolean", "default": False, "description": "true=仅检查格式是否正确但不修改文件"},

                        # ---- backup 参数 ----
                        "backup_action": {"type": "string", "enum": ["create", "list", "restore"], "default": "create", "description": "备份子操作: create=创建备份, list=列出版本, restore=恢复指定版本"},
                        "version": {"type": "integer", "description": "要恢复的版本号（backup_action=restore时使用，不传则恢复最新版）"},
                    }
                }
            ),

            # ===== 环境检查 ⭐⭐⭐ =====
            Tool(
                name="check_environment",
                description="【优先级 ⭐⭐⭐】环境检查 — 诊断 Delphi 编译环境、检测编译器、安装 pasfmt\n"
                            "【触发词】检查环境、检测编译器、诊断、环境状态、环境就绪、编译器找不到\n"
                            "【action 说明】\n"
                            '  action="check"         默认 — 检查当前编译环境状态（有多少编译器可用）\n'
                            '  action="detect"        重新从注册表/指定路径检测 Delphi 编译器\n'
                            '  action="install"       下载并安装 pasfmt 格式化工具\n'
                            '  action="format_install"安装 pasfmt RAD Studio 插件\n'
                            "【协作链】首次使用→check_environment(action=check)→compile→失败→check_environment(action=detect)\n"
                            "【示例】\n"
                            '   check_environment(action="check")   # "检查环境"\n'
                            '   check_environment(action="detect", search_path="D:\\Delphi")  # "指定路径检测"',
                inputSchema={
                    "type": "object",
                    "properties": {
                        "action": {"type": "string", "enum": ["check", "detect", "install", "format_install"], "default": "check", "description": "操作类型: check=检查, detect=检测编译器, install=安装pasfmt, format_install=安装pasfmt RAD插件"},
                        "search_path": {"type": "string", "description": "额外搜索路径（action=detect时使用）"},
                        "install_dir": {"type": "string", "description": "安装目录（action=install/format_install时使用）"},
                        "delphi_version": {"type": "string", "default": "11", "description": "Delphi版本（action=format_install时使用，如\"11\"、\"12\"）"},
                    }
                }
            ),

            # ===== 异步任务管理 ⭐ =====
            Tool(
                name="async_task",
                description="【优先级 ⭐】异步任务管理 — 管理后台构建知识库等耗时任务\n"
                            "【触发词】任务状态、查看进度、后台任务、构建进度、取消任务\n"
                            "【action 说明】\n"
                            '  action="start"  启动异步任务（通常 delphi_kb(action=build) 已自动启动，无需手动调用）\n'
                            '  action="status" 查询任务状态（返回进度百分比和状态）\n'
                            '  action="result" 获取任务结果\n'
                            '  action="list"   列出所有任务\n'
                            '  action="cancel" 取消运行中的任务\n'
                            "【示例】\n"
                            '   async_task(action="status", task_id="...")  # "查看任务进度"\n'
                            '   async_task(action="list")                   # "列出所有任务"',
                inputSchema={
                    "type": "object",
                    "properties": {
                        "action": {"type": "string", "enum": ["start", "status", "result", "list", "cancel"], "description": "操作类型", "default": "list"},
                        "task_id": {"type": "string", "description": "任务ID（action=status/result/cancel时使用）"},
                        "task_type": {"type": "string", "description": "任务类型（action=start时使用），如: build_knowledge_base, build_thirdparty_knowledge_base, init_project_knowledge_base, build_document_knowledge_base, build_embedding"},
                        "task_params": {"type": "object", "description": "任务参数（action=start时使用，根据task_type不同而不同）"},
                        "show_progress": {"type": "boolean", "default": True, "description": "是否显示进度"},
                    }
                }
            ),

            # ===== 组件包安装 ⭐⭐ =====
            Tool(
                name="install_package",
                description="【优先级 ⭐⭐】编译并安装 Delphi 组件包到 IDE\n"
                            "【触发词】安装组件、安装包、编译包、dpk安装、注册组件、install package\n"
                            "自动将设计期包注册到 IDE，运行期包仅编译\n"
                            "支持 .dproj / .dpk / .groupproj 三种格式\n"
                            "【协作链】install_package→list_installed_packages 验证安装\n"
                            "【示例】\n"
                            '   install_package(package_path="MyPackage.dpk")  # "安装组件包"',
                inputSchema={
                    "type": "object",
                    "properties": {
                        "package_path": {"type": "string", "description": "包文件路径(.dproj/.dpk/.groupproj) [必需]"},
                        "target_platform": {"type": "string", "enum": ["win32", "win64"], "default": "win32", "description": "目标平台"},
                        "build_configuration": {"type": "string", "default": "Debug", "description": "构建配置(Debug/Release)"},
                        "timeout": {"type": "integer", "default": 300, "description": "超时时间(秒)"},
                        "install": {"type": "boolean", "default": True, "description": "是否自动安装到 IDE"},
                    },
                    "required": ["package_path"]
                }
            ),

            # ===== 列出已安装的组件包 =====
            Tool(
                name="list_installed_packages",
                description="列出已安装到 IDE 的 Delphi 组件包\n"
                            "【触发词】已安装的包、列出组件、查看已安装、验证安装\n"
                            "【协作链】install_package 后调用此工具验证组件已成功注册",
                inputSchema={
                    "type": "object",
                    "properties": {}
                }
            ),

            # ===== 编码规则（AI 必读）⭐⭐⭐ =====
            Tool(
                name="get_coding_rules",
                description="【优先级 ⭐⭐⭐】获取 Delphi 编码规则 — AI 写/改 Delphi 代码前必须先调用\n"
                            "【触发词】编码规则、编码规范、代码风格、命名规范、规则、coding rules\n"
                            "【Delphi 文件触发】\n"
                            "  ⚠️ 看到 .pas .dfm .dproj .dpk .dpr .inc .res 等 Delphi 文件时，必须先调用此工具\n"
                            "  ⚠️ 在写/修改任何 Delphi 代码前，必须先 get_coding_rules 了解编码规范\n"
                            "【section 参数】按需获取各章节（节省 token）：\n"
                            '  section="workflow"    — 工作流总览（先看这个了解整体流程）\n'
                            '  section="writing"     — 写 Delphi 代码时的命名/格式/泛型规则\n'
                            '  section="review"      — 编译后审查代码（含完整审核表）\n'
                            '  section="safety"      — 安全敏感操作规则\n'
                            '  section="agent_rules" — Agent 操作硬规则\n'
                            "不传 section=返回工作流总览+章节索引（推荐首次调用）\n"
                            "【协作链】任何 .pas/.dproj 操作前→get_coding_rules(section='workflow') 了解流程",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "project_path": {"type": "string", "description": "项目路径（可选），用于查找项目自定义的编码规则文件(CODING_RULES.mdc)"},
                        "section": {"type": "string", "description": "章节名称（可选），如 workflow/writing/review/safety/agent_rules/kb_search/format/compile/cleanup/kb_build。不传则返回工作流总览+章节索引"},
                    }
                }
            ),

            # ===== 代码托管平台统一工具 =====
            Tool(
                name="code_hosting",
                description="【代码托管平台】统一操作 Gitea / GitHub / GitLab + Git 本地操作\n"
                            "通过 platform 切换后端(gitea/github/gitlab)，action 选择操作。\n"
                            "\n"
                            "▶ 平台 API 操作:\n"
                            '  code_hosting(platform="gitea", action="create_issue", ...)\n'
                            '  code_hosting(platform="github", action="create_issue", ...)\n'
                            "\n"
                            "▶ Git 本地操作（无需 platform）:\n"
                            '  code_hosting(action="git_clone", repo_url="...", mirror="镜像源")\n'
                            '  code_hosting(action="git_commit", work_dir=".", commit_message="...")\n'
                            "\n"
                            "▶ GitHub 国内访问:\n"
                            "  拉取: git_clone 支持 mirror 参数指定镜像源\n"
                            "  推送: 依赖用户自身的 SSH/HTTPS 代理配置，工具不做假设\n"
                            "\n"
                            "▶ action 列表:\n"
                            "  create_token | init_labels | create_issue | close_issue\n"
                            "  add_comment | list_issues\n"
                            "  --- 同步操作 ---\n"
                            "  git_status | git_add | git_commit\n"
                            "  --- 异步操作（后台执行，返回 task_id） ---\n"
                            "  git_clone | git_push | git_push_retry\n"
                            "  --- 查询异步任务状态 ---\n"
                            '  async_task(action="status", task_id="...")',
                inputSchema={
                    "type": "object",
                    "properties": {
                        "platform": {"type": "string", "enum": ["gitea", "github", "gitlab"], "description": "平台类型（API 操作需要，Git 本地操作不需要）"},
                        "action": {"type": "string", "description": "操作类型: create_token, init_labels, create_issue, close_issue, add_comment, list_issues, git_clone, git_add, git_commit, git_push, git_push_retry, git_status"},
                        "base_url": {"type": "string", "description": "平台实例地址，如 https://code.qdac.cc:3000 (API 操作需要)"},
                        "token": {"type": "string", "description": "API 访问令牌 (API 操作需要)"},
                        "repo": {"type": "string", "description": "仓库名，格式 owner/repo (API 操作需要)"},
                        "issue_number": {"type": "integer", "description": "工单编号 (close_issue/add_comment 需要)"},
                        "title": {"type": "string", "description": "工单标题 (create_issue 需要)"},
                        "body": {"type": "string", "description": "正文内容，支持 Markdown (create_issue/add_comment 需要)"},
                        "label_names": {"type": "array", "items": {"type": "string"}, "description": "标签名称列表 (create_issue 可选)"},
                        "comment_body": {"type": "string", "description": "关闭工单时的说明 (close_issue 可选)"},
                        "state": {"type": "string", "enum": ["open", "closed", "all"], "description": "工单过滤状态 (list_issues 可选，默认 open)"},
                        "username": {"type": "string", "description": "用户名 (create_token 需要)"},
                        "password": {"type": "string", "description": "密码 (create_token 需要)"},
                        "token_name": {"type": "string", "description": "Token 名称 (create_token 可选，默认 delphi-mcp)"},
                        # Git 操作参数
                        "work_dir": {"type": "string", "description": "Git 仓库本地路径 (git_* 操作需要)"},
                        "repo_url": {"type": "string", "description": "远程仓库 URL (git_clone 需要)"},
                        "mirror": {"type": "string", "description": "GitHub 镜像源地址，如 https://hub.fastgit.xyz (git_clone 可选)"},
                        "branch": {"type": "string", "description": "分支名 (git_clone/git_push 可选)"},
                        "commit_message": {"type": "string", "description": "提交信息 (git_commit 需要)"},
                        "files": {"type": "array", "items": {"type": "string"}, "description": "要 add 的文件列表 (git_add 需要)"},
                        "remote_name": {"type": "string", "description": "远程名称 (git_push/git_push_retry 可选，默认 origin)"},
                        "retry_interval": {"type": "integer", "description": "重试间隔秒数 (git_push_retry 可选，默认 300)"},
                        "task_id": {"type": "string", "description": "异步任务ID (配合 async_task 工具查询)"},
                    },
                    "required": ["action"]
                }
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict):
        """调用工具"""
        logger.info(f"调用工具: {name}")
        result = None
        
        try:
            if name == "compile_project":
                # 合并 compile_file, get_compiler_args
                proj_path = arguments.get("project_path", "")
                if proj_path.lower().endswith('.pas'):
                    # 文件模式：检查语法
                    result = await compile_file(
                        file_path=proj_path,
                        unit_search_paths=arguments.get('unit_search_paths'),
                        warning_level=arguments.get('warning_level', 2),
                        disabled_warnings=arguments.get('disabled_warnings'),
                        compiler_version=arguments.get('compiler_version'),
                    )
                elif arguments.get("get_args_only"):
                    # 仅获取参数 — 过滤出 get_compiler_args 接受的参数
                    _ACCEPTED_GET_ARGS_KEYS = {
                        "project_path", "target_platform", "output_path", "compiler_version",
                        "conditional_defines", "unit_search_paths", "resource_search_paths",
                        "optimization_enabled", "debug_info_enabled", "warning_level",
                        "disabled_warnings", "output_type", "runtime_library", "build_configuration",
                    }
                    filtered = {k: v for k, v in arguments.items() if k in _ACCEPTED_GET_ARGS_KEYS}
                    result = await get_compiler_args(**filtered)
                else:
                    # 项目模式：编译
                    result = await compile_project(**arguments)
            
            elif name == "delphi_kb":
                action = arguments.get("action", "search")
                kb_type = arguments.get("kb_type", "all")
                
                if action == "search":
                    if kb_type == "document":
                        result = await doc_tools.search_documents(arguments)
                    else:
                        result = await kb_tools.search_knowledge(arguments)
                elif action == "stats":
                    if kb_type == "document":
                        result = await doc_tools.get_document_statistics(arguments)
                    else:
                        result = await kb_tools.get_unified_knowledge_stats(arguments)
                elif action == "build":
                    # action=build 需要数分钟到数十分钟，自动使用异步任务方式
                    from src.tools.async_tasks import start_async_task
                    async_mode = arguments.get("async_mode", True)
                    if async_mode:
                        # 异步模式：启动后台任务并立即返回 task_id，让 AI 轮询进度
                        version = arguments.get("version")
                        force_rebuild = arguments.get("force_rebuild", False)
                        
                        # 根据 kb_type 决定任务类型
                        if kb_type in ["all", "delphi"]:
                            task_type = "build_knowledge_base"
                        elif kb_type == "thirdparty":
                            task_type = "build_thirdparty_knowledge_base"
                        elif kb_type == "project":
                            task_type = "init_project_knowledge_base"
                        elif kb_type == "document":
                            # 文档知识库构建
                            task_type = "build_document_knowledge_base"
                        else:
                            task_type = "build_knowledge_base"
                        
                        incremental = arguments.get("incremental", False)
                        
                        # 根据任务类型准备参数
                        if task_type == "build_document_knowledge_base":
                            directory = arguments.get("directory")
                            if not directory:
                                detected = _auto_detect_delphi_help_dir()
                                if detected:
                                    directory = detected
                                    logger.info(f"自动检测到 Delphi 帮助目录: {directory}")
                                else:
                                    logger.warning("未提供 directory 且未检测到 Delphi 帮助目录")
                            task_params = {
                                "urls": arguments.get("urls", []),
                                "directory": directory,
                                "extensions": arguments.get("extensions", [".chm"]),
                                "start_url": arguments.get("start_url"),
                                "max_pages": arguments.get("max_pages", 100),
                                "max_depth": arguments.get("max_depth", 3),
                                "domain_filter": arguments.get("domain_filter"),
                                "url_pattern": arguments.get("url_pattern"),
                                "exclude_dirs": arguments.get("exclude_dirs"),
                                "force_rebuild": arguments.get("force_rebuild", False)
                            }
                        elif task_type == "init_project_knowledge_base":
                            from src.tools.knowledge_base import _resolve_project_path
                            resolved_path = _resolve_project_path(arguments.get("project_path"))
                            task_params = {
                                "project_path": resolved_path,
                                "version": version,
                                "force_rebuild": force_rebuild,
                                "build_thirdparty": arguments.get("build_thirdparty", True),
                                "build_project": arguments.get("build_project", True),
                            }
                        else:
                            task_params = {
                                "version": version,
                                "force_rebuild": force_rebuild,
                                "incremental": incremental
                            }
                        
                        task_result = await start_async_task({
                            "task_type": task_type,
                            "task_params": task_params,
                            "show_progress": arguments.get("show_progress", True)
                        })
                        result = task_result
                    else:
                        # 同步模式（非推荐）
                        result = await kb_tools.build_unified_knowledge_base(arguments)
                elif action == "build_embedding":
                    # 构建 embedding 向量（异步，避免模型加载超时）
                    from src.tools.knowledge_base import _resolve_project_path
                    pp = _resolve_project_path(arguments.get("project_path"))
                    if not pp:
                        result = {"error": "未检测到项目路径"}
                    else:
                        from src.tools.async_tasks import start_async_task
                        task_result = await start_async_task({
                            "task_type": "build_embedding",
                            "task_params": {"project_path": pp},
                            "show_progress": True
                        })
                        result = task_result
                elif action == "scan":
                    if kb_type == "document":
                        result = await doc_tools.scan_documents(arguments)
                    else:
                        result = {"error": f"action=scan 仅支持 kb_type=document"}
                elif action == "web":
                    if kb_type == "document":
                        result = await doc_tools.add_web_document(arguments)
                    else:
                        result = {"error": f"action=web 仅支持 kb_type=document"}
                elif action == "read":
                    url = arguments.get("url")
                    doc_id = arguments.get("doc_id")
                    file_path = arguments.get("file_path")
                    
                    if url or doc_id:
                        result = await doc_tools.read_document(arguments)
                    elif file_path:
                        result = await read_source_file(arguments)
                    else:
                        result = {"error": "action=read 需要 url/doc_id 或 file_path 参数"}
                else:
                    result = {"error": f"未知action: {action}"}
            
            elif name == "file_tool":
                result = await file_tool.handle_file_tool(arguments)
            
            elif name == "check_environment":
                # 合并 search_compilers, install_pasfmt, install_pasfmt_rad
                action = arguments.get("action", "check")
                if action == "detect":
                    result = await search_compilers(search_path=arguments.get("search_path"))
                elif action == "check":
                    result = await check_environment()
                elif action == "install":
                    result = await pasfmt.download_and_install_pasfmt(install_dir=arguments.get("install_dir"))
                elif action == "format_install":
                    result = await pasfmt.download_and_install_pasfmt_rad(
                        delphi_version=arguments.get("delphi_version", "11"),
                        install_dir=arguments.get("install_dir"),
                    )
                else:
                    result = {"error": f"未知action: {action}"}
            
            elif name == "async_task":
                # 合并 start_async_task, get_task_status, get_task_result, list_tasks, cancel_task
                action = arguments.get("action", "list")
                if action == "start":
                    result = await async_tools.start_async_task(arguments)
                elif action == "status":
                    result = await async_tools.get_task_status(arguments)
                elif action == "result":
                    result = await async_tools.get_task_result(arguments)
                elif action == "list":
                    result = await async_tools.list_tasks(arguments)
                elif action == "cancel":
                    result = await async_tools.cancel_task(arguments)
                else:
                    result = {"error": f"未知action: {action}"}
            
            elif name == "install_package":
                result = await install_package(
                    package_path=arguments.get("package_path", ""),
                    target_platform=arguments.get("target_platform", "win32"),
                    build_configuration=arguments.get("build_configuration", "Debug"),
                    timeout=arguments.get("timeout", 300),
                    install=arguments.get("install", True)
                )
            
            elif name == "list_installed_packages":
                result = await list_installed_packages()
            
            elif name == "get_coding_rules":
                from src.tools.coding_rules import get_coding_rules
                result = await get_coding_rules(
                    project_path=arguments.get("project_path"),
                    section=arguments.get("section")
                )

            elif name == "code_hosting":
                result = code_hosting(**arguments)

            else:
                raise ValueError(f"未知工具: {name}")

            # ============================================================
            # P2: 智能提示 — 在工具返回结果中注入下一步建议
            # ============================================================
            hint = _get_smart_hint(name, result, arguments)
            if hint:
                if isinstance(result, CallToolResult):
                    if result.content and hasattr(result.content[0], 'text'):
                        original_text = result.content[0].text
                        result.content[0].text = original_text + "\n\n" + hint
                elif isinstance(result, dict):
                    msg = result.get('message', '')
                    if isinstance(msg, str):
                        result['message'] = msg + "\n\n" + hint

            # ============================================================
            # P3: API 调用日志 (受 log_api_calls 开关控制)
            # ============================================================
            log_api_call(logger, name, arguments, result)

            # 统一返回格式：确保返回 CallToolResult
            if isinstance(result, dict):
                text = str(result.get('message', str(result)))
                is_error = (
                    result.get('status') == 'failed'
                    or result.get('success') is False
                    or 'error' in result
                )
                return CallToolResult(content=[{"type": "text", "text": text}], isError=is_error)
            else:
                return result

        except Exception as e:
            # 异常也记录到 API 日志
            log_api_call(logger, name, arguments, {"error": str(e)})
            logger.error(f"工具调用失败: {str(e)}", exc_info=True)
            return CallToolResult(
                content=[{"type": "text", "text": f"错误: {str(e)}"}],
                isError=True
            )

    # 注册 MCP 资源
    _resources_dir = project_root / "config"

    @server.list_resources()
    async def list_resources():
        """列出可用资源"""
        from mcp.types import Resource
        resources = []
        coding_rules_path = _resources_dir / "CODING_RULES.mdc"
        if coding_rules_path.exists():
            resources.append(Resource(
                uri="delphi://coding-rules",
                name="CODING_RULES",
                title="Delphi 编码规范",
                description="Delphi 源码编码规则，包含命名规范、格式化、类型声明顺序、修改/审核代码规则等",
                mimeType="text/markdown"
            ))
        return resources

    @server.read_resource()
    async def read_resource(uri: str):
        """读取资源内容"""
        from mcp.types import ReadResourceResult, TextResourceContents
        from pydantic import AnyUrl

        if uri == "delphi://coding-rules":
            rules_path = _resources_dir / "CODING_RULES.mdc"
            if rules_path.exists():
                with open(rules_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                return ReadResourceResult(
                    contents=[TextResourceContents(
                        uri=AnyUrl(uri),
                        mimeType="text/markdown",
                        text=content
                    )]
                )
            return ReadResourceResult(
                contents=[TextResourceContents(
                    uri=AnyUrl(uri),
                    text="编码规则文件不存在"
                )]
            )
        raise ValueError(f"未知资源: {uri}")

    # 启动服务器
    logger.info("MCP Server 启动完成,准备接收请求...")
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


def _cleanup_resources():
    """清理资源：关闭后台任务、DB连接等"""
    logger.info("清理资源中...")
    try:
        from src.tools.knowledge_base import _cleanup_pkb_cache
        _cleanup_pkb_cache()
    except Exception:
        logger.warning("清理资源时发生异常", exc_info=True)
    logger.info("资源清理完成")


def main():
    """主函数"""
    try:
        asyncio.run(run_server())
    except KeyboardInterrupt:
        logger.info("服务器已停止")
    except Exception as e:
        logger.error(f"服务器运行失败: {str(e)}", exc_info=True)
        sys.exit(1)
    finally:
        _cleanup_resources()


if __name__ == "__main__":
    main()
