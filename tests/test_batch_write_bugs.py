#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""batch_write edge case tests."""

import sys, os, tempfile, shutil
from pathlib import Path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
import pytest
from src.tools.file_tool import handle_batch_write


def _mf(path, txt):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(txt)


def _ok(r):
    assert r.get("status") == "success", f"expected success, got: {r}"


# --- Bug 1: content includes original text -> duplicate ---


@pytest.mark.asyncio
async def test_insert_keeps_original_no_dup():
    """[4,5) replace F1, content has F1+new line -> no dup"""
    d = tempfile.mkdtemp(prefix="b1_")
    try:
        f = os.path.join(d, "U.pas")
        _mf(f, "unit U;\ninterface\ntype\n  T=class\n    F1: Integer;\n    F2: String;\n  end;\nimplementation\nend.\n")
        r = await handle_batch_write({"file_path": f, "edits": [
            {"start_line": 4, "end_line": 5, "content": "    F1: Integer;\n    F1b: Boolean;", "description": "add"},
        ], "backup": False})
        _ok(r)
        with open(f) as fh:
            c = fh.read()
        assert c.count("F1: Integer") == 1, f"F1 dup:\n{c}"
    finally:
        shutil.rmtree(d, ignore_errors=True)


@pytest.mark.asyncio
async def test_insert_adjacent_no_dup():
    """adjacent [5,6)+[6,7), content has original -> no dup"""
    d = tempfile.mkdtemp(prefix="b1a_")
    try:
        f = os.path.join(d, "U.pas")
        _mf(f, "unit U;\ninterface\ntype\n  T=class\n    F1: Integer;\n    F2: String;\n    procedure Bar;\n  end;\nimplementation\nend.\n")
        r = await handle_batch_write({"file_path": f, "edits": [
            {"start_line": 5, "end_line": 6, "content": "    F2: String;\n    F2b: Boolean;", "description": "add after F2"},
            {"start_line": 6, "end_line": 7, "content": "    procedure Bar;", "description": "keep Bar"},
        ], "backup": False})
        _ok(r)
        with open(f) as fh:
            c = fh.read()
        assert c.count("F2: String") == 1, f"F2 dup:\n{c}"
        assert c.count("procedure Bar") == 1, f"Bar dup:\n{c}"
        assert "F2b: Boolean" in c
    finally:
        shutil.rmtree(d, ignore_errors=True)


@pytest.mark.asyncio
async def test_insert_end_line_none_no_dup():
    """end_line=None, content has original -> no dup, ends with end."""
    d = tempfile.mkdtemp(prefix="b1b_")
    try:
        f = os.path.join(d, "U.pas")
        _mf(f, "unit U;\ninterface\ntype\n  T=class\n    F1: Integer;\n    F2: String;\n  end;\nend.\n")
        r = await handle_batch_write({"file_path": f, "edits": [
            {"start_line": 4, "content": "    F1: Integer;\n    F1b: Boolean;\n  end;\nend.", "description": "F1 to EOF"},
        ], "backup": False})
        _ok(r)
        with open(f) as fh:
            c = fh.read()
        assert c.count("F1: Integer") == 1, f"F1 dup:\n{c}"
        assert c.rstrip().endswith("end."), f"no end.:\n{c}"
    finally:
        shutil.rmtree(d, ignore_errors=True)


# --- Bug 2: end. handling ---


@pytest.mark.asyncio
async def test_enddot_after_edit():
    """edit near end, nothing after end."""
    d = tempfile.mkdtemp(prefix="b2_")
    try:
        f = os.path.join(d, "U.pas")
        _mf(f, "unit U;\ninterface\nimplementation\n\nprocedure Foo;\nbegin\nend;\n\nend.\n")
        r = await handle_batch_write({"file_path": f, "edits": [
            {"start_line": 4, "end_line": 7, "content": "procedure Foo;\nbegin\n  // work\nend;", "description": "edit Foo"},
        ], "backup": False})
        _ok(r)
        with open(f) as fh:
            c = fh.read()
        rest = c[c.rfind("end.") + 4:].strip()
        assert rest == "", f"after end.:\n{c}"
    finally:
        shutil.rmtree(d, ignore_errors=True)


@pytest.mark.asyncio
async def test_enddot_adjacent_edits():
    """multiple edits, end. not duplicated"""
    d = tempfile.mkdtemp(prefix="b2a_")
    try:
        f = os.path.join(d, "U.pas")
        _mf(f, "unit U;\ninterface\nimplementation\n\nprocedure A;\nbegin\nend;\n\nprocedure B;\nbegin\nend;\n\nend.\n")
        r = await handle_batch_write({"file_path": f, "edits": [
            {"start_line": 4, "end_line": 7, "content": "procedure A;\nbegin\n  // A\nend;", "description": "edit A"},
            {"start_line": 8, "end_line": 11, "content": "procedure B;\nbegin\n  // B\nend;", "description": "edit B"},
        ], "backup": False})
        _ok(r)
        with open(f) as fh:
            c = fh.read()
        rest = c[c.rfind("end.") + 4:].strip()
        assert rest == "", f"after end.:\n{c}"
        assert c.count("end.") == 1
    finally:
        shutil.rmtree(d, ignore_errors=True)


@pytest.mark.asyncio
async def test_enddot_replace_tail():
    """replace tail including end., content ends with end. -> clean"""
    d = tempfile.mkdtemp(prefix="b2c_")
    try:
        f = os.path.join(d, "U.pas")
        _mf(f, "unit U;\ninterface\nimplementation\n\nprocedure Foo;\nbegin\nend;\n\nend.\n")
        r = await handle_batch_write({"file_path": f, "edits": [
            {"start_line": 7, "end_line": 9, "content": "procedure Foo;\nbegin\n  Work;\nend;\n\nend.", "description": "replace tail"},
        ], "backup": False})
        _ok(r)
        with open(f) as fh:
            c = fh.read()
        rest = c[c.rfind("end.") + 4:].strip()
        assert rest == "", f"after end.:\n{c}"
        assert c.count("end.") == 1
    finally:
        shutil.rmtree(d, ignore_errors=True)


@pytest.mark.asyncio
async def test_enddot_no_trailing_newline():
    """original file no trailing \n -> clean after end."""
    d = tempfile.mkdtemp(prefix="b2d_")
    try:
        f = os.path.join(d, "U.pas")
        _mf(f, "unit U;\ninterface\nimplementation\n\nprocedure Foo;\nbegin\nend;\n\nend.")
        r = await handle_batch_write({"file_path": f, "edits": [
            {"start_line": 4, "end_line": 7, "content": "procedure Foo;\nbegin\n  Work;\nend;", "description": "edit Foo"},
        ], "backup": False})
        _ok(r)
        with open(f) as fh:
            c = fh.read()
        rest = c[c.rfind("end.") + 4:].strip()
        assert rest == "", f"after end.:\n{c}"
    finally:
        shutil.rmtree(d, ignore_errors=True)


@pytest.mark.asyncio
async def test_enddot_delete_empty_before():
    """delete empty line before end. -> end. remains"""
    d = tempfile.mkdtemp(prefix="b2e_")
    try:
        f = os.path.join(d, "U.pas")
        _mf(f, "unit U;\n\ninterface\n\nimplementation\n\nprocedure Foo;\nbegin\nend;\n\nend.\n")
        r = await handle_batch_write({"file_path": f, "edits": [
            {"start_line": 9, "end_line": 10, "content": "", "description": "del empty before end."},
        ], "backup": False})
        _ok(r)
        with open(f) as fh:
            c = fh.read()
        rest = c[c.rfind("end.") + 4:].strip()
        assert rest == "", f"after end.:\n{c}"
        assert c.count("end.") == 1
    finally:
        shutil.rmtree(d, ignore_errors=True)


@pytest.mark.asyncio
async def test_enddot_delete_enddot_line():
    """replace tail including end. -> no orphan code"""
    d = tempfile.mkdtemp(prefix="b2f_")
    try:
        f = os.path.join(d, "U.pas")
        _mf(f, "unit U;\ninterface\nimplementation\n\nprocedure Foo;\nbegin\nend;\n\nend.\n")
        r = await handle_batch_write({"file_path": f, "edits": [
            {"start_line": 7, "end_line": 9, "content": "  Work;\nend;\n\nend.", "description": "replace tail incl end."},
        ], "backup": False})
        _ok(r)
        with open(f) as fh:
            c = fh.read()
        rest = c[c.rfind("end.") + 4:].strip()
        assert rest == "", f"after end.:\n{c}"
        assert c.count("end.") == 1
    finally:
        shutil.rmtree(d, ignore_errors=True)

@pytest.mark.asyncio
async def test_sanity_warn_on_dup_first_line():
    """content 首行与被替换行相同 → ⚠️ 警告出现（但写入仍然成功）"""
    d = tempfile.mkdtemp(prefix="warn_")
    try:
        f = os.path.join(d, "U.pas")
        _mf(f, "unit U;\ninterface\ntype\n  T=class\n    F1: Integer;\n  end;\nend.\n")
        r = await handle_batch_write({"file_path": f, "edits": [
            {"start_line": 4, "end_line": 5, "content": "    F1: Integer;\n    F1b: Boolean;", "description": "保留F1加字段"},
        ], "backup": False})
        assert r.get("status") == "success", f"应成功但返回了:\n{r}"
        msg = r.get("message", "")
        assert "⚠️" in msg, f"期望警告但未出现:\n{msg}"
        assert "content 首行" in msg, f"错误信息缺少原因:\n{msg}"
        # 文件应有 F1 且无重复
        with open(f) as fh:
            c = fh.read()
        assert c.count("F1: Integer") == 1, f'F1 dup:\n{c}'
        assert "F1b: Boolean" in c, f'缺少 F1b:\n{c}'
    finally:
        shutil.rmtree(d, ignore_errors=True)


@pytest.mark.asyncio
async def test_force_bypasses_dup_first_line():
    """force=true 时跳过 content 首行重复检查"""
    d = tempfile.mkdtemp(prefix="force_")
    try:
        f = os.path.join(d, "U.pas")
        _mf(f, "unit U;\ninterface\ntype\n  T=class\n    F1: Integer;\n  end;\nend.\n")
        r = await handle_batch_write({"file_path": f, "edits": [
            {"start_line": 4, "end_line": 5, "content": "    F1: Integer;\n    F1b: Boolean;", "description": "保留F1加字段"},
        ], "backup": False, "force": True})
        assert r.get("status") == "success", f"force=true 应允许写入:\n{r}"
        # 文件应正常写入，无重复
        with open(f) as fh:
            c = fh.read()
        assert c.count("F1: Integer") == 1, f'F1 dup:\n{c}'
        assert "F1b: Boolean" in c, f'缺少 F1b:\n{c}'
    finally:
        shutil.rmtree(d, ignore_errors=True)


@pytest.mark.asyncio
async def test_post_merge_dup_detection():
    """编辑后产生连续重复行 → 阻止写入"""
    d = tempfile.mkdtemp(prefix="dup_merge_")
    try:
        f = os.path.join(d, "U.pas")
        _mf(f, "unit U;\ninterface\ntype\n  T=class\n    F1: Integer;\n    F2: String;\n  end;\nend.\n")
        with open(f) as fh:
            original = fh.read()
        # 两个 edit 相邻且第一个的 content 末尾与第二个的 content 开头相同 → 产生边界重复
        r = await handle_batch_write({"file_path": f, "edits": [
            {"start_line": 4, "end_line": 5, "content": "    F1: Integer;\n    Extra: Boolean;", "description": "edit F1"},
            {"start_line": 5, "end_line": 6, "content": "    Extra: Boolean;\n    F2: String;", "description": "edit F2"},
        ], "backup": False})
        assert r.get("status") == "failed", f"应检测到重复行:\n{r}"
        msg = r.get("message", "")
        assert "连续重复" in msg, f"错误信息不匹配:\n{msg}"
        # 文件不应被修改
        with open(f) as fh:
            c = fh.read()
        assert c == original, f"文件被意外修改:\n原内容:\n{original}\n当前:\n{c}"
    finally:
        shutil.rmtree(d, ignore_errors=True)


@pytest.mark.asyncio
async def test_force_bypasses_post_merge_dup():
    """force=true 时跳过最终结果重复检查"""
    d = tempfile.mkdtemp(prefix="dup_force_")
    try:
        f = os.path.join(d, "U.pas")
        _mf(f, "unit U;\ninterface\ntype\n  T=class\n    F1: Integer;\n    F2: String;\n  end;\nend.\n")
        r = await handle_batch_write({"file_path": f, "edits": [
            {"start_line": 4, "end_line": 5, "content": "    F1: Integer;\n    Extra: Boolean;", "description": "edit F1"},
            {"start_line": 5, "end_line": 6, "content": "    Extra: Boolean;\n    F2: String;", "description": "edit F2"},
        ], "backup": False, "force": True})
        assert r.get("status") == "success", f"force=true 应跳过重复检测:\n{r}"
    finally:
        shutil.rmtree(d, ignore_errors=True)

