"""
文件备份工具 — __history 备份/恢复/列表

提供与 Delphi IDE 兼容的 __history 备份机制。
备份文件命名: 文件名.~版本号~ (如 Unit.pas.~1~)
"""

import os
import shutil
from typing import Optional, List, Dict
from .logger import get_logger

logger = get_logger(__name__)


def detect_encoding(file_path: str) -> str:
    """
    检测文件编码。

    检测顺序:
        1. BOM (UTF-16 LE/BE, UTF-8 with BOM)
        2. UTF-8 解码尝试
        3. GBK 解码尝试
        4. 回退: UTF-8

    Args:
        file_path: 文件路径

    Returns:
        编码名称: "utf-8", "utf-8-sig", "utf-16", "gbk"
    """
    try:
        with open(file_path, 'rb') as f:
            raw_data = f.read()

        if raw_data.startswith(b'\xff\xfe') or raw_data.startswith(b'\xfe\xff'):
            return 'utf-16'
        elif raw_data.startswith(b'\xef\xbb\xbf'):
            return 'utf-8-sig'
        else:
            try:
                raw_data.decode('utf-8')
                return 'utf-8'
            except UnicodeDecodeError:
                try:
                    raw_data.decode('gbk')
                    return 'gbk'
                except UnicodeDecodeError:
                    return 'utf-8'
    except Exception as e:
        logger.warning(f"检测文件编码失败: {e}，使用默认编码 utf-8")
        return 'utf-8'


def create_backup(file_path: str) -> Optional[str]:
    """
    创建 __history 备份文件。

    在源文件所在目录下创建 __history 子目录，生成带递增版本号的备份。
    版本号格式: 文件名.~N~ (与 Delphi IDE 兼容)

    Args:
        file_path: 源文件路径

    Returns:
        备份文件路径，失败返回 None
    """
    try:
        if not os.path.isfile(file_path):
            logger.warning(f"备份失败，文件不存在: {file_path}")
            return None

        file_dir = os.path.dirname(os.path.abspath(file_path))
        history_dir = os.path.join(file_dir, "__history")
        os.makedirs(history_dir, exist_ok=True)

        base_name = os.path.basename(file_path)

        # 查找现有备份，确定新版本号
        backup_files = [
            f for f in os.listdir(history_dir)
            if f.startswith(f"{base_name}.~") and f.endswith("~")
        ]

        max_version = 0
        for backup_file in backup_files:
            try:
                version_str = backup_file[len(base_name) + 2:-1]  # 去掉 "文件名.~" 和 "~"
                version = int(version_str)
                if version > max_version:
                    max_version = version
            except (ValueError, IndexError):
                continue

        new_version = max_version + 1 if max_version > 0 else 1
        backup_path = os.path.join(history_dir, f"{base_name}.~{new_version}~")

        shutil.copy2(file_path, backup_path)
        logger.info(f"创建备份文件: {backup_path}")
        return backup_path

    except Exception as e:
        logger.warning(f"创建备份文件失败: {e}")
        return None


def list_backups(file_path: str) -> List[Dict]:
    """
    列出指定文件的所有备份版本。

    Args:
        file_path: 源文件路径

    Returns:
        备份版本列表，每个元素包含 version, path, size, mtime 字段。
        按版本号降序排列（最新的在前）。
    """
    file_dir = os.path.dirname(os.path.abspath(file_path))
    history_dir = os.path.join(file_dir, "__history")

    if not os.path.isdir(history_dir):
        return []

    base_name = os.path.basename(file_path)
    backups = []

    for f in os.listdir(history_dir):
        if not (f.startswith(f"{base_name}.~") and f.endswith("~")):
            continue

        full_path = os.path.join(history_dir, f)
        try:
            version_str = f[len(base_name) + 2:-1]
            version = int(version_str)
            stat = os.stat(full_path)
            backups.append({
                "version": version,
                "path": full_path,
                "size": stat.st_size,
                "mtime": stat.st_mtime,
            })
        except (ValueError, OSError):
            continue

    backups.sort(key=lambda x: x["version"], reverse=True)
    return backups


def restore_backup(file_path: str, version: Optional[int] = None) -> Optional[str]:
    """
    从 __history 恢复文件到指定版本。

    Args:
        file_path: 源文件路径
        version: 版本号，不传则使用最新版本

    Returns:
        恢复的备份文件路径，失败返回 None
    """
    backups = list_backups(file_path)
    if not backups:
        logger.warning(f"恢复失败，没有找到备份文件: {file_path}")
        return None

    if version is not None:
        target = next((b for b in backups if b["version"] == version), None)
        if not target:
            logger.warning(f"恢复失败，未找到版本 {version}，可用版本: {[b['version'] for b in backups]}")
            return None
    else:
        target = backups[0]  # 最新版本

    try:
        # 恢复前先备份当前文件（安全网）
        create_backup(file_path)

        shutil.copy2(target["path"], file_path)
        logger.info(f"已从备份恢复: {target['path']} → {file_path}")
        return target["path"]

    except Exception as e:
        logger.error(f"恢复备份失败: {e}")
        return None
