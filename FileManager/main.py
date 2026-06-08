"""
FileManager 主程序 - Everything 风格文件搜索桌面应用
提供极简的即时搜索体验：输入即搜、键盘驱动、系统托盘常驻
"""
import sys
import os
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

# 添加项目根目录到系统路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from FileManager.backend.error_logger import get_logger, ErrorLogger
from FileManager.backend.search_scheduler import SearchScheduler
from FileManager.backend.history_manager import HistoryManager, ConfigManager
from FileManager.backend.path_validator import check_root_path
from FileManager.backend.data_utils import sort_results


# ==================== 配色规范（Everything 浅色主题）====================
COLORS = {
    'bg': '#FFFFFF',           # 纯白背景
    'fg': '#1E1E1E',           # 近黑文字
    'entry_bg': '#FFFFFF',     # 输入框白底
    'entry_focus': '#0078D4',  # Windows蓝聚焦环
    'select_bg': '#CBE7F5',    # 半透明蓝选中底
    'header_bg': '#F0F0F0',    # 表头浅灰
    'header_fg': '#3C3C3C',    # 表头深灰文字
    'status_bg': '#F5F5F5',    # 状态行浅灰底
    'status_fg': '#6E6E6E',    # 状态行中灰文字
    'border': '#E5E5E5',       # 分隔线
    'accent': '#0078D4',       # 强调色(Windows蓝)
}

# 全局字体配置
FONT = ("Segoe UI", 10)
FONT_BOLD = ("Segoe UI", 10, "bold")


class FileManagerApp:
    """
    Everything 风格文件搜索桌面应用主类

    核心功能：
    - 极简两区域布局（搜索栏 + 结果列表）
    - 即时搜索机制（300ms防抖）
    - 键盘完全驱动操作
    - 系统托盘常驻
    - 全局热键唤醒
    """

    def __init__(self, root: tk.Tk) -> None:
        """
        初始化窗口、加载配置、创建控件、绑定事件

        :param root: Tkinter 根窗口对象
        """
        self.root = root
        self.logger: ErrorLogger = get_logger()

        # 初始化配置管理器
        project_dir = Path(__file__).parent.parent
        self.config_manager = ConfigManager(config_dir=project_dir)
        self.history_manager = HistoryManager(
            history_dir=project_dir,
            config_manager=self.config_manager
        )

        # 当前状态变量
        self.current_directory: Optional[Path] = None
        self.search_results: List[Dict[str, Any]] = []
        self.last_search_time: float = 0.0
        self._tray_icon = None

        # 搜索动画状态变量
        self._animation_running: bool = False
        self._spinner_angle: float = 0.0
        self._spinner_job: Optional[str] = None
        self._dots_job: Optional[str] = None
        self._pulse_job: Optional[str] = None
        self._dots_count: int = 0
        self._original_icon_text: str = "🔍"

        # 初始化UI
        self._setup_window()
        self._create_ui()
        self._init_search_scheduler()
        self._bind_events()
        self._setup_tray()
        self._setup_global_hotkey()

        # 加载历史目录到下拉框
        self._load_directory_history()

        # 设置默认目录（优先级：配置 > 历史记录 > 当前目录）
        default_dir = self.config_manager.get('ui.default_directory', '')
        if default_dir and Path(default_dir).exists():
            self._set_directory(Path(default_dir))
        else:
            # 尝试使用历史中最近的目录
            history = self.history_manager.get_directory_history(limit=1)
            if history and Path(history[0]).exists():
                self._set_directory(Path(history[0]))
            # 如果都没有，显示空状态提示（不自动设置目录）

        # 聚焦搜索框
        self.search_entry.focus_set()

        # 确保窗口显示在最前面
        self.root.lift()
        self.root.attributes('-topmost', True)
        self.root.after(100, lambda: self.root.attributes('-topmost', False))

        self.logger.log_info("FileManager 应用初始化完成")

    def _setup_window(self) -> None:
        """设置主窗口属性"""
        self.root.title("FileManager")
        self.root.configure(bg=COLORS['bg'])

        # 从配置恢复窗口位置和大小
        width = self.config_manager.get('ui.window_width', 600)
        height = self.config_manager.get('ui.window_height', 480)

        self.root.geometry(f"{width}x{height}")
        self.root.minsize(500, 400)

        # 尝试恢复窗口位置
        pos_x = self.config_manager.get('ui.window_x')
        pos_y = self.config_manager.get('ui.window_y')
        if pos_x is not None and pos_y is not None:
            try:
                self.root.geometry(f"+{pos_x}+{pos_y}")
            except Exception:
                pass

        # 关闭时最小化到托盘（不退出）
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

    def _create_ui(self) -> None:
        """创建所有UI控件"""
        # 主容器
        self.main_frame = ttk.Frame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        # 创建各区域
        self._create_path_bar()
        self._create_search_bar()
        self._create_results_tree()
        self._create_status_bar()

    def _create_path_bar(self) -> None:
        """创建顶部路径栏区域"""
        path_frame = tk.Frame(self.main_frame, bg=COLORS['bg'], height=35)
        path_frame.pack(fill=tk.X, padx=(0, 0), pady=(2, 0))
        path_frame.pack_propagate(False)

        # 目录选择下拉框
        self.directory_var = tk.StringVar()
        self.directory_combo = ttk.Combobox(
            path_frame,
            textvariable=self.directory_var,
            font=FONT,
            width=40,
            state='readonly'
        )
        self.directory_combo.pack(side=tk.LEFT, padx=(5, 5), pady=5)
        self.directory_combo.bind('<<ComboboxSelected>>', self._on_directory_change)

        # 浏览按钮
        browse_btn = tk.Button(
            path_frame,
            text="📁",
            font=FONT,
            width=3,
            command=self._browse_directory,
            bg=COLORS['bg'],
            activebackground=COLORS['select_bg'],
            relief=tk.FLAT,
            cursor="hand2"
        )
        browse_btn.pack(side=tk.LEFT, padx=2, pady=5)

        # 刷新按钮
        refresh_btn = tk.Button(
            path_frame,
            text="🔄",
            font=FONT,
            width=3,
            command=self._refresh_search,
            bg=COLORS['bg'],
            activebackground=COLORS['select_bg'],
            relief=tk.FLAT,
            cursor="hand2"
        )
        refresh_btn.pack(side=tk.LEFT, padx=2, pady=5)

    def _create_search_bar(self) -> None:
        """创建搜索栏区域（含搜索动画旋转指示器）"""
        search_frame = tk.Frame(self.main_frame, bg=COLORS['border'], height=45)
        search_frame.pack(fill=tk.X, padx=(0, 0), pady=(2, 0))
        search_frame.pack_propagate(False)

        # ===== 搜索图标/旋转动画区域 =====
        # 使用 Canvas 绘制可旋转的加载指示器
        self.spinner_canvas = tk.Canvas(
            search_frame,
            width=22,
            height=22,
            bg=COLORS['bg'],
            highlightthickness=0
        )
        self.spinner_canvas.pack(side=tk.LEFT, padx=(8, 5), pady=11)

        # 绘制初始静态 🔍 图标（用文字模拟）
        self._spinner_text_id = self.spinner_canvas.create_text(
            11, 11, text="🔍", font=("Segoe UI Emoji", 12), anchor='center'
        )

        # 搜索输入框
        self.search_var = tk.StringVar()
        self.search_entry = tk.Entry(
            search_frame,
            textvariable=self.search_var,
            font=FONT,
            bg=COLORS['entry_bg'],
            fg=COLORS['fg'],
            relief=tk.FLAT,
            insertbackground=COLORS['fg']
        )
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5), pady=8)

        # placeholder 效果
        self.placeholder_text = "输入关键词开始搜索文件..."
        self._show_placeholder()

        # 设置按钮
        settings_btn = tk.Button(
            search_frame,
            text="⚙️",
            font=FONT,
            width=3,
            command=self._show_settings,
            bg=COLORS['bg'],
            activebackground=COLORS['select_bg'],
            relief=tk.FLAT,
            cursor="hand2"
        )
        settings_btn.pack(side=tk.RIGHT, padx=(2, 8), pady=10)

        # 最小化到托盘按钮
        minimize_btn = tk.Button(
            search_frame,
            text="🗘",
            font=FONT,
            width=3,
            command=lambda: self._on_closing(),
            bg=COLORS['bg'],
            activebackground=COLORS['select_bg'],
            relief=tk.FLAT,
            cursor="hand2"
        )
        minimize_btn.pack(side=tk.RIGHT, padx=2, pady=10)

    def _create_results_tree(self) -> None:
        """创建结果列表 Treeview（含空状态提示）"""
        # Treeview 容器
        tree_frame = tk.Frame(self.main_frame, bg=COLORS['bg'])
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=(0, 0), pady=(2, 0))

        # 定义列
        columns = ('name', 'path', 'size', 'date', 'type')

        self.results_tree = ttk.Treeview(
            tree_frame,
            columns=columns,
            show='headings',
            selectmode='browse',
            style='Custom.Treeview'
        )

        # 配置列
        self.results_tree.heading('name', text='文件名', command=lambda: self._sort_by_column('name'))
        self.results_tree.heading('path', text='路径', command=lambda: self._sort_by_column('path'))
        self.results_tree.heading('size', text='大小', command=lambda: self._sort_by_column('size'))
        self.results_tree.heading('date', text='日期', command=lambda: self._sort_by_column('date'))
        self.results_tree.heading('type', text='类型', command=lambda: self._sort_by_column('type'))

        # 设置列宽和对齐方式
        self.results_tree.column('name', width=200, minwidth=150, anchor='w')
        self.results_tree.column('path', width=200, minwidth=150, anchor='w')
        self.results_tree.column('size', width=80, minwidth=60, anchor='e')
        self.results_tree.column('date', width=100, minwidth=80, anchor='w')
        self.results_tree.column('type', width=70, minwidth=50, anchor='w')

        # 滚动条
        scrollbar_y = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.results_tree.yview)
        scrollbar_x = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=self.results_tree.xview)

        self.results_tree.configure(yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)

        # 布局
        self.results_tree.grid(row=0, column=0, sticky='nsew')
        scrollbar_y.grid(row=0, column=1, sticky='ns')
        scrollbar_x.grid(row=1, column=0, sticky='ew')

        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        # ===== 空状态提示标签（居中显示在Treeview上方） =====
        self.empty_label = tk.Label(
            tree_frame,
            text="📂 请先选择要搜索的目录",
            font=("Segoe UI", 12),
            bg=COLORS['bg'],
            fg=COLORS['status_fg']
        )
        self.empty_label.place(relx=0.5, rely=0.5, anchor='center')

        # 配置样式（兼容 Windows 多主题）
        style = ttk.Style()

        # 检测当前平台并选择合适的主题
        available_themes = style.theme_names()
        if 'clam' in available_themes:
            style.theme_use('clam')
        elif 'default' in available_themes:
            style.theme_use('default')

        style.configure(
            'Custom.Treeview',
            background=COLORS['bg'],
            foreground=COLORS['fg'],
            fieldbackground=COLORS['bg'],
            font=FONT,
            rowheight=25
        )
        style.configure(
            'Custom.Treeview.Heading',
            background=COLORS['header_bg'],
            foreground=COLORS['header_fg'],
            font=FONT_BOLD
        )
        style.map(
            'Custom.Treeview',
            background=[('selected', COLORS['select_bg'])],
            foreground=[('selected', COLORS['fg'])]
        )

        # 绑定选择事件
        self.results_tree.bind('<<TreeviewSelect>>', self._on_tree_select)
        self.results_tree.bind('<Double-1>', lambda e: self._open_file())

    def _create_status_bar(self) -> None:
        """创建底部迷你状态行"""
        status_frame = tk.Frame(self.main_frame, bg=COLORS['status_bg'], height=24)
        status_frame.pack(fill=tk.X, side=tk.BOTTOM)
        status_frame.pack_propagate(False)

        # 左侧：结果统计
        self.status_left = tk.Label(
            status_frame,
            text="就绪",
            font=("Segoe UI", 9),
            bg=COLORS['status_bg'],
            fg=COLORS['status_fg'],
            anchor='w'
        )
        self.status_left.pack(side=tk.LEFT, padx=(10, 0))

        # 中间：耗时
        self.status_center = tk.Label(
            status_frame,
            text="",
            font=("Segoe UI", 9),
            bg=COLORS['status_bg'],
            fg=COLORS['status_fg']
        )
        self.status_center.pack(side=tk.LEFT, padx=20)

        # 右侧：当前目录
        self.status_right = tk.Label(
            status_frame,
            text="",
            font=("Segoe UI", 9),
            bg=COLORS['status_bg'],
            fg=COLORS['status_fg'],
            anchor='e'
        )
        self.status_right.pack(side=tk.RIGHT, padx=(0, 10))

    def _init_search_scheduler(self) -> None:
        """初始化搜索调度器"""
        self.scheduler = SearchScheduler(
            callback=self._search_callback,
            root_widget=self.root
        )

    def _bind_events(self) -> None:
        """绑定所有事件"""
        # 搜索框事件
        self.search_entry.bind('<KeyRelease>', self._on_key_release)
        self.search_entry.bind('<Return>', self._on_enter)
        self.search_entry.bind('<Escape>', self._on_escape)
        self.search_entry.bind('<Down>', self._focus_to_tree)
        self.search_entry.bind('<FocusIn>', self._on_search_focus_in)
        self.search_entry.bind('<FocusOut>', self._on_search_focus_out)

        # 绑定键盘快捷键到根窗口和树形控件
        self._bind_keyboard()

        # 窗口大小变化事件
        self.root.bind('<Configure>', self._on_window_configure)

    def _bind_keyboard(self) -> None:
        """绑定所有键盘快捷键"""
        # 结果列表键盘事件
        self.results_tree.bind('<Up>', lambda e: self._navigate_tree(-1))
        self.results_tree.bind('<Down>', lambda e: self._navigate_tree(1))
        self.results_tree.bind('<Return>', lambda e: self._open_file())
        self.results_tree.bind('<Control-Return>', lambda e: self._open_location())
        self.results_tree.bind('<Control-c>', lambda e: self._copy_path())
        self.results_tree.bind('<Delete>', lambda e: self._delete_selected_item())
        self.results_tree.bind('<Tab>', lambda e: self._toggle_focus())
        self.results_tree.bind('<F2>', lambda e: self._rename_file())

        # 右键菜单
        self.results_tree.bind('<Button-3>', self._show_context_menu)

    def _on_key_release(self, event: tk.Event) -> None:
        """
        即时搜索触发：KeyRelease事件处理

        获取当前输入内容并调用SearchScheduler进行防抖检索，
        搜索开始时立即启动动画反馈
        """
        keyword = self.search_var.get().strip()

        if not self.current_directory:
            return

        # 启动搜索动画（用户有输入即显示加载状态）
        if keyword:
            self._start_search_animation()

        # 获取防抖延迟配置
        debounce_ms = self.config_manager.get('search.debounce_delay', 300)

        # 调用调度器发起检索请求
        self.scheduler.request_search(
            root_path=self.current_directory,
            keyword=keyword,
            debounce_ms=debounce_ms
        )

    def _on_enter(self, event: Optional[tk.Event] = None) -> None:
        """
        Enter键立即执行检索（跳过防抖）
        """
        keyword = self.search_var.get().strip()

        if not self.current_directory:
            messagebox.showwarning("提示", "请先选择要搜索的目录")
            return

        # 启动搜索动画
        self._start_search_animation()

        # 立即执行检索
        self.scheduler.request_search_immediate(
            root_path=self.current_directory,
            keyword=keyword
        )

    def _on_escape(self, event: Optional[tk.Event] = None) -> None:
        """
        Escape键清空搜索框和结果列表
        """
        # 停止搜索动画
        self._stop_search_animation()

        self.search_var.set("")
        self._clear_results()
        self._update_status(left_text="就绪", center_text="", right_text="")
        self._show_placeholder()

    def _focus_to_tree(self, event: Optional[tk.Event] = None) -> None:
        """
        将焦点从搜索框移到结果列表第一行
        """
        if self.results_tree.get_children():
            self.results_tree.selection_set(self.results_tree.get_children()[0])
            self.results_tree.focus_set()

    def _search_callback(self, results: List[Dict[str, Any]]) -> None:
        """
        搜索完成回调函数

        处理流程：
        0. 停止所有搜索动画
        1. 记录耗时
        2. 清空旧结果
        3. 将新结果填充到Treeview
        4. 更新状态行统计信息
        5. 保存搜索历史

        :param results: 搜索结果列表，每项为文件信息字典
        """
        # 停止搜索动画
        self._stop_search_animation()

        # 记录耗时
        elapsed = time.time() - self.last_search_time if self.last_search_time > 0 else 0

        # 保存结果引用
        self.search_results = results

        # 填充结果到Treeview
        self._populate_results(results)

        # 更新状态行
        count = len(results)
        self._update_status(
            left_text=f"已找到 {count} 个文件" if count > 0 else "未找到匹配文件",
            center_text=f"{elapsed:.2f}s" if elapsed > 0 else "",
            right_text=str(self.current_directory) if self.current_directory else ""
        )

        # 保存搜索历史
        if results:
            keyword = self.search_var.get().strip()
            try:
                self.history_manager.save_history(
                    root=str(self.current_directory),
                    keyword=keyword,
                    count=count
                )
            except Exception as e:
                self.logger.log_warning("保存搜索历史失败", exc=e)

    def _populate_results(self, results: List[Dict[str, Any]]) -> None:
        """
        填充搜索结果到Treeview

        :param results: 文件信息字典列表
        """
        # 清空现有结果
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)

        # 控制空状态标签：有数据时隐藏，无数据时显示提示
        if not results:
            self.empty_label.place(relx=0.5, rely=0.5, anchor='center')
            keyword = self.search_var.get().strip()
            if keyword:
                self.empty_label.config(text=f"😕 未找到匹配 \"{keyword}\" 的文件\n\n建议: 检查拼写 / 尝试通配符 (*.pdf) / 更换目录")
            elif not self.current_directory:
                self.empty_label.config(text="📂 请先选择要搜索的目录\n\n点击 📁 按钮浏览文件夹")
            else:
                self.empty_label.config(text="📂 输入关键词开始搜索文件")
            return

        # 有结果时隐藏空状态提示
        self.empty_label.place_forget()

        # 应用排序
        sort_key = self.config_manager.get('search.sort_key', 'name')
        reverse = self.config_manager.get('search.sort_reverse', False)
        sorted_results = sort_results(results, sort_key, reverse)

        # 限制最大结果显示数
        max_results = self.config_manager.get('search.max_results', 10000)
        display_results = sorted_results[:max_results]

        # 是否隐藏隐藏文件
        hide_hidden = self.config_manager.get('ui.show_hidden_files', True)

        # 插入数据
        inserted_count = 0
        for item_data in display_results:
            try:
                name = item_data.get('name', '')
                path = item_data.get('path', '')
                size_formatted = item_data.get('size_formatted', '0 B')
                date_formatted = item_data.get('modified_time_formatted', '')
                file_type = item_data.get('type', '')

                # 过滤隐藏文件（以.开头的文件）
                if hide_hidden and name.startswith('.'):
                    continue

                self.results_tree.insert('', tk.END, values=(
                    name,
                    path,
                    size_formatted,
                    date_formatted,
                    file_type
                ), tags=(file_type,))
                inserted_count += 1
            except Exception as e:
                self.logger.log_warning(f"插入结果项失败: {item_data}", exc=e)
                continue

        self.logger.log_info(f"Treeview已填充 {inserted_count} 条结果")

    def _clear_results(self) -> None:
        """清空结果列表并显示空状态提示"""
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)
        self.search_results = []
        # 显示空状态提示
        self.empty_label.place(relx=0.5, rely=0.5, anchor='center')
        if self.current_directory:
            self.empty_label.config(text="📂 输入关键词开始搜索文件")
        else:
            self.empty_label.config(text="📂 请先选择要搜索的目录\n\n点击 📁 按钮浏览文件夹")

    def _update_status(
        self,
        left_text: str = "",
        center_text: str = "",
        right_text: str = ""
    ) -> None:
        """
        更新迷你状态行显示内容

        :param left_text: 左侧文本（结果统计）
        :param center_text: 中间文本（耗时）
        :param right_text: 右侧文本（当前目录）
        """
        self.status_left.config(text=left_text, fg=COLORS['status_fg'])
        self.status_center.config(text=center_text)
        self.status_right.config(text=right_text)

    def _on_tree_select(self, event: tk.Event) -> None:
        """
        结果列表选中事件处理

        更新状态行显示选中文件的详细信息
        """
        selection = self.results_tree.selection()
        if not selection:
            return

        item_id = selection[0]
        values = self.results_tree.item(item_id, 'values')

        if values and len(values) >= 5:
            name, path, size, date, file_type = values
            self._update_status(
                left_text=f"已找到 {len(self.search_results)} 个文件 │ {name}",
                center_text=f"{size} │ {date}",
                right_text=path
            )

    def _navigate_tree(self, direction: int) -> None:
        """
        在结果列表中上下移动选中行

        :param direction: 移动方向，-1向上，1向下
        """
        items = self.results_tree.get_children()
        if not items:
            return

        current_selection = self.results_tree.selection()
        if not current_selection:
            # 无选中项时选中第一个或最后一个
            target_index = 0 if direction > 0 else len(items) - 1
        else:
            current_index = items.index(current_selection[0])
            target_index = (current_index + direction) % len(items)

        self.results_tree.selection_set(items[target_index])
        self.results_tree.see(items[target_index])

    def _open_file(self) -> None:
        """
        打开选中的文件（使用系统默认程序）

        这是唯一允许使用os的地方
        """
        file_path = self._get_selected_file_path()
        if not file_path or not Path(file_path).exists():
            messagebox.showwarning("提示", "请先选择一个有效的文件")
            return

        try:
            os.startfile(file_path)
            self.logger.log_info(f"打开文件: {file_path}")
        except Exception as e:
            self.logger.log_error(f"打开文件失败: {file_path}", exc=e)
            messagebox.showerror("错误", f"无法打开文件:\n{str(e)}")

    def _open_location(self) -> None:
        """
        打开文件所在的文件夹（在资源管理器中定位）
        """
        file_path = self._get_selected_file_path()
        if not file_path or not Path(file_path).exists():
            messagebox.showwarning("提示", "请先选择一个有效的文件")
            return

        try:
            folder_path = str(Path(file_path).parent)
            os.startfile(folder_path)
            self.logger.log_info(f"打开文件夹: {folder_path}")
        except Exception as e:
            self.logger.log_error(f"打开文件夹失败: {folder_path}", exc=e)
            messagebox.showerror("错误", f"无法打开文件夹:\n{str(e)}")

    def _copy_path(self) -> None:
        """
        复制选中文件的完整路径到剪贴板
        """
        file_path = self._get_selected_file_path()
        if not file_path:
            return

        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(file_path)
            self.logger.log_info(f"复制路径到剪贴板: {file_path}")
        except Exception as e:
            self.logger.log_error("复制路径失败", exc=e)

    def _copy_name(self) -> None:
        """
        复制选中文件的名称到剪贴板
        """
        selection = self.results_tree.selection()
        if not selection:
            return

        try:
            values = self.results_tree.item(selection[0], 'values')
            if values:
                name = values[0]
                self.root.clipboard_clear()
                self.root.clipboard_append(name)
                self.logger.log_info(f"复制文件名到剪贴板: {name}")
        except Exception as e:
            self.logger.log_error("复制文件名失败", exc=e)

    def _copy_full_path(self) -> None:
        """
        复制完整路径（与_copy_path相同，用于右键菜单）
        """
        self._copy_path()

    def _delete_selected_item(self) -> None:
        """
        从结果列表移除选中的项（不删除实际文件）
        """
        selection = self.results_tree.selection()
        if not selection:
            return

        for item_id in selection:
            self.results_tree.delete(item_id)

        self.logger.log_debug("从结果列表移除选中项")

    def _rename_file(self) -> None:
        """
        重命名选中的文件
        """
        file_path_str = self._get_selected_file_path()
        if not file_path_str or not Path(file_path_str).exists():
            messagebox.showwarning("提示", "请先选择一个有效的文件")
            return

        old_name = Path(file_path_str).name
        new_name = simpledialog.askstring(
            "重命名",
            "请输入新的文件名:",
            initialvalue=old_name
        )

        if new_name and new_name != old_name:
            try:
                old_path = Path(file_path_str)
                new_path = old_path.parent / new_name
                old_path.rename(new_path)

                self.logger.log_info(f"重命名文件: {old_name} -> {new_name}")
                messagebox.showinfo("成功", "文件重命名成功")

                # 刷新搜索结果
                self._refresh_search()
            except Exception as e:
                self.logger.log_error(f"重命名文件失败: {file_path_str}", exc=e)
                messagebox.showerror("错误", f"重命名失败:\n{str(e)}")

    def _delete_file(self) -> None:
        """
        删除选中的实际文件（需二次确认）
        """
        file_path_str = self._get_selected_file_path()
        if not file_path_str or not Path(file_path_str).exists():
            messagebox.showwarning("提示", "请先选择一个有效的文件")
            return

        # 二次确认
        confirm = messagebox.askyesno(
            "确认删除",
            f"确定要删除以下文件吗？\n\n{file_path_str}\n\n此操作不可撤销！"
        )

        if confirm:
            try:
                Path(file_path_str).unlink()
                self.logger.log_info(f"删除文件: {file_path_str}")
                messagebox.showinfo("成功", "文件已删除")

                # 刷新搜索结果
                self._refresh_search()
            except Exception as e:
                self.logger.log_error(f"删除文件失败: {file_path_str}", exc=e)
                messagebox.showerror("错误", f"删除失败:\n{str(e)}")

    def _show_context_menu(self, event: tk.Event) -> None:
        """
        显示右键上下文菜单

        :param event: 鼠标事件
        """
        # 选中右键点击的行
        item_id = self.results_tree.identify_row(event.y)
        if item_id:
            self.results_tree.selection_set(item_id)

        # 创建菜单
        context_menu = tk.Menu(self.root, tearoff=0)

        context_menu.add_command(label="📂 打开文件", command=self._open_file, accelerator="Enter")
        context_menu.add_command(label="📁 打开所在位置", command=self._open_location, accelerator="Ctrl+Enter")

        context_menu.add_separator()

        context_menu.add_command(label="📋 复制名称", command=self._copy_name)
        context_menu.add_command(label="📋 复制路径", command=self._copy_path, accelerator="Ctrl+C")
        context_menu.add_command(label="📋 复制完整路径", command=self._copy_full_path)

        context_menu.add_separator()

        context_menu.add_command(label="✏️  重命名", command=self._rename_file, accelerator="F2")
        context_menu.add_command(label="🗑️  删除文件", command=self._delete_file)

        context_menu.add_separator()

        context_menu.add_command(label="📤 导出选中项...", command=lambda: self._export_results(selected_only=True), accelerator="Ctrl+E")
        context_menu.add_command(label="📤 导出全部结果...", command=lambda: self._export_results(selected_only=False))

        context_menu.add_separator()

        context_menu.add_command(label="ℹ️  属性", command=self._show_properties)

        # 显示菜单
        try:
            context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            context_menu.grab_release()

    def _show_properties(self) -> None:
        """
        显示选中文件的详细属性
        """
        selection = self.results_tree.selection()
        if not selection:
            return

        values = self.results_tree.item(selection[0], 'values')
        if not values or len(values) < 5:
            return

        name, path, size, date, file_type = values

        # 创建属性对话框
        prop_dialog = tk.Toplevel(self.root)
        prop_dialog.title("文件属性")
        prop_dialog.geometry("400x300")
        prop_dialog.resizable(False, False)
        prop_dialog.transient(self.root)
        prop_dialog.grab_set()

        frame = tk.Frame(prop_dialog, bg=COLORS['bg'], padx=20, pady=20)
        frame.pack(fill=tk.BOTH, expand=True)

        # 显示属性信息
        properties = [
            ("文件名:", name),
            ("完整路径:", path),
            ("大小:", size),
            ("修改日期:", date),
            ("类型:", file_type),
        ]

        for i, (label, value) in enumerate(properties):
            tk.Label(frame, text=label, font=FONT_BOLD, bg=COLORS['bg'], fg=COLORS['fg']).grid(
                row=i, column=0, sticky='w', pady=5
            )
            tk.Label(frame, text=value, font=FONT, bg=COLORS['bg'], fg=COLORS['status_fg']).grid(
                row=i, column=1, sticky='w', pady=5, padx=(10, 0)
            )

        # 关闭按钮
        close_btn = tk.Button(
            frame,
            text="关闭",
            font=FONT,
            command=prop_dialog.destroy,
            width=10
        )
        close_btn.grid(row=len(properties), column=0, columnspan=2, pady=(20, 0))

    def _browse_directory(self) -> None:
        """
        弹出文件夹选择对话框
        """
        initial_dir = str(self.current_directory) if self.current_directory else "C:\\"

        directory = filedialog.askdirectory(
            title="选择要搜索的目录",
            initialdir=initial_dir
        )

        if directory:
            self._set_directory(Path(directory))

    def _refresh_search(self) -> None:
        """
        使用当前参数重新扫描目录
        """
        if not self.current_directory:
            messagebox.showwarning("提示", "请先选择要搜索的目录")
            return

        keyword = self.search_var.get().strip()

        if keyword:
            # 如果有搜索词，重新执行搜索
            self.last_search_time = time.time()
            self.scheduler.request_search_immediate(
                root_path=self.current_directory,
                keyword=keyword
            )
        else:
            # 无搜索词则列出所有文件
            self.last_search_time = time.time()
            self.scheduler.request_search_immediate(
                root_path=self.current_directory,
                keyword=""
            )

    def _on_directory_change(self, event: tk.Event) -> None:
        """
        目录下拉框切换事件处理

        :param event: Combobox选择事件
        """
        selected_dir = self.directory_var.get()
        if selected_dir:
            valid, msg, path_obj = check_root_path(selected_dir)
            if valid and path_obj:
                self._set_directory(path_obj)

    def _set_directory(self, directory: Path) -> None:
        """
        设置当前搜索目录

        :param directory: 目标目录Path对象
        """
        self.current_directory = directory.resolve()
        self.directory_var.set(str(self.current_directory))

        # 保存到目录历史
        try:
            self.history_manager.add_directory_history(str(self.current_directory))
        except Exception as e:
            self.logger.log_warning("保存目录历史失败", exc=e)

        # 更新状态行右侧显示
        self._update_status(right_text=str(self.current_directory))

        # 保存默认目录到配置
        try:
            self.config_manager.set('ui.default_directory', str(self.current_directory))
        except Exception as e:
            self.logger.log_warning("保存默认目录配置失败", exc=e)

        # 切换目录后始终触发检索（空关键词=列出所有文件，符合 Everything 交互模式）
        keyword = self.search_var.get().strip()
        self.last_search_time = time.time()
        self.scheduler.request_search(
            root_path=self.current_directory,
            keyword=keyword,
            debounce_ms=100  # 切换目录时使用较短延迟快速响应
        )

    def _load_directory_history(self) -> None:
        """
        加载目录历史记录到下拉框
        """
        try:
            history_list = self.history_manager.get_directory_history(limit=15)
            if history_list:
                self.directory_combo['values'] = history_list
        except Exception as e:
            self.logger.log_warning("加载目录历史失败", exc=e)

    def _export_results(self, selected_only: bool = False) -> None:
        """
        导出搜索结果到CSV文件

        :param selected_only: 是否只导出选中项
        """
        if selected_only:
            # 导出选中项
            selection = self.results_tree.selection()
            if not selection:
                messagebox.showinfo("提示", "请先选择要导出的项目")
                return

            data_to_export = []
            for item_id in selection:
                values = self.results_tree.item(item_id, 'values')
                if values and len(values) >= 5:
                    data_to_export.append({
                        'name': values[0],
                        'path': values[1],
                        'size': values[2],
                        'date': values[3],
                        'type': values[4]
                    })
        else:
            # 导出全部结果
            data_to_export = self.search_results

        if not data_to_export:
            messagebox.showinfo("提示", "没有可导出的数据")
            return

        # 选择保存路径
        save_path = filedialog.asksaveasfilename(
            title="导出结果",
            defaultextension=".csv",
            filetypes=[
                ("CSV文件", "*.csv"),
                ("文本文件", "*.txt"),
                ("所有文件", "*.*")
            ],
            initialfile=f"search_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )

        if save_path:
            try:
                success = False
                if save_path.endswith('.csv'):
                    success = self.history_manager.export_to_csv(data_to_export, save_path)
                else:
                    success = self.history_manager.export_to_txt(data_to_export, save_path)

                if success:
                    messagebox.showinfo("成功", f"结果已导出到:\n{save_path}")
                    self.logger.log_info(f"导出结果成功: {save_path}, 数量={len(data_to_export)}")
                else:
                    messagebox.showerror("错误", "导出失败")
            except Exception as e:
                self.logger.log_error("导出结果失败", exc=e)
                messagebox.showerror("错误", f"导出失败:\n{str(e)}")

    def _show_settings(self) -> None:
        """
        显示设置面板（Toplevel模态窗口）
        """
        settings_window = tk.Toplevel(self.root)
        settings_window.title("设置")
        settings_window.geometry("450x550")
        settings_window.resizable(False, False)
        settings_window.transient(self.root)
        settings_window.grab_set()
        settings_window.configure(bg=COLORS['bg'])

        # 主框架
        main_frame = tk.Frame(settings_window, bg=COLORS['bg'], padx=25, pady=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # ===== 排序选项 =====
        sort_frame = tk.LabelFrame(main_frame, text="排序选项", font=FONT_BOLD, bg=COLORS['bg'], fg=COLORS['fg'], padx=10, pady=10)
        sort_frame.pack(fill=tk.X, pady=(0, 15))

        # 排序字段
        tk.Label(sort_frame, text="排序依据:", font=FONT, bg=COLORS['bg'], fg=COLORS['fg']).grid(row=0, column=0, sticky='w', pady=5)

        current_sort_key = self.config_manager.get('search.sort_key', 'name')
        sort_key_var = tk.StringVar(value=current_sort_key)
        sort_keys = [('名称', 'name'), ('大小', 'size'), ('日期', 'date'), ('类型', 'type')]

        sort_combo = ttk.Combobox(sort_frame, textvariable=sort_key_var, state='readonly', width=15, font=FONT)
        sort_combo['values'] = [k[0] for k in sort_keys]
        sort_combo.grid(row=0, column=1, sticky='w', padx=10, pady=5)

        # 排序方向
        current_reverse = self.config_manager.get('search.sort_reverse', False)
        reverse_var = tk.BooleanVar(value=current_reverse)

        tk.Label(sort_frame, text="排序方向:", font=FONT, bg=COLORS['bg'], fg=COLORS['fg']).grid(row=1, column=0, sticky='w', pady=5)

        dir_frame = tk.Frame(sort_frame, bg=COLORS['bg'])
        dir_frame.grid(row=1, column=1, sticky='w', padx=10, pady=5)

        tk.Radiobutton(dir_frame, text="升序", variable=reverse_var, value=False, bg=COLORS['bg'], font=FONT).pack(side=tk.LEFT)
        tk.Radiobutton(dir_frame, text="降序", variable=reverse_var, value=True, bg=COLORS['bg'], font=FONT).pack(side=tk.LEFT, padx=(10, 0))

        # ===== 搜索设置 =====
        search_frame = tk.LabelFrame(main_frame, text="搜索设置", font=FONT_BOLD, bg=COLORS['bg'], fg=COLORS['fg'], padx=10, pady=10)
        search_frame.pack(fill=tk.X, pady=(0, 15))

        # 防抖延迟滑块
        current_debounce = self.config_manager.get('search.debounce_delay', 300)
        debounce_var = tk.IntVar(value=current_debounce)

        tk.Label(search_frame, text=f"防抖延迟: {current_debounce}ms", font=FONT, bg=COLORS['bg'], fg=COLORS['fg']).grid(row=0, column=0, sticky='w', pady=5)

        debounce_label = tk.Label(search_frame, text=f"{current_debounce}ms", font=FONT, bg=COLORS['bg'], fg=COLORS['accent'])
        debounce_label.grid(row=0, column=2, sticky='w', padx=10)

        def update_debounce_label(val):
            ms = int(float(val))
            debounce_label.config(text=f"{ms}ms")

        debounce_scale = tk.Scale(
            search_frame,
            from_=100,
            to=1000,
            orient=tk.HORIZONTAL,
            variable=debounce_var,
            command=update_debounce_label,
            length=200,
            bg=COLORS['bg'],
            fg=COLORS['fg'],
            highlightthickness=0,
            troughcolor=COLORS['border']
        )
        debounce_scale.grid(row=1, column=0, columnspan=3, sticky='ew', pady=5)

        # 最大结果显示数
        current_max = self.config_manager.get('search.max_results', 10000)
        max_var = tk.IntVar(value=current_max)

        tk.Label(search_frame, text="最大结果数:", font=FONT, bg=COLORS['bg'], fg=COLORS['fg']).grid(row=2, column=0, sticky='w', pady=5)
        max_entry = tk.Entry(search_frame, textvariable=max_var, width=15, font=FONT)
        max_entry.grid(row=2, column=1, sticky='w', padx=10, pady=5)

        # ===== 显示选项 =====
        display_frame = tk.LabelFrame(main_frame, text="显示选项", font=FONT_BOLD, bg=COLORS['bg'], fg=COLORS['fg'], padx=10, pady=10)
        display_frame.pack(fill=tk.X, pady=(0, 15))

        # 隐藏隐藏文件开关
        current_hide = self.config_manager.get('ui.show_hidden_files', True)
        hide_var = tk.BooleanVar(value=current_hide)

        hide_check = tk.Checkbutton(
            display_frame,
            text="隐藏以点号(.)开头的文件",
            variable=hide_var,
            bg=COLORS['bg'],
            font=FONT,
            selectcolor=COLORS['bg'],
            activebackground=COLORS['bg']
        )
        hide_check.pack(anchor='w')

        # ===== 按钮区域 =====
        btn_frame = tk.Frame(main_frame, bg=COLORS['bg'])
        btn_frame.pack(fill=tk.X, pady=(15, 0))

        def apply_settings():
            """应用设置"""
            try:
                # 获取排序字段映射
                selected_sort_text = sort_key_var.get()
                selected_sort_key = next((k[1] for k in sort_keys if k[0] == selected_sort_text), 'name')

                # 保存所有设置
                self.config_manager.set('search.sort_key', selected_sort_key)
                self.config_manager.set('search.sort_reverse', reverse_var.get())
                self.config_manager.set('search.debounce_delay', debounce_var.get())

                # 验证最大结果数
                try:
                    max_val = max_var.get()
                    if max_val < 1:
                        max_val = 10000
                except:
                    max_val = 10000
                self.config_manager.set('search.max_results', max_val)
                self.config_manager.set('ui.show_hidden_files', hide_var.get())

                # 保存配置文件
                self.config_manager.save()

                messagebox.showinfo("成功", "设置已保存")
                settings_window.destroy()

                # 如果有结果，刷新显示
                if self.search_results:
                    self._populate_results(self.search_results)

            except Exception as e:
                self.logger.log_error("保存设置失败", exc=e)
                messagebox.showerror("错误", f"保存设置失败:\n{str(e)}")

        def reset_settings():
            """重置为默认设置"""
            if messagebox.askyesno("确认", "确定要重置所有设置为默认值吗？"):
                self.config_manager.reset_to_defaults()
                messagebox.showinfo("成功", "已重置为默认设置")
                settings_window.destroy()

        tk.Button(btn_frame, text="应用", font=FONT, command=apply_settings, width=12).pack(side=tk.LEFT, padx=(0, 10))
        tk.Button(btn_frame, text="重置默认", font=FONT, command=reset_settings, width=12).pack(side=tk.LEFT, padx=(0, 10))
        tk.Button(btn_frame, text="取消", font=FONT, command=settings_window.destroy, width=12).pack(side=tk.RIGHT)

    def _toggle_focus(self) -> None:
        """
        Tab键：在搜索框和结果列表间切换焦点
        """
        if self.root.focus_get() == self.search_entry:
            if self.results_tree.get_children():
                self.results_tree.focus_set()
        else:
            self.search_entry.focus_set()

    def _show_placeholder(self) -> None:
        """显示搜索框placeholder效果"""
        if not self.search_var.get():
            self.search_entry.insert(0, self.placeholder_text)
            self.search_entry.config(fg='#999999')

    def _on_search_focus_in(self, event: tk.Event) -> None:
        """搜索框聚焦时清除placeholder"""
        if self.search_var.get() == self.placeholder_text:
            self.search_var.set("")
            self.search_entry.config(fg=COLORS['fg'])

    def _on_search_focus_out(self, event: tk.Event) -> None:
        """搜索框失焦且为空时恢复placeholder"""
        if not self.search_var.get():
            self._show_placeholder()

    # ==================== 搜索动画系统 ====================

    def _start_search_animation(self) -> None:
        """
        启动全部搜索动画效果（三重动画并行）

        动画组成：
          1. 旋转圆环指示器 - 替换 🔍 为旋转加载圈
          2. 状态行动画文字 - "正在扫描..." 循环点号
          3. 搜索栏边框脉冲 - 蓝色呼吸灯效果
        """
        if self._animation_running:
            return  # 防止重复启动

        self._animation_running = True
        self.last_search_time = time.time()

        # ---- 1. 启动旋转圆环动画 ----
        self._spinner_angle = 0.0
        self._animate_spinner()

        # ---- 2. 启动状态行点点动画 ----
        self._dots_count = 0
        self._animate_dots()

        # ---- 3. 搜索栏边框脉冲动画 ----
        self._pulse_phase = 0
        self._animate_pulse()

    def _stop_search_animation(self) -> None:
        """
        停止所有搜索动画，恢复静态状态

        将旋转指示器还原为 🔍 图标，
        清除所有 after() 定时任务，重置状态变量
        """
        if not self._animation_running:
            return

        self._animation_running = False

        # 取消所有定时任务
        if self._spinner_job:
            try:
                self.root.after_cancel(self._spinner_job)
            except Exception:
                pass
            self._spinner_job = None

        if self._dots_job:
            try:
                self.root.after_cancel(self._dots_job)
            except Exception:
                pass
            self._dots_job = None

        if self._pulse_job:
            try:
                self.root.after_cancel(self._pulse_job)
            except Exception:
                pass
            self._pulse_job = None

        # 还原静态 🔍 图标
        try:
            self.spinner_canvas.delete("all")
            self._spinner_text_id = self.spinner_canvas.create_text(
                11, 11, text="🔍", font=("Segoe UI Emoji", 12), anchor='center'
            )
        except Exception:
            pass

        # 还原搜索框边框（移除脉冲高亮）
        try:
            self.search_entry.config(highlightthickness=0)
        except Exception:
            pass

    def _animate_spinner(self) -> None:
        """
        旋转圆环动画帧 - 每 50ms 绘制一帧

        使用 Canvas arc 绘制一段不完整的圆弧，
        每帧旋转 30 度，形成连续旋转的加载指示器效果。
        颜色使用 Windows 蓝 (#0078D4)，线宽 2.5px。
        """
        if not self._animation_running:
            return

        try:
            self.spinner_canvas.delete("all")

            cx, cy = 11, 11  # 圆心坐标
            outer_r = 9      # 外半径
            inner_r = 5      # 内半径（形成圆环）
            angle = self._spinner_angle

            # 绘制背景淡色轨迹圆（已走过的部分用深色，未走部分浅色）
            self.spinner_canvas.create_oval(
                cx - outer_r, cy - outer_r,
                cx + outer_r, cy + outer_r,
                outline='#E8E8E8', width=2.5
            )

            # 绘制旋转的进度圆弧（100度扇形，每帧偏移30度）
            self.spinner_canvas.create_arc(
                cx - outer_r, cy - outer_r,
                cx + outer_r, cy + outer_r,
                start=angle, extent=100,
                outline=COLORS['accent'], width=2.5,
                style=tk.ARC
            )

            # 更新角度（顺时针旋转，每次+30度）
            self._spinner_angle = (self._spinner_angle + 30) % 360

            # 排定下一帧（50ms 后）
            self._spinner_job = self.root.after(50, self._animate_spinner)

        except Exception as e:
            self.logger.log_warning("旋转动画帧绘制失败", exc=e)

    def _animate_dots(self) -> None:
        """
        状态行点点动画 - 每 400ms 循环一次

        在迷你状态行左侧显示：
          "正在扫描..." → "正在扫描." → "正在扫描.." → "正在扫描..."
        形成打字机式的动态进度提示。
        """
        if not self._animation_running:
            return

        try:
            self._dots_count = (self._dots_count + 1) % 4
            dots = "." * self._dots_count
            self.status_left.config(
                text=f"🔍 正在扫描{dots}",
                fg=COLORS['accent']  # 扫描中用蓝色强调
            )

            # 400ms 后更新下一帧
            self._dots_job = self.root.after(400, self._animate_dots)

        except Exception as e:
            self.logger.log_warning("状态行动画更新失败", exc=e)

    def _animate_pulse(self) -> None:
        """
        搜索栏边框脉冲/呼吸灯动画 - 每 80ms 一帧

        让搜索输入框的边框颜色在白色和浅蓝之间渐变，
        形成"呼吸"般的视觉反馈，表示系统正在工作中。
        使用正弦函数计算平滑的透明度过渡。
        """
        if not self._animation_running:
            return

        try:
            self._pulse_phase = (self._pulse_phase + 15) % 360

            # 用正弦函数计算脉冲强度 (0.0 ~ 1.0)
            import math
            intensity = (math.sin(math.radians(self._pulse_phase)) + 1) / 2

            # 在纯白和浅蓝之间插值
            r = int(255 - intensity * (255 - 200))
            g = int(255 - intensity * (255 - 225))
            b = int(255 - intensity * (255 - 246))

            pulse_color = f"#{r:02x}{g:02x}{b:02x}"

            # 应用到搜索框高亮边框
            self.search_entry.config(highlightbackground=pulse_color, highlightthickness=1)

            # 80ms 后下一帧
            self._pulse_job = self.root.after(80, self._animate_pulse)

        except Exception as e:
            self.logger.log_warning("脉冲动画帧绘制失败", exc=e)

    # ==================== 搜索动画系统结束 ====================

    def _get_selected_file_path(self) -> Optional[str]:
        """
        获取当前选中项的完整文件路径

        :return: 文件路径字符串，无选中时返回None
        """
        selection = self.results_tree.selection()
        if not selection:
            return None

        values = self.results_tree.item(selection[0], 'values')
        if values and len(values) >= 2:
            return values[1]  # path列在第二位
        return None

    def _sort_by_column(self, col: str) -> None:
        """
        点击表头按该列排序

        :param col: 排序列名
        """
        # 切换排序方向
        current_reverse = self.config_manager.get('search.sort_reverse', False)

        # 如果是同一列，切换方向；否则使用默认升序
        current_sort = self.config_manager.get('search.sort_key', 'name')
        if current_sort == col:
            new_reverse = not current_reverse
        else:
            new_reverse = False

        # 保存新排序设置
        self.config_manager.set('search.sort_key', col)
        self.config_manager.set('search.sort_reverse', new_reverse)

        # 重新填充结果
        if self.search_results:
            self._populate_results(self.search_results)

    def _on_window_configure(self, event: tk.Event) -> None:
        """
        窗口大小变化事件处理（保存窗口尺寸）

        :param event: Configure事件
        """
        # 只在主窗口大小变化时响应
        if event.widget == self.root:
            try:
                geo = self.root.geometry()
                # 解析几何字符串获取宽高
                parts = geo.split('+')[0].split('x')
                if len(parts) == 2:
                    width, height = int(parts[0]), int(parts[1])
                    self.config_manager.set('ui.window_width', width)
                    self.config_manager.set('ui.window_height', height)
            except Exception:
                pass

    def _save_config(self) -> None:
        """保存当前配置到文件"""
        try:
            # 保存窗口位置
            geo = self.root.geometry()
            parts = geo.split('+')
            if len(parts) >= 3:
                self.config_manager.set('ui.window_x', int(parts[1]))
                self.config_manager.set('ui.window_y', int(parts[2]))

            self.config_manager.save()
            self.logger.log_info("配置已保存")
        except Exception as e:
            self.logger.log_error("保存配置失败", exc=e)

    def _on_closing(self) -> None:
        """
        关闭窗口处理（最小化到系统托盘）

        如果托盘不可用，则直接退出
        """
        self._save_config()

        if self._tray_icon:
            # 有托盘支持时，最小化到托盘
            self.root.withdraw()
            self.logger.log_info("窗口已最小化到系统托盘")
        else:
            # 无托盘支持时，确认退出
            if messagebox.askokcancel("退出", "确定要退出 FileManager 吗？"):
                self._cleanup_and_exit()

    def _cleanup_and_exit(self) -> None:
        """清理资源并退出应用"""
        try:
            # 中断正在执行的检索
            if hasattr(self, 'scheduler'):
                self.scheduler.stop_current()
                self.scheduler.cancel_pending()

            # 保存配置
            self._save_config()

            self.logger.log_info("FileManager 应用正常退出")
        except Exception as e:
            self.logger.log_error("退出清理过程发生异常", exc=e)
        finally:
            self.root.destroy()

    def _setup_tray(self) -> None:
        """
        设置系统托盘集成

        尝试导入pystray，如果不可用则优雅降级（仅不启用托盘功能）
        """
        try:
            from PIL import Image, ImageDraw
            import pystray
            from pystray import MenuItem, Menu

            # 创建简单的托盘图标
            image = Image.new('RGBA', (64, 64), (255, 255, 255, 0))
            draw = ImageDraw.Draw(image)
            draw.text((16, 16), "FM", fill='#0078D4')

            def on_show(icon, item):
                """显示窗口"""
                self.root.deiconify()
                self.root.lift()
                self.search_entry.focus_set()

            def on_exit(icon, item):
                """退出应用"""
                icon.stop()
                self._cleanup_and_exit()

            # 创建托盘菜单
            menu = Menu(
                MenuItem('显示/隐藏', on_show, default=True),
                Menu.SEPARATOR,
                MenuItem('退出', on_exit)
            )

            # 创建托盘图标
            self._tray_icon = pystray.Icon(
                name="FileManager",
                icon=image,
                title="FileManager - 文件搜索",
                menu=menu
            )

            # 启动托盘图标（在独立线程中运行）
            def run_tray():
                self._tray_icon.run()

            import threading
            tray_thread = threading.Thread(target=run_tray, daemon=True)
            tray_thread.start()

            self.logger.log_info("系统托盘已启用")

        except ImportError:
            self.logger.log_warning("pystray 或 PIL 不可用，系统托盘功能已禁用")
            self._tray_icon = None
        except Exception as e:
            self.logger.log_error("初始化系统托盘失败", exc=e)
            self._tray_icon = None

    def _setup_global_hotkey(self) -> None:
        """
        注册全局热键

        尝试使用keyboard库注册Ctrl+Ctrl唤醒窗口，如果不可用则跳过
        """
        try:
            import keyboard

            def toggle_window():
                """全局热键回调：切换窗口显示/隐藏"""
                try:
                    if self.root.winfo_viewable():
                        self.root.withdraw()
                    else:
                        self.root.deiconify()
                        self.root.lift()
                        self.search_entry.focus_set()
                except Exception as e:
                    self.logger.log_warning("热键切换窗口失败", exc=e)

            # 注册 Ctrl+Ctrl 连按两次唤醒
            keyboard.add_hotkey('ctrl+ctrl', toggle_window)
            self.logger.log_info("全局热键 Ctrl+Ctrl 已注册")

        except ImportError:
            self.logger.log_warning("keyboard 库不可用，全局热键功能已禁用")
        except Exception as e:
            self.logger.log_error("注册全局热键失败", exc=e)


def main() -> None:
    """主程序入口"""
    try:
        # 创建主窗口
        root = tk.Tk()

        # 设置DPI感知（Windows高分辨率支持）
        try:
            from ctypes import windll
            windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass

        # 创建应用实例
        app = FileManagerApp(root)

        # 运行主循环
        root.mainloop()

    except Exception as e:
        logger = get_logger()
        logger.log_error("应用程序启动失败", exc=e)
        raise


if __name__ == "__main__":
    main()
