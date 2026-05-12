#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
验证器 (Validator class) 测试
"""

import sys
import os
import tempfile
import shutil
from pathlib import Path

project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.utils.validator import Validator


def test_validate_compiler_path_valid():
    python_exe = sys.executable
    ok, msg = Validator.validate_compiler_path(python_exe)
    assert ok, f"expected valid: {msg}"


def test_validate_compiler_path_nonexistent():
    ok, msg = Validator.validate_compiler_path(r"C:\nonexistent\dcc32.exe")
    assert not ok
    assert "不存在" in msg


def test_validate_compiler_path_empty():
    ok, msg = Validator.validate_compiler_path("")
    assert not ok


def test_validate_compiler_path_dotdot():
    ok, msg = Validator.validate_compiler_path(r"C:\..\dcc32.exe")
    assert not ok


def test_validate_project_path_valid():
    tmp = tempfile.NamedTemporaryFile(suffix='.dproj', delete=False)
    tmp.close()
    try:
        ok, msg = Validator.validate_project_path(tmp.name)
        assert ok, f"expected valid: {msg}"
    finally:
        os.unlink(tmp.name)


def test_validate_project_path_nonexistent():
    ok, msg = Validator.validate_project_path(r"C:\nonexistent.dproj")
    assert not ok


def test_validate_project_path_empty():
    ok, msg = Validator.validate_project_path("")
    assert not ok


def test_validate_output_path():
    tmpdir = tempfile.mkdtemp()
    try:
        ok, msg = Validator.validate_output_path(tmpdir)
        assert ok, f"expected valid: {msg}"
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_validate_output_path_nonexistent():
    ok, msg = Validator.validate_output_path(r"C:\nonexistent_output_dir")
    assert not ok
    assert "不存在" in msg


def test_validate_search_paths_empty():
    ok, msg = Validator.validate_search_paths([])
    assert ok


def test_validate_search_paths_valid():
    tmpdir = tempfile.mkdtemp()
    try:
        ok, msg = Validator.validate_search_paths([tmpdir])
        assert ok
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_validate_search_paths_dotdot():
    ok, msg = Validator.validate_search_paths([r"C:\..\bad"])
    assert not ok


def test_validate_timeout_valid():
    ok, msg = Validator.validate_timeout(30)
    assert ok


def test_validate_timeout_zero():
    ok, msg = Validator.validate_timeout(0)
    assert not ok


def test_validate_timeout_too_large():
    ok, msg = Validator.validate_timeout(9999)
    assert not ok


def test_validate_warning_level_valid():
    ok, msg = Validator.validate_warning_level(2)
    assert ok


def test_validate_warning_level_out_of_range():
    ok, msg = Validator.validate_warning_level(5)
    assert not ok
