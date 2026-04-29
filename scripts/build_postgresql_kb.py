#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
建立 PostgreSQL 在线帮助知识库
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.services.knowledge_base.scan_generic_documents import (
    GenericDocumentScanner,
    WebDocumentProcessor
)


def test_postgresql_page():
    """测试抓取 PostgreSQL 文档主页"""
    print("=" * 60)
    print("测试抓取 PostgreSQL 文档主页")
    print("=" * 60)
    
    url = "https://www.postgresql.org/docs/current/index.html"
    
    processor = WebDocumentProcessor()
    
    print(f"\n抓取: {url}")
    result = processor.process_url(url, timeout=30)
    
    if result:
        print(f"\n✓ 抓取成功")
        print(f"标题: {result['title']}")
        print(f"内容类型: {result['content_type']}")
        print(f"大小: {result['size']} 字节")
        print(f"行数: {result['line_count']}")
        print(f"章节数: {len(result.get('sections', []))}")
        print(f"代码块数: {len(result.get('code_examples', []))}")
        
        print(f"\n章节列表:")
        for i, section in enumerate(result.get('sections', [])[:10], 1):
            print(f"  {i}. {'  ' * (section['level']-1)}{section['title']}")
        
        if len(result.get('sections', [])) > 10:
            print(f"  ... 还有 {len(result['sections']) - 10} 个章节")
        
        return True
    else:
        print(f"\n✗ 抓取失败")
        return False


def build_postgresql_kb():
    """建立 PostgreSQL 文档知识库"""
    print("\n" + "=" * 60)
    print("建立 PostgreSQL 文档知识库")
    print("=" * 60)
    
    import time
    start_time = time.time()
    
    server_root = Path(__file__).parent.parent.parent
    kb_dir = str(server_root / "data" / "document-knowledge-base")
    
    # 确保目录存在
    Path(kb_dir).mkdir(parents=True, exist_ok=True)
    
    scanner = GenericDocumentScanner(kb_dir)
    
    urls = [
        # 主要文档
        "https://www.postgresql.org/docs/current/index.html",
        "https://www.postgresql.org/docs/current/tutorial.html",
        "https://www.postgresql.org/docs/current/sql.html",
        "https://www.postgresql.org/docs/current/functions.html",
        # SQL 命令
        "https://www.postgresql.org/docs/current/sql-commands.html",
        "https://www.postgresql.org/docs/current/sql-select.html",
        "https://www.postgresql.org/docs/current/sql-insert.html",
        "https://www.postgresql.org/docs/current/sql-update.html",
        "https://www.postgresql.org/docs/current/sql-delete.html",
        "https://www.postgresql.org/docs/current/sql-createtable.html",
        "https://www.postgresql.org/docs/current/sql-altertable.html",
        "https://www.postgresql.org/docs/current/sql-droptable.html",
        "https://www.postgresql.org/docs/current/sql-createindex.html",
        "https://www.postgresql.org/docs/current/sql-createview.html",
        # 数据类型
        "https://www.postgresql.org/docs/current/datatype.html",
        "https://www.postgresql.org/docs/current/datatype-numeric.html",
        "https://www.postgresql.org/docs/current/datatype-character.html",
        "https://www.postgresql.org/docs/current/datatype-datetime.html",
        # 索引
        "https://www.postgresql.org/docs/current/indexes.html",
        "https://www.postgresql.org/docs/current/indexes-types.html",
        # 查询
        "https://www.postgresql.org/docs/current/queries.html",
        "https://www.postgresql.org/docs/current/queries-table-expressions.html",
        # 高级功能
        "https://www.postgresql.org/docs/current/functions-string.html",
        "https://www.postgresql.org/docs/current/functions-math.html",
        "https://www.postgresql.org/docs/current/functions-datetime.html",
        "https://www.postgresql.org/docs/current/functions-aggregate.html",
        # 事务
        "https://www.postgresql.org/docs/current/transaction-iso.html",
        # 性能
        "https://www.postgresql.org/docs/current/performance-tips.html",
        # 管理
        "https://www.postgresql.org/docs/current/runtime-config.html",
        "https://www.postgresql.org/docs/current/maintenance.html",
    ]
    
    print(f"\n添加 {len(urls)} 个 PostgreSQL 文档页面...")
    
    success = 0
    failed = 0
    
    for url in urls:
        print(f"\n处理: {url}")
        result = scanner.add_web_document(url)
        
        if result and not (isinstance(result, dict) and 'error' in result):
            print(f"  ✓ 标题: {result.get('title', 'N/A')}")
            print(f"  ✓ 大小: {result.get('size', 0)} 字节")
            success += 1
        else:
            error = result.get('error', 'Unknown') if isinstance(result, dict) else 'Unknown'
            print(f"  ✗ 失败: {error}")
            failed += 1
    
    print(f"\n" + "=" * 60)
    print("统计")
    print("=" * 60)
    print(f"成功: {success}")
    print(f"失败: {failed}")
    
    elapsed_time = time.time() - start_time
    print(f"耗时: {elapsed_time:.2f} 秒")
    if success > 0:
        print(f"平均速度: {elapsed_time/success:.2f} 秒/页面")
    
    stats = scanner.get_statistics()
    print(f"\n知识库总文档数: {stats['total_documents']}")
    
    if stats.get('by_type'):
        print(f"\n按类型统计:")
        for content_type, count in stats['by_type'].items():
            print(f"  {content_type}: {count}")
    
    return success > 0


def search_postgresql():
    """搜索 PostgreSQL 文档"""
    print("\n" + "=" * 60)
    print("搜索 PostgreSQL 文档")
    print("=" * 60)
    
    server_root = Path(__file__).parent.parent.parent
    kb_dir = str(server_root / "data" / "document-knowledge-base")
    
    scanner = GenericDocumentScanner(kb_dir)
    
    queries = ["PostgreSQL", "SELECT", "CREATE TABLE"]
    
    for query in queries:
        print(f"\n搜索: '{query}'")
        results = scanner.search(query, top_k=3)
        
        if results:
            print(f"找到 {len(results)} 个结果:")
            for i, doc in enumerate(results, 1):
                print(f"  {i}. {doc['title'][:50]}")
                print(f"     类型: {doc['content_type']}")
        else:
            print("  未找到结果")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="PostgreSQL 文档知识库")
    parser.add_argument("--test", action="store_true", help="测试抓取单个页面")
    parser.add_argument("--build", action="store_true", help="建立知识库")
    parser.add_argument("--search", action="store_true", help="搜索文档")
    
    args = parser.parse_args()
    
    if args.test:
        test_postgresql_page()
    elif args.build:
        build_postgresql_kb()
    elif args.search:
        search_postgresql()
    else:
        # 默认：全部执行
        if test_postgresql_page():
            build_postgresql_kb()
            search_postgresql()
