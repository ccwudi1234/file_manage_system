"""
历史管理和配置持久化模块

功能：
- ConfigManager: 应用配置的加载、保存、读取、修改
- HistoryManager: 搜索历史、目录历史的管理和导出

所有文件操作使用 pathlib，异常通过 error_logger 记录
"""
import json
import csv
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional, Union

from .error_logger import get_logger, catch_errors


# 获取日志实例
logger = get_logger()


class ConfigManager:
    """
    配置管理器（V2.0新增）

    负责应用配置的持久化存储，包括：
    - 加载/保存配置文件
    - 读写配置项
    - 提供默认值回退机制
    """

    # 配置文件名
    CONFIG_FILE = "config.json"

    # 默认配置值
    DEFAULTS: Dict[str, Any] = {
        "app": {
            "name": "FileManager",
            "version": "2.0.0",
            "language": "zh_CN"
        },
        "ui": {
            "theme": "light",
            "window_width": 1200,
            "window_height": 800,
            "font_size": 12,
            "show_hidden_files": False,
            "auto_refresh_interval": 5
        },
        "search": {
            "max_results": 1000,
            "case_sensitive": False,
            "search_subdirectories": True,
            "debounce_delay": 300,
            "file_types_filter": []
        },
        "history": {
            "max_search_history": 50,
            "max_directory_history": 20,
            "auto_save": True
        },
        "advanced": {
            "log_level": "INFO",
            "enable_system_tray": False,
            "global_hotkey": "",
            "thread_pool_size": 4
        }
    }

    def __init__(self, config_dir: Optional[Path] = None):
        """
        初始化配置管理器

        :param config_dir: 配置文件所在目录，默认为项目根目录
        """
        self.config_path = Path(config_dir) / self.CONFIG_FILE if config_dir else Path(self.CONFIG_FILE)
        self._config: Dict[str, Any] = {}
        self.load()

    @catch_errors(logger=logger, context={'class': 'ConfigManager', 'method': 'load'})
    def load(self) -> Dict[str, Any]:
        """
        从文件加载配置

        如果文件不存在或解析失败，则使用默认配置

        :return: 加载后的配置字典
        """
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)

                # 深度合并：保留用户设置，补充缺失的默认值
                self._config = self._deep_merge(self.DEFAULTS.copy(), loaded_config)

                logger.log_info(
                    f"配置文件加载成功",
                    file=str(self.config_path)
                )
            else:
                # 文件不存在，使用默认配置
                self._config = self.DEFAULTS.copy()
                logger.log_info(
                    "配置文件不存在，使用默认配置",
                    file=str(self.config_path)
                )

        except json.JSONDecodeError as e:
            logger.log_error(
                f"配置文件JSON格式错误，将使用默认配置",
                exc=e,
                file=str(self.config_path)
            )
            self._config = self.DEFAULTS.copy()

        except Exception as e:
            logger.log_error(
                f"加载配置文件失败，将使用默认配置",
                exc=e,
                file=str(self.config_path)
            )
            self._config = self.DEFAULTS.copy()

        return self._config

    @catch_errors(logger=logger, context={'class': 'ConfigManager', 'method': 'save'})
    def save(self, config: Optional[Dict[str, Any]] = None) -> bool:
        """
        保存配置到文件

        :param config: 要保存的配置字典，如果为None则保存当前配置
        :return: 是否保存成功
        """
        if config is not None:
            self._config = config

        try:
            # 确保父目录存在
            self.config_path.parent.mkdir(parents=True, exist_ok=True)

            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(
                    self._config,
                    f,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True
                )

            logger.log_info("配置文件保存成功", file=str(self.config_path))
            return True

        except Exception as e:
            logger.log_error("保存配置文件失败", exc=e, file=str(self.config_path))
            return False

    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置值（支持点号分隔的嵌套键）

        示例：
            config.get('ui.theme') -> 'light'
            config.get('app.name') -> 'FileManager'

        :param key: 配置键（支持 'section.key' 格式）
        :param default: 键不存在时的默认值
        :return: 配置值
        """
        try:
            # 支持嵌套访问（如 'ui.theme'）
            keys = key.split('.')
            value = self._config

            for k in keys:
                if isinstance(value, dict) and k in value:
                    value = value[k]
                else:
                    return default

            return value

        except Exception as e:
            logger.log_warning(f"获取配置项失败: {key}", exc=e)
            return default

    def set(self, key: str, value: Any) -> bool:
        """
        设置配置值（支持点号分隔的嵌套键）

        示例：
            config.set('ui.theme', 'dark')

        :param key: 配置键（支持 'section.key' 格式）
            :param value: 要设置的值
        :return: 是否设置成功
        """
        try:
            keys = key.split('.')
            config = self._config

            # 遍历到目标位置
            for k in keys[:-1]:
                if k not in config or not isinstance(config[k], dict):
                    config[k] = {}
                config = config[k]

            # 设置值
            config[keys[-1]] = value
            logger.log_debug(f"配置项已更新: {key} = {value}")
            return True

        except Exception as e:
            logger.log_error(f"设置配置项失败: {key}", exc=e)
            return False

    def _deep_merge(self, base: Dict, override: Dict) -> Dict:
        """
        深度合并两个字典（override 的值优先）

        :param base: 基础字典（默认配置）
        :param override: 覆盖字典（用户配置）
        :return: 合并后的新字典
        """
        result = base.copy()

        for key, value in override.items():
            if (key in result and isinstance(result[key], dict)
                    and isinstance(value, dict)):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value

        return result

    def reset_to_defaults(self) -> bool:
        """
        重置所有配置为默认值

        :return: 是否重置成功
        """
        self._config = self.DEFAULTS.copy()
        return self.save()


class HistoryManager:
    """
    历史记录管理器

    管理以下历史数据：
    - 搜索历史（关键词 + 统计信息）
    - 目录访问历史
    - 提供导出功能（CSV/TXT）
    """

    # 历史记录文件名
    HISTORY_FILE = "history.json"

    def __init__(self, history_dir: Optional[Path] = None, config_manager: Optional[ConfigManager] = None):
        """
        初始化历史管理器

        :param history_dir: 历史文件目录，默认为项目根目录
        :param config_manager: 配置管理器实例（用于读取历史相关配置）
        """
        self.history_path = Path(history_dir) / self.HISTORY_FILE if history_dir else Path(self.HISTORY_FILE)
        self.config_manager = config_manager or ConfigManager()
        self._data: Dict[str, Any] = {
            "search_history": [],
            "directory_history": []
        }
        self._load_history()

    @catch_errors(logger=logger, context={'class': 'HistoryManager', 'method': '_load_history'})
    def _load_history(self) -> None:
        """从文件加载历史记录"""
        try:
            if self.history_path.exists():
                with open(self.history_path, 'r', encoding='utf-8') as f:
                    loaded_data = json.load(f)

                # 确保数据结构完整
                self._data = {
                    "search_history": loaded_data.get("search_history", []),
                    "directory_history": loaded_data.get("directory_history", [])
                }

                logger.log_info(
                    "历史记录加载成功",
                    file=str(self.history_path),
                    search_count=len(self._data["search_history"]),
                    dir_count=len(self._data["directory_history"])
                )
            else:
                logger.log_info("历史记录文件不存在，将创建新文件")

        except json.JSONDecodeError as e:
            logger.log_error("历史记录文件格式错误，将重新初始化", exc=e)
            self._data = {"search_history": [], "directory_history": []}

        except Exception as e:
            logger.log_error("加载历史记录失败", exc=e)
            self._data = {"search_history": [], "directory_history": []}

    @catch_errors(logger=logger, context={'class': 'HistoryManager', 'method': '_save_history'})
    def _save_history(self) -> bool:
        """保存历史记录到文件"""
        try:
            # 确保父目录存在
            self.history_path.parent.mkdir(parents=True, exist_ok=True)

            with open(self.history_path, 'w', encoding='utf-8') as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)

            logger.log_debug("历史记录已保存", file=str(self.history_path))
            return True

        except Exception as e:
            logger.log_error("保存历史记录失败", exc=e)
            return False

    def save_history(self, root: str, keyword: str, count: int) -> bool:
        """
        保存一条完整的搜索历史记录

        :param root: 搜索的根目录路径
        :param keyword: 搜索关键词
        :param count: 搜索结果数量
        :return: 是否保存成功
        """
        try:
            history_entry = {
                "root": root,
                "keyword": keyword,
                "count": count,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }

            # 添加到搜索历史头部
            self._data["search_history"].insert(0, history_entry)

            # 限制最大数量
            max_items = self.config_manager.get('history.max_search_history', 50)
            self._data["search_history"] = self._data["search_history"][:max_items]

            return self._save_history()

        except Exception as e:
            logger.log_error("保存搜索历史失败", exc=e, keyword=keyword)
            return False

    def get_history_list(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        获取最近的搜索历史列表

        :param limit: 返回的最大条数
        :return: 历史记录列表（每项包含 root, keyword, count, timestamp）
        """
        try:
            return self._data["search_history"][:limit]
        except Exception as e:
            logger.log_error("获取历史列表失败", exc=e)
            return []

    def add_search_history(self, keyword: str) -> bool:
        """
        快捷方式：仅添加搜索关键词到历史（简化版）

        :param keyword: 搜索关键词
        :return: 是否添加成功
        """
        try:
            # 检查是否已存在相同关键词
            existing_keywords = [h.get('keyword', '') for h in self._data["search_history"]]

            if keyword in existing_keywords:
                # 移动到最前面
                self._data["search_history"] = [
                    h for h in self._data["search_history"]
                    if h.get('keyword', '') != keyword
                ]

            # 添加到头部
            self._data["search_history"].insert(0, {
                "root": "",
                "keyword": keyword,
                "count": 0,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })

            # 限制最大数量
            max_items = self.config_manager.get('history.max_search_history', 50)
            self._data["search_history"] = self._data["search_history"][:max_items]

            return self._save_history()

        except Exception as e:
            logger.log_error("添加搜索历史失败", exc=e, keyword=keyword)
            return False

    def get_search_history(self, limit: int = 20) -> List[str]:
        """
        获取搜索关键词列表（仅返回关键词字符串）

        :param limit: 返回的最大条数
        :return: 关键词字符串列表
        """
        try:
            keywords = [
                h.get('keyword', '')
                for h in self._data["search_history"]
                if h.get('keyword')
            ]
            return keywords[:limit]
        except Exception as e:
            logger.log_error("获取搜索历史失败", exc=e)
            return []

    def add_directory_history(self, dir_path: str) -> bool:
        """
        添加目录访问历史

        :param dir_path: 目录路径
        :return: 是否添加成功
        """
        try:
            # 检查是否已存在
            if dir_path in self._data["directory_history"]:
                # 移动到最前面
                self._data["directory_history"].remove(dir_path)

            # 添加到头部
            self._data["directory_history"].insert(0, dir_path)

            # 限制最大数量
            max_items = self.config_manager.get('history.max_directory_history', 20)
            self._data["directory_history"] = self._data["directory_history"][:max_items]

            return self._save_history()

        except Exception as e:
            logger.log_error("添加目录历史失败", exc=e, dir_path=dir_path)
            return False

    def get_directory_history(self, limit: int = 10) -> List[str]:
        """
        获取最近访问的目录列表

        :param limit: 返回的最大条数
        :return: 目录路径字符串列表
        """
        try:
            return self._data["directory_history"][:limit]
        except Exception as e:
            logger.log_error("获取目录历史失败", exc=e)
            return []

    @catch_errors(logger=logger, context={'class': 'HistoryManager', 'method': 'export_to_csv'})
    def export_to_csv(self, data_list: List[Dict[str, Any]], save_path: Union[str, Path]) -> bool:
        """
        导出数据到 CSV 文件

        :param data_list: 要导出的数据列表（字典列表）
        :param save_path: 保存路径
        :return: 是否导出成功
        """
        try:
            save_path = Path(save_path)

            if not data_list:
                logger.log_warning("导出CSV失败：数据列表为空")
                return False

            # 提取所有可能的字段名
            fieldnames = set()
            for item in data_list:
                fieldnames.update(item.keys())
            fieldnames = sorted(fieldnames)

            # 写入 CSV
            with open(save_path, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(data_list)

            logger.log_info(
                f"CSV导出成功",
                file=str(save_path),
                record_count=len(data_list)
            )
            return True

        except Exception as e:
            logger.log_error("导出CSV失败", exc=e, file=str(save_path))
            return False

    @catch_errors(logger=logger, context={'class': 'HistoryManager', 'method': 'export_to_txt'})
    def export_to_txt(self, data_list: List[Dict[str, Any]], save_path: Union[str, Path]) -> bool:
        """
        导出数据到文本文件（格式化的表格形式）

        :param data_list: 要导出的数据列表
        :param save_path: 保存路径
        :return: 是否导出成功
        """
        try:
            save_path = Path(save_path)

            if not data_list:
                logger.log_warning("导出TXT失败：数据列表为空")
                return False

            lines = []
            lines.append("=" * 80)
            lines.append(f"FileManager 数据导出 | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            lines.append(f"共 {len(data_list)} 条记录")
            lines.append("=" * 80)
            lines.append("")

            # 写入每条记录
            for idx, item in enumerate(data_list, 1):
                lines.append(f"--- 记录 {idx} ---")
                for key, value in item.items():
                    lines.append(f"{key}: {value}")
                lines.append("")

            # 写入文件
            with open(save_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(lines))

            logger.log_info(
                f"TXT导出成功",
                file=str(save_path),
                record_count=len(data_list)
            )
            return True

        except Exception as e:
            logger.log_error("导出TXT失败", exc=e, file=str(save_path))
            return False

    def clear_search_history(self) -> bool:
        """
        清空搜索历史

        :return: 是否清空成功
        """
        try:
            self._data["search_history"] = []
            return self._save_history()
        except Exception as e:
            logger.log_error("清空搜索历史失败", exc=e)
            return False

    def clear_directory_history(self) -> bool:
        """
        清空目录历史

        :return: 是否清空成功
        """
        try:
            self._data["directory_history"] = []
            return self._save_history()
        except Exception as e:
            logger.log_error("清空目录历史失败", exc=e)
            return False

    def export_all_history_csv(self, save_path: Union[str, Path]) -> bool:
        """
        导出全部历史记录到 CSV

        :param save_path: 保存路径
        :return: 是否导出成功
        """
        all_data = self._data.get("search_history", []) + [
            {"path": d, "type": "directory"}
            for d in self._data.get("directory_history", [])
        ]
        return self.export_to_csv(all_data, save_path)
