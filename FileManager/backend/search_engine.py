"""
核心检索引擎模块
提供目录遍历、关键词匹配、中断感知等核心检索功能
支持 Everything 式搜索语法（通配符/排除/多条件AND）
所有异常通过 error_logger 记录
"""
import fnmatch
import threading
from pathlib import Path
from typing import Callable, List

from .error_logger import get_logger


# 获取全局日志实例
logger = get_logger()


def scan_files(
    root_path: Path,
    keyword: str,
    stop_flag: threading.Event = None,
    progress_callback: Callable[[int], None] = None,
    max_results: int = 10000
) -> List[Path]:
    """
    递归遍历目录并匹配关键词（支持中断和进度报告）

    :param root_path: 有效的根目录Path对象
    :param keyword: 检索关键词，支持 Everything 式搜索语法
                    - 空关键词: 匹配全部文件
                    - 排除语法: "!mp3" → 文件名不含 mp3
                    - 多条件AND: "report pdf" → 名称含 report 且 含 pdf
                    - 通配符: "*.pdf", "report.*"
                    - 普通模糊: "report" → 文件名包含 report
    :param stop_flag: 外部中断信号，被 set() 时立即停止遍历
    :param progress_callback: 进度回调(已扫描文件数)，用于实时更新UI
    :param max_results: 最大返回结果数量限制，默认10000
    :return: 匹配的Path对象列表
    """
    matched_files: List[Path] = []
    scanned_count = 0

    try:
        for item in root_path.rglob("*"):
            # 中断检查：每处理一个文件检查一次 stop_flag
            if stop_flag is not None and stop_flag.is_set():
                logger.log_info(f"检索被用户中断，已扫描 {scanned_count} 个文件")
                break

            # 尝试匹配关键词
            try:
                if _match_keyword(item.name, keyword):
                    matched_files.append(item)

                    # 达到最大结果数限制时提前终止
                    if len(matched_files) >= max_results:
                        logger.log_info(
                            f"已达最大结果数限制 {max_results}，停止扫描",
                            scanned=scanned_count
                        )
                        break

            except PermissionError as e:
                # 跳过无权访问的项并记录日志
                logger.log_warning(f"跳过无权限访问的项: {item}", exc=e)
                continue
            except OSError as e:
                # 跳过系统错误项并记录日志
                logger.log_warning(f"跳过系统错误的项: {item}", exc=e)
                continue

            scanned_count += 1

            # 进度回调节流：每 100 个文件报告一次，避免过于频繁更新UI
            if progress_callback is not None and scanned_count % 100 == 0:
                try:
                    progress_callback(scanned_count)
                except Exception as e:
                    logger.log_warning("进度回调执行失败", exc=e)

    except Exception as e:
        logger.log_error(f"扫描过程中发生异常: {root_path}", exc=e)

    return matched_files


def _match_keyword(filename: str, keyword: str) -> bool:
    """
    Everything 风格的关键词匹配

    支持的搜索语法：
      - 空关键词: 返回 True（匹配全部）
      - 排除语法: "!mp3" → 文件名不含 mp3
      - 多条件AND: "report pdf" → 名称含 report 且 含 pdf
      - 通配符: "*.pdf", "report.*" → fnmatch 匹配
      - 普通模糊: "report" → 文件名包含 report

    所有匹配使用小写比较（大小写不敏感）

    :param filename: 待匹配的文件名字符串
    :param keyword: 检索关键词字符串
    :return: 是否匹配成功
    """
    keyword_lower = keyword.lower().strip()
    filename_lower = filename.lower()

    # 空关键词匹配全部文件
    if not keyword_lower:
        return True

    # 排除语法：以 '!' 开头时取反匹配结果
    if keyword_lower.startswith('!'):
        exclude_pattern = keyword_lower[1:]
        if not exclude_pattern:
            return True
        return not _match_single(filename_lower, exclude_pattern)

    # 多条件 AND：包含空格时拆分，每个子条件必须都满足
    if ' ' in keyword_lower:
        parts = keyword_lower.split()
        return all(_match_single(filename_lower, p) for p in parts)

    # 单条件匹配（模糊包含或通配符）
    return _match_single(filename_lower, keyword_lower)


def _match_single(filename: str, pattern: str) -> bool:
    """
    单条件匹配（模糊包含或通配符）

    匹配规则：
      - pattern 包含 * 或 ? 通配符时 → 使用 fnmatch.fnmatch() 精确模式匹配
      - 否则 → 使用纯文本模糊包含（pattern in filename）

    :param filename: 小写化的文件名字符串
    :param pattern: 小写化的匹配模式字符串
    :return: 是否匹配成功
    """
    # 包含通配符 (* 或 ?) → 使用 fnmatch 进行模式匹配
    if '*' in pattern or '?' in pattern:
        try:
            return fnmatch.fnmatch(filename, pattern)
        except Exception as e:
            logger.log_warning(f"通配符匹配失败: pattern={pattern}, filename={filename}", exc=e)
            return False

    # 纯文本 → 模糊包含匹配
    return pattern in filename
