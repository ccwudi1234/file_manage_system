"""
即时搜索调度器模块
管理所有检索请求的生命周期，是 V2.0 最关键的架构模块

核心功能：
  - 防抖管理：合并连续的快速输入（默认300ms）
  - 线程生命周期：确保同一时刻只有1个活跃检索线程
  - 中断协调：新检索发起时安全中断旧线程
  - 回调分发：检索完成后将结果分发给UI刷新函数

状态流转：Idle → Debouncing → Running → Completed/Cancelled → Idle
"""
import threading
import time
from pathlib import Path
from typing import Callable, List, Dict, Any, Optional

from .error_logger import get_logger
from .search_engine import scan_files
from .data_utils import parse_file_info


# 获取全局日志实例
logger = get_logger()


class SearchScheduler:
    """
    即时搜索调度器 — 管理所有检索请求的生命周期

    负责协调「即时搜索」的复杂时序逻辑：
    1. 接收前端传入的检索请求
    2. 通过防抖 Timer 合并快速连续输入
    3. 在子线程中执行耗时扫描操作
    4. 通过 Tkinter after() 机制安全回调主线程刷新UI
    5. 支持随时中断当前检索并启动新检索
    """

    def __init__(
        self,
        callback: Callable[[List[Dict[str, Any]]], None],
        root_widget=None
    ) -> None:
        """
        初始化搜索调度器

        :param callback: 检索完成后的回调函数，签名为 callback(results: list[dict])
                         回调在主线程中通过 root_widget.after(0, ...) 执行
        :param root_widget: Tkinter 根窗口对象，用于 after() 方法调度主线程回调
        """
        self._callback = callback
        self._root = root_widget
        self._logger = logger

        # 内部状态属性
        self._stop_flag: Optional[threading.Event] = None
        self._debounce_timer: Optional[threading.Timer] = None
        self._current_thread: Optional[threading.Thread] = None
        self._state: str = "idle"
        self._start_time: float = 0.0

        # 待执行的检索参数（防抖期间暂存）
        self._pending_root_path: Optional[Path] = None
        self._pending_keyword: str = ""

    def request_search(
        self,
        root_path: Path,
        keyword: str,
        debounce_ms: int = 300
    ) -> None:
        """
        发起一次检索请求（带防抖）

        执行流程：
        1. 取消上一轮未触发的防抖 Timer
        2. 中断上一轮正在执行的检索线程（设置 stop_flag）
        3. 创建新的 stop_flag (threading.Event)
        4. 启动新的防抖 Timer（debounce_ms 毫秒后执行实际检索）

        :param root_path: 检索根目录路径
        :param keyword: 检索关键词
        :param debounce_ms: 防抖毫秒数，默认300ms
        """
        # 1. 取消上一轮未触发的防抖 Timer
        if self._debounce_timer is not None:
            self._debounce_timer.cancel()
            self._debounce_timer = None

        # 2. 中断上一轮正在执行的检索线程
        if self._current_thread is not None and self._current_thread.is_alive():
            if self._stop_flag is not None:
                self._stop_flag.set()
            # 不 join() 等待旧线程退出，让旧线程自行退出
            self._logger.log_debug("已发送中断信号给上一轮检索线程")

        # 3. 创建新的中断标记（给即将创建的新线程使用）
        self._stop_flag = threading.Event()

        # 4. 暂存检索参数并启动新的防抖 Timer
        self._pending_root_path = root_path
        self._pending_keyword = keyword
        self._state = "debouncing"

        self._debounce_timer = threading.Timer(
            debounce_ms / 1000.0,
            self._on_debounce_timeout
        )
        self._debounce_timer.start()

    def request_search_immediate(self, root_path: Path, keyword: str) -> None:
        """
        立即执行检索（跳过防抖），用于 Enter 键触发

        执行流程：
        1. 取消当前待执行的防抖任务
        2. 中断上一轮正在执行的检索线程
        3. 直接执行检索（不经过防抖等待）

        :param root_path: 检索根目录路径
        :param keyword: 检索关键词
        """
        # 取消待执行的防抖任务
        self.cancel_pending()

        # 中断上一轮正在执行的检索线程
        self.stop_current()

        # 更新待执行参数
        self._pending_root_path = root_path
        self._pending_keyword = keyword

        # 直接执行检索
        self._execute_search()

    def cancel_pending(self) -> None:
        """取消当前待执行的防抖任务"""
        if self._debounce_timer is not None:
            self._debounce_timer.cancel()
            self._debounce_timer = None
            self._logger.log_debug("已取消待执行的防抖任务")

        # 如果处于防抖状态，恢复到空闲状态
        if self._state == "debouncing":
            self._state = "idle"

    def stop_current(self) -> None:
        """中断当前正在执行的检索线程"""
        if self._current_thread is not None and self._current_thread.is_alive():
            if self._stop_flag is not None:
                self._stop_flag.set()
            self._logger.log_info("已发送中断信号，正在停止当前检索线程")
        else:
            self._logger.log_debug("当前没有正在运行的检索线程")

    def is_running(self) -> bool:
        """
        是否有正在执行的检索

        :return: True 表示有活跃的工作线程在运行
        """
        return (
            self._current_thread is not None
            and self._current_thread.is_alive()
            and self._state == "running"
        )

    @property
    def state(self) -> str:
        """
        返回当前调度器状态

        可能的状态值：
          - idle: 空闲，无任何检索活动
          - debouncing: 防抖等待中，用户输入尚未稳定
          - running: 正在执行检索

        :return: 当前状态字符串
        """
        return self._state

    def _on_debounce_timeout(self) -> None:
        """
        防抖计时器超时回调

        当用户停止输入超过 debounce_ms 毫秒后触发，
        清除防抖计时器引用并执行实际检索
        """
        self._debounce_timer = None
        self._execute_search()

    def _execute_search(self) -> None:
        """
        实际执行检索的核心方法

        内部逻辑：
        1. 更新状态为 "running"
        2. 记录开始时间
        3. 在新 daemon Thread 中执行 scan_files()
        4. 如果未被中断(stop_flag未set)，则用 data_utils.parse_file_info() 处理结果
        5. 通过 self._root.after(0, lambda: self._callback(processed_results)) 回到主线程回调
        6. 更新状态为 "idle"
        7. 任何异常都要记录到 error_logger
        """
        # 提取待执行的参数
        root_path = self._pending_root_path
        keyword = self._pending_keyword

        if root_path is None:
            self._logger.log_warning("执行检索失败：缺少根目录路径")
            self._state = "idle"
            return

        # 保存当前 stop_flag 引用（避免被后续请求覆盖）
        current_stop_flag = self._stop_flag

        # 更新状态为运行中
        self._state = "running"
        self._start_time = time.time()

        self._logger.log_info(
            f"开始执行检索",
            root_path=str(root_path),
            keyword=keyword
        )

        def _run() -> None:
            """工作线程中执行的检索逻辑"""
            processed_results: List[Dict[str, Any]] = []

            try:
                # 调用检索引擎进行文件扫描
                raw_results = scan_files(
                    root_path=root_path,
                    keyword=keyword,
                    stop_flag=current_stop_flag
                )

                # 只有未被中断才处理和返回结果
                if current_stop_flag is not None and not current_stop_flag.is_set():
                    # 使用 data_utils 解析每个文件的详细信息
                    for file_path in raw_results:
                        try:
                            file_info = parse_file_info(file_path, root_path)
                            if file_info:
                                processed_results.append(file_info)
                        except Exception as e:
                            self._logger.log_warning(
                                f"解析文件信息时跳过: {file_path}",
                                exc=e
                            )
                            continue

                    elapsed = time.time() - self._start_time
                    self._logger.log_info(
                        f"检索完成",
                        result_count=len(processed_results),
                        elapsed=f"{elapsed:.2f}s"
                    )

                    # 通过 after() 回到主线程执行回调
                    if self._root is not None:
                        results_to_callback = processed_results[:]
                        self._root.after(
                            0,
                            lambda: self._callback(results_to_callback)
                        )
                    else:
                        # 无 root_widget 时直接调用（非Tkinter场景或测试场景）
                        self._callback(processed_results)

                else:
                    self._logger.log_info("检索已被中断，丢弃结果")

            except Exception as e:
                self._logger.log_error(f"检索过程发生异常", exc=e)
            finally:
                # 无论成功还是异常，都恢复空闲状态
                self._state = "idle"

        # 创建并启动守护工作线程
        self._current_thread = threading.Thread(target=_run, daemon=True)
        self._current_thread.start()
