#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试文件备份工具 — src/utils/file_backup.py

覆盖:
  - create_backup: 新文件/已存在文件/文件不存在/编码检测
  - list_backups: 有备份/无备份/版本排序
  - restore_backup: 恢复最新版/指定版本/版本不存在
  - detect_encoding: UTF-8/GBK/UTF-16/UTF-8-BOM
"""

import sys
import os
import tempfile
import shutil
from pathlib import Path

project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.utils.file_backup import (
    create_backup, list_backups, restore_backup, detect_encoding
)


# ============================================================
# Fixtures
# ============================================================

def _make_temp_file(content: str = "unit Test;\nbegin\nend.\n",
                    encoding: str = "utf-8") -> str:
    """创建临时文件并返回路径"""
    fd, path = tempfile.mkstemp(suffix=".pas")
    os.close(fd)
    with open(path, "w", encoding=encoding) as f:
        f.write(content)
    return path


# ============================================================
# detect_encoding
# ============================================================

def test_detect_encoding_utf8():
    path = _make_temp_file("hello world", "utf-8")
    try:
        enc = detect_encoding(path)
        assert enc == "utf-8", f"expected utf-8, got {enc}"
    finally:
        os.unlink(path)


def test_detect_encoding_gbk():
    # GBK 编码的中文字符
    gbk_bytes = "中文测试".encode("gbk")
    fd, path = tempfile.mkstemp(suffix=".txt")
    os.close(fd)
    try:
        with open(path, "wb") as f:
            f.write(gbk_bytes)
        enc = detect_encoding(path)
        assert enc == "gbk", f"expected gbk, got {enc}"
    finally:
        os.unlink(path)


def test_detect_encoding_utf16():
    utf16_bytes = "hello".encode("utf-16-le")
    fd, path = tempfile.mkstemp(suffix=".txt")
    os.close(fd)
    try:
        with open(path, "wb") as f:
            # utf-16 BOM
            f.write(b'\xff\xfe' + utf16_bytes)
        enc = detect_encoding(path)
        assert enc == "utf-16", f"expected utf-16, got {enc}"
    finally:
        os.unlink(path)


def test_detect_encoding_utf8_bom():
    fd, path = tempfile.mkstemp(suffix=".txt")
    os.close(fd)
    try:
        with open(path, "wb") as f:
            f.write(b'\xef\xbb\xbfunit Test;')
        enc = detect_encoding(path)
        assert enc == "utf-8-sig", f"expected utf-8-sig, got {enc}"
    finally:
        os.unlink(path)


def test_detect_encoding_nonexistent_file():
    enc = detect_encoding(r"C:\nonexistent\file.pas")
    assert enc == "utf-8", "should fallback to utf-8"


# ============================================================
# create_backup
# ============================================================

def test_create_backup_new_file():
    path = _make_temp_file("unit Test;\nbegin\nend.\n")
    history_dir = os.path.join(os.path.dirname(path), "__history")
    try:
        bp = create_backup(path)
        assert bp is not None, "backup path should not be None"
        assert os.path.isfile(bp), f"backup file not found: {bp}"
        # 验证命名: filename.~1~
        base = os.path.basename(path)
        expected = os.path.join(os.path.dirname(path), "__history", f"{base}.~1~")
        assert bp == expected, f"unexpected backup path: {bp}"
    finally:
        shutil.rmtree(history_dir, ignore_errors=True)
        os.unlink(path)


def test_create_backup_version_increment():
    path = _make_temp_file("version1")
    history_dir = os.path.join(os.path.dirname(path), "__history")
    try:
        bp1 = create_backup(path)
        assert bp1.endswith(".~1~")

        # 修改文件后再次备份
        with open(path, "w") as f:
            f.write("version2")
        bp2 = create_backup(path)
        assert bp2.endswith(".~2~"), f"expected .~2~, got {bp2}"

        # 第三次
        with open(path, "w") as f:
            f.write("version3")
        bp3 = create_backup(path)
        assert bp3.endswith(".~3~"), f"expected .~3~, got {bp3}"
    finally:
        shutil.rmtree(history_dir, ignore_errors=True)
        os.unlink(path)


def test_create_backup_file_not_exist():
    bp = create_backup(r"C:\nonexistent\file.pas")
    assert bp is None, "should return None for nonexistent file"


def test_create_backup_preserves_content():
    original = "unit Test;\nconst ANSWER = 42;\nbegin\nend.\n"
    path = _make_temp_file(original)
    history_dir = os.path.join(os.path.dirname(path), "__history")
    try:
        bp = create_backup(path)
        with open(bp, "r") as f:
            backed = f.read()
        assert backed == original, "backup content mismatch"
    finally:
        shutil.rmtree(history_dir, ignore_errors=True)
        os.unlink(path)


# ============================================================
# list_backups
# ============================================================

def test_list_backups_empty():
    path = _make_temp_file("hello")
    try:
        backups = list_backups(path)
        assert backups == [], f"expected empty list, got {backups}"
    finally:
        os.unlink(path)


def test_list_backups_multiple():
    path = _make_temp_file("v1")
    history_dir = os.path.join(os.path.dirname(path), "__history")
    try:
        create_backup(path)
        with open(path, "w") as f:
            f.write("v2")
        create_backup(path)
        with open(path, "w") as f:
            f.write("v3")
        create_backup(path)

        backups = list_backups(path)
        assert len(backups) == 3, f"expected 3 backups, got {len(backups)}"
        # 按版本降序
        versions = [b["version"] for b in backups]
        assert versions == [3, 2, 1], f"expected [3,2,1], got {versions}"
        for b in backups:
            assert "path" in b
            assert "size" in b
            assert "mtime" in b
    finally:
        shutil.rmtree(history_dir, ignore_errors=True)
        os.unlink(path)


def test_list_backups_nonexistent_dir():
    path = r"C:\nonexistent\file.pas"
    backups = list_backups(path)
    assert backups == []


# ============================================================
# restore_backup
# ============================================================

def test_restore_backup_latest():
    path = _make_temp_file("original")
    history_dir = os.path.join(os.path.dirname(path), "__history")
    try:
        create_backup(path)
        # 修改文件
        with open(path, "w") as f:
            f.write("modified")
        # 再备份一次（restore_backup 会先备份当前版本）
        create_backup(path)
        # 修改内容并验证
        with open(path, "w") as f:
            f.write("lost")

        bp = restore_backup(path)  # 恢复到最新备份
        assert bp is not None, "restore should succeed"
        with open(path, "r") as f:
            content = f.read()
        assert content == "modified", f"expected 'modified', got '{content}'"
    finally:
        shutil.rmtree(history_dir, ignore_errors=True)
        os.unlink(path)


def test_restore_backup_specific_version():
    path = _make_temp_file("v1")
    history_dir = os.path.join(os.path.dirname(path), "__history")
    try:
        create_backup(path)  # v1
        with open(path, "w") as f:
            f.write("v2")
        create_backup(path)  # v2
        with open(path, "w") as f:
            f.write("v3")

        bp = restore_backup(path, version=1)
        assert bp is not None
        with open(path, "r") as f:
            content = f.read()
        assert content == "v1", f"expected 'v1', got '{content}'"
    finally:
        shutil.rmtree(history_dir, ignore_errors=True)
        os.unlink(path)


def test_restore_backup_version_not_found():
    path = _make_temp_file("hello")
    history_dir = os.path.join(os.path.dirname(path), "__history")
    try:
        create_backup(path)
        bp = restore_backup(path, version=99)
        assert bp is None, "should return None for nonexistent version"
    finally:
        shutil.rmtree(history_dir, ignore_errors=True)
        os.unlink(path)


def test_restore_backup_no_backups():
    path = _make_temp_file("hello")
    try:
        bp = restore_backup(path)
        assert bp is None, "should return None when no backups exist"
    finally:
        os.unlink(path)


# ============================================================
# Edge cases
# ============================================================

def test_backup_file_with_spaces():
    """文件名含空格"""
    tmp_dir = tempfile.mkdtemp()
    path = os.path.join(tmp_dir, "my unit.pas")
    with open(path, "w", encoding="utf-8") as f:
        f.write("unit Test;")
    try:
        bp = create_backup(path)
        assert bp is not None
        assert os.path.isfile(bp)
        assert "my unit.pas.~1~" in bp
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
