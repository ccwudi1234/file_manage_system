"""
错误监控日志系统模块
提供全面的错误捕获、记录和分析功能
支持双通道输出（文件+控制台）、日志轮转、装饰器和上下文管理器
"""
import logging
import functools
import traceback
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, Callable, Type
from logging.handlers import RotatingFileHandler


class ErrorLogger:
    """
    全局错误监控日志系统

    功能特性：
    - 双通道日志输出（文件 + 控制台）
    - 按大小自动轮转日志文件（最大5MB，保留7个备份）
    - 结构化日志格式，包含时间戳、级别、错误类型、堆栈信息、上下文变量
    - 提供便捷的日志记录方法
    """

    # 类变量，保存全局单例实例
    _instance: Optional['ErrorLogger'] = None

    def __new__(cls, *args, **kwargs):
        """单例模式，确保全局只有一个日志实例"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, log_dir: str = "logs", log_level: int = logging.INFO):
        """
        初始化日志系统

        :param log_dir: 日志文件存储目录，默认为项目根目录下的 logs/
        :param log_level: 日志级别，默认为 INFO
        """
        # 避免重复初始化
        if hasattr(self, '_initialized') and self._initialized:
            return

        self.log_dir = Path(log_dir)
        self.log_level = log_level
        self.logger_name = "FileManager"

        # 确保日志目录存在
        self._ensure_log_dir()

        # 创建 logger
        self.logger = logging.getLogger(self.logger_name)
        self.logger.setLevel(log_level)

        # 避免重复添加处理器
        if not self.logger.handlers:
            self._setup_handlers()

        self._initialized = True

    def _ensure_log_dir(self) -> None:
        """确保日志目录存在"""
        try:
            self.log_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            print(f"警告：无法创建日志目录 {self.log_dir}: {e}")
            # 回退到当前目录
            self.log_dir = Path(".")

    def _setup_handlers(self) -> None:
        """配置日志处理器（文件 + 控制台）"""
        # 定义详细的日志格式
        log_format = (
            "%(asctime)s | %(levelname)-8s | %(error_type)-20s | "
            "%(message)s | %(context)s | %(stack_trace)s"
        )
        formatter = logging.Formatter(log_format, datefmt="%Y-%m-%d %H:%M:%S")

        # 1. 文件处理器（带轮转）
        log_file = self.log_dir / f"file_manager_{datetime.now().strftime('%Y-%m-%d')}.log"
        file_handler = RotatingFileHandler(
            filename=str(log_file),
            maxBytes=5 * 1024 * 1024,  # 5MB
            backupCount=7,
            encoding='utf-8'
        )
        file_handler.setLevel(self.log_level)
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)

        # 2. 控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(self.log_level)
        # 控制台使用简化格式
        console_format = (
            "%(asctime)s | %(levelname)-8s | %(message)s"
        )
        console_formatter = logging.Formatter(console_format, datefmt="%H:%M:%S")
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)

    def _build_log_record(
        self,
        level: int,
        message: str,
        error_type: Optional[Type[Exception]] = None,
        stack_trace: Optional[str] = None,
        context_vars: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        构建并记录日志

        :param level: 日志级别
        :param message: 日志消息
        :param error_type: 异常类型（如 PermissionError, ValueError 等）
        :param stack_trace: 堆栈跟踪信息
        :param context_vars: 相关上下文变量字典
        """
        # 准备额外信息
        extra = {
            'error_type': error_type.__name__ if error_type else 'None',
            'context': str(context_vars) if context_vars else '{}',
            'stack_trace': stack_trace.replace('\n', '\\n') if stack_trace else 'None'
        }

        self.logger.log(level, message, extra=extra)

    def log(
        self,
        level: int,
        message: str,
        error_type: Optional[Type[Exception]] = None,
        stack_trace: Optional[str] = None,
        context_vars: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        记录日志（通用方法）

        :param level: 日志级别 (DEBUG/INFO/WARNING/ERROR/CRITICAL)
        :param message: 日志消息
        :param error_type: 异常类型（如 PermissionError, ValueError 等）
        :param stack_trace: 堆栈跟踪信息
        :param context_vars: 相关上下文变量字典
        """
        self._build_log_record(level, message, error_type, stack_trace, context_vars)

    def log_error(self, message: str, exc: Optional[Exception] = None, **context) -> None:
        """
        便捷方法：记录 ERROR 级别日志

        :param message: 错误消息
        :param exc: 异常实例（可选，用于提取类型和堆栈）
        :param context: 上下文变量（关键字参数）
        """
        error_type = type(exc) if exc else None
        stack_trace = traceback.format_exc() if exc else None
        context_vars = dict(context) if context else None
        self.log(logging.ERROR, message, error_type, stack_trace, context_vars)

    def log_warning(self, message: str, **context) -> None:
        """
        便捷方法：记录 WARNING 级别日志

        :param message: 警告消息
        :param context: 上下文变量（关键字参数）
        """
        context_vars = dict(context) if context else None
        self.log(logging.WARNING, message, None, None, context_vars)

    def log_info(self, message: str, **context) -> None:
        """
        便捷方法：记录 INFO 级别日志

        :param message: 信息消息
        :param context: 上下文变量（关键字参数）
        """
        context_vars = dict(context) if context else None
        self.log(logging.INFO, message, None, None, context_vars)

    def log_debug(self, message: str, **context) -> None:
        """
        便捷方法：记录 DEBUG 级别日志

        :param message: 调试消息
        :param context: 上下文变量（关键字参数）
        """
        context_vars = dict(context) if context else None
        self.log(logging.DEBUG, message, None, None, context_vars)


# 创建全局默认日志实例
_default_logger: Optional[ErrorLogger] = None


def get_logger(log_dir: str = "logs", log_level: int = logging.INFO) -> ErrorLogger:
    """
    获取全局日志实例（懒加载单例）

    :param log_dir: 日志目录
    :param log_level: 日志级别
    :return: ErrorLogger 实例
    """
    global _default_logger
    if _default_logger is None:
        _default_logger = ErrorLogger(log_dir=log_dir, log_level=log_level)
    return _default_logger


def catch_errors(
    logger: Optional[ErrorLogger] = None,
    reraise: bool = False,
    default: Any = None,
    context: Optional[Dict[str, Any]] = None
) -> Callable:
    """
    错误捕获装饰器，自动记录异常到日志系统

    使用示例：
        @catch_errors()
        def risky_function():
            pass

        @catch_errors(reraise=True, default=[], context={'module': 'search'})
        def search_files():
            pass

    :param logger: ErrorLogger 实例，默认使用全局实例
    :param reraise: 是否重新抛出异常，默认 False
    :param default: 异常发生时的返回值，默认 None
    :param context: 额外的上下文信息
    :return: 装饰后的函数
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # 使用传入的 logger 或全局实例
            lg = logger or get_logger()

            try:
                return func(*args, **kwargs)
            except Exception as e:
                # 构建上下文信息
                ctx = {
                    'function': func.__name__,
                    'module': func.__module__,
                    'args_count': len(args),
                    'kwargs_count': len(kwargs)
                }
                if context:
                    ctx.update(context)

                # 记录异常
                lg.log_error(
                    message=f"函数 {func.__name__} 执行失败: {str(e)}",
                    exc=e,
                    **ctx
                )

                # 根据配置决定是否重新抛出
                if reraise:
                    raise
                return default

        return wrapper

    return decorator


class ErrorContext:
    """
    上下文管理器，用于 with 块内的错误捕获和记录

    使用示例：
        with ErrorContext(context={'operation': 'file_read'}) as ctx:
            # 可能抛出异常的代码
            data = read_file(path)

        if ctx.error:
            print("操作失败，已记录到日志")
    """

    def __init__(
        self,
        logger: Optional[ErrorLogger] = None,
        reraise: bool = False,
        context: Optional[Dict[str, Any]] = None
    ):
        """
        初始化上下文管理器

        :param logger: ErrorLogger 实例
        :param reraise: 是否重新抛出异常
        :param context: 额外上下文信息
        """
        self.logger = logger or get_logger()
        self.reraise = reraise
        self.context = context or {}
        self.error: Optional[Exception] = None
        self.error_message: Optional[str] = None

    def __enter__(self) -> 'ErrorContext':
        """进入上下文"""
        self.logger.log_debug(
            f"进入 ErrorContext 上下文",
            **self.context
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        """
        退出上下文，处理异常

        :return: True 表示异常已被处理，False 表示继续抛出
        """
        if exc_type is not None:
            self.error = exc_val
            self.error_message = str(exc_val)

            # 记录异常
            stack_trace = ''.join(traceback.format_exception(exc_type, exc_val, exc_tb))
            self.logger.log(
                level=logging.ERROR,
                message=f"ErrorContext 捕获异常: {self.error_message}",
                error_type=exc_type,
                stack_trace=stack_trace,
                context_vars=self.context
            )

            if self.reraise:
                return False  # 继续抛出异常
            return True  # 抑制异常

        self.logger.log_debug(
            f"正常退出 ErrorContext 上下文",
            **self.context
        )
        return False
