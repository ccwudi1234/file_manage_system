"""
路径校验模块
负责验证用户输入的路径是否合法、可访问
所有异常通过 error_logger 记录
"""
from pathlib import Path
from typing import Tuple, Optional

from .error_logger import get_logger, catch_errors


# 获取日志实例
logger = get_logger()


@catch_errors(logger=logger, default=(False, "路径校验过程发生异常", None), context={'module': 'path_validator'})
def check_root_path(path_str: str) -> Tuple[bool, str, Optional[Path]]:
    """
    校验根路径的有效性

    校验规则：
    1. 路径字符串不能为空
    2. 路径必须存在
    3. 路径必须是目录（不是文件）

    :param path_str: 用户输入的路径字符串
    :return: 元组 (校验结果bool, 提示文案str, Path对象或None)
             - 校验成功: (True, "路径有效", Path对象)
             - 校验失败: (False, 错误提示, None)
    """
    # 1. 检查空值
    if not path_str or not path_str.strip():
        msg = "错误：路径不能为空"
        logger.log_warning(msg, input_value=path_str)
        return (False, msg, None)

    # 2. 去除首尾空白
    path_str = path_str.strip()

    try:
        # 3. 创建 Path 对象
        path = Path(path_str)

        # 4. 检查路径是否存在
        if not path.exists():
            msg = f"错误：路径不存在 - {path_str}"
            logger.log_warning(msg, path=str(path))
            return (False, msg, None)

        # 5. 检查是否为目录
        if not path.is_dir():
            msg = f"错误：指定的路径是文件而非文件夹 - {path_str}"
            logger.log_warning(msg, path=str(path), is_file=True)
            return (False, msg, None)

        # 6. 校验通过
        logger.log_info(f"路径校验通过: {path.resolve()}", path=str(path.resolve()))
        return (True, "路径有效", path.resolve())

    except PermissionError as e:
        msg = f"错误：没有权限访问该路径 - {path_str}"
        logger.log_error(msg, exc=e, path=path_str)
        return (False, msg, None)

    except OSError as e:
        msg = f"错误：系统无法识别该路径 - {path_str}"
        logger.log_error(msg, exc=e, path=path_str)
        return (False, msg, None)

    except Exception as e:
        msg = f"错误：路径校验过程中发生未知异常 - {path_str}"
        logger.log_error(msg, exc=e, path=path_str)
        return (False, msg, None)


def validate_path_exists(path: Path) -> bool:
    """
    简单的路径存在性检查（辅助函数）

    :param path: Path 对象
    :return: 是否存在
    """
    try:
        return path.exists()
    except Exception as e:
        logger.log_error(f"检查路径存在性失败: {path}", exc=e)
        return False


def is_readable_path(path: Path) -> bool:
    """
    检查路径是否可读

    :param path: Path 对象
    :return: 是否可读
    """
    try:
        # 尝试访问路径
        path.resolve()
        if path.is_dir():
            # 目录：尝试列出内容
            list(path.iterdir())
        return True
    except PermissionError as e:
        logger.log_warning(f"路径不可读（权限不足）: {path}", exc=e)
        return False
    except Exception as e:
        logger.log_error(f"检查路径可读性失败: {path}", exc=e)
        return False
