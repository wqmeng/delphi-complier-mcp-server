import sys
sys.path.insert(0, 'C:/User/delphi-complier-mcp-server')

from pathlib import Path

project_path = r"C:\User\diandaxia\diandaxia.dproj"
project_path_obj = Path(project_path)
project_dir = project_path_obj.parent
kb_dir = project_dir / ".delphi-kb"

print(f"project_path: {project_path}")
print(f"project_path_obj: {project_path_obj}")
print(f"project_dir: {project_dir}")
print(f"kb_dir: {kb_dir}")
print(f"kb_dir exists: {kb_dir.exists()}")

# 创建目录
kb_dir.mkdir(parents=True, exist_ok=True)
print(f"after mkdir, kb_dir exists: {kb_dir.exists()}")

# 尝试创建数据库
import sqlite3
db_file = kb_dir / "knowledge.sqlite"
print(f"db_file: {db_file}")

conn = sqlite3.connect(str(db_file))
cursor = conn.cursor()
cursor.execute("CREATE TABLE IF NOT EXISTS test (id INTEGER)")
conn.commit()
conn.close()
print("数据库写入成功")

# 检查文件
print(f"db_file exists: {db_file.exists()}")
print(f"db_file size: {db_file.stat().st_size}")
