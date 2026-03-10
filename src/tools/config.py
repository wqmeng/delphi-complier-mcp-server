"""
配置管理工具

提供编译器配置管理功能
"""

from typing import Optional, Dict, Any
from ..models.compiler_config import CompilerConfig
from ..services.config_manager import ConfigManager
from ..utils.validator import Validator
from ..utils.logger import get_logger

logger = get_logger(__name__)

# 全局配置管理器实例
_config_manager: Optional[ConfigManager] = None


def set_config_manager(manager: ConfigManager):
    """设置配置管理器实例"""
    global _config_manager
    _config_manager = manager


async def set_compiler_config(
    name: str,
    path: str,
    is_default: bool = False,
    version: Optional[str] = None
) -> Dict[str, Any]:
    """
    配置 Delphi 编译器

    Args:
        name: 编译器版本名称
        path: 编译器可执行文件路径
        is_default: 是否设为默认编译器
        version: 编译器版本号

    Returns:
        配置结果字典
    """
    logger.info(f"收到配置编译器请求: {name}")

    if _config_manager is None:
        logger.error("配置管理器未初始化")
        return {
            "success": False,
            "message": "配置管理器未初始化",
            "compiler_name": name
        }

    try:
        # 验证编译器路径
        validator = Validator()
        is_valid, error_msg = validator.validate_compiler_path(path)
        if not is_valid:
            logger.error(f"编译器路径验证失败: {error_msg}")
            return {
                "success": False,
                "message": error_msg,
                "compiler_name": name
            }

        # 创建编译器配置
        compiler = CompilerConfig(
            name=name,
            path=path,
            is_default=is_default,
            version=version
        )

        # 添加配置
        _config_manager.add_compiler(compiler)

        logger.info(f"编译器配置成功: {name}")
        return {
            "success": True,
            "message": f"编译器配置成功: {name}",
            "compiler_name": name
        }

    except Exception as e:
        error_msg = f"配置过程发生异常: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {
            "success": False,
            "message": error_msg,
            "compiler_name": name
        }


async def get_compiler_list() -> Dict[str, Any]:
    """
    获取所有编译器配置列表

    Returns:
        编译器配置列表字典
    """
    logger.info("收到获取编译器列表请求")

    if _config_manager is None:
        logger.error("配置管理器未初始化")
        return {
            "success": False,
            "message": "配置管理器未初始化",
            "compilers": []
        }

    try:
        compilers = _config_manager.get_all_compilers()
        default_compiler = _config_manager.get_compiler()

        return {
            "success": True,
            "message": f"共 {len(compilers)} 个编译器配置",
            "compilers": [c.to_dict() for c in compilers],
            "default_compiler": default_compiler.name if default_compiler else None
        }

    except Exception as e:
        error_msg = f"获取编译器列表过程发生异常: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {
            "success": False,
            "message": error_msg,
            "compilers": []
        }


async def remove_compiler_config(name: str) -> Dict[str, Any]:
    """
    删除编译器配置

    Args:
        name: 编译器名称

    Returns:
        删除结果字典
    """
    logger.info(f"收到删除编译器配置请求: {name}")

    if _config_manager is None:
        logger.error("配置管理器未初始化")
        return {
            "success": False,
            "message": "配置管理器未初始化",
            "compiler_name": name
        }

    try:
        result = _config_manager.remove_compiler(name)

        if result:
            logger.info(f"编译器配置删除成功: {name}")
            return {
                "success": True,
                "message": f"编译器配置删除成功: {name}",
                "compiler_name": name
            }
        else:
            logger.warning(f"编译器配置不存在: {name}")
            return {
                "success": False,
                "message": f"编译器配置不存在: {name}",
                "compiler_name": name
            }

    except Exception as e:
        error_msg = f"删除过程发生异常: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {
            "success": False,
            "message": error_msg,
            "compiler_name": name
        }
