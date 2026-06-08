# FileManager - 仿 Everything 文件检索系统

<p align="center">
  <strong>一款轻量级、即时响应的本地文件搜索工具</strong><br>
  <sub>Python / Tkinter / 零核心依赖</sub>
</p>

---

## 功能特性

### Everything 风格交互体验

- **即时搜索** — 输入即搜，300ms 智能防抖，无需点击搜索按钮
- **极简界面** — 纯白背景 + Windows 原生蓝，两区域布局（搜索栏 + 结果列表）
- **键盘完全驱动** — 15+ 快捷键，鼠标可选，操作效率最大化
- **系统托盘集成** — 关闭窗口最小化到托盘，随时唤起
- **全局热键** — 双击 `Ctrl` 从任何应用中快速调出窗口

### 强大的搜索语法

| 语法 | 示例 | 说明 |
|------|------|------|
| 模糊匹配 | `report` | 文件名包含 "report" |
| 通配符 | `*.pdf` | 匹配所有 PDF 文件 |
| 排除语法 | `!mp3` | 排除所有 mp3 文件 |
| 多条件 AND | `report pdf` | 同时包含两个词 |
| 全量列出 | *(空关键词)* | 列出目录下所有文件 |

### 核心技术亮点

- **可中断扫描** — 新搜索自动取消旧搜索，零资源浪费
- **实时动画反馈** — 旋转加载圈 + 脉冲边框 + 进度提示
- **错误监控日志** — 双通道日志（文件+控制台），自动轮转，结构化记录
- **配置持久化** — 窗口位置、历史记录、偏好设置全部自动保存
- **优雅降级** — 可选依赖缺失时自动禁用对应功能，不影响主流程

## 技术栈

| 类别 | 技术 |
|------|------|
| 语言 | Python 3.9+ |
| GUI 框架 | tkinter (ttk) |
| 文件操作 | pathlib（纯标准库） |
| 多线程 | threading (Timer + Event + daemon Thread) |
| 日志系统 | logging (RotatingFileHandler) |
| 核心依赖 | **零外部依赖** |
| 可选依赖 | pystray (系统托盘), keyboard (全局热键) |

## 项目结构

```
file_manage_system/
├── filemanager/                    # 主程序包
│   ├── main.py                     # UI 入口（Everything 风格主程序）
│   ├── backend/                    # 后端五层架构
│   │   ├── error_logger.py         # 错误监控日志系统（单例/双通道/轮转）
│   │   ├── path_validator.py       # 路径校验层
│   │   ├── search_scheduler.py     # 搜索调度器（防抖/中断/状态机）
│   │   ├── search_engine.py        # 核心引擎（可中断遍历/Everything语法）
│   │   ├── data_utils.py           # 数据处理工具（99种扩展名/格式化/排序）
│   │   └── history_manager.py      # 历史管理 + ConfigManager 配置持久化
│   └── assets/                     # 资源目录
├── logs/                           # 错误日志（自动创建）
├── config.json                     # 用户配置
├── history.json                    # 搜索历史
├── requirements.txt                # 依赖声明
├── .gitignore
├── 前端设计.md                      # V2.0 UI 规范文档
└── 后端设计.md                      # V2.0 后端架构文档
```

## 快速开始

### 环境要求

- Python 3.9 或更高版本
- Windows 操作器（Linux/macOS 未充分测试）

### 安装运行

```bash
# 1. 克隆项目
git clone <your-repo-url>
cd file_manage_system

# 2. 创建虚拟环境（推荐）
python -m venv venv
venv\Scripts\activate    # Windows
# source venv/bin/activate  # Linux/macOS

# 3. 安装依赖（核心功能无需安装，以下为可选增强功能）
pip install pystray Pillow keyboard

# 4. 启动
python -m filemanager.main
```

### 打包为独立 exe（推荐）

```bash
# 安装打包工具
pip install pyinstaller

# 打包
pyinstaller --onefile --windowed --name FileManager --icon=assets/icon.ico filemanager/main.py

# 生成的 exe 在 dist/ 目录下
```

## 使用指南

### 界面布局

```
┌──────────────────────────────────────────────┐
│ [D:\Documents ▼] [📁浏览] [🔄刷新]           │ ← 路径选择栏
├──────────────────────────────────────────────┤
│ 🔍│ 搜索框（输入即搜，无需回车）      │⚙️│🗘│   │ ← 搜索栏
├──────────────────────────────────────────────┤
│ 文件名 │ 路径        │ 大小  │ 日期       │ 类型│ ← 结果表头
│ ──────────────────────────────────────────── │
│ (搜索结果列表，支持排序和滚动)                  │
├──────────────────────────────────────────────┤
│ 已找到 N 个文件 (X.XXs) │ D:\Documents       │ ← 迷你状态行
└──────────────────────────────────────────────┘
```

### 键盘快捷键

| 快捷键 | 功能 |
|--------|------|
| `Enter` | 打开选中文件 |
| `↑` / `↓` | 上/下移动选中行 |
| `Esc` | 清空搜索和结果 |
| `Ctrl + Enter` | 打开文件所在文件夹 |
| `Ctrl + C` | 复制文件路径到剪贴板 |
| `Tab` | 搜索框 ↔ 结果列表切换焦点 |
| `F2` | 重命名文件 |
| `Delete` | 从结果列表移除该项 |
| `Ctrl + E` | 导出当前结果 |
| `Ctrl + Ctrl` | 全局热键唤起窗口 |

### 右键菜单

打开文件 / 打开所在位置 / 复制路径 / 重命名 / 删除 / 导出 / 属性

## 架构设计

### 五层后端架构

```
UI 层 (main.py)
    ↓ 请求
SearchScheduler (search_scheduler.py)   ← 防抖 + 中断 + 状态机
    ↓ 调度
SearchEngine (search_engine.py)          ← 可中断遍历 + Everything 语法解析
    ↓ 处理
DataUtils (data_utils.py)                ← 格式化 / 分类 / 排序
    ↓ 持久化
HistoryManager (history_manager.py)      ← 历史记录 + 配置管理
```

### 即时搜索数据流

```
用户输入 → KeyRelease 事件
    ↓
SearchScheduler.request_search()
    ├─ 取消旧的防抖 Timer
    ├─ 设置 stop_flag 中断旧线程
    └─ 启动新的 300ms Timer
        ↓ (超时或 Enter 立即触发)
    scan_files() [daemon Thread]
        ├─ rglob("*") 遍历目录
        ├─ 每100个文件检查 stop_flag
        └─ _match_keyword() 匹配
            ↓
    parse_file_info() 转换为字典
        ↓
    root.after(0, callback) 回主线程
        ↓
    Treeview.insert() 渲染结果 + 更新状态行
```

### 搜索动画系统

搜索进行时三重并行动画：

1. **旋转圆环** — Canvas arc 绘制蓝色加载指示器（50ms/帧）
2. **点点动画** — 状态行 `"正在扫描..."` 循环递增（400ms/帧）
3. **脉冲边框** — 搜索框正弦渐变呼吸灯效果（80ms/帧）

## 配置说明

配置文件 `config.json` 支持以下自定义项：

| 分类 | 配置项 | 默认值 | 说明 |
|------|--------|--------|------|
| ui | `theme` | light | 主题（light/dark） |
| ui | `window_width/height` | 1200x800 | 窗口尺寸 |
| search | `debounce_delay` | 300 | 防抖延迟(ms) |
| search | `max_results` | 1000 | 最大结果显示数 |
| search | `sort_key` | date | 默认排序字段 |
| advanced | `log_level` | INFO | 日志级别 |

## 开发计划

- [ ] V2.5: 搜索结果内存缓存（首次扫描后瞬时过滤）
- [ ] V2.5: 文件预览面板（图片/txt/pdf 预览）
- [ ] V3.0: 后台索引引擎（毫秒级搜索响应）
- [ ] V3.0: 正则表达式搜索支持
- [ ] V4.0: 多标签页支持
- [ ] V4.0: 插件系统

## 许可证

MIT License

---

<p align="center">
  <sub>灵感来源于 <a href="https://www.voidtools.com/">Everything</a> — 最快的 Windows 文件搜索工具</sub>
</p>
#   f i l e _ m a n a g e _ s y s t e m  
 #   f i l e _ m a n a g e _ s y s t e m  
 