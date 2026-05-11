"""
Delphi 版本号与名称映射工具

提供统一的版本名称查询，避免多处重复定义。
所有新旧版本映射应集中在此维护。
"""

# 注册表版本键 → 产品名称（完整映射）
DELPHI_VERSION_NAMES: dict[str, str] = {
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

# .dproj 版本前缀(整数部分) → 产品名称
# 用于 get_compiler_for_project 匹配编译器
PROJECT_VERSION_PREFIX_MAP: dict[str, str] = {
    "37": "Delphi 13 Florence",
    "23": "Delphi 12 Athens",
    "22": "Delphi 11 Alexandria",
    "21": "Delphi 10.4 Sydney",
    "20": "Delphi 10.3 Rio",
    "19": "Delphi 10.2 Tokyo",
    "18": "Delphi 10.1 Berlin",
    "17": "Delphi 10 Seattle",
    "16": "Delphi XE8",
    "15": "Delphi XE7",
    "14": "Delphi XE6",
    "12": "Delphi XE5",
    "11": "Delphi XE4",
    "10": "Delphi XE3",
    "9": "Delphi XE2",
    "8": "Delphi XE",
}


def get_version_name(version_key: str) -> str:
    """根据版本号键获取 Delphi 产品名称"""
    return DELPHI_VERSION_NAMES.get(version_key, f"Delphi {version_key}")


def get_version_name_from_path(delphi_path: str) -> str:
    """从安装路径（末尾含版本号）提取版本并获取名称"""
    import re
    path = delphi_path.rstrip("\\/")
    match = re.search(r"(\d+\.\d+)$", path)
    if not match:
        return "Delphi Unknown"
    return get_version_name(match.group(1))


def get_project_version_name(version_prefix: str) -> str | None:
    """根据 .dproj 版本前缀获取 Delphi 产品名称"""
    return PROJECT_VERSION_PREFIX_MAP.get(version_prefix)
