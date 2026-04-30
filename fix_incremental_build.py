#!/usr/bin/env python
"""修复增量构建的脚本"""

import re

# 读取文件
with open('src/services/knowledge_base/thirdparty_knowledge_base.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. 在 "unique_count = len(unique_files)" 后添加加载现有文件hash的代码
old_text = '''        unique_count = len(unique_files)
        if unique_count < total_files:
            logger.info(f"去重后剩余 {unique_count} 个唯一文件")

        # 直接保存到 SQLite (统一Schema)
        db_file = self.kb_dir / "knowledge.sqlite"
        conn = sqlite3.connect(str(db_file))
        cursor = conn.cursor()
        
        current_time = datetime.now().timestamp()
        
        # force_rebuild时清空旧数据
        if force_rebuild:
            try:
                cursor.execute("DELETE FROM files")
                cursor.execute("DELETE FROM vocabularies")
                cursor.execute("DELETE FROM vocabulary")
                cursor.execute("DELETE FROM metadata")
                conn.commit()
                logger.info("已清空旧知识库数据")
            except Exception:
                pass'''

new_text = '''        unique_count = len(unique_files)
        if unique_count < total_files:
            logger.info(f"去重后剩余 {unique_count} 个唯一文件")

        # 直接保存到 SQLite (统一Schema)
        db_file = self.kb_dir / "knowledge.sqlite"
        conn = sqlite3.connect(str(db_file))
        cursor = conn.cursor()
        
        current_time = datetime.now().timestamp()
        
        # force_rebuild时清空旧数据
        if force_rebuild:
            try:
                cursor.execute("DELETE FROM files")
                cursor.execute("DELETE FROM vocabularies")
                cursor.execute("DELETE FROM vocabulary")
                cursor.execute("DELETE FROM metadata")
                conn.commit()
                logger.info("已清空旧知识库数据")
            except Exception:
                pass
        
        # 增量构建：加载现有文件的hash
        existing_files = {}
        if not force_rebuild:
            cursor.execute("SELECT id, full_path, hash FROM files")
            for row in cursor.fetchall():
                existing_files[row[1]] = {'id': row[0], 'hash': row[2]}
            logger.info(f"现有文件数: {len(existing_files)}")'''

content = content.replace(old_text, new_text)

# 2. 修改插入源文件的循环，添加变更检测
old_insert = '''        # 插入源文件
        logger.info("保存源文件到数据库...")
        batch_size = 1000
        for i, file_info in enumerate(unique_files):
            # 转换 units 和 uses 为字符串
            units = file_info.get('units', [])
            if isinstance(units, list):
                units = ','.join(units)
            uses = file_info.get('uses', [])
            if isinstance(uses, list):
                uses = ','.join(uses)
            
            cursor.execute("""
                INSERT INTO files (full_path, relative_path, extension, size, line_count, hash, 
                    last_modified, category, units_defined, units_imported, description, 
                    scan_timestamp, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                file_info.get('full_path', ''),'''

new_insert = '''        # 插入源文件
        logger.info("保存源文件到数据库...")
        batch_size = 1000
        skipped_files = 0
        updated_files = 0
        new_files = 0
        
        for i, file_info in enumerate(unique_files):
            full_path = file_info.get('full_path', '')
            new_hash = file_info.get('hash', '')
            
            # 增量构建：检查文件是否变更
            if not force_rebuild and full_path in existing_files:
                existing_info = existing_files[full_path]
                if existing_info['hash'] == new_hash:
                    # 文件未变更，跳过
                    skipped_files += 1
                    continue
                
                # 文件已变更，删除旧的vocabularies
                old_file_id = existing_info['id']
                cursor.execute("DELETE FROM vocabularies WHERE file_id = ?", (old_file_id,))
                updated_files += 1
            else:
                new_files += 1
            
            # 转换 units 和 uses 为字符串
            units = file_info.get('units', [])
            if isinstance(units, list):
                units = ','.join(units)
            uses = file_info.get('uses', [])
            if isinstance(uses, list):
                uses = ','.join(uses)
            
            cursor.execute("""
                INSERT OR REPLACE INTO files (full_path, relative_path, extension, size, line_count, hash, 
                    last_modified, category, units_defined, units_imported, description, 
                    scan_timestamp, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                full_path,'''

content = content.replace(old_insert, new_insert)

# 3. 添加统计日志
old_commit = '''            if (i + 1) % batch_size == 0:
                conn.commit()
                logger.info(f"  已处理 {i+1}/{len(unique_files)} 源文件")

        # 插入帮助文档'''

new_commit = '''            if (i + 1) % batch_size == 0:
                conn.commit()
                logger.info(f"  已处理 {i+1}/{len(unique_files)} 源文件")
        
        if skipped_files > 0:
            logger.info(f"增量构建: 跳过 {skipped_files} 个未变更文件, 更新 {updated_files} 个变更文件, 新增 {new_files} 个文件")

        # 插入帮助文档'''

content = content.replace(old_commit, new_commit)

# 4. 修改帮助文档插入，使用 INSERT OR REPLACE
old_help = '''                cursor.execute("""
                    INSERT INTO files (full_path, relative_path, extension, size, line_count, hash, 
                        last_modified, category, units_defined, units_imported, description, 
                        scan_timestamp, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    help_doc.get('full_path', ''),'''

new_help = '''                cursor.execute("""
                    INSERT OR REPLACE INTO files (full_path, relative_path, extension, size, line_count, hash, 
                        last_modified, category, units_defined, units_imported, description, 
                        scan_timestamp, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    help_doc.get('full_path', ''),'''

content = content.replace(old_help, new_help)

# 保存文件
with open('src/services/knowledge_base/thirdparty_knowledge_base.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("✓ 增量构建修复完成")
