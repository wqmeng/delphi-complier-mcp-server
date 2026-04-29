"""
文档知识库辅助函数
用于 delphi_kb 工具的文档操作
"""

from typing import Any
from mcp.types import CallToolResult
from pathlib import Path

from ..services.knowledge_base.scan_generic_documents import (
    GenericDocumentScanner,
    WebDocumentProcessor
)


_doc_scanner = None


def _get_scanner() -> GenericDocumentScanner:
    """获取文档扫描器实例"""
    global _doc_scanner
    
    if _doc_scanner is None:
        server_root = Path(__file__).parent.parent.parent
        kb_dir = str(server_root / "data" / "document-knowledge-base")
        
        kb_path = Path(kb_dir)
        kb_path.mkdir(parents=True, exist_ok=True)
        
        _doc_scanner = GenericDocumentScanner(kb_dir)
    
    return _doc_scanner


async def scan_documents(arguments: Any) -> CallToolResult:
    """扫描目录中的文档"""
    directory = arguments.get("directory")
    extensions = arguments.get("extensions")
    max_workers = arguments.get("max_workers")
    
    if not directory:
        return CallToolResult(
            content=[{"type": "text", "text": "请提供 directory 参数"}],
            isError=True
        )
    
    dir_path = Path(directory)
    if not dir_path.exists():
        return CallToolResult(
            content=[{"type": "text", "text": f"目录不存在: {directory}"}],
            isError=True
        )
    
    scanner = _get_scanner()
    result = scanner.scan_directory(
        directory=directory,
        extensions=extensions,
        max_workers=max_workers
    )
    
    if 'error' in result:
        return CallToolResult(
            content=[{"type": "text", "text": f"扫描失败: {result['error']}"}],
            isError=True
        )
    
    output = f"文档扫描完成:\n"
    output += f"  总文件数: {result['total_files']}\n"
    output += f"  处理成功: {result['processed']}\n"
    output += f"  处理失败: {result['failed']}\n"
    
    stats = scanner.get_statistics()
    if stats.get('by_type'):
        output += f"\n按类型统计:\n"
        for content_type, count in stats['by_type'].items():
            output += f"  {content_type}: {count}\n"
    
    return CallToolResult(content=[{"type": "text", "text": output}])


async def add_web_document(arguments: Any) -> CallToolResult:
    """添加网页文档"""
    url = arguments.get("url")
    
    if not url:
        return CallToolResult(
            content=[{"type": "text", "text": "请提供 url 参数"}],
            isError=True
        )
    
    if not url.startswith(('http://', 'https://')):
        return CallToolResult(
            content=[{"type": "text", "text": "URL 必须以 http:// 或 https:// 开头"}],
            isError=True
        )
    
    scanner = _get_scanner()
    result = scanner.add_web_document(url)
    
    if result is None:
        return CallToolResult(
            content=[{"type": "text", "text": f"添加网页失败: {url}"}],
            isError=True
        )
    
    if isinstance(result, dict) and 'error' in result:
        return CallToolResult(
            content=[{"type": "text", "text": f"添加网页失败: {result['error']}"}],
            isError=True
        )
    
    output = f"网页添加成功:\n"
    output += f"  标题: {result.get('title', 'N/A')}\n"
    output += f"  URL: {url}\n"
    output += f"  大小: {result.get('size', 0)} 字节\n"
    output += f"  行数: {result.get('line_count', 0)}\n"
    output += f"  章节数: {len(result.get('sections', []))}\n"
    output += f"  代码块数: {len(result.get('code_examples', []))}\n"
    
    return CallToolResult(content=[{"type": "text", "text": output}])


async def search_documents(arguments: Any) -> CallToolResult:
    """搜索文档"""
    query = arguments.get("query")
    content_type = arguments.get("content_type")
    top_k = arguments.get("top_k", 10)
    
    if not query:
        return CallToolResult(
            content=[{"type": "text", "text": "请提供 query 参数"}],
            isError=True
        )
    
    scanner = _get_scanner()
    results = scanner.search(query, content_type=content_type, top_k=top_k)
    
    if not results:
        return CallToolResult(
            content=[{"type": "text", "text": f"未找到匹配 '{query}' 的文档"}]
        )
    
    output = f"搜索 '{query}'"
    if content_type:
        output += f" (类型: {content_type})"
    output += f" - 找到 {len(results)} 个结果:\n\n"
    
    for i, doc in enumerate(results, 1):
        output += f"{i}. {doc.get('title', 'N/A')}\n"
        output += f"   类型: {doc.get('content_type', 'N/A')}\n"
        
        if doc.get('url'):
            output += f"   URL: {doc.get('url')}\n"
        else:
            output += f"   路径: {doc.get('path', 'N/A')}\n"
        
        output += f"   大小: {doc.get('size', 0)} 字节\n"
        
        content = doc.get('content', '')
        if content:
            preview = content[:200].replace('\n', ' ')
            output += f"   预览: {preview}...\n"
        
        output += "\n"
    
    return CallToolResult(content=[{"type": "text", "text": output}])


async def get_document_statistics(arguments: Any) -> CallToolResult:
    """获取文档统计信息"""
    scanner = _get_scanner()
    stats = scanner.get_statistics()
    
    output = "文档知识库统计:\n"
    output += f"  总文档数: {stats.get('total_documents', 0)}\n\n"
    
    by_type = stats.get('by_type', {})
    if by_type:
        output += "按类型统计:\n"
        for content_type, count in by_type.items():
            output += f"  {content_type}: {count}\n"
    
    return CallToolResult(content=[{"type": "text", "text": output}])
