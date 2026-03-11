"""
Delphi 帮助文档知识库 MCP 工具

版权所有 (C) 吉林省左右软件开发有限公司
Copyright (C) Equilibrium Software Development Co., Ltd, Jilin

提供帮助文档知识库查询和管理的 MCP 工具
"""

from typing import Any
from mcp.types import CallToolResult

from ..services.knowledge_base.help_knowledge_base import DelphiHelpKnowledgeBase
from ..utils.logger import get_logger

logger = get_logger(__name__)

# 全局帮助文档知识库实例
_help_kb = None


def get_help_knowledge_base() -> DelphiHelpKnowledgeBase:
    """获取帮助文档知识库实例"""
    global _help_kb
    if _help_kb is None:
        _help_kb = DelphiHelpKnowledgeBase()
    return _help_kb


async def build_help_knowledge_base(arguments: Any) -> CallToolResult:
    """
    构建 Delphi 帮助文档知识库

    Args:
        arguments: 包含以下参数:
            - force_rebuild: 是否强制重建 (可选,默认 false)

    Returns:
        构建结果
    """
    force_rebuild = arguments.get("force_rebuild", False)

    try:
        help_kb = get_help_knowledge_base()

        logger.info("构建帮助文档知识库...")
        success = help_kb.build_knowledge_base(force_rebuild=force_rebuild)

        if success:
            stats = help_kb.get_statistics()
            return CallToolResult(
                content=[{
                    "type": "text",
                    "text": f"帮助文档知识库构建成功!\n\n"
                            f"统计信息:\n"
                            f"- 文档数量: {stats.get('total_documents', 0)}\n"
                            f"- 数据库大小: {stats.get('database_size_mb', 0):.2f} MB"
                }]
            )
        else:
            return CallToolResult(
                content=[{"type": "text", "text": "帮助文档知识库构建失败"}],
                isError=True
            )

    except Exception as e:
        logger.error(f"构建帮助文档知识库失败: {e}", exc_info=True)
        return CallToolResult(
            content=[{"type": "text", "text": f"构建帮助文档知识库时出错: {str(e)}"}],
            isError=True
        )


async def search_help(arguments: Any) -> CallToolResult:
    """
    搜索 Delphi 帮助文档

    Args:
        arguments: 包含以下参数:
            - query: 搜索查询 (必需)
            - top_k: 返回结果数量 (可选,默认 10)

    Returns:
        搜索结果
    """
    query = arguments.get("query")
    if not query:
        return CallToolResult(
            content=[{"type": "text", "text": "请提供搜索查询"}],
            isError=True
        )

    top_k = arguments.get("top_k", 10)

    try:
        help_kb = get_help_knowledge_base()
        results = help_kb.search(query, top_k=top_k)

        if not results:
            return CallToolResult(
                content=[{"type": "text", "text": f"未找到与 '{query}' 相关的帮助文档"}]
            )

        # 格式化结果
        output = f"帮助文档搜索 '{query}' 的结果:\n\n"
        for i, result in enumerate(results, 1):
            output += f"{i}. [{result['type']}] {result['name']} (相似度: {result['score']:.3f})\n"

        return CallToolResult(content=[{"type": "text", "text": output}])

    except Exception as e:
        logger.error(f"搜索帮助文档失败: {e}", exc_info=True)
        return CallToolResult(
            content=[{"type": "text", "text": f"搜索帮助文档时出错: {str(e)}"}],
            isError=True
        )


async def get_help_kb_stats(arguments: Any) -> CallToolResult:
    """
    获取帮助文档知识库统计信息

    Args:
        arguments: 无参数

    Returns:
        统计信息
    """
    try:
        help_kb = get_help_knowledge_base()
        stats = help_kb.get_statistics()

        output = "Delphi 帮助文档知识库统计信息:\n\n"
        output += f"- 文档数量: {stats.get('total_documents', 0)}\n"
        output += f"- 数据库大小: {stats.get('database_size_mb', 0):.2f} MB\n"
        output += f"\n知识库位置: {help_kb.kb_dir}"

        return CallToolResult(content=[{"type": "text", "text": output}])

    except Exception as e:
        logger.error(f"获取统计信息失败: {e}", exc_info=True)
        return CallToolResult(
            content=[{"type": "text", "text": f"获取统计信息时出错: {str(e)}"}],
            isError=True
        )
