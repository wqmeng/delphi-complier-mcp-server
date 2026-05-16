#!/usr/bin/env python3
"""Daofy MCP Server 安装/卸载脚本 - 配置 AI Agent"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

MCP_SERVER_NAME = "daofy-delphi-mcp-server"
LEGACY_SERVER_NAME = "delphi-compiler"


def _enable_ansi() -> bool:
    """启用 Windows CMD ANSI 支持，返回是否成功"""
    if sys.platform != "win32":
        return True
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        for handle_id in (-11, -12):
            handle = kernel32.GetStdHandle(handle_id)
            mode = ctypes.c_ulong()
            if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
                kernel32.SetConsoleMode(handle, mode.value | 0x0004)
        return True
    except Exception:
        return False


_HAS_COLOR = _enable_ansi()

# ANSI 颜色
GREEN = "\033[92m" if _HAS_COLOR else ""
YELLOW = "\033[93m" if _HAS_COLOR else ""
RED = "\033[91m" if _HAS_COLOR else ""
CYAN = "\033[96m" if _HAS_COLOR else ""
GRAY = "\033[90m" if _HAS_COLOR else ""
RESET = "\033[0m" if _HAS_COLOR else ""


def cprint(msg: str, color: str = "") -> None:
    print(f"{color}{msg}{RESET}")


def success(msg: str) -> None:
    cprint(f"[SUCCESS] {msg}", GREEN)


def info(msg: str) -> None:
    cprint(msg, CYAN)


def warn(msg: str) -> None:
    cprint(f"[WARNING] {msg}", YELLOW)


def error(msg: str) -> None:
    cprint(f"[ERROR] {msg}", RED)


def separator(title: str = "") -> None:
    line = "=" * 60
    if title:
        cprint(line, CYAN)
        cprint(f"  {title}", CYAN)
        cprint(line, CYAN)
    else:
        cprint(line, CYAN)


def get_script_dir() -> Path:
    return Path(__file__).resolve().parent


def get_python_exe() -> str:
    venv = get_script_dir() / "venv" / "Scripts" / "python.exe"
    if venv.exists():
        return str(venv)
    return sys.executable


# ============================================================
# JSON 读写
# ============================================================

def read_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def write_json(path: str, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def is_mcp_configured(config_path: str, server_name: str, config_type: str) -> bool:
    if not os.path.exists(config_path):
        return False
    try:
        data = read_json(config_path)
        node_key = "mcp" if config_type == "OpenCode" else "mcpServers"
        node = data.get(node_key, {})
        return server_name in node
    except Exception:
        return False


def is_mcp_configured_any(config_path: str, config_type: str) -> bool:
    return (
        is_mcp_configured(config_path, MCP_SERVER_NAME, config_type)
        or is_mcp_configured(config_path, LEGACY_SERVER_NAME, config_type)
    )


def add_mcp_config(config_path: str, server_name: str, mcp_config: dict, config_type: str) -> None:
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    if os.path.exists(config_path):
        data = read_json(config_path)
    else:
        data = {}
    node_key = "mcp" if config_type == "OpenCode" else "mcpServers"
    if node_key not in data:
        data[node_key] = {}
    data[node_key][server_name] = mcp_config
    write_json(config_path, data)


def remove_mcp_config(config_path: str, server_name: str, config_type: str) -> bool:
    if not os.path.exists(config_path):
        return False
    data = read_json(config_path)
    node_key = "mcp" if config_type == "OpenCode" else "mcpServers"
    node = data.get(node_key, {})
    if server_name not in node:
        return False
    del node[server_name]
    write_json(config_path, data)
    return True


# ============================================================
# AI Agent 检测
# ============================================================

def _env(name: str) -> str:
    return os.environ.get(name, "")


def _userprofile() -> str:
    return _env("USERPROFILE") or _env("HOME") or str(Path.home())


def _detect_path(paths: list[str]) -> str | None:
    for p in paths:
        if p and os.path.exists(p):
            return p
    return None


AGENT_DEFINITIONS = {
    "Claude Desktop": {
        "config_type": "Standard",
        "doc_url": "https://support.claude.com/en/articles/10949351",
        "config_path": lambda: os.path.join(_env("APPDATA"), "Claude", "claude_desktop_config.json"),
        "detect_paths": lambda: [
            os.path.join(_env("LOCALAPPDATA"), "Programs", "Claude", "Claude.exe"),
            os.path.join(_env("ProgramFiles"), "Claude", "Claude.exe"),
        ],
    },
    "Trae": {
        "config_type": "Standard",
        "doc_url": "https://docs.trae.ai/ide/add-mcp-servers",
        "config_path": lambda: (
            p if os.path.exists(p := os.path.join(_userprofile(), ".trae-cn", "mcp_config.json"))
            else os.path.join(_userprofile(), ".trae", "mcp_config.json")
        ),
        "detect_paths": lambda: [
            os.path.join(_env("LOCALAPPDATA"), "Programs", "Trae", "Trae.exe"),
            os.path.join(_env("ProgramFiles"), "Trae", "Trae.exe"),
        ],
    },
    "CodeArts Agent": {
        "config_type": "Standard",
        "modes": ["project"],
        "doc_url": "https://support.huaweicloud.com/usermanual-codeartssnap/codeartsdoer_ug_0010.html",
        "config_path": lambda: (
            p if os.path.exists(p := os.path.join(str(get_script_dir()), ".codeartsdoer", "mcp", "mcp_settings.json"))
            else os.path.join(_userprofile(), ".codeartsdoer", "mcp", "mcp_settings.json")
        ),
        "detect_paths": lambda: [
            os.path.join(_env("LOCALAPPDATA"), "Programs", "CodeArts", "CodeArts.exe"),
            os.path.join(_env("ProgramFiles"), "CodeArts", "CodeArts.exe"),
            os.path.join(_env("APPDATA"), "codearts-agent"),
        ],
    },
    "Cursor": {
        "config_type": "Standard",
        "doc_url": "https://cursor.com/help/customization/mcp",
        "config_path": lambda: os.path.join(_userprofile(), ".cursor", "mcp.json"),
        "detect_paths": lambda: [
            os.path.join(_env("LOCALAPPDATA"), "Programs", "Cursor", "Cursor.exe"),
            os.path.join(_env("ProgramFiles"), "Cursor", "Cursor.exe"),
            os.path.join(_env("APPDATA"), "Cursor"),
        ],
    },
    "OpenCode": {
        "config_type": "OpenCode",
        "modes": ["global", "project"],
        "doc_url": "https://mintlify.com/opencode-ai/opencode/core-concepts/configuration",
        "config_path": lambda: (
            p if os.path.exists(p := os.path.join(_userprofile(), ".config", "opencode", "opencode.json"))
            else os.path.join(_userprofile(), ".opencode.json")
        ),
        "project_config_relpath": ".opencode.json",
        "detect_paths": lambda: [],
        "detect_command": lambda: shutil.which("opencode") is not None,
    },
    "Windsurf": {
        "config_type": "Standard",
        "doc_url": "https://docs.open.cx/mcp/clients/windsurf",
        "config_path": lambda: os.path.join(_userprofile(), ".codeium", "windsurf", "mcp_config.json"),
        "detect_paths": lambda: [
            os.path.join(_env("LOCALAPPDATA"), "Programs", "Windsurf", "Windsurf.exe"),
            os.path.join(_env("ProgramFiles"), "Windsurf", "Windsurf.exe"),
            os.path.join(_env("APPDATA"), "Windsurf"),
        ],
    },
    "Cline": {
        "config_type": "Standard",
        "doc_url": "https://docs.cline.bot/getting-started/config",
        "config_path": lambda: (
            p if os.path.exists(p := os.path.join(_userprofile(), ".cline", "data", "settings", "cline_mcp_settings.json"))
            else os.path.join(_env("APPDATA"), "Code", "User", "globalStorage",
                              "saoudrizwan.claude-dev", "settings", "cline_mcp_settings.json")
        ),
        "detect_paths": lambda: [],
        "detect_vscode_ext": lambda: "saoudrizwan.claude-dev",
    },
    "Roo Code": {
        "config_type": "Standard",
        "doc_url": "",
        "config_path": lambda: os.path.join(_userprofile(), ".roo", "mcp.json"),
        "detect_paths": lambda: [],
        "detect_vscode_ext": lambda: "rooveterinaryinc.roo-cline",
    },
    "通义灵码": {
        "config_type": "Standard",
        "doc_url": "",
        "config_path": lambda: os.path.join(_userprofile(), ".tongyi", "mcp.json"),
        "detect_paths": lambda: [],
        "detect_vscode_ext": lambda: "tongyi",
        "experimental": True,
    },
    "豆包": {
        "config_type": "Standard",
        "doc_url": "",
        "config_path": lambda: os.path.join(_userprofile(), ".doubao", "mcp.json"),
        "detect_paths": lambda: [
            os.path.join(_env("LOCALAPPDATA"), "Programs", "Doubao", "Doubao.exe"),
        ],
        "experimental": True,
    },
    "Kimi": {
        "config_type": "Standard",
        "doc_url": "https://moonshotai.github.io/kimi-cli/zh/customization/mcp.html",
        "config_path": lambda: os.path.join(_userprofile(), ".kimi", "mcp.json"),
        "detect_paths": lambda: [
            os.path.join(_env("LOCALAPPDATA"), "Programs", "Kimi", "Kimi.exe"),
        ],
        "experimental": True,
    },
    "智谱清言": {
        "config_type": "Standard",
        "doc_url": "",
        "config_path": lambda: os.path.join(_userprofile(), ".chatglm", "mcp.json"),
        "detect_paths": lambda: [
            os.path.join(_env("LOCALAPPDATA"), "Programs", "ChatGLM", "ChatGLM.exe"),
        ],
        "experimental": True,
    },
}


def _get_project_relative_config_path(agent_name: str, agent_defn: dict | None = None) -> str:
    """获取项目级 Agent 在项目目录下的相对配置文件路径"""
    # 优先从 agent 定义中的 project_config_relpath 读取
    if agent_defn and agent_defn.get("project_config_relpath"):
        return agent_defn["project_config_relpath"]
    # 静态映射兜底
    mapping: dict[str, str] = {
        "CodeArts Agent": os.path.join(".codeartsdoer", "mcp", "mcp_settings.json"),
        "OpenCode": ".opencode.json",
    }
    return mapping.get(agent_name, "")


def _check_vscode_ext(pattern: str) -> bool:
    ext_dir = os.path.join(_userprofile(), ".vscode", "extensions")
    if not os.path.isdir(ext_dir):
        return False
    for d in os.listdir(ext_dir):
        if pattern.lower() in d.lower():
            return True
    return False


def detect_agents() -> list[dict]:
    results = []
    for name, defn in AGENT_DEFINITIONS.items():
        installed = False
        install_path = None

        paths = defn.get("detect_paths", lambda: [])()
        install_path = _detect_path(paths)
        if install_path:
            installed = True

        if not installed and defn.get("detect_command", lambda: False)():
            installed = True
            install_path = shutil.which("opencode") or "CLI"

        ext_pattern = defn.get("detect_vscode_ext", None)
        if not installed and ext_pattern and _check_vscode_ext(ext_pattern):
            installed = True

        config_path = defn["config_path"]()
        if not installed and os.path.exists(config_path):
            installed = True
            install_path = install_path or "Unknown"

        experimental = defn.get("experimental", False)
        results.append({
            "name": name,
            "installed": installed,
            "path": install_path,
            "config_path": config_path,
            "config_type": defn["config_type"],
            "modes": defn.get("modes", ["global"]),
            "project_config_relpath": defn.get("project_config_relpath", ""),
            "doc_url": defn["doc_url"],
            "experimental": experimental,
        })
    return results


# ============================================================
# MCP 配置生成
# ============================================================

def get_mcp_config(python_exe: str, config_type: str, project_dir: str = "") -> dict:
    script_dir = str(get_script_dir())
    server_script = os.path.join(script_dir, "src", "server.py")
    cwd = project_dir if project_dir and os.path.isdir(project_dir) else script_dir

    if config_type == "OpenCode":
        # OpenCode McpLocalConfig: command 是数组（包含命令和参数），无 args/cwd
        return {
            "type": "local",
            "command": [python_exe, server_script],
            "environment": {
                "PYTHONIOENCODING": "utf-8",
                "PYTHONUNBUFFERED": "1",
                "PYTHONUTF8": "1",
            },
        }
    else:
        return {
            "command": python_exe,
            "args": [server_script],
            "cwd": cwd,
            "env": {
                "PYTHONUNBUFFERED": "1",
                "PYTHONIOENCODING": "utf-8",
                "PYTHONUTF8": "1",
            },
        }


# ============================================================
# 交互选择
# ============================================================

# ============================================================
# 安装
# ============================================================

def do_install(python_exe: str, project_dir: str = "", agent_filter: str = "All", force: bool = False) -> None:
    separator("道飞/Daofy Delphi MCP Server 安装脚本")

    server_script = os.path.join(str(get_script_dir()), "src", "server.py")
    if not os.path.exists(server_script):
        error(f"MCP Server 脚本不存在: {server_script}")
        sys.exit(1)

    agents = detect_agents()

    # 按过滤器筛选
    if agent_filter != "All":
        filter_map = {
            "Claude": "Claude Desktop", "Trae": "Trae", "CodeArts": "CodeArts Agent",
            "Cursor": "Cursor", "OpenCode": "OpenCode", "Windsurf": "Windsurf",
            "Cline": "Cline", "Roo": "Roo Code", "Tongyi": "通义灵码",
            "Doubao": "豆包", "Kimi": "Kimi", "ChatGLM": "智谱清言",
        }
        target = filter_map.get(agent_filter, agent_filter)
        agents = [a for a in agents if a["name"] == target]

    installed_agents = [a for a in agents if a["installed"]]
    not_installed_agents = [a for a in agents if not a["installed"]]

    if not installed_agents:
        warn("未检测到任何已安装的 AI Agent")
        sys.exit(0)

    # ================================================================
    # 分两组展示：全局配置 / 项目级配置
    # 支持两种模式的 Agent 会同时出现在两个组中（以不同编号区分）
    # ================================================================
    display_items: list[tuple[dict, str]] = []  # (agent, implied_mode)
    for a in installed_agents:
        if "global" in a["modes"]:
            display_items.append((a, "global"))
    project_start = len(display_items) + 1
    for a in installed_agents:
        if "project" in a["modes"]:
            display_items.append((a, "project"))

    info("已安装的 AI Agent（输入编号选择，a=全选，q=退出）:")
    info("")
    info("--- 全局配置（选择后将配置到默认路径）---")
    for i, (a, _) in enumerate(display_items, 1):
        if i == project_start:
            info("")
            info("--- 项目级配置（选择后需指定项目目录）---")
        is_project_item = i >= project_start
        exp = " [Experimental]" if a["experimental"] else ""
        if is_project_item:
            # 项目级：安装时不知道路径，不显示状态和路径
            cprint(f"  [{i:2d}] {a['name']}{exp}", YELLOW)
        else:
            configured = is_mcp_configured_any(a["config_path"], a["config_type"])
            status = "已配置" if configured else "未配置"
            cprint(f"  [{i:2d}] {a['name']}{exp} ({status})", GREEN)
            if a["path"] and a["path"] != "Unknown":
                cprint(f"        路径: {a['path']}", GRAY)
            cprint(f"        配置: {a['config_path']}", GRAY)

    if not_installed_agents:
        names = ", ".join(a["name"] for a in not_installed_agents)
        info(f"未安装的 AI Agent: {names}")

    # 交互选择
    if agent_filter != "All":
        filter_map = {
            "Claude": "Claude Desktop", "Trae": "Trae", "CodeArts": "CodeArts Agent",
            "Cursor": "Cursor", "OpenCode": "OpenCode", "Windsurf": "Windsurf",
            "Cline": "Cline", "Roo": "Roo Code", "Tongyi": "通义灵码",
            "Doubao": "豆包", "Kimi": "Kimi", "ChatGLM": "智谱清言",
        }
        target = filter_map.get(agent_filter, agent_filter)
        selected = [a for a in installed_agents if a["name"] == target]
        # 自动推断 implied_mode
        for a in selected:
            a["_implied_mode"] = "project" if "project" in a["modes"] and "global" not in a["modes"] else "global"
    else:
        if len(display_items) <= 1:
            selected = [a for a, _ in display_items]
        else:
            info("")
            info("请选择要配置的 AI Agent（多选用逗号分隔，如 1,3,5）")
            info("输入 a 或 all 全选，输入 q 退出")
            try:
                choice = input(f"{CYAN}选择 [1-{len(display_items)}/a/q]: {RESET}").strip()
            except EOFError:
                choice = "q"
            if not choice or choice.lower() == "q":
                info("已取消")
                sys.exit(0)
            if choice.lower() in ("a", "all"):
                # 全选：每个 display 项独立复制，保留各自的 implied_mode
                selected = []
                for agent, implied_mode in display_items:
                    entry = dict(agent)
                    entry["_implied_mode"] = implied_mode
                    selected.append(entry)
            else:
                selected = []
                for part in choice.replace(" ", ",").split(","):
                    part = part.strip()
                    if part.isdigit():
                        idx = int(part)
                        if 1 <= idx <= len(display_items):
                            agent, implied_mode = display_items[idx - 1]
                            entry = dict(agent)
                            entry["_implied_mode"] = implied_mode
                            selected.append(entry)
                        else:
                            warn(f"忽略无效选择: {idx}")
                if not selected:
                    warn("未选择任何有效的 Agent")
                    sys.exit(0)

    # agent_filter 模式或未设置 _implied_mode 的自动推断
    for a in selected:
        if "_implied_mode" not in a:
            a["_implied_mode"] = "project" if "project" in a["modes"] and "global" not in a["modes"] else "global"

    # 项目级 Agent 始终需要用户输入项目目录
    need_path = [a for a in selected if a["_implied_mode"] == "project" and not project_dir]
    if need_path:
        default_dir = str(get_script_dir())
        info("")
        info("以下 Agent 需要指定项目目录：")
        for a in need_path:
            rel = _get_project_relative_config_path(a["name"], a)
            cprint(f"  - {a['name']} ({rel})", YELLOW)
        try:
            user_input = input(f"{CYAN}项目目录 [默认: {default_dir}]: {RESET}").strip()
        except EOFError:
            user_input = ""
        project_dir = user_input if user_input else default_dir
    # 根据 project_dir 更新项目级 Agent 的配置文件路径
    if project_dir:
        for a in selected:
            if a["_implied_mode"] == "project":
                rel_path = _get_project_relative_config_path(a["name"], a)
                if rel_path:
                    a["config_path"] = os.path.join(project_dir, rel_path)

    info("")
    info("将配置以下 Agent:")
    for a in selected:
        cprint(f"  - {a['name']}", GREEN)

    separator("配置 MCP Server")
    success_count = 0

    for a in selected:
        info(f"正在配置 {a['name']}...")
        info(f"配置文件: {a['config_path']}")

        configured = is_mcp_configured_any(a["config_path"], a["config_type"])
        if configured and not force:
            info(f"{a['name']} 已配置 MCP Server，跳过（使用 --force 强制重新配置）")
            success_count += 1
            continue

        if force and configured:
            for sn in (MCP_SERVER_NAME, LEGACY_SERVER_NAME):
                remove_mcp_config(a["config_path"], sn, a["config_type"])

        mcp_cfg = get_mcp_config(python_exe, a["config_type"], project_dir)
        try:
            add_mcp_config(a["config_path"], MCP_SERVER_NAME, mcp_cfg, a["config_type"])
            success(f"已配置 MCP Server 到: {a['config_path']}")
            success_count += 1
        except Exception as e:
            error(f"配置失败: {e}")

    separator("安装结果")
    info(f"成功配置: {success_count} 个 AI Agent")
    if success_count > 0:
        success("MCP Server 安装完成！")
        info("请重启相应的 AI Agent 使配置生效")


# ============================================================
# 卸载
# ============================================================

def do_uninstall(agent_filter: str = "All", project_dir: str = "") -> None:
    separator("道飞/Daofy Delphi MCP Server 卸载脚本")

    agents = detect_agents()

    # 如果 CLI 指定了 project_dir，直接应用到所有支持项目级的 Agent
    if project_dir:
        for a in agents:
            if "project" in a["modes"]:
                rel_path = _get_project_relative_config_path(a["name"], a)
                if rel_path:
                    a["config_path"] = os.path.join(project_dir, rel_path)
                a["installed"] = True

    installed_agents = [a for a in agents if a["installed"]]

    if not installed_agents:
        warn("未检测到任何已安装的 AI Agent")
        sys.exit(0)

    # ================================================================
    # 分两组展示：全局配置 / 项目级配置（同安装流程）
    # ================================================================
    display_items: list[tuple[dict, str]] = []
    for a in installed_agents:
        if "global" in a["modes"]:
            display_items.append((a, "global"))
    project_start = len(display_items) + 1
    for a in installed_agents:
        if "project" in a["modes"]:
            display_items.append((a, "project"))

    info("（输入编号选择，a=全选，q=退出）")
    info("")
    info("--- 全局配置 ---")
    for i, (a, _) in enumerate(display_items, 1):
        if i == project_start:
            info("")
            info("--- 项目级配置（选择后需指定项目目录）---")
        is_project_item = i >= project_start
        exp = " [Experimental]" if a["experimental"] else ""
        if is_project_item and not project_dir:
            cprint(f"  [{i:2d}] {a['name']}{exp}", YELLOW)
        else:
            configured = is_mcp_configured_any(a["config_path"], a["config_type"])
            status = "已配置" if configured else "未配置"
            color = GREEN if configured else YELLOW
            cprint(f"  [{i:2d}] {a['name']}{exp} ({status})", color)
            cprint(f"      配置: {a['config_path']}", GRAY)

    # 交互选择
    if agent_filter != "All":
        filter_map = {
            "Claude": "Claude Desktop", "Trae": "Trae", "CodeArts": "CodeArts Agent",
            "Cursor": "Cursor", "OpenCode": "OpenCode", "Windsurf": "Windsurf",
            "Cline": "Cline", "Roo": "Roo Code", "Tongyi": "通义灵码",
            "Doubao": "豆包", "Kimi": "Kimi", "ChatGLM": "智谱清言",
        }
        target = filter_map.get(agent_filter, agent_filter)
        selected = [a for a in installed_agents if a["name"] == target]
        for a in selected:
            a["_implied_mode"] = "project" if "project" in a["modes"] and "global" not in a["modes"] else "global"
    else:
        if len(display_items) <= 1:
            selected_with_modes = display_items
        else:
            info("")
            info("请选择要卸载的 AI Agent（多选用逗号分隔，如 1,3,5）")
            info("输入 a 或 all 全选，输入 q 退出")
            try:
                choice = input(f"{CYAN}选择 [1-{len(display_items)}/a/q]: {RESET}").strip()
            except EOFError:
                choice = "q"
            if not choice or choice.lower() == "q":
                info("已取消")
                sys.exit(0)
            if choice.lower() in ("a", "all"):
                selected_with_modes = display_items
            else:
                selected_with_modes = []
                for part in choice.replace(" ", ",").split(","):
                    part = part.strip()
                    if part.isdigit():
                        idx = int(part)
                        if 1 <= idx <= len(display_items):
                            selected_with_modes.append(display_items[idx - 1])
                        else:
                            warn(f"忽略无效选择: {idx}")
                if not selected_with_modes:
                    warn("未选择任何有效的 Agent")
                    sys.exit(0)
        # 转为独立 dict 列表，保留 implied_mode
        selected = []
        for agent, implied_mode in selected_with_modes:
            entry = dict(agent)
            entry["_implied_mode"] = implied_mode
            selected.append(entry)

    if not selected:
        sys.exit(0)

    # 为项目级 Agent 补充路径检测（选中后才提示）
    for a in selected:
        if a["_implied_mode"] == "project" and not project_dir:
            info("")
            rel = _get_project_relative_config_path(a["name"], a)
            info(f"{a['name']} 使用项目级 MCP 配置（{rel}），请输入项目目录")
            default_dir = str(get_script_dir())
            try:
                user_input = input(f"{CYAN}项目目录 [默认: {default_dir}]: {RESET}").strip()
            except EOFError:
                user_input = ""
            project_dir = user_input or default_dir
            rel_path = _get_project_relative_config_path(a["name"], a)
            if rel_path:
                a["config_path"] = os.path.join(project_dir, rel_path)

    # 过滤出实际已配置的 Agent
    to_uninstall = []
    for a in selected:
        configured = is_mcp_configured_any(a["config_path"], a["config_type"])
        if not configured:
            if a["_implied_mode"] == "project" and "global" not in a["modes"]:
                warn(f"{a['name']} 在 {a['config_path']} 未找到 MCP 配置，跳过")
            else:
                info(f"{a['name']} 未配置此 MCP Server，跳过")
            continue
        to_uninstall.append(a)

    if not to_uninstall:
        info("没有需要卸载的 MCP 配置")
        sys.exit(0)

    info("")
    warn("将卸载以下 Agent 的 MCP Server 配置:")
    for a in to_uninstall:
        cprint(f"  - {a['name']}", YELLOW)
        cprint(f"      配置: {a['config_path']}", GRAY)
    try:
        confirm = input(f"{RED}确认卸载? [y/N]: {RESET}").strip()
    except EOFError:
        confirm = "n"
    if confirm.lower() != "y":
        info("已取消")
        sys.exit(0)

    separator("卸载 MCP Server")
    success_count = 0

    for a in to_uninstall:
        info(f"正在卸载 {a['name']}...")
        removed_any = False
        for sn in (MCP_SERVER_NAME, LEGACY_SERVER_NAME):
            if is_mcp_configured(a["config_path"], sn, a["config_type"]):
                if remove_mcp_config(a["config_path"], sn, a["config_type"]):
                    removed_any = True
        if removed_any:
            success(f"已从 {a['name']} 移除 MCP Server 配置")
            success_count += 1
        else:
            info(f"{a['name']} 未配置此 MCP Server，跳过")

    separator("卸载结果")
    info(f"成功卸载: {success_count} 个 AI Agent")
    if success_count > 0:
        success("MCP Server 卸载完成！")
        info("请重启相应的 AI Agent 使配置生效")


# ============================================================
# 入口
# ============================================================

# ============================================================
# 自安装：检查当前目录是否为 MCP Server 目录
# ============================================================

RELEASE_REPO = "daofy-nlp/delphi-complier-mcp-server"
RELEASE_API = f"https://api.github.com/repos/{RELEASE_REPO}/releases/latest"


def _is_server_dir() -> bool:
    """检查当前目录是否包含 MCP Server 核心文件"""
    script_dir = get_script_dir()
    return (script_dir / "src" / "server.py").exists() and (script_dir / "requirements.txt").exists()


MAX_RETRY = 30
RETRY_DELAY = 2  # 秒


def _retry_urlopen(url: str, headers: dict | None = None, timeout: int = 15, max_retry: int = MAX_RETRY) -> bytes:
    """带重试的 urllib 请求，最多重试 max_retry 次"""
    import urllib.request
    import urllib.error
    import time

    last_err = None
    for attempt in range(1, max_retry + 1):
        try:
            req = urllib.request.Request(url, headers=headers or {})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as e:
            last_err = e
            if attempt < max_retry:
                wait = RETRY_DELAY * min(attempt, 10)
                warn(f"请求失败(第{attempt}次): {e}，{wait}秒后重试...")
                time.sleep(wait)
    raise last_err  # type: ignore[misc]


def _get_latest_release_url() -> tuple[str, str]:
    """获取最新 release 的 zip 下载地址和版本号"""
    try:
        data = json.loads(_retry_urlopen(RELEASE_API, headers={"User-Agent": "daofy-installer"}).decode("utf-8"))
        version = data.get("tag_name", "unknown")
        for asset in data.get("assets", []):
            name = asset.get("name", "")
            if name.endswith(".zip"):
                return asset["browser_download_url"], version
    except Exception as e:
        warn(f"获取 Release 信息失败: {e}")
    return "", ""


def _download_file(url: str, dest: str) -> bool:
    """下载文件到指定路径，带重试"""
    import urllib.request
    import time

    last_err = None
    for attempt in range(1, MAX_RETRY + 1):
        try:
            if attempt == 1:
                info(f"正在下载: {url}")
            else:
                info(f"重试下载(第{attempt}次)...")
            urllib.request.urlretrieve(url, dest)
            return True
        except Exception as e:
            last_err = e
            if os.path.exists(dest):
                os.remove(dest)
            if attempt < MAX_RETRY:
                wait = RETRY_DELAY * min(attempt, 10)
                warn(f"下载失败(第{attempt}次): {e}，{wait}秒后重试...")
                time.sleep(wait)
    error(f"下载失败(已重试{MAX_RETRY}次): {last_err}")
    return False


def ensure_server_files() -> bool:
    """检查当前目录是否为 MCP Server 安装目录，如果不是则下载并解压最新 release。

    返回 True 表示文件就绪（已有或已安装），False 表示失败。
    不会覆盖当前正在执行的 bat 文件。
    """
    if _is_server_dir():
        return True

    separator("MCP Server 文件未找到")
    info("当前目录不包含 MCP Server 核心文件 (src/server.py)")
    info("将自动下载最新 Release 并解压到当前目录")
    info("")

    zip_url, version = _get_latest_release_url()
    if not zip_url:
        error("无法获取最新 Release 下载地址")
        error(f"请手动下载: https://github.com/{RELEASE_REPO}/releases")
        return False

    info(f"最新版本: {version}")

    with tempfile.TemporaryDirectory(prefix="daofy-install-") as tmp_dir:
        zip_path = os.path.join(tmp_dir, f"delphi-mcp-server-{version}.zip")
        if not _download_file(zip_url, zip_path):
            return False

        info("正在解压...")
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(tmp_dir)
        except Exception as e:
            error(f"解压失败: {e}")
            return False

        # 找到解压后的子目录（release zip 通常包含一个顶层目录）
        src_dir = tmp_dir
        entries = os.listdir(tmp_dir)
        extracted_dirs = [e for e in entries if e != os.path.basename(zip_path) and os.path.isdir(os.path.join(tmp_dir, e))]
        if len(extracted_dirs) == 1:
            src_dir = os.path.join(tmp_dir, extracted_dirs[0])
        elif len(extracted_dirs) > 1:
            # 找包含 src/server.py 的目录
            for d in extracted_dirs:
                if os.path.exists(os.path.join(tmp_dir, d, "src", "server.py")):
                    src_dir = os.path.join(tmp_dir, d)
                    break

        if not os.path.exists(os.path.join(src_dir, "src", "server.py")):
            error("解压后未找到 src/server.py")
            return False

        # 复制文件到当前目录，跳过 .bat 文件（正在运行）
        dest_dir = str(get_script_dir())
        bat_files = set()
        info(f"正在安装文件到: {dest_dir}")
        for root, dirs, files in os.walk(src_dir):
            rel_root = os.path.relpath(root, src_dir)
            for f in files:
                src_file = os.path.join(root, f)
                if rel_root == ".":
                    dest_file = os.path.join(dest_dir, f)
                else:
                    dest_file = os.path.join(dest_dir, rel_root, f)

                # 跳过正在运行的 .bat 文件，稍后覆盖
                if f.lower().endswith(".bat"):
                    bat_files.add((src_file, dest_file))
                    continue

                os.makedirs(os.path.dirname(dest_file), exist_ok=True)
                shutil.copy2(src_file, dest_file)

        # 最后覆盖 .bat 文件（bat 已读入内存，覆盖不影响本次执行）
        for src_bat, dest_bat in bat_files:
            shutil.copy2(src_bat, dest_bat)

        success(f"MCP Server {version} 安装完成")
        return True


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Daofy MCP Server 安装/卸载脚本")
    parser.add_argument("--uninstall", action="store_true", help="卸载模式")
    parser.add_argument("--agent", default="All",
                        choices=["Claude", "Trae", "CodeArts", "Cursor", "OpenCode",
                                 "Windsurf", "Cline", "Roo", "Tongyi", "Doubao",
                                 "Kimi", "ChatGLM", "All"],
                        help="指定 AI Agent")
    parser.add_argument("--force", action="store_true", help="强制重新配置")
    parser.add_argument("--python", default="", help="Python 解释器路径")
    parser.add_argument("--project-dir", default="",
                        help="项目目录路径（项目级 MCP 配置的 Agent 使用，不传则交互式输入）")
    args = parser.parse_args()

    if args.uninstall:
        do_uninstall(agent_filter=args.agent, project_dir=args.project_dir)
    else:
        # 检查 MCP Server 文件是否存在，不存在则自动下载解压
        if not ensure_server_files():
            error("MCP Server 文件准备失败")
            sys.exit(1)

        python_exe = args.python or get_python_exe()
        if not os.path.exists(python_exe):
            error(f"Python 不存在: {python_exe}")
            sys.exit(1)
        do_install(python_exe, project_dir=args.project_dir,
                   agent_filter=args.agent, force=args.force)


if __name__ == "__main__":
    main()
