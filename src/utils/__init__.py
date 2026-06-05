"""
工具函数包

包含编码检测、路径处理等通用工具函数
"""

import ctypes
import locale
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def get_console_encoding() -> str:
    """获取当前控制台的实际编码。
    
    在 Windows 上，控制台代码页（GetConsoleOutputCP）可能与系统 ANSI 编码
    （locale.getpreferredencoding）不同。例如 Python 启用 UTF-8 模式时，
    控制台代码页为 65001 (UTF-8)，但 ANSI 编码仍为 cp936 (GBK)。
    
    写入 batch 文件和解码子进程输出时，必须使用控制台代码页而非 ANSI 编码，
    否则包含中文路径的内容会出现乱码。
    
    Returns:
        编码名称字符串，如 'cp65001'、'cp936'、'utf-8' 等
    """
    try:
        cp = ctypes.windll.kernel32.GetConsoleOutputCP()
        if cp > 0:
            return f'cp{cp}'
    except Exception as e:
        logger.debug("获取控制台编码失败（回退到 ANSI 编码）: %s", e)
    return locale.getpreferredencoding()
