#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Delphi 版本映射工具测试
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.utils.delphi_versions import (
    DELPHI_VERSION_NAMES,
    PROJECT_VERSION_PREFIX_MAP,
    get_version_name,
    get_version_name_from_path,
    get_project_version_name,
)


def test_all_known_versions_have_names():
    """所有已知版本号都有对应的产品名称"""
    known = {
        "37.0": "Delphi 13 Florence",
        "23.0": "Delphi 12 Athens",
        "22.0": "Delphi 11 Alexandria",
        "21.0": "Delphi 10.4 Sydney",
        "20.0": "Delphi 10.3 Rio",
        "19.0": "Delphi 10.2 Tokyo",
        "18.0": "Delphi 10.1 Berlin",
        "17.0": "Delphi 10 Seattle",
        "16.0": "Delphi XE8",
        "15.0": "Delphi XE7",
        "14.0": "Delphi XE6",
        "12.0": "Delphi XE5",
        "11.0": "Delphi XE4",
        "10.0": "Delphi XE3",
        "9.0": "Delphi XE2",
        "8.0": "Delphi XE",
        "7.0": "Delphi 2010",
        "6.0": "Delphi 2009",
        "5.0": "Delphi 2007",
        "4.0": "Delphi 2006",
        "3.0": "Delphi 2005",
    }
    for ver, expected_name in known.items():
        assert DELPHI_VERSION_NAMES[ver] == expected_name, f"{ver} → {expected_name}"
    assert len(DELPHI_VERSION_NAMES) == len(known)


def test_get_version_name():
    """get_version_name 的已知版本和未知版本回退"""
    assert get_version_name("37.0") == "Delphi 13 Florence"
    assert get_version_name("22.0") == "Delphi 11 Alexandria"
    assert get_version_name("99.0") == "Delphi 99.0"  # 未知版本回退


def test_get_version_name_from_path():
    """从安装路径提取版本号"""
    assert get_version_name_from_path(r"C:\Program Files\Embarcadero\Studio\22.0") == "Delphi 11 Alexandria"
    assert get_version_name_from_path(r"C:\Program Files\Embarcadero\Studio\23.0\\") == "Delphi 12 Athens"
    # 不含版本号的路径
    assert get_version_name_from_path(r"C:\Delphi") == "Delphi Unknown"


def test_get_project_version_name():
    """项目版本前缀映射"""
    assert get_project_version_name("22") == "Delphi 11 Alexandria"
    assert get_project_version_name("37") == "Delphi 13 Florence"
    assert get_project_version_name("99") is None  # 未知前缀


def test_project_prefix_map_completeness():
    """每个已知版本在 PROJECT_VERSION_PREFIX_MAP 中都有对应的前缀条目（13除外）"""
    for full_key in ("37", "23", "22", "21", "20", "19", "18", "17",
                     "16", "15", "14", "12", "11", "10", "9", "8"):
        assert full_key in PROJECT_VERSION_PREFIX_MAP, f"缺少前缀 {full_key}"
    # 确保不存在的版本（如"13"）没有被错误包含
    assert "13" not in PROJECT_VERSION_PREFIX_MAP


def test_project_prefix_no_unexpected_entries():
    """PROJECT_VERSION_PREFIX_MAP 中不应有不存在的虚拟版本（XE10、XE9 等）"""
    for prefix, name in PROJECT_VERSION_PREFIX_MAP.items():
        assert "XE10" not in name, f"不应存在虚拟版本 XE10: {prefix} → {name}"
        assert "XE9" not in name, f"不应存在虚拟版本 XE9: {prefix} → {name}"
        assert "XE8" not in name or prefix in ("16",), f"XE8 只应出现在 16: {prefix} → {name}"


def test_name_consistency():
    """同一版本在 DELPHI_VERSION_NAMES 和 PROJECT_VERSION_PREFIX_MAP 中名称一致"""
    for prefix, name in PROJECT_VERSION_PREFIX_MAP.items():
        full_key = prefix + ".0"
        if full_key in DELPHI_VERSION_NAMES:
            assert DELPHI_VERSION_NAMES[full_key] == name, \
                f"版本 {prefix} 在两份映射中的名称不一致: {DELPHI_VERSION_NAMES[full_key]} vs {name}"
