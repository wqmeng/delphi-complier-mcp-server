#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 file_tool 集成 — src/tools/file_tool.py

工具返回值统一为 dict:
  success: {"status": "success", "message": "..."}
  error:   {"status": "failed", "message": "..."}
"""

import sys
import os
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, AsyncMock
import pytest

project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.tools.file_tool import (
    handle_file_tool, handle_read, handle_write,
    handle_backup, handle_format
)


# ============================================================
# Helpers
# ============================================================

def _make_file(path: str, content: str = "unit Test;\nbegin\nend.\n",
               encoding: str = "utf-8") -> str:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding=encoding) as f:
        f.write(content)
    return path


def _assert_success(result: dict):
    assert result.get("status") == "success", \
        f"expected success, got: {result}"


def _assert_error(result: dict):
    assert result.get("status") == "failed", \
        f"expected error, got: {result}"


# ============================================================
# handle_read
# ============================================================

@pytest.mark.asyncio
async def test_read_missing_file_path():
    result = await handle_read({"search_type": "path"})
    _assert_error(result)
    assert "file_path" in result["message"].lower()


@pytest.mark.asyncio
async def test_read_file_not_found():
    result = await handle_read({
        "file_path": r"C:\nonexistent_file_12345.pas",
    })
    assert isinstance(result, dict)


@pytest.mark.asyncio
async def test_read_existing_file():
    tmp = tempfile.NamedTemporaryFile(suffix=".pas", mode="w", delete=False,
                                      encoding="utf-8")
    tmp.write("unit Test;\nbegin\nend.\n")
    tmp.close()
    try:
        result = await handle_read({"file_path": tmp.name})
        assert isinstance(result, dict)
    finally:
        os.unlink(tmp.name)


@pytest.mark.asyncio
async def test_read_search_type_class():
    result = await handle_read({
        "search_type": "class",
        "type_name": "TForm1",
    })
    assert isinstance(result, dict)


@pytest.mark.asyncio
async def test_read_search_type_function():
    result = await handle_read({
        "search_type": "function",
        "function_name": "Create",
    })
    assert isinstance(result, dict)


# ============================================================
# handle_write
# ============================================================

@pytest.mark.asyncio
async def test_write_new_file():
    tmp_dir = tempfile.mkdtemp()
    file_path = os.path.join(tmp_dir, "TestUnit.pas")
    try:
        result = await handle_write({
            "file_path": file_path,
            "content": "unit TestUnit;\nbegin\nend.\n",
            "backup": False,
        })
        _assert_success(result)
        assert "文件已写入" in result["message"]
        assert os.path.isfile(file_path)
        with open(file_path, "r") as f:
            assert "unit TestUnit" in f.read()
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_write_existing_file_with_backup():
    tmp_dir = tempfile.mkdtemp()
    file_path = os.path.join(tmp_dir, "TestUnit.pas")
    _make_file(file_path, "original content")
    history_dir = os.path.join(tmp_dir, "__history")
    try:
        result = await handle_write({
            "file_path": file_path,
            "content": "modified content",
            "backup": True,
        })
        _assert_success(result)
        assert "备份已创建" in result["message"]

        backups = os.listdir(history_dir)
        assert len(backups) == 1
        assert backups[0].endswith(".~1~")

        bp = os.path.join(history_dir, backups[0])
        with open(bp, "r") as f:
            assert f.read() == "original content"
        with open(file_path, "r") as f:
            assert f.read() == "modified content"
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_write_backup_version_increment():
    tmp_dir = tempfile.mkdtemp()
    file_path = os.path.join(tmp_dir, "TestUnit.pas")
    _make_file(file_path, "v1")
    history_dir = os.path.join(tmp_dir, "__history")
    try:
        await handle_write({"file_path": file_path, "content": "v2", "backup": True})
        await handle_write({"file_path": file_path, "content": "v3", "backup": True})

        backups = sorted(os.listdir(history_dir))
        assert len(backups) == 2
        assert backups[0].endswith(".~1~")
        assert backups[1].endswith(".~2~")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_write_missing_file_path():
    result = await handle_write({"content": "hello"})
    _assert_error(result)


@pytest.mark.asyncio
async def test_write_missing_content():
    result = await handle_write({"file_path": "test.pas"})
    _assert_error(result)


@pytest.mark.asyncio
async def test_write_preserves_encoding():
    tmp_dir = tempfile.mkdtemp()
    file_path = os.path.join(tmp_dir, "test_gbk.pas")
    gbk_content = "unit Test;\n// 中文注释\nbegin\nend.\n"
    with open(file_path, "w", encoding="gbk") as f:
        f.write(gbk_content)
    try:
        result = await handle_write({
            "file_path": file_path,
            "content": gbk_content,
            "backup": False,
        })
        _assert_success(result)
        assert "编码: gbk" in result["message"]

        with open(file_path, "rb") as f:
            raw = f.read()
        raw.decode("gbk")  # 不应抛异常
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_write_format_after():
    tmp_dir = tempfile.mkdtemp()
    file_path = os.path.join(tmp_dir, "TestUnit.pas")
    _make_file(file_path, "unit  TestUnit ;\nbegin\nend.")
    try:
        with patch("src.tools.file_tool.pasfmt.format_file",
                   new_callable=AsyncMock) as mock_fmt:
            mock_fmt.return_value = {
                "status": "success", "formatted": True,
                "message": "ok"
            }
            result = await handle_write({
                "file_path": file_path,
                "content": "unit TestUnit;\nbegin\nend.\n",
                "backup": False,
                "format_after_write": True,
            })
            _assert_success(result)
            mock_fmt.assert_called_once()
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ============================================================
# handle_backup
# ============================================================

@pytest.mark.asyncio
async def test_backup_create():
    tmp_dir = tempfile.mkdtemp()
    file_path = os.path.join(tmp_dir, "test.pas")
    _make_file(file_path, "hello")
    try:
        result = await handle_backup({
            "file_path": file_path,
            "backup_action": "create",
        })
        _assert_success(result)
        assert "备份已创建" in result["message"]
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_backup_list():
    tmp_dir = tempfile.mkdtemp()
    file_path = os.path.join(tmp_dir, "test.pas")
    _make_file(file_path, "v1")
    history_dir = os.path.join(tmp_dir, "__history")
    try:
        await handle_backup({"file_path": file_path, "backup_action": "create"})
        with open(file_path, "w") as f:
            f.write("v2")
        await handle_backup({"file_path": file_path, "backup_action": "create"})

        result = await handle_backup({
            "file_path": file_path,
            "backup_action": "list",
        })
        _assert_success(result)
        assert "备份数: 2" in result["message"]
    finally:
        shutil.rmtree(history_dir, ignore_errors=True)
        shutil.rmtree(tmp_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_backup_restore():
    tmp_dir = tempfile.mkdtemp()
    file_path = os.path.join(tmp_dir, "test.pas")
    _make_file(file_path, "original")
    history_dir = os.path.join(tmp_dir, "__history")
    try:
        await handle_backup({"file_path": file_path, "backup_action": "create"})
        with open(file_path, "w") as f:
            f.write("modified")
        result = await handle_backup({
            "file_path": file_path,
            "backup_action": "restore",
        })
        _assert_success(result)
        assert "已从" in result["message"]
        with open(file_path, "r") as f:
            assert f.read() == "original"
    finally:
        shutil.rmtree(history_dir, ignore_errors=True)
        shutil.rmtree(tmp_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_backup_restore_specific_version():
    tmp_dir = tempfile.mkdtemp()
    file_path = os.path.join(tmp_dir, "test.pas")
    _make_file(file_path, "v1")
    history_dir = os.path.join(tmp_dir, "__history")
    try:
        from src.utils.file_backup import create_backup
        create_backup(file_path)
        with open(file_path, "w") as f:
            f.write("v2")
        create_backup(file_path)
        with open(file_path, "w") as f:
            f.write("v3")

        result = await handle_backup({
            "file_path": file_path,
            "backup_action": "restore",
            "version": 1,
        })
        _assert_success(result)
        with open(file_path, "r") as f:
            assert f.read() == "v1"
    finally:
        shutil.rmtree(history_dir, ignore_errors=True)
        shutil.rmtree(tmp_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_backup_missing_file_path():
    result = await handle_backup({"backup_action": "create"})
    _assert_error(result)


@pytest.mark.asyncio
async def test_backup_list_empty():
    tmp_dir = tempfile.mkdtemp()
    file_path = os.path.join(tmp_dir, "nobackups.pas")
    _make_file(file_path, "hello")
    try:
        result = await handle_backup({
            "file_path": file_path,
            "backup_action": "list",
        })
        _assert_success(result)  # 空列表也是成功
        assert "没有找到" in result["message"]
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ============================================================
# handle_format (error paths)
# ============================================================

@pytest.mark.asyncio
async def test_format_missing_file_path():
    result = await handle_format({})
    _assert_error(result)


@pytest.mark.asyncio
async def test_format_nonexistent_file():
    result = await handle_format({
        "file_path": r"C:\nonexistent.pas",
    })
    assert isinstance(result, dict)


# ============================================================
# handle_file_tool — 主入口路由
# ============================================================

@pytest.mark.asyncio
async def test_main_entry_read():
    result = await handle_file_tool({"action": "read", "file_path": "/nonexistent"})
    assert isinstance(result, dict)


@pytest.mark.asyncio
async def test_main_entry_write():
    tmp_dir = tempfile.mkdtemp()
    file_path = os.path.join(tmp_dir, "test.pas")
    try:
        result = await handle_file_tool({
            "action": "write",
            "file_path": file_path,
            "content": "unit Test;\nbegin\nend.\n",
            "backup": False,
        })
        _assert_success(result)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_main_entry_backup():
    tmp_dir = tempfile.mkdtemp()
    file_path = os.path.join(tmp_dir, "test.pas")
    _make_file(file_path, "data")
    try:
        result = await handle_file_tool({
            "action": "backup",
            "file_path": file_path,
            "backup_action": "create",
        })
        _assert_success(result)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_main_entry_unknown_action():
    result = await handle_file_tool({"action": "nonexistent"})
    _assert_error(result)
    assert "未知 action" in result["message"]


@pytest.mark.asyncio
async def test_main_entry_default_action_is_read():
    result = await handle_file_tool({"file_path": "test.pas"})
    assert isinstance(result, dict)
