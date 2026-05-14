#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SQLiteVectorKnowledgeBase 测试

注意：SQLiteVectorKnowledgeBase 要求数据库已初始化 schema 才能构造，
因此测试先创建 schema 再实例化 KB，然后测试各方法。
"""

import sys
import sqlite3
import tempfile
import shutil
from pathlib import Path

import pytest

project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.services.knowledge_base.sqlite_vector_query_knowledge_base import (
    SQLiteVectorKnowledgeBase,
)


def _init_schema(db_path: Path):
    """初始化 SQLiteVectorKnowledgeBase 所需的数据库 schema（使用统一 schema 定义）"""
    from src.services.knowledge_base.schema import create_source_tables

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-64000")
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.execute("PRAGMA busy_timeout=10000")

    # 使用统一 schema 建表，确保与生产环境一致
    create_source_tables(conn.cursor())

    conn.execute("INSERT OR REPLACE INTO metadata (key, value, updated_at) VALUES (?, ?, ?)",
                 ('hash', 'test-hash', 0.0))
    conn.execute("INSERT OR REPLACE INTO metadata (key, value, updated_at) VALUES (?, ?, ?)",
                 ('total_files', '0', 0.0))
    conn.execute("INSERT OR REPLACE INTO metadata (key, value, updated_at) VALUES (?, ?, ?)",
                 ('schema_version', '1', 0.0))
    conn.commit()
    # 创建 index 目录（load_index 缓存路径需要）
    (db_path.parent / "index").mkdir(parents=True, exist_ok=True)
    conn.close()


def _make_kb(temp_dir: str) -> SQLiteVectorKnowledgeBase:
    """创建带预初始化 schema 的 KB 实例"""
    db_path = Path(temp_dir) / "test.db"
    _init_schema(db_path)
    return SQLiteVectorKnowledgeBase(temp_dir, db_file="test.db")


def test_init_custom_db_file():
    """使用自定义数据库文件名"""
    tmpdir = tempfile.mkdtemp()
    try:
        kb = _make_kb(tmpdir)
        assert Path(tmpdir, "test.db").exists()
        assert Path(tmpdir, "index").is_dir()
        kb.close()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_get_connection_returns_connection():
    """_get_connection 返回可用的 sqlite3.Connection"""
    tmpdir = tempfile.mkdtemp()
    try:
        kb = _make_kb(tmpdir)
        conn = kb._get_connection()
        assert conn is not None
        cur = conn.execute("SELECT 1")
        assert cur.fetchone()[0] == 1
        kb.close()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_close_releases_connection():
    """close 后 _get_connection 返回新连接"""
    tmpdir = tempfile.mkdtemp()
    try:
        kb = _make_kb(tmpdir)
        conn1 = kb._get_connection()
        kb.close()
        conn2 = kb._get_connection()
        assert conn2 is not None
        assert conn2 is not conn1
        kb.close()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    import pytest
    pytest.main([__file__])
