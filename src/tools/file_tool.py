"""
file_tool — 统一 Delphi 文件操作工具

整合读取/写入/格式化/备份管理，覆盖文件操作完整生命周期。

Action 模式:
  read    读取文件内容（继承 read_source_file，支持按路径/类名/函数名搜索）
  write   写入文件内容（自动备份到 __history，支持 DFM 透明转换）
  format  格式化 Delphi 源码（继承 format_delphi，pasfmt 驱动）
  backup  备份管理（创建/恢复/列表/对比）

返回值统一为 dict，遵循项目规范:
  success: {"status": "success", "message": "...", ...}
  error:   {"status": "failed", "message": "..."}
"""

import os
import shutil
import tempfile
from typing import Any, Optional, Dict
from ..utils.logger import get_logger
from ..utils.file_backup import create_backup, list_backups, restore_backup, detect_encoding
from . import pasfmt
from .read_source_file import read_source_file as _read_file, search_and_read_file as _search_read_file
from . import dfm_utils

logger = get_logger(__name__)

# 支持的文件扩展名
_DELPHI_EXTENSIONS = {'.pas', '.dpr', '.dpk', '.dfm', '.fmx', '.inc', '.dproj'}


def _is_delphi_file(file_path: str) -> bool:
    """判断是否是 Delphi 源文件"""
    ext = os.path.splitext(file_path)[1].lower()
    return ext in _DELPHI_EXTENSIONS


def _is_dfm_file(file_path: str) -> bool:
    """判断是否是 DFM 文件"""
    return os.path.splitext(file_path)[1].lower() == '.dfm'


def _wrap_error(msg: str) -> Dict[str, Any]:
    """构造错误 dict"""
    return {"status": "failed", "message": msg}


async def _read_content(
    file_path: str,
    start_line: int = 1,
    max_lines: int = 500,
    search_in: str = "all",
    project_path: Optional[str] = None,
) -> Dict[str, Any]:
    """读取文件内容的内部实现，委托给 read_source_file 并统一返回格式"""
    args = {
        "file_path": file_path,
        "start_line": start_line,
        "max_lines": max_lines,
        "search_in": search_in,
        "project_path": project_path,
    }
    result = await _read_file(args)
    # read_source_file 返回 CallToolResult，转为 dict
    if result.isError:
        return {"status": "failed", "message": result.content[0].text if result.content else "读取失败"}
    return {"status": "success", "message": result.content[0].text if result.content else ""}


async def _search_and_read(
    search_type: str,
    type_name: Optional[str] = None,
    record_name: Optional[str] = None,
    function_name: Optional[str] = None,
    search_in: str = "all",
    start_line: int = 1,
    max_lines: int = 100,
) -> Dict[str, Any]:
    """按类名/函数名搜索并读取文件"""
    args = {
        "type_name": type_name,
        "record_name": record_name,
        "function_name": function_name,
        "search_in": search_in,
        "start_line": start_line,
        "max_lines": max_lines,
    }
    result = await _search_read_file(args)
    if result.isError:
        return {"status": "failed", "message": result.content[0].text if result.content else "搜索失败"}
    return {"status": "success", "message": result.content[0].text if result.content else ""}


async def handle_read(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    处理 read action。

    支持两种模式:
      1. 按路径读取: file_path 参数
      2. 按搜索读取: search_type + type_name/function_name

    DFM 文件透明处理：二进制 DFM 自动转换为文本再读取。
    """
    file_path = arguments.get("file_path")
    search_type = arguments.get("search_type", "path")
    start_line = arguments.get("start_line", 1)
    max_lines = min(arguments.get("max_lines", 500), 1000)
    search_in = arguments.get("search_in", "all")
    project_path = arguments.get("project_path")

    # --- 搜索模式 ---
    if search_type != "path":
        return await _search_and_read(
            search_type=search_type,
            type_name=arguments.get("type_name") or arguments.get("class_name"),
            record_name=arguments.get("record_name"),
            function_name=arguments.get("function_name"),
            search_in=search_in,
            start_line=start_line,
            max_lines=max_lines,
        )

    # --- 路径模式 ---
    if not file_path:
        return _wrap_error("请提供 file_path 参数")

    # DFM 二进制→文本透明转换
    tmp_cleanup = None
    if _is_dfm_file(file_path):
        fmt = dfm_utils._detect_dfm_format(file_path)
        if fmt == "binary":
            tmp_dir = tempfile.mkdtemp(prefix="filetool_")
            tmp_text = os.path.join(tmp_dir, os.path.basename(file_path) + ".txt")
            result = await dfm_utils.convert_dfm(file_path, tmp_text, to_text=True)
            if result.get("success"):
                file_path = tmp_text
                tmp_cleanup = tmp_dir

    try:
        return await _read_content(
            file_path=file_path,
            start_line=start_line,
            max_lines=max_lines,
            search_in=search_in,
            project_path=project_path,
        )
    finally:
        if tmp_cleanup:
            shutil.rmtree(tmp_cleanup, ignore_errors=True)


async def handle_write(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    处理 write action。

    核心特性:
      - 自动备份原文件到 __history（backup=True 默认）
      - 自动检测并保持原始编码
      - DFM 文件自动处理：如果原文件是二进制，写出后自动转回二进制
    """
    file_path = arguments.get("file_path")
    content = arguments.get("content")
    backup = arguments.get("backup", True)
    encoding = arguments.get("encoding", "auto")
    format_after = arguments.get("format_after_write", False)

    if not file_path:
        return _wrap_error("请提供 file_path 参数")
    if content is None:
        return _wrap_error("请提供 content 参数")

    # 检测原始文件状态
    backup_path = None
    file_exists = os.path.isfile(file_path)
    original_encoding = None
    is_dfm_binary = False

    if file_exists:
        if _is_dfm_file(file_path):
            fmt = dfm_utils._detect_dfm_format(file_path)
            is_dfm_binary = (fmt == "binary")

        if encoding == "auto":
            original_encoding = detect_encoding(file_path)
        else:
            original_encoding = encoding

        if backup:
            backup_path = create_backup(file_path)
    else:
        original_encoding = encoding if encoding != "auto" else "utf-8"

    # 写入文件
    try:
        tmp_fd, tmp_path = tempfile.mkstemp(
            suffix=os.path.splitext(file_path)[1],
            dir=os.path.dirname(os.path.abspath(file_path)),
        )
        os.close(tmp_fd)

        write_encoding = original_encoding or "utf-8"
        try:
            with open(tmp_path, "w", encoding=write_encoding, newline='') as f:
                f.write(content)
        except UnicodeEncodeError:
            logger.warning(f"编码 {write_encoding} 写出失败，回退到 utf-8")
            with open(tmp_path, "w", encoding="utf-8", newline='') as f:
                f.write(content)
            write_encoding = "utf-8"

        # DFM 二进制格式处理
        if is_dfm_binary:
            text_tmp = tmp_path + ".txt"
            os.rename(tmp_path, text_tmp)
            try:
                conv_result = await dfm_utils.convert_dfm(text_tmp, tmp_path, to_text=False)
                if not conv_result.get("success"):
                    os.rename(text_tmp, tmp_path)
                    logger.warning(f"DFM 二进制转换失败，已保留文本格式: {conv_result.get('message')}")
                else:
                    os.remove(text_tmp)
            except Exception as e:
                if os.path.exists(text_tmp):
                    os.rename(text_tmp, tmp_path)
                logger.warning(f"DFM 转换异常，已保留文本格式: {e}")

        shutil.move(tmp_path, file_path)

        # 写入后自动格式化
        fmt_msg = ""
        if format_after and _is_delphi_file(file_path):
            try:
                fmt_result = await pasfmt.format_file(file_path=file_path, backup=False)
                if fmt_result.get("formatted"):
                    fmt_msg = "，写入后已格式化"
            except Exception:
                pass

        result_lines = [
            f"文件已写入: {file_path}",
            f"编码: {write_encoding}",
        ]
        if backup and file_exists:
            result_lines.append(f"备份已创建: {backup_path}")
        if is_dfm_binary:
            result_lines.append("格式: 已转换为二进制 DFM")
        if fmt_msg:
            result_lines.append(fmt_msg)

        return {"status": "success", "message": "\n".join(result_lines)}

    except Exception as e:
        logger.error(f"写入文件失败: {e}", exc_info=True)
        return _wrap_error(f"写入文件失败: {str(e)}")


async def handle_format(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    处理 format action — 委托给 pasfmt.format_file。
    """
    file_path = arguments.get("file_path")
    if not file_path:
        return _wrap_error("请提供 file_path 参数")

    action = arguments.get("format_action", "file")
    uses_style = arguments.get("uses_style")
    check_only = arguments.get("check_only", False)
    backup_flag = arguments.get("backup", True)

    if action == "code":
        code = arguments.get("code", "")
        if not code:
            return _wrap_error("请提供 code 参数")
        result = await pasfmt.format_code(
            code=code,
            config_path=arguments.get("config_path"),
            uses_style=uses_style,
        )
    elif action == "check":
        result = await pasfmt.format_file(
            file_path=file_path,
            check_only=True,
        )
    else:
        result = await pasfmt.format_file(
            file_path=file_path,
            config_path=arguments.get("config_path"),
            backup=backup_flag,
            in_place=True,
            uses_style=uses_style,
        )

    # pasfmt.format_file 已经返回 dict，透传即可
    return result


async def handle_backup(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    处理 backup action — 备份管理。

    子 action:
      create  创建备份（默认）
      list    列出所有备份版本
      restore 恢复指定版本
    """
    file_path = arguments.get("file_path")
    backup_action = arguments.get("backup_action", "create")
    version = arguments.get("version")

    if not file_path:
        return _wrap_error("请提供 file_path 参数")

    if backup_action == "create":
        bp = create_backup(file_path)
        if bp:
            return {"status": "success", "message": f"备份已创建: {bp}"}
        return _wrap_error(f"备份失败: {file_path}")

    elif backup_action == "list":
        backups = list_backups(file_path)
        if not backups:
            return {"status": "success", "message": f"没有找到 {file_path} 的备份文件"}
        lines = [f"文件: {file_path}", f"备份数: {len(backups)}", ""]
        for b in backups:
            from datetime import datetime
            ts = datetime.fromtimestamp(b["mtime"]).strftime("%Y-%m-%d %H:%M:%S")
            size_kb = b["size"] / 1024
            lines.append(f"  v{b['version']}: {ts}  ({size_kb:.1f} KB)  {b['path']}")
        return {"status": "success", "message": "\n".join(lines)}

    elif backup_action == "restore":
        bp = restore_backup(file_path, version=version)
        if bp:
            ver_str = f"v{version}" if version else "最新版本"
            return {"status": "success", "message": f"已从 {ver_str} 恢复: {bp}"}
        return _wrap_error(f"恢复失败: {file_path}")

    else:
        return _wrap_error(f"未知 backup_action: {backup_action}")


# ============================================================
# 主入口
# ============================================================

async def handle_file_tool(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    file_tool 主入口。

    根据 action 参数路由到对应的处理函数:
      read    → handle_read
      write   → handle_write
      format  → handle_format
      backup  → handle_backup
    """
    action = arguments.get("action", "read")

    if action == "read":
        return await handle_read(arguments)
    elif action == "write":
        return await handle_write(arguments)
    elif action == "format":
        return await handle_format(arguments)
    elif action == "backup":
        return await handle_backup(arguments)
    else:
        return _wrap_error(f"未知 action: {action}。支持的 action: read, write, format, backup")
