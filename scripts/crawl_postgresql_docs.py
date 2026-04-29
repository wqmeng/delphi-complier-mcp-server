#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动爬取 PostgreSQL 完整文档
从主页发现所有链接并递归抓取
"""

import sys
import time
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse
from collections import deque

project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.services.knowledge_base.scan_generic_documents import (
    GenericDocumentScanner,
    WebDocumentProcessor
)


def extract_links(html_content, base_url, domain_filter=None):
    """从 HTML 中提取链接"""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return []
    
    soup = BeautifulSoup(html_content, 'html.parser')
    links = []
    
    for tag in soup.find_all('a', href=True):
        href = tag['href']
        
        # 转换为绝对 URL
        full_url = urljoin(base_url, href)
        
        # 解析 URL
        parsed = urlparse(full_url)
        
        # 过滤
        if domain_filter and parsed.netloc != domain_filter:
            continue
        
        # 忽略锚点
        if '#' in full_url:
            full_url = full_url.split('#')[0]
        
        # 忽略非 HTML
        if any(ext in full_url.lower() for ext in ['.pdf', '.zip', '.png', '.jpg', '.gif']):
            continue
        
        # 只要 .html 页面
        if not full_url.endswith('.html'):
            continue
        
        links.append(full_url)
    
    return list(set(links))


def crawl_postgresql_docs(max_pages=100, max_depth=3):
    """爬取 PostgreSQL 文档"""
    print("=" * 60)
    print("自动爬取 PostgreSQL 完整文档")
    print("=" * 60)
    
    server_root = Path(__file__).parent.parent.parent
    kb_dir = str(server_root / "data" / "document-knowledge-base")
    Path(kb_dir).mkdir(parents=True, exist_ok=True)
    
    scanner = GenericDocumentScanner(kb_dir)
    processor = WebDocumentProcessor()
    
    # 起始 URL
    base_url = "https://www.postgresql.org/docs/current/"
    start_urls = [
        "https://www.postgresql.org/docs/current/index.html",
    ]
    
    # 已访问和待访问
    visited = set()
    queue = deque([(url, 0) for url in start_urls])
    
    # 统计
    stats = {
        'success': 0,
        'failed': 0,
        'skipped': 0,
        'total_size': 0,
    }
    
    start_time = time.time()
    
    print(f"\n最大页面数: {max_pages}")
    print(f"最大深度: {max_depth}")
    print(f"起始 URL: {start_urls[0]}")
    print()
    
    while queue and stats['success'] < max_pages:
        url, depth = queue.popleft()
        
        # 检查是否已访问
        if url in visited:
            continue
        
        # 检查深度
        if depth > max_depth:
            continue
        
        # 检查是否为 PostgreSQL 文档
        if '/docs/' not in url:
            continue
        
        visited.add(url)
        
        # 处理当前页面
        print(f"[{stats['success']+1}/{max_pages}] 深度 {depth}: {url[:70]}...")
        
        result = processor.process_url(url, timeout=30)
        
        if result:
            # 添加到知识库
            scanner.add_web_document(url)
            
            stats['success'] += 1
            stats['total_size'] += result.get('size', 0)
            
            # 提取新链接 - 需要原始 HTML
            if depth < max_depth:
                try:
                    import requests
                    resp = requests.get(url, timeout=20)
                    html_content = resp.text
                    new_links = extract_links(html_content, url, domain_filter='www.postgresql.org')
                    
                    new_count = 0
                    for link in new_links:
                        if link not in visited and '/docs/current/' in link:
                            queue.append((link, depth + 1))
                            new_count += 1
                    
                    if new_count > 0:
                        print(f"  ✓ 发现 {new_count} 个新链接 (队列: {len(queue)})")
                except Exception as e:
                    print(f"  ! 提取链接失败: {e}")
        else:
            stats['failed'] += 1
            print(f"  ✗ 失败")
    
    elapsed = time.time() - start_time
    
    print(f"\n" + "=" * 60)
    print("爬取完成")
    print("=" * 60)
    print(f"成功: {stats['success']}")
    print(f"失败: {stats['failed']}")
    print(f"总大小: {stats['total_size'] / 1024:.1f} KB")
    print(f"耗时: {elapsed:.1f} 秒")
    if stats['success'] > 0:
        print(f"平均速度: {elapsed/stats['success']:.2f} 秒/页面")
    
    # 知识库统计
    kb_stats = scanner.get_statistics()
    print(f"\n知识库总文档数: {kb_stats['total_documents']}")
    
    return stats['success']


def interactive_crawl():
    """交互式爬取"""
    print("PostgreSQL 文档爬虫")
    print("=" * 60)
    
    # 选择模式
    print("\n爬取模式:")
    print("1. 快速模式 (100 页面, 深度 2)")
    print("2. 标准模式 (300 页面, 深度 3)")
    print("3. 完整模式 (500 页面, 深度 4)")
    
    try:
        choice = input("\n请选择 (1-3, 默认 1): ").strip()
    except:
        choice = "1"
    
    configs = {
        '1': (100, 2),
        '2': (300, 3),
        '3': (500, 4),
    }
    
    max_pages, max_depth = configs.get(choice, (100, 2))
    
    crawl_postgresql_docs(max_pages=max_pages, max_depth=max_depth)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="爬取 PostgreSQL 完整文档")
    parser.add_argument("--max-pages", type=int, default=100, help="最大页面数")
    parser.add_argument("--max-depth", type=int, default=3, help="最大深度")
    parser.add_argument("--interactive", action="store_true", help="交互模式")
    
    args = parser.parse_args()
    
    if args.interactive:
        interactive_crawl()
    else:
        crawl_postgresql_docs(max_pages=args.max_pages, max_depth=args.max_depth)
