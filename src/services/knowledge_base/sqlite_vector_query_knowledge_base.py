#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Delphi 知识库查询接口 (SQLite + 内置向量扩展)
使用纯 Python 实现的向量搜索功能,无需外部依赖
"""

import json
import sqlite3
import math
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from collections import defaultdict, Counter
import time
import hashlib


class SQLiteVectorKnowledgeBase:
    def __init__(self, kb_dir: str, force_rebuild: bool = False):
        self.kb_dir = Path(kb_dir)
        self.index_dir = self.kb_dir / "index"
        self.source_index_file = self.index_dir / "source_index.json"
        self.metadata_file = self.index_dir / "metadata.json"
        self.db_file = self.index_dir / "knowledge_base_vector.sqlite"
        self.source_dir = None

        # SQLite 连接
        self.conn = None

        # 向量词汇表
        self.vocabulary = {}  # word -> id
        self.idf_weights = {}  # word -> idf weight

        # 加载索引
        self.load_index(force_rebuild)

    def load_index(self, force_rebuild: bool = False):
        """加载知识库索引"""
        try:
            # 加载元数据
            with open(self.metadata_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
                self.source_dir = metadata.get('source_directory')

            print(f"知识库加载成功! 包含 {metadata['statistics']['total_files']} 个文件")

            # 打开 SQLite 数据库
            self.conn = sqlite3.connect(str(self.db_file))
            self.conn.row_factory = sqlite3.Row

            # 检查是否需要重建索引
            cursor = self.conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='metadata'")
            if not cursor.fetchone() or force_rebuild:
                self.build_vector_index()
            else:
                # 验证缓存是否有效
                cursor.execute("SELECT hash FROM metadata")
                cached_hash = cursor.fetchone()
                if cached_hash:
                    cached_hash = cached_hash['hash']
                else:
                    cached_hash = None

                current_hash = self.get_index_hash()

                if cached_hash != current_hash:
                    print("缓存已过期,重新构建索引...")
                    self.build_vector_index()
                else:
                    print("使用缓存的索引 (SQLite 向量扩展模式)")
                    self.load_vocabulary()

        except Exception as e:
            print(f"加载知识库失败: {e}")
            if self.conn:
                self.conn.close()
            raise

    def get_index_hash(self) -> str:
        """计算原始索引的哈希值"""
        index_stat = self.source_index_file.stat()
        metadata_stat = self.metadata_file.stat()

        hash_str = f"{index_stat.st_mtime}_{index_stat.st_size}_{metadata_stat.st_mtime}_{metadata_stat.st_size}"
        return hashlib.md5(hash_str.encode()).hexdigest()

    def tokenize(self, text: str) -> List[str]:
        """简单的分词函数"""
        # 转换为小写
        text = text.lower()
        # 分割单词 (处理驼峰命名)
        words = []
        current_word = ""
        for char in text:
            if char.isalpha():
                current_word += char
            else:
                if current_word:
                    words.append(current_word)
                    current_word = ""
        if current_word:
            words.append(current_word)

        # 处理驼峰命名
        result = []
        for word in words:
            # 简单的驼峰分割
            if len(word) > 1:
                new_words = []
                i = 0
                while i < len(word):
                    if i > 0 and word[i].isupper():
                        new_words.append(word[i])
                    else:
                        if new_words:
                            new_words[-1] += word[i]
                        else:
                            new_words.append(word[i])
                    i += 1
                result.extend(new_words)
            else:
                result.append(word)

        return result

    def build_vocabulary(self, documents: List[str]) -> Tuple[Dict[str, int], Dict[str, float]]:
        """构建词汇表和 IDF 权重"""
        # 统计词频
        doc_freq = defaultdict(int)
        word_freq_per_doc = []

        for doc in documents:
            words = set(self.tokenize(doc))
            for word in words:
                doc_freq[word] += 1
            word_freq_per_doc.append(Counter(self.tokenize(doc)))

        # 计算 IDF
        idf_weights = {}
        doc_count = len(documents)
        for word, freq in doc_freq.items():
            idf_weights[word] = math.log(doc_count / (freq + 1)) + 1

        # 构建词汇表
        vocabulary = {word: idx for idx, word in enumerate(sorted(doc_freq.keys()))}

        return vocabulary, idf_weights

    def text_to_vector(self, text: str) -> Dict[int, float]:
        """将文本转换为 TF-IDF 稀疏向量 (使用字典存储)"""
        words = self.tokenize(text)
        word_freq = Counter(words)

        # 构建稀疏向量 (只存储非零值)
        vector = {}
        for word, freq in word_freq.items():
            if word in self.vocabulary:
                tf = freq / len(words)
                idf = self.idf_weights.get(word, 1.0)
                vector[self.vocabulary[word]] = tf * idf

        return vector

    def cosine_similarity(self, vec1: Dict[int, float], vec2: Dict[int, float]) -> float:
        """计算稀疏向量的余弦相似度"""
        # 计算点积
        dot_product = 0.0
        for idx, val in vec1.items():
            if idx in vec2:
                dot_product += val * vec2[idx]

        # 计算范数
        norm1 = math.sqrt(sum(val * val for val in vec1.values()))
        norm2 = math.sqrt(sum(val * val for val in vec2.values()))

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)

    def build_vector_index(self):
        """构建向量索引"""
        print("正在构建 SQLite 向量索引...")
        start_time = time.time()

        cursor = self.conn.cursor()

        # 删除现有表
        cursor.execute("DROP TABLE IF EXISTS metadata")
        cursor.execute("DROP TABLE IF EXISTS files")
        cursor.execute("DROP TABLE IF EXISTS classes")
        cursor.execute("DROP TABLE IF EXISTS functions")
        cursor.execute("DROP TABLE IF EXISTS units")
        cursor.execute("DROP TABLE IF EXISTS keywords")
        cursor.execute("DROP TABLE IF EXISTS vocabulary")
        cursor.execute("DROP TABLE IF EXISTS class_vectors")
        cursor.execute("DROP TABLE IF EXISTS function_vectors")

        # 创建表
        cursor.execute("""
            CREATE TABLE metadata (
                hash TEXT PRIMARY KEY,
                timestamp REAL,
                total_files INTEGER,
                total_lines INTEGER,
                vector_size INTEGER
            )
        """)

        cursor.execute("""
            CREATE TABLE vocabulary (
                id INTEGER PRIMARY KEY,
                word TEXT UNIQUE,
                idf_weight REAL
            )
        """)

        cursor.execute("""
            CREATE TABLE files (
                path TEXT PRIMARY KEY,
                full_path TEXT,
                extension TEXT,
                size INTEGER,
                line_count INTEGER,
                hash TEXT,
                last_modified TEXT,
                units TEXT,
                uses TEXT,
                description TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE classes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name_lower TEXT,
                name TEXT,
                base_class TEXT,
                line INTEGER,
                file_path TEXT,
                description TEXT,
                vector BLOB,
                FOREIGN KEY (file_path) REFERENCES files(path)
            )
        """)

        cursor.execute("""
            CREATE TABLE functions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name_lower TEXT,
                name TEXT,
                line INTEGER,
                type TEXT,
                file_path TEXT,
                description TEXT,
                vector BLOB,
                FOREIGN KEY (file_path) REFERENCES files(path)
            )
        """)

        cursor.execute("""
            CREATE TABLE units (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name_lower TEXT,
                name TEXT,
                file_path TEXT,
                description TEXT,
                FOREIGN KEY (file_path) REFERENCES files(path)
            )
        """)

        cursor.execute("""
            CREATE TABLE keywords (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                keyword_lower TEXT,
                keyword TEXT,
                file_path TEXT,
                FOREIGN KEY (file_path) REFERENCES files(path)
            )
        """)

        # 创建索引
        cursor.execute("CREATE INDEX idx_classes_name_lower ON classes(name_lower)")
        cursor.execute("CREATE INDEX idx_functions_name_lower ON functions(name_lower)")
        cursor.execute("CREATE INDEX idx_units_name_lower ON units(name_lower)")
        cursor.execute("CREATE INDEX idx_keywords_keyword_lower ON keywords(keyword_lower)")

        # 加载原始索引
        with open(self.source_index_file, 'r', encoding='utf-8') as f:
            source_index = json.load(f)

        # 收集所有文档用于构建词汇表
        all_documents = []

        for file_info in source_index['files']:
            file_path = file_info['path']

            # 处理类
            for cls in file_info.get('classes', []):
                class_desc = f"Class {cls['name']} inherits from {cls['base_class']} at line {cls['line']} in {file_path}"
                all_documents.append(class_desc)

            # 处理函数
            for func in file_info.get('functions', []):
                func_desc = f"{func.get('type', 'function')} {func['name']} at line {func['line']} in {file_path}"
                all_documents.append(func_desc)

        # 构建词汇表
        print("正在构建词汇表...")
        self.vocabulary, self.idf_weights = self.build_vocabulary(all_documents)

        # 保存词汇表到数据库 (批量插入)
        print("正在保存词汇表...")
        vocab_data = [(word_id, word, self.idf_weights[word]) for word, word_id in self.vocabulary.items()]
        cursor.executemany("""
            INSERT INTO vocabulary (id, word, idf_weight)
            VALUES (?, ?, ?)
        """, vocab_data)
        self.conn.commit()

        # 插入元数据
        cursor.execute("""
            INSERT INTO metadata (hash, timestamp, total_files, total_lines, vector_size)
            VALUES (?, ?, ?, ?, ?)
        """, (
            self.get_index_hash(),
            time.time(),
            source_index['statistics']['total_files'],
            source_index['statistics']['total_lines'],
            len(self.vocabulary)
        ))

        # 处理文件和插入数据 (批量插入,带进度显示)
        print("正在处理文件和构建向量...")
        total_files = len(source_index['files'])
        processed_files = 0
        last_progress = 0

        files_data = []
        classes_data = []
        functions_data = []
        units_data = []
        keywords_data = []

        for file_info in source_index['files']:
            file_path = file_info['path']
            file_desc = f"{file_info['path']} {file_info.get('units', [])} {len(file_info.get('classes', []))} classes {len(file_info.get('functions', []))} functions"

            # 收集文件数据
            files_data.append((
                file_info['path'],
                file_info['full_path'],
                file_info['extension'],
                file_info['size'],
                file_info['line_count'],
                file_info['hash'],
                file_info['last_modified'],
                json.dumps(file_info.get('units', [])),
                json.dumps(file_info.get('uses', [])),
                file_desc
            ))

            # 处理类
            for cls in file_info.get('classes', []):
                class_desc = f"Class {cls['name']} inherits from {cls['base_class']} at line {cls['line']} in {file_path}"
                vector = self.text_to_vector(class_desc)
                classes_data.append((
                    cls['name'].lower(),
                    cls['name'],
                    cls['base_class'],
                    cls['line'],
                    file_path,
                    class_desc,
                    json.dumps(vector)
                ))

            # 处理函数
            for func in file_info.get('functions', []):
                func_desc = f"{func.get('type', 'function')} {func['name']} at line {func['line']} in {file_path}"
                vector = self.text_to_vector(func_desc)
                functions_data.append((
                    func['name'].lower(),
                    func['name'],
                    func['line'],
                    func.get('type', 'function'),
                    file_path,
                    func_desc,
                    json.dumps(vector)
                ))

            # 插入单元
            for unit in file_info.get('units', []):
                units_data.append((
                    unit.lower(),
                    unit,
                    file_path,
                    f"Unit {unit} in {file_path}"
                ))

            # 插入关键词
            keywords = set()
            for unit in file_info.get('units', []):
                keywords.add(unit.lower())
            for cls in file_info.get('classes', []):
                keywords.add(cls['name'].lower())
            for func in file_info.get('functions', []):
                keywords.add(func['name'].lower())

            for keyword in keywords:
                keywords_data.append((keyword, keyword, file_path))

            # 进度显示
            processed_files += 1
            progress = int(processed_files / total_files * 100)
            if progress >= last_progress + 5:  # 每 5% 显示一次
                print(f"处理进度: {progress}% ({processed_files}/{total_files} 文件)")
                last_progress = progress

        print(f"处理进度: 100% ({processed_files}/{total_files} 文件)")
        print(f"收集完成: {len(files_data)} 文件, {len(classes_data)} 类, {len(functions_data)} 函数, {len(units_data)} 单元, {len(keywords_data)} 关键词")

        # 批量插入数据
        print("正在批量插入数据...")
        print(f"  - 插入文件数据 ({len(files_data)} 条)...")
        cursor.executemany("""
            INSERT INTO files (
                path, full_path, extension, size, line_count,
                hash, last_modified, units, uses, description
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, files_data)
        print(f"  - 文件数据插入完成")

        print(f"  - 插入类数据 ({len(classes_data)} 条)...")
        cursor.executemany("""
            INSERT INTO classes (name_lower, name, base_class, line, file_path, description, vector)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, classes_data)
        print(f"  - 类数据插入完成")

        print(f"  - 插入函数数据 ({len(functions_data)} 条)...")
        cursor.executemany("""
            INSERT INTO functions (name_lower, name, line, type, file_path, description, vector)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, functions_data)
        print(f"  - 函数数据插入完成")

        print(f"  - 插入单元数据 ({len(units_data)} 条)...")
        cursor.executemany("""
            INSERT INTO units (name_lower, name, file_path, description)
            VALUES (?, ?, ?, ?)
        """, units_data)
        print(f"  - 单元数据插入完成")

        print(f"  - 插入关键词数据 ({len(keywords_data)} 条)...")
        cursor.executemany("""
            INSERT INTO keywords (keyword_lower, keyword, file_path)
            VALUES (?, ?, ?)
        """, keywords_data)
        print(f"  - 关键词数据插入完成")

        # 提交事务
        self.conn.commit()

        # 优化数据库
        cursor.execute("ANALYZE")
        self.conn.commit()

        elapsed = (time.time() - start_time) * 1000
        print(f"SQLite 向量索引构建完成! 耗时: {elapsed:.2f}ms")
        print(f"词汇表大小: {len(self.vocabulary)}")

    def load_vocabulary(self):
        """从数据库加载词汇表"""
        print("正在加载词汇表...")
        cursor = self.conn.cursor()

        cursor.execute("SELECT id, word, idf_weight FROM vocabulary")
        for row in cursor.fetchall():
            self.vocabulary[row['word']] = row['id']
            self.idf_weights[row['word']] = row['idf_weight']

        print(f"词汇表加载完成! 大小: {len(self.vocabulary)}")

    def semantic_search_classes(self, query: str, top_k: int = 10) -> List[Tuple[str, float]]:
        """语义搜索类"""
        query_vector = self.text_to_vector(query)

        cursor = self.conn.cursor()
        cursor.execute("SELECT name, vector FROM classes")

        results = []
        for row in cursor.fetchall():
            stored_vector = json.loads(row['vector'])
            # 转换键为整数
            stored_vector_int = {int(k): v for k, v in stored_vector.items()}
            similarity = self.cosine_similarity(query_vector, stored_vector_int)
            if similarity > 0:
                results.append((row['name'], similarity))

        # 排序并返回 top-k
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    def semantic_search_functions(self, query: str, top_k: int = 10) -> List[Tuple[str, float]]:
        """语义搜索函数"""
        query_vector = self.text_to_vector(query)

        cursor = self.conn.cursor()
        cursor.execute("SELECT name, vector FROM functions")

        results = []
        for row in cursor.fetchall():
            stored_vector = json.loads(row['vector'])
            # 转换键为整数
            stored_vector_int = {int(k): v for k, v in stored_vector.items()}
            similarity = self.cosine_similarity(query_vector, stored_vector_int)
            if similarity > 0:
                results.append((row['name'], similarity))

        # 排序并返回 top-k
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    def search_by_class_name(self, class_name: str) -> List[Dict]:
        """根据类名搜索 (精确匹配)"""
        class_name_lower = class_name.lower()
        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT c.name, c.base_class, c.line, f.* FROM classes c
            INNER JOIN files f ON c.file_path = f.path
            WHERE c.name_lower = ?
        """, (class_name_lower,))

        results = []
        for row in cursor.fetchall():
            results.append({
                'file': {
                    'path': row['path'],
                    'full_path': row['full_path'],
                    'extension': row['extension'],
                    'size': row['size'],
                    'line_count': row['line_count'],
                    'hash': row['hash'],
                    'last_modified': row['last_modified'],
                    'units': json.loads(row['units']),
                    'uses': json.loads(row['uses'])
                },
                'class': {
                    'name': row['name'],
                    'base_class': row['base_class'],
                    'line': row['line']
                }
            })

        return results

    def search_by_function_name(self, function_name: str) -> List[Dict]:
        """根据函数名搜索 (精确匹配)"""
        function_name_lower = function_name.lower()
        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT func.name, func.line, func.type, f.* FROM functions func
            INNER JOIN files f ON func.file_path = f.path
            WHERE func.name_lower = ?
        """, (function_name_lower,))

        results = []
        for row in cursor.fetchall():
            results.append({
                'file': {
                    'path': row['path'],
                    'full_path': row['full_path'],
                    'extension': row['extension'],
                    'size': row['size'],
                    'line_count': row['line_count'],
                    'hash': row['hash'],
                    'last_modified': row['last_modified'],
                    'units': json.loads(row['units']),
                    'uses': json.loads(row['uses'])
                },
                'function': {
                    'name': row['name'],
                    'line': row['line'],
                    'type': row['type']
                }
            })

        return results

    def search_by_keyword(self, keyword: str, search_in: List[str] = None) -> List[Dict]:
        """根据关键词搜索 (精确匹配)"""
        keyword_lower = keyword.lower()
        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT DISTINCT f.* FROM files f
            INNER JOIN keywords k ON f.path = k.file_path
            WHERE k.keyword_lower = ?
        """, (keyword_lower,))

        results = []
        for row in cursor.fetchall():
            results.append({
                'path': row['path'],
                'full_path': row['full_path'],
                'extension': row['extension'],
                'size': row['size'],
                'line_count': row['line_count'],
                'hash': row['hash'],
                'last_modified': row['last_modified'],
                'units': json.loads(row['units']),
                'uses': json.loads(row['uses'])
            })

        return results

    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
            self.conn = None

    def __del__(self):
        """析构函数,确保数据库连接关闭"""
        self.close()


def main():
    """命令行查询接口"""
    import argparse

    parser = argparse.ArgumentParser(description='Delphi 知识库查询工具 (SQLite 向量扩展版)')
    parser.add_argument('--kb-dir', default=r'c:\User\diandaxia\delphi-knowledge-base',
                       help='知识库目录')
    parser.add_argument('--search-type', choices=['unit', 'class', 'function', 'keyword', 'semantic'],
                       default='semantic', help='搜索类型')
    parser.add_argument('--query', required=True, help='搜索查询')
    parser.add_argument('--top-k', type=int, default=10, help='语义搜索返回结果数量')
    parser.add_argument('--rebuild', action='store_true', help='强制重新构建索引')

    args = parser.parse_args()

    # 初始化知识库
    kb = SQLiteVectorKnowledgeBase(args.kb_dir, force_rebuild=args.rebuild)

    try:
        # 执行搜索
        if args.search_type == 'semantic':
            # 语义搜索
            class_results = kb.semantic_search_classes(args.query, top_k=args.top_k)
            function_results = kb.semantic_search_functions(args.query, top_k=args.top_k)

            print(f"语义搜索 '{args.query}' 的结果:")
            print(f"\n最相关的类:")
            for class_name, score in class_results[:5]:
                exact_results = kb.search_by_class_name(class_name)
                if exact_results:
                    result = exact_results[0]
                    print(f"  {result['class']['name']} (相似度: {score:.3f}) - {result['file']['path']}")

            print(f"\n最相关的函数:")
            for func_name, score in function_results[:5]:
                exact_results = kb.search_by_function_name(func_name)
                if exact_results:
                    result = exact_results[0]
                    print(f"  {result['function']['name']} (相似度: {score:.3f}) - {result['file']['path']}")

        elif args.search_type == 'class':
            results = kb.search_by_class_name(args.query)
            print(f"找到 {len(results)} 个类: '{args.query}'")
            for i, result in enumerate(results[:10], 1):
                print(f"\n{i}. {result['file']['path']}")
                print(f"   - 类: {result['class']['name']}")

        elif args.search_type == 'function':
            results = kb.search_by_function_name(args.query)
            print(f"找到 {len(results)} 个函数: '{args.query}'")
            for i, result in enumerate(results[:10], 1):
                print(f"\n{i}. {result['file']['path']}")
                print(f"   - 函数: {result['function']['name']}")

        elif args.search_type == 'keyword':
            results = kb.search_by_keyword(args.query)
            print(f"找到 {len(results)} 个文件包含关键词: '{args.query}'")
            for i, result in enumerate(results[:10], 1):
                print(f"\n{i}. {result['path']}")

    finally:
        kb.close()


if __name__ == "__main__":
    main()
