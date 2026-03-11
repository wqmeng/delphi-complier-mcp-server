"""
Delphi 帮助文档知识库服务

版权所有 (C) 吉林省左右软件开发有限公司
Copyright (C) Equilibrium Software Development Co., Ltd, Jilin

从 Delphi CHM 帮助文件中提取内容并构建知识库
"""

import os
import re
import json
import time
import shutil
import hashlib
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from html.parser import HTMLParser
from bs4 import BeautifulSoup

from .sqlite_vector_query_knowledge_base import SQLiteVectorKnowledgeBase
from ...utils.logger import get_logger

logger = get_logger(__name__)


class HTMLContentExtractor:
    """HTML 内容提取器"""

    def __init__(self):
        self.title_patterns = [
            r'<title>(.*?)</title>',
            r'<h1[^>]*>(.*?)</h1>',
            r'<h2[^>]*>(.*?)</h2>',
        ]

    def extract_text(self, html_content: str) -> Tuple[str, str]:
        """
        从 HTML 中提取纯文本内容

        Args:
            html_content: HTML 内容

        Returns:
            (标题, 正文内容)
        """
        try:
            soup = BeautifulSoup(html_content, 'html.parser')

            # 移除脚本和样式
            for script in soup(["script", "style", "nav", "footer", "header"]):
                script.decompose()

            # 提取标题
            title = ""
            if soup.title:
                title = soup.title.get_text(strip=True)
            elif soup.h1:
                title = soup.h1.get_text(strip=True)
            elif soup.h2:
                title = soup.h2.get_text(strip=True)

            # 提取正文
            # 优先查找主要内容区域
            main_content = soup.find('main') or soup.find('article') or soup.find('div', class_='content') or soup.find('body')

            if main_content:
                text = main_content.get_text(separator='\n', strip=True)
            else:
                text = soup.get_text(separator='\n', strip=True)

            # 清理多余空白
            text = re.sub(r'\n{3,}', '\n\n', text)
            text = re.sub(r' {2,}', ' ', text)

            return title, text

        except Exception as e:
            # 如果 BeautifulSoup 不可用，使用简单的正则提取
            return self._extract_with_regex(html_content)

    def _extract_with_regex(self, html_content: str) -> Tuple[str, str]:
        """使用正则表达式提取内容（备用方法）"""
        # 提取标题
        title = ""
        for pattern in self.title_patterns:
            match = re.search(pattern, html_content, re.IGNORECASE | re.DOTALL)
            if match:
                title = re.sub(r'<[^>]+>', '', match.group(1)).strip()
                break

        # 移除 HTML 标签
        text = re.sub(r'<script[^>]*>.*?</script>', '', html_content, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()

        return title, text


class DelphiHelpKnowledgeBase:
    """Delphi 帮助文档知识库"""

    # Delphi 帮助文件列表
    HELP_FILES = {
        'vcl': 'VCL (Visual Component Library) 帮助',
        'fmx': 'FireMonkey (FMX) 帮助',
        'system': 'System 单元帮助',
        'libraries': '运行时库帮助',
        'data': '数据库帮助',
        'codeexamples': '代码示例',
        'topics': '主题帮助',
        'Indy10': 'Indy 网络组件帮助',
        'TeeChart': 'TeeChart 图表帮助',
    }

    def __init__(self, kb_dir: Optional[str] = None):
        """
        初始化帮助文档知识库

        Args:
            kb_dir: 知识库目录路径
        """
        if kb_dir is None:
            # 默认路径: MCP 服务器目录下的 data/help-knowledge-base
            server_root = Path(__file__).parent.parent.parent.parent
            kb_dir = server_root / "data" / "help-knowledge-base"

        self.kb_dir = Path(kb_dir)
        self.kb_dir.mkdir(parents=True, exist_ok=True)
        (self.kb_dir / "index").mkdir(exist_ok=True)
        (self.kb_dir / "extracted").mkdir(exist_ok=True)

        self.kb_instance: Optional[SQLiteVectorKnowledgeBase] = None
        self.extractor = HTMLContentExtractor()

        # 7-Zip 路径
        self.sevenzip_path = self._find_7zip()

        # Delphi 帮助目录
        self.delphi_help_dir = self._find_delphi_help_dir()

        logger.info(f"帮助文档知识库初始化: {self.kb_dir}")

    def _find_7zip(self) -> Optional[str]:
        """查找 7-Zip 安装路径"""
        possible_paths = [
            r"C:\Program Files\7-Zip\7z.exe",
            r"C:\Program Files (x86)\7-Zip\7z.exe",
        ]
        for path in possible_paths:
            if Path(path).exists():
                return path
        return None

    def _find_delphi_help_dir(self) -> Optional[str]:
        """查找 Delphi 帮助目录"""
        import winreg
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"SOFTWARE\Embarcadero\BDS")
            version_key = winreg.EnumKey(key, 0)
            version_path = winreg.OpenKey(key, version_key)
            root_dir = winreg.QueryValueEx(version_path, "RootDir")[0]
            winreg.CloseKey(version_path)
            winreg.CloseKey(key)

            help_dir = Path(root_dir) / "Help" / "Doc"
            if help_dir.exists():
                return str(help_dir)
        except Exception as e:
            logger.warning(f"查找 Delphi 帮助目录失败: {e}")

        # 默认路径
        default_path = r"C:\Program Files (x86)\Embarcadero\Studio\22.0\Help\Doc"
        if Path(default_path).exists():
            return default_path

        return None

    def extract_chm(self, chm_path: str, output_dir: str) -> bool:
        """
        解压 CHM 文件

        Args:
            chm_path: CHM 文件路径
            output_dir: 输出目录

        Returns:
            是否成功
        """
        if not self.sevenzip_path:
            logger.error("未找到 7-Zip，无法解压 CHM 文件")
            return False

        try:
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)

            # 使用 7-Zip 解压
            result = subprocess.run(
                [self.sevenzip_path, 'x', '-y', f'-o{output_dir}', chm_path],
                capture_output=True,
                text=True,
                timeout=300
            )

            if result.returncode == 0:
                logger.info(f"成功解压: {chm_path}")
                return True
            else:
                logger.error(f"解压失败: {result.stderr}")
                return False

        except Exception as e:
            logger.error(f"解压 CHM 文件失败: {e}")
            return False

    def scan_html_files(self, directory: str) -> List[Dict]:
        """
        扫描目录中的 HTML 文件

        Args:
            directory: 目录路径

        Returns:
            文档列表
        """
        documents = []
        html_files = list(Path(directory).rglob("*.html")) + list(Path(directory).rglob("*.htm"))

        for html_file in html_files:
            try:
                with open(html_file, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()

                title, text = self.extractor.extract_text(content)

                if text and len(text) > 100:  # 忽略太短的文档
                    documents.append({
                        'path': str(html_file.relative_to(directory)),
                        'full_path': str(html_file),
                        'title': title,
                        'content': text,
                        'size': len(text),
                        'hash': hashlib.md5(text.encode()).hexdigest()
                    })

            except Exception as e:
                logger.warning(f"处理文件失败 {html_file}: {e}")

        return documents

    def build_knowledge_base(self, force_rebuild: bool = False) -> bool:
        """
        构建帮助文档知识库

        Args:
            force_rebuild: 是否强制重建

        Returns:
            是否成功
        """
        if not self.delphi_help_dir:
            logger.error("未找到 Delphi 帮助目录")
            return False

        # 检查是否需要重建
        if not force_rebuild and (self.kb_dir / "index" / "source_index.json").exists():
            logger.info("帮助文档知识库已存在，跳过构建")
            return True

        logger.info("开始构建帮助文档知识库...")

        all_documents = []
        extracted_dir = self.kb_dir / "extracted"

        # 处理每个 CHM 文件
        for help_name, help_desc in self.HELP_FILES.items():
            chm_path = Path(self.delphi_help_dir) / f"{help_name}.chm"

            if not chm_path.exists():
                logger.warning(f"帮助文件不存在: {chm_path}")
                continue

            logger.info(f"处理: {help_desc} ({chm_path.name})")

            # 解压 CHM
            output_dir = extracted_dir / help_name
            if not output_dir.exists() or force_rebuild:
                if not self.extract_chm(str(chm_path), str(output_dir)):
                    continue

            # 扫描 HTML 文件
            documents = self.scan_html_files(str(output_dir))

            # 添加来源信息
            for doc in documents:
                doc['source'] = help_name
                doc['source_desc'] = help_desc

            all_documents.extend(documents)
            logger.info(f"  提取到 {len(documents)} 个文档")

        if not all_documents:
            logger.error("未提取到任何文档")
            return False

        # 保存索引
        index_data = {
            'documents': all_documents,
            'statistics': {
                'total_documents': len(all_documents),
                'total_size': sum(d['size'] for d in all_documents),
                'sources': list(self.HELP_FILES.keys()),
                'build_time': datetime.now().isoformat()
            }
        }

        index_file = self.kb_dir / "index" / "source_index.json"
        with open(index_file, 'w', encoding='utf-8') as f:
            json.dump(index_data, f, ensure_ascii=False, indent=2)

        # 构建向量索引
        logger.info("构建向量索引...")
        self._build_vector_index(all_documents)

        logger.info(f"帮助文档知识库构建完成，共 {len(all_documents)} 个文档")
        return True

    def _build_vector_index(self, documents: List[Dict]):
        """构建向量索引"""
        # 创建临时扫描结果格式
        files_data = []
        for i, doc in enumerate(documents):
            files_data.append({
                'path': doc['path'],
                'full_path': doc['full_path'],
                'extension': '.html',
                'size': doc['size'],
                'line_count': doc['size'] // 50,  # 估算行数
                'hash': doc['hash'],
                'last_modified': datetime.now().isoformat(),
                'units': [],
                'uses': [],
                'classes': [],
                'functions': [],
                'description': f"{doc['title']}\n{doc['content'][:500]}"
            })

        scan_result = {
            'files': files_data,
            'statistics': {
                'total_files': len(files_data),
                'total_lines': sum(f['line_count'] for f in files_data)
            }
        }

        # 保存为知识库格式
        index_file = self.kb_dir / "index" / "source_index.json"
        with open(index_file, 'w', encoding='utf-8') as f:
            json.dump(scan_result, f, ensure_ascii=False, indent=2)

        # 保存元数据
        metadata = {
            'version': '1.0',
            'source_directory': str(self.delphi_help_dir),
            'scan_date': datetime.now().isoformat(),
            'statistics': scan_result['statistics']
        }

        metadata_file = self.kb_dir / "index" / "metadata.json"
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

        # 构建向量索引
        self.kb_instance = SQLiteVectorKnowledgeBase(str(self.kb_dir), force_rebuild=True)

    def load_knowledge_base(self) -> bool:
        """加载知识库"""
        try:
            if self.kb_instance is None:
                self.kb_instance = SQLiteVectorKnowledgeBase(str(self.kb_dir))
            return True
        except Exception as e:
            logger.error(f"加载知识库失败: {e}")
            return False

    def search(self, query: str, top_k: int = 10) -> List[Dict]:
        """
        搜索帮助文档

        Args:
            query: 搜索查询
            top_k: 返回结果数量

        Returns:
            搜索结果
        """
        if not self.load_knowledge_base():
            return []

        # 使用语义搜索
        results = []

        # 搜索类
        class_results = self.kb_instance.semantic_search_classes(query, top_k)
        for name, score in class_results:
            results.append({
                'type': 'class',
                'name': name,
                'score': score
            })

        # 搜索函数
        func_results = self.kb_instance.semantic_search_functions(query, top_k)
        for name, score in func_results:
            results.append({
                'type': 'function',
                'name': name,
                'score': score
            })

        # 按相似度排序
        results.sort(key=lambda x: x['score'], reverse=True)
        return results[:top_k]

    def search_by_keyword(self, keyword: str) -> List[Dict]:
        """关键词搜索"""
        if not self.load_knowledge_base():
            return []
        return self.kb_instance.search_by_keyword(keyword)

    def get_statistics(self) -> Dict:
        """获取统计信息"""
        stats = {
            'total_documents': 0,
            'sources': {},
            'database_size_mb': 0
        }

        try:
            index_file = self.kb_dir / "index" / "source_index.json"
            if index_file.exists():
                with open(index_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    stats['total_documents'] = data.get('statistics', {}).get('total_files', 0)

            db_file = self.kb_dir / "index" / "knowledge_base_vector.sqlite"
            if db_file.exists():
                stats['database_size_mb'] = db_file.stat().st_size / (1024 * 1024)

        except Exception as e:
            logger.warning(f"获取统计信息失败: {e}")

        return stats

    def close(self):
        """关闭知识库"""
        if self.kb_instance:
            self.kb_instance.close()
            self.kb_instance = None
