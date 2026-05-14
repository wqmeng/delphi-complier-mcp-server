#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 Delphi 知识库集成

测试 MCP Server 中的知识库功能
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.services.knowledge_base import DelphiKnowledgeBaseService


def test_delphi_versions():
    """测试检测 Delphi 版本"""
    print("=" * 60)
    print("测试 1: 检测 Delphi 版本")
    print("=" * 60)

    kb_service = DelphiKnowledgeBaseService()

    versions = kb_service.detect_delphi_versions()
    print(f"\n检测到 {len(versions)} 个 Delphi 版本:")

    for i, version in enumerate(versions, 1):
        print(f"\n{i}. {version['name']} ({version['version']})")
        print(f"   根目录: {version['root_dir']}")
        print(f"   源码目录: {version['source_dir']}")

    assert len(versions) > 0, "未检测到已安装的 Delphi 版本"


def test_build_knowledge_base():
    """测试构建知识库"""
    print("\n" + "=" * 60)
    print("测试 2: 构建知识库")
    print("=" * 60)

    kb_service = DelphiKnowledgeBaseService()

    # 检查是否已有知识库
    stats = kb_service.get_statistics()
    if stats:
        print(f"\n知识库已存在:")
        print(f"- 类数量: {stats.get('classes', 0)}")
        print(f"- 函数数量: {stats.get('functions', 0)}")
        print(f"- 文件数量: {stats.get('files', 0)}")

        print("\n跳过构建 (使用现有知识库)")
    else:
        # 构建知识库
        print("\n开始构建知识库...")
        success = kb_service.build_knowledge_base(force_rebuild=True)
        assert success, "知识库构建失败"
        stats = kb_service.get_statistics()

    print(f"\n知识库就绪:")
    print(f"- 类数量: {stats.get('classes', 0)}")
    print(f"- 函数数量: {stats.get('functions', 0)}")
    print(f"- 文件数量: {stats.get('files', 0)}")


def test_search_class():
    """测试搜索类"""
    print("\n" + "=" * 60)
    print("测试 3: 搜索类")
    print("=" * 60)

    kb_service = DelphiKnowledgeBaseService()

    # 检查知识库是否存在
    stats = kb_service.get_statistics()
    if not stats:
        print("\n知识库不存在,请先构建知识库")
        return

    # 搜索类
    class_name = "TButton"
    print(f"\n搜索类: {class_name}")

    results = kb_service.search_by_name(class_name)
    results = [r for r in results if r.get('kind_code', '') == 'TC']

    assert results, f"未找到类 '{class_name}'"
    print(f"\n找到 {len(results)} 个类 '{class_name}':")
    for i, result in enumerate(results[:3], 1):
        file_info = result.get('file', {})
        if 'class' in result:
            class_info = result['class']
        else:
            class_info = {'name': result.get('name', class_name), 'base_class': result.get('parent', ''), 'line': result.get('line', '')}
        
        print(f"\n{i}. 文件: {file_info.get('path', 'unknown')}")
        print(f"   类名: {class_info.get('name', class_name)}")
        print(f"   基类: {class_info.get('base_class', '')}")
        print(f"   行号: {class_info.get('line', '')}")


def test_semantic_search():
    """测试语义搜索"""
    print("\n" + "=" * 60)
    print("测试 4: 语义搜索")
    print("=" * 60)

    kb_service = DelphiKnowledgeBaseService()

    # 检查知识库是否存在
    stats = kb_service.get_statistics()
    if not stats:
        print("\n知识库不存在,请先构建知识库")
        return

    # 语义搜索（使用单次查询，RTL KB 走反转索引降级）
    query = "button"
    print(f"\n语义搜索: '{query}'")

    class_results = kb_service.semantic_search_classes(query, top_k=5)
    function_results = kb_service.semantic_search_functions(query, top_k=5)

    assert class_results or function_results, f"未找到与 '{query}' 相关的内容"
    print(f"\n找到相关内容:")

    if class_results:
        print(f"\n相关的类:")
        for class_name, score in class_results[:5]:
            print(f"  - {class_name} (相似度: {score:.3f})")

    if function_results:
        print(f"\n相关的函数:")
        for func_name, score in function_results[:5]:
            print(f"  - {func_name} (相似度: {score:.3f})")


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("Delphi 知识库集成测试")
    print("=" * 60)

    tests = [
        ("检测 Delphi 版本", test_delphi_versions),
        ("构建知识库", test_build_knowledge_base),
        ("搜索类", test_search_class),
        ("语义搜索", test_semantic_search),
    ]

    results = []

    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n测试失败: {e}")
            results.append((test_name, False))

    # 打印测试结果
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)

    for test_name, result in results:
        status = "[通过]" if result else "[失败]"
        print(f"{test_name}: {status}")

    # 统计
    passed = sum(1 for _, result in results if result)
    total = len(results)
    print(f"\n总计: {passed}/{total} 测试通过")

    if passed == total:
        print("\n所有测试通过!")
    else:
        print(f"\n{total - passed} 个测试失败")


if __name__ == "__main__":
    main()
