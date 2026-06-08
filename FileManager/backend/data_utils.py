"""
数据处理工具模块
提供文件大小格式化、时间转换、文件类型识别、数据筛选排序等功能
所有操作均有异常处理，通过 error_logger 记录错误
"""
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

from .error_logger import get_logger, catch_errors


# 获取日志实例
logger = get_logger()


# ==================== 文件类型分类映射表 ====================
# 全面覆盖常见扩展名
FILE_TYPE_MAP = {
    # 文档类
    '文档': {
        '.txt', '.doc', '.docx', '.pdf', '.xls', '.xlsx', '.ppt', '.pptx',
        '.csv', '.rtf', '.odt', '.ods', '.odp', '.md', '.json', '.xml',
        '.html', '.htm', '.log', '.ini', '.cfg', '.yaml', '.yml', '.toml'
    },
    # 图片类
    '图片': {
        '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.ico', '.svg', '.webp',
        '.tiff', '.tif', '.psd', '.raw', '.heic', '.heif', '.avif'
    },
    # 音频类
    '音频': {
        '.mp3', '.wav', '.flac', '.aac', '.ogg', '.wma', '.m4a', '.ape',
        '.mid', '.midi'
    },
    # 视频类
    '视频': {
        '.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v',
        '.rmvb', '.3gp', '.ts', '.mts'
    },
    # 压缩包
    '压缩包': {
        '.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.xz', '.cab',
        '.iso', '.dmg'
    },
    # 程序/代码
    '程序': {
        '.py', '.js', '.java', '.c', '.cpp', '.h', '.cs', '.go', '.rs',
        '.rb', '.php', '.swift', '.kt', '.ts', '.vue', '.jsx', '.tsx',
        '.bat', '.cmd', '.sh', '.ps1', '.exe', '.msi', '.dll', '.so',
        '.class', '.jar', '.whl'
    },
}


@catch_errors(logger=logger, default="0 B", context={'function': 'format_size'})
def format_size(bytes_size: int) -> str:
    """
    将字节数转换为人类可读的格式（KB/MB/GB/TB）

    :param bytes_size: 字节数（整数）
    :return: 格式化后的字符串，如 "1.5 MB"
    """
    if bytes_size < 0:
        logger.log_warning("接收到负的字节大小", size=bytes_size)
        return "0 B"

    # 单位定义（1024进制）
    units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
    size = float(bytes_size)
    unit_index = 0

    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1

    # 根据大小选择精度
    if unit_index == 0:
        return f"{int(size)} {units[unit_index]}"
    elif size < 10:
        return f"{size:.2f} {units[unit_index]}"
    elif size < 100:
        return f"{size:.1f} {units[unit_index]}"
    else:
        return f"{size:.0f} {units[unit_index]}"


@catch_errors(logger=logger, default="未知时间", context={'function': 'format_time'})
def format_time(timestamp: float) -> str:
    """
    将时间戳转换为格式化的日期时间字符串

    :param timestamp: Unix 时间戳（秒级或毫秒级）
    :return: 格式化字符串 "YYYY-MM-DD HH:MM:SS"
    """
    if timestamp is None:
        return "未知时间"

    try:
        # 处理毫秒级时间戳
        if timestamp > 1e12:
            timestamp = timestamp / 1000

        dt = datetime.fromtimestamp(timestamp)
        return dt.strftime("%Y-%m-%d %H:%M:%S")

    except (OSError, ValueError, OverflowError) as e:
        logger.log_error(f"时间戳转换失败: {timestamp}", exc=e)
        return "无效时间"


@catch_errors(logger=logger, default="其他", context={'function': 'get_file_type'})
def get_file_type(file_path: Path) -> str:
    """
    根据文件扩展名判断文件类型分类

    分类类别：文档 / 图片 / 音频 / 视频 / 压缩包 / 程序 / 文件夹 / 其他

    :param file_path: 文件路径对象
    :return: 文件类型字符串
    """
    try:
        # 检查是否为目录
        if file_path.is_dir():
            return "文件夹"

        # 获取扩展名（小写）
        ext = file_path.suffix.lower()

        if not ext:
            return "其他"  # 无扩展名的文件

        # 遍历分类映射表查找匹配项
        for file_type, extensions in FILE_TYPE_MAP.items():
            if ext in extensions:
                return file_type

        return "其他"

    except Exception as e:
        logger.log_error(f"获取文件类型失败: {file_path}", exc=e)
        return "其他"


@catch_errors(logger=logger, default={}, context={'function': 'parse_file_info'})
def parse_file_info(file_path: Path, root_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    解析文件/文件夹的完整信息为结构化字典

    返回的字典包含：
    - name: 文件名
    - path: 完整路径
    - relative_path: 相对路径（如果提供了 root_path）
    - type: 文件类型分类
    - size: 文件大小（字节）
    - size_formatted: 格式化后的大小
    - modified_time: 最后修改时间（时间戳）
    - modified_time_formatted: 格式化后的修改时间
    - is_dir: 是否为目录
    - extension: 文件扩展名

    :param file_path: 文件/文件夹路径
    :param root_path: 根路径（用于计算相对路径），可选
    :return: 包含文件信息的字典
    """
    try:
        # 基本路径信息
        info = {
            'name': file_path.name,
            'path': str(file_path.resolve()),
            'relative_path': '',
            'type': '',
            'size': 0,
            'size_formatted': '0 B',
            'modified_time': 0,
            'modified_time_formatted': '未知时间',
            'is_dir': file_path.is_dir(),
            'extension': file_path.suffix.lower()
        }

        # 文件类型
        info['type'] = get_file_type(file_path)

        # 相对路径
        if root_path:
            info['relative_path'] = get_relative_path(file_path, root_path)

        # 获取文件统计信息
        if file_path.exists():
            stat = file_path.stat()
            info['size'] = stat.st_size
            info['size_formatted'] = format_size(stat.st_size)
            info['modified_time'] = stat.st_mtime
            info['modified_time_formatted'] = format_time(stat.st_mtime)

        return info

    except Exception as e:
        logger.log_error(f"解析文件信息失败: {file_path}", exc=e)
        return {}


@catch_errors(logger=logger, default="", context={'function': 'get_relative_path'})
def get_relative_path(file_path: Path, root_path: Path) -> str:
    """
    计算文件相对于根路径的相对路径

    :param file_path: 文件的绝对路径
    :param root_path: 根目录路径
    :return: 相对路径字符串
    """
    try:
        # 确保都是绝对路径
        file_abs = file_path.resolve()
        root_abs = root_path.resolve()

        # 计算相对路径
        relative = file_abs.relative_to(root_abs)
        return str(relative).replace('\\', '/')  # 统一使用正斜杠

    except ValueError:
        # 文件不在根路径下
        logger.log_warning(
            f"文件不在根路径范围内",
            file=str(file_path),
            root=str(root_path)
        )
        return file_path.name

    except Exception as e:
        logger.log_error(f"计算相对路径失败", exc=e, file=str(file_path))
        return file_path.name


@catch_errors(logger=logger, default=[], context={'function': 'filter_results'})
def filter_results(data_list: List[Dict[str, Any]], **filters) -> List[Dict[str, Any]]:
    """
    对结果列表进行多条件筛选

    支持的筛选方式：
    - 精确匹配：filter_results(data, name='test.txt')
    - 包含匹配（字符串）：filter_results(data, name__contains='test')
    - 范围匹配（数值）：filter_results(data, size__gt=1024)
      支持的操作符：__gt (大于), __gte (大于等于), __lt (小于), __lte (小于等于), __ne (不等于)

    :param data_list: 待筛选的数据列表（字典列表）
    :param filters: 筛选条件（关键字参数）
    :return: 筛选后的数据列表
    """
    if not data_list or not filters:
        return data_list

    result = data_list.copy()

    for filter_key, filter_value in filters.items():
        # 解析操作符
        field = filter_key
        operator = '__eq'  # 默认等值比较

        for op in ['__contains', '__gt', '__gte', '__lt', '__lte', '__ne', '__startswith', '__endswith']:
            if filter_key.endswith(op):
                field = filter_key[:-len(op)]
                operator = op
                break

        # 执行筛选
        filtered_data = []
        for item in result:
            if field not in item:
                continue

            value = item[field]

            try:
                match = False

                if operator == '__eq':
                    match = value == filter_value
                elif operator == '__contains':
                    match = str(filter_value).lower() in str(value).lower()
                elif operator == '__gt':
                    match = value > filter_value
                elif operator == '__gte':
                    match = value >= filter_value
                elif operator == '__lt':
                    match = value < filter_value
                elif operator == '__lte':
                    match = value <= filter_value
                elif operator == '__ne':
                    match = value != filter_value
                elif operator == '__startswith':
                    match = str(value).lower().startswith(str(filter_value).lower())
                elif operator == '__endswith':
                    match = str(value).lower().endswith(str(filter_value).lower())

                if match:
                    filtered_data.append(item)

            except Exception as e:
                logger.log_warning(
                    f"筛选条件执行失败: 字段={field}, 操作符={operator}",
                    exc=e
                )
                # 筛选失败时保留该项（保守策略）
                filtered_data.append(item)

        result = filtered_data

    return result


@catch_errors(logger=logger, default=[], context={'function': 'sort_results'})
def sort_results(
    data_list: List[Dict[str, Any]],
    sort_key: str,
    reverse: bool = False
) -> List[Dict[str, Any]]:
    """
    对结果列表按指定字段排序

    自动处理：
    - 数值型字段按数值排序
    - 字符串字段按字典序排序（忽略大小写）
    - 缺失字段的项排到最后

    :param data_list: 待排序的数据列表
    :param sort_key: 排序依据的字段名
    :param reverse: 是否降序排列，默认 False（升序）
    :return: 排序后的新列表
    """
    if not data_list or not sort_key:
        return data_list

    def sort_key_func(item: Dict[str, Any]):
        """提取排序键值的辅助函数"""
        value = item.get(sort_key)

        # 缺失字段排到最后
        if value is None:
            return (1, '')  # 元组第二项确保类型一致

        # 尝试数值排序
        if isinstance(value, (int, float)):
            return (0, value)

        # 字符串排序（忽略大小写）
        return (0, str(value).lower())

    try:
        return sorted(data_list, key=sort_key_func, reverse=reverse)

    except Exception as e:
        logger.log_error(f"排序失败: 排序字段={sort_key}", exc=e)
        return data_list


def batch_parse_files(file_paths: List[Path], root_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """
    批量解析多个文件的信息

    :param file_paths: 文件路径列表
    :param root_path: 根路径（可选）
    :return: 文件信息字典列表
    """
    results = []

    for file_path in file_paths:
        try:
            info = parse_file_info(file_path, root_path)
            if info:
                results.append(info)
        except Exception as e:
            logger.log_warning(f"批量解析时跳过文件: {file_path}", exc=e)
            continue

    return results
