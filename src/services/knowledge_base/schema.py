"""
知识库 Schema 定义 —— 统一建表脚本

所有知识库构建器（SmartCache、ProjectKB、ThirdPartyKB、GenericDocumentKB）
都应从此模块获取 CREATE TABLE SQL，确保表结构一致。
"""

import json
import logging
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ============================================================
# Schema 版本管理
# ============================================================
SCHEMA_VERSION = 1
"""
当前知识库 schema 版本号。
每次修改表结构时递增，用于在加载时检测旧库并提示重建。

版本历史:
  - 1: 当前版本。vocabularies 统一 schema + relative_path 列 + name_lower_rev 反转索引 + metadata 版本管理
"""

SCHEMA_VERSION_KEY = 'schema_version'
"""metadata 表中存储版本号的 key 名称"""


def get_schema_version_from_db(cursor) -> int:
    """从 metadata 表读取 schema 版本号，返回 0 表示无版本信息（旧库）"""
    try:
        cursor.execute(f"SELECT value FROM metadata WHERE key = '{SCHEMA_VERSION_KEY}'")
        row = cursor.fetchone()
        if row:
            return int(row[0])
    except Exception:
        pass
    return 0


def set_schema_version_in_db(cursor, version=None):
    """将 schema 版本号写入 metadata 表"""
    v = version if version is not None else SCHEMA_VERSION
    cursor.execute(
        "INSERT OR REPLACE INTO metadata (key, value, updated_at) VALUES (?, ?, ?)",
        (SCHEMA_VERSION_KEY, str(v), datetime.now().timestamp())
    )


def check_schema_version(cursor, kb_name: str = "unknown") -> bool:
    """
    检查 schema 版本是否匹配。
    返回 True 表示版本匹配或可兼容，False 表示需要重建。
    """
    stored = get_schema_version_from_db(cursor)
    if stored == 0:
        logger.info(f"[{kb_name}] 知识库无版本信息，假定为旧版 schema (v1)")
        return True  # 旧版兼容处理
    if stored == SCHEMA_VERSION:
        return True  # 版本匹配
    logger.warning(f"[{kb_name}] 知识库 schema 版本不匹配: 当前 v{stored}, 期望 v{SCHEMA_VERSION}，建议重建")
    return False


# ============================================================
# 源码知识库表结构（files / vocabularies / metadata）
# ============================================================

SOURCE_FILES_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_path TEXT UNIQUE NOT NULL,
    relative_path TEXT,
    extension TEXT,
    size INTEGER,
    line_count INTEGER,
    hash TEXT,
    last_modified TEXT,
    category TEXT,
    units_defined TEXT,
    units_imported TEXT,
    description TEXT,
    scan_timestamp REAL,
    created_at REAL DEFAULT (julianday('now')),
    updated_at REAL DEFAULT (julianday('now'))
)
"""

SOURCE_VOCABULARIES_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS vocabularies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL,
    name TEXT NOT NULL,
    name_lower TEXT NOT NULL,
    name_lower_rev TEXT,
    file_id INTEGER,
    line INTEGER,
    base_class TEXT,
    description TEXT,
    vector BLOB,
    vector_status TEXT DEFAULT 'pending',
    attributes TEXT,
    created_at REAL DEFAULT (julianday('now')),
    updated_at REAL DEFAULT (julianday('now')),
    FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE
)
"""

SOURCE_METADATA_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS metadata (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at REAL DEFAULT (julianday('now'))
)
"""

SOURCE_INDEXES_SQL: List[str] = [
    "CREATE INDEX IF NOT EXISTS idx_files_path ON files(relative_path)",
    "CREATE INDEX IF NOT EXISTS idx_files_extension ON files(extension)",
    "CREATE INDEX IF NOT EXISTS idx_files_category ON files(category)",
    "CREATE INDEX IF NOT EXISTS idx_vocabularies_type ON vocabularies(type)",
    "CREATE INDEX IF NOT EXISTS idx_vocabularies_name ON vocabularies(name)",
    "CREATE INDEX IF NOT EXISTS idx_vocabularies_name_lower ON vocabularies(name_lower)",
    "CREATE INDEX IF NOT EXISTS idx_vocabularies_name_lower_rev ON vocabularies(name_lower_rev)",
    "CREATE INDEX IF NOT EXISTS idx_vocabularies_file_id ON vocabularies(file_id)",
    "CREATE INDEX IF NOT EXISTS idx_vocabularies_vector_status ON vocabularies(vector_status)",
]


def create_source_tables(cursor):
    """创建源码知识库的所有表 + 索引"""
    cursor.execute(SOURCE_FILES_TABLE_SQL)
    cursor.execute(SOURCE_VOCABULARIES_TABLE_SQL)
    cursor.execute(SOURCE_METADATA_TABLE_SQL)
    for sql in SOURCE_INDEXES_SQL:
        cursor.execute(sql)


def drop_source_tables(cursor):
    """删除源码知识库的所有表"""
    cursor.execute("DROP TABLE IF EXISTS vocabularies")
    cursor.execute("DROP TABLE IF EXISTS files")
    cursor.execute("DROP TABLE IF EXISTS metadata")


# ============================================================
# 文档知识库表结构（documents / document_entities + FTS5）
# ============================================================

DOCUMENTS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT NOT NULL,
    full_path TEXT NOT NULL,
    extension TEXT,
    title TEXT,
    title_lower TEXT,
    title_rev TEXT,
    content TEXT,
    content_type TEXT,
    file_size INTEGER,
    size INTEGER,
    line_count INTEGER,
    hash TEXT,
    last_modified TEXT,
    sections TEXT,
    code_examples TEXT,
    url TEXT,
    requires_extraction INTEGER DEFAULT 0,
    language TEXT DEFAULT 'en'
)
"""

DOCUMENT_ENTITIES_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS document_entities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    kind TEXT NOT NULL,
    line INTEGER,
    definition TEXT,
    FOREIGN KEY (document_id) REFERENCES documents(id)
)
"""

DOCUMENTS_INDEXES_SQL: List[str] = [
    "CREATE INDEX IF NOT EXISTS idx_documents_path ON documents(path)",
    "CREATE INDEX IF NOT EXISTS idx_documents_hash ON documents(hash)",
    "CREATE INDEX IF NOT EXISTS idx_documents_title_lower ON documents(title_lower)",
    "CREATE INDEX IF NOT EXISTS idx_documents_title_rev ON documents(title_rev)",
    "CREATE INDEX IF NOT EXISTS idx_documents_language ON documents(language)",
    "CREATE INDEX IF NOT EXISTS idx_document_entities_name ON document_entities(name)",
]

# 文档知识库也使用统一的 metadata 表记录构建信息
DOCUMENTS_METADATA_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS metadata (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at REAL DEFAULT (julianday('now'))
)
"""


def create_document_tables(cursor):
    """创建文档知识库的所有表 + 索引"""
    cursor.execute(DOCUMENTS_TABLE_SQL)
    cursor.execute(DOCUMENT_ENTITIES_TABLE_SQL)
    cursor.execute(DOCUMENTS_METADATA_TABLE_SQL)
    for sql in DOCUMENTS_INDEXES_SQL:
        cursor.execute(sql)


def drop_document_tables(cursor):
    """删除文档知识库的所有表"""
    cursor.execute("DROP TABLE IF EXISTS document_entities")
    cursor.execute("DROP TABLE IF EXISTS documents")
    cursor.execute("DROP TABLE IF EXISTS metadata")


# ============================================================
# 通用 PRAGMA 设置
# ============================================================

def apply_performance_pragmas(conn, use_wal: bool = False):
    """
    应用 SQLite 性能优化 PRAGMA

    Args:
        conn: SQLite 连接
        use_wal: 是否使用 WAL 模式（构建时用 WAL 提升写入性能，查询时用 DELETE 避免 .wal 残留）
    """
    if use_wal:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
    else:
        conn.execute("PRAGMA journal_mode=DELETE")
        conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-200000")
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.execute("PRAGMA busy_timeout=10000")
    conn.execute("PRAGMA locking_mode=NORMAL")


__all__ = [
    'SCHEMA_VERSION',
    'SCHEMA_VERSION_KEY',
    'get_schema_version_from_db',
    'set_schema_version_in_db',
    'check_schema_version',
    'SOURCE_FILES_TABLE_SQL',
    'SOURCE_VOCABULARIES_TABLE_SQL',
    'SOURCE_METADATA_TABLE_SQL',
    'SOURCE_INDEXES_SQL',
    'create_source_tables',
    'drop_source_tables',
    'DOCUMENTS_TABLE_SQL',
    'DOCUMENT_ENTITIES_TABLE_SQL',
    'DOCUMENTS_INDEXES_SQL',
    'create_document_tables',
    'drop_document_tables',
    'apply_performance_pragmas',
]
