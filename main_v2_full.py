"""
TG 批量私信系统 - 完整版 v2.3
检测优化 + 数据库锁定修复 + Web自动登录
"""

# 版本号
VERSION = "v2.3.0"

# 隐私保护说明：
# 代理信息不会保存到 JSON 文件中
# 只在程序运行时使用，导出的账号不包含代理配置

import os
import sys
import asyncio
import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox
from pathlib import Path
import threading
from datetime import datetime
import random
import time
import json
import logging
import warnings

# 禁用 Telethon 的 Task exception 警告
warnings.filterwarnings("ignore", message=".*Task exception was never retrieved.*")
logging.getLogger('telethon').setLevel(logging.CRITICAL)  # 只显示严重错误

try:
    from telethon import TelegramClient, errors, functions
    from telethon.tl.types import InputPeerUser, User
    from telethon.tl.functions.messages import GetDialogsRequest
    from telethon.tl.types import InputPeerEmpty, UserStatusOnline, UserStatusRecently
except ImportError:
    print("❌ 缺少 telethon 库,请运行: pip install telethon")
    sys.exit(1)

# 导入完整版模块
try:
    import config
    from modules.user_scraper_full import UserScraper
    from modules.message_sender_full import MessageSender
    from modules.account_manager_full import AccountManager
    from modules.proxy_manager import ProxyManager
except ImportError as e:
    print(f"❌ 导入模块失败: {e}")
    print("请确保 config.py 和 modules/ 目录存在")
    sys.exit(1)

# 使用配置文件中的 API 和 Emoji
API_ID = config.API_ID
API_HASH = config.API_HASH
RANDOM_EMOJIS = config.RANDOM_EMOJIS


class TGMassDM:
    def __init__(self, root):
        self.root = root
        self.root.title(f"TG 批量私信系统 {VERSION}")
        self.root.geometry("1200x800")
        self.root.minsize(900, 600)  # 设置最小窗口尺寸

        # 设置异步异常处理器,禁止打印 AuthKeyDuplicatedError
        def custom_exception_handler(loop, context):
            exception = context.get('exception')
            if exception:
                # 只抑制 AuthKeyDuplicatedError,其他异常仍然记录
                if 'AuthKeyDuplicatedError' not in str(exception):
                    # 默认处理其他异常
                    loop.default_exception_handler(context)
            else:
                loop.default_exception_handler(context)

        # 获取或创建事件循环
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        loop.set_exception_handler(custom_exception_handler)

        # 使用配置文件中的 API
        self.api_id = API_ID
        self.api_hash = API_HASH

        # 初始化模块
        self.account_manager = AccountManager(
            self.api_id,
            self.api_hash,
            config.SESSIONS_DIR,
            config.ACCOUNTS_FILE,
            self.log
        )
        
        self.user_scraper = UserScraper(
            self.api_id,
            self.api_hash,
            self.log,
            self.root  # 传入 root 用于 UI 更新
        )
        
        self.message_sender = MessageSender(
            self.api_id,
            self.api_hash,
            self.log
        )
        
        self.proxy_manager = ProxyManager(self.log)

        # 数据存储
        self.accounts = []  # {path, selected, status, username, phone, first_name, proxy, 2fa}
        self.targets = []   # 目标用户列表
        self.collected_users = []  # 采集的用户
        self.is_running = False
        self.stop_flag = False  # 停止标志

        # 检测配置(问题 4:并发优化)
        self.check_concurrent = tk.IntVar(value=10)  # 并发数量(降低到 10 避免数据库锁定)
        self.check_batch_delay = tk.IntVar(value=2)  # 批次间隔(秒)
        self.check_timeout = tk.IntVar(value=30)  # 超时时间(秒)

        # 配置文件路径（向后兼容旧版本）
        self.config_file = "config.json"
        self.accounts_dir = str(config.SESSIONS_DIR)
        self.targets_file = str(config.DATA_DIR / "targets.json")
        self.forward_posts_file = str(config.DATA_DIR / "forward_posts.json")
        self.message_text_file = str(config.DATA_DIR / "message_text.json")

        # 创建账号文件夹（向后兼容）
        config.SESSIONS_DIR.mkdir(exist_ok=True)
        config.DATA_DIR.mkdir(exist_ok=True)
        if not os.path.exists(self.accounts_dir):
            os.makedirs(self.accounts_dir)

        self.setup_ui()

        # 加载配置和账号
        self.load_config()
        self.load_accounts()
        self.load_targets()  # 加载目标用户
        self.load_forward_posts()  # 加载转发链接
        self.load_message_text()  # 加载文本消息
        self.load_proxies()  # 加载代理列表

    def setup_ui(self):
        """设置界面"""

        # ========== 顶部标题栏 ==========
        title_frame = ttk.Frame(self.root, padding="10")
        title_frame.pack(fill=tk.X)

        ttk.Label(title_frame, text=f"📱 TG 批量私信系统 {VERSION}",
                 font=("微软雅黑", 16, "bold")).pack(side=tk.LEFT, padx=10)

        # ========== 功能标签栏 ==========
        tab_frame = ttk.Frame(self.root)
        tab_frame.pack(fill=tk.BOTH, expand=True, padx=10)

        # 使用 PanedWindow 可拖动分隔栏(问题 11:UI 布局优化)
        main_paned = ttk.PanedWindow(tab_frame, orient=tk.VERTICAL)
        main_paned.pack(fill=tk.BOTH, expand=True)

        # 上方:标签页区域(50%)
        notebook_frame = ttk.Frame(main_paned)
        main_paned.add(notebook_frame, weight=1)

        self.notebook = ttk.Notebook(notebook_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # 设置标签字体
        style = ttk.Style()
        style.configure('TNotebook.Tab', font=('微软雅黑', 12, 'bold'), padding=[20, 10])

        # 设置 Menubutton 样式,让它看起来像普通按钮
        style.configure('TMenubutton',
                       relief='raised',
                       borderwidth=2,
                       padding=6)

        # 设置代理管理按钮样式(左对齐)
        style.configure('Proxy.TButton',
                       anchor='w')  # 'w' = west = 左对齐

        # 创建四个功能标签页
        self.setup_tab_accounts()
        self.setup_tab_messaging()
        self.setup_tab_scraper()
        self.setup_tab_proxy()  # 新增:代理管理

        # 下方:日志区域(50%)
        log_container = ttk.Frame(main_paned)
        main_paned.add(log_container, weight=1)

        # 控制按钮
        control_frame = ttk.Frame(log_container, padding="5")
        control_frame.pack(fill=tk.X)

        # 开始按钮(根据当前标签页决定行为)
        self.start_btn = ttk.Button(control_frame, text="🚀 开始", width=15,
                                    command=self.on_start_button_click)
        self.start_btn.pack(side=tk.LEFT, padx=5)

        self.stop_btn = ttk.Button(control_frame, text="⏸️ 停止", width=15,
                                   command=self.stop_task, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=5)

        # 采集进度标签（仅采集页面显示）
        self.scrape_progress_label = ttk.Label(control_frame, text="", 
                                               font=("微软雅黑", 11),
                                               foreground="blue")
        # 默认隐藏
        
        # 进度显示(在按钮右侧,使用 Frame 包含三个 Label)
        # 默认隐藏，只在私信广告页面显示
        progress_container = ttk.Frame(control_frame)
        # progress_container.pack(side=tk.LEFT, padx=20)  # 默认不 pack
        self.progress_container = progress_container  # 保存引用用于后续显示/隐藏

        self.progress_total_label = ttk.Label(progress_container, text="",
                                              font=("微软雅黑", 14, "bold"),
                                              foreground="blue")
        self.progress_total_label.pack(side=tk.LEFT)

        self.progress_success_label = ttk.Label(progress_container, text="",
                                                font=("微软雅黑", 14, "bold"),
                                                foreground="green")
        self.progress_success_label.pack(side=tk.LEFT, padx=(10, 0))

        self.progress_failed_label = ttk.Label(progress_container, text="",
                                               font=("微软雅黑", 14, "bold"),
                                               foreground="red")
        self.progress_failed_label.pack(side=tk.LEFT, padx=(10, 0))

        # 日志框架
        log_frame = ttk.LabelFrame(log_container, text="📝 运行日志", padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(5, 0))

        self.log_text = scrolledtext.ScrolledText(log_frame, height=10,
                                                  font=("Consolas", 9))
        self.log_text.pack(fill=tk.BOTH, expand=True)

        # 欢迎日志
        self.log(f"✅ TG 批量私信系统 {VERSION} 已启动")
        self.log("📋 功能: 账号管理、私信广告、采集用户")
        self.log("💡 点击顶部标签切换功能")

        # 保存 main_paned 引用以便后续设置
        self.main_paned = main_paned

        # 延迟设置分割位置(确保窗口完全渲染后)
        self.root.after(100, self.set_initial_sash_position)

        # 应用加载的配置
        self.apply_loaded_config()

        # 显示自动加载的账号
        self.refresh_account_tree()

        # 更新选中数量和表头
        self.update_selected_count()

        # 绑定标签切换事件
        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed)

        # 绑定窗口缩放事件
        self.root.bind("<Configure>", self.on_window_resize)
        self.last_resize_time = 0  # 防抖

    def on_tab_changed(self, event):
        """标签页切换事件"""
        current_tab = self.notebook.index(self.notebook.select())

        # 显示/隐藏进度条（只在私信广告页面显示）
        if current_tab == 1:  # 私信广告页面
            if not self.progress_container.winfo_ismapped():
                self.progress_container.pack(side=tk.LEFT, padx=20)
            # 隐藏采集进度
            if self.scrape_progress_label.winfo_ismapped():
                self.scrape_progress_label.pack_forget()
        elif current_tab == 2:  # 采集用户页面
            # 隐藏私信进度
            if self.progress_container.winfo_ismapped():
                self.progress_container.pack_forget()
            # 显示采集进度（如果有）
            if hasattr(self, 'is_scraping') and self.is_scraping:
                if not self.scrape_progress_label.winfo_ismapped():
                    self.scrape_progress_label.pack(side=tk.LEFT, padx=20)
        else:  # 其他页面
            if self.progress_container.winfo_ismapped():
                self.progress_container.pack_forget()
            if self.scrape_progress_label.winfo_ismapped():
                self.scrape_progress_label.pack_forget()

        # 根据标签页显示/隐藏开始停止按钮
        if current_tab == 3:  # 代理管理页面 - 隐藏按钮
            self.start_btn.pack_forget()
            self.stop_btn.pack_forget()
        else:  # 其他页面 - 显示按钮
            # 检查按钮是否已经显示
            if not self.start_btn.winfo_ismapped():
                # 重新打包按钮（直接 pack，不指定 before）
                self.start_btn.pack(side=tk.LEFT, padx=5)
                self.stop_btn.pack(side=tk.LEFT, padx=5)

        if current_tab == 1:  # 私信广告页面
            # 延迟设置布局
            self.root.after(100, self.set_messaging_sash_position)

    def on_window_resize(self, event):
        """窗口缩放事件(防抖处理)"""
        import time
        current_time = time.time()

        # 只在窗口缩放完成后300ms执行(防抖)
        if current_time - self.last_resize_time > 0.3:
            self.last_resize_time = current_time

            # 如果在私信广告页面,重新调整布局
            try:
                current_tab = self.notebook.index(self.notebook.select())
                if current_tab == 1:  # 私信广告页面
                    self.root.after(100, self.set_messaging_sash_position)
                elif current_tab == 0:  # 账号管理页面
                    self.root.after(100, self.set_initial_sash_position)
            except:
                pass

    def set_initial_sash_position(self):
        """设置初始分割位置(延迟执行)- 仅影响主界面"""
        try:
            # 强制更新窗口
            self.root.update()

            window_height = self.root.winfo_height()
            # self.log(f"🔍 窗口高度: {window_height}px")  # 静默

            if window_height > 100:
                split_position = int(window_height * 0.5)  # 50% 位置
                # self.log(f"🔧 设置分割位置: {split_position}px")  # 静默

                # 设置分割位置
                self.main_paned.sashpos(0, split_position)

                # 验证是否设置成功
                actual_pos = self.main_paned.sashpos(0)
                # self.log(f"✅ 实际分割位置: {actual_pos}px")  # 静默

                if actual_pos != split_position:
                    # self.log(f"⚠️ 位置不匹配,重试...")  # 静默
                    self.root.after(200, lambda: self.main_paned.sashpos(0, split_position))
            # else:
                # self.log(f"⚠️ 窗口高度异常: {window_height}px")  # 静默
        except Exception as e:
            pass  # 静默处理错误

    def set_messaging_sash_position(self):
        """设置私信广告分割位置(自适应布局,确保右侧最小宽度)"""
        try:
            # 强制更新窗口
            self.root.update_idletasks()
            self.root.update()

            window_width = self.root.winfo_width()

            if window_width > 100:  # 确保窗口已渲染
                # 右侧最小宽度:400px(确保配置项显示完整)
                min_right_width = 400

                # 根据窗口宽度智能调整比例
                if window_width >= 1400:
                    # 大屏幕:左65% 右35%
                    ratio = 0.65
                elif window_width >= 1000:
                    # 中等屏幕:左60% 右40%
                    ratio = 0.60
                else:
                    # 小屏幕:保证右侧至少400px
                    ratio = min(0.55, (window_width - min_right_width) / window_width)

                split_position = int(window_width * ratio)

                # 确保右侧至少有最小宽度
                if window_width - split_position < min_right_width:
                    split_position = window_width - min_right_width

                self.messaging_paned.sashpos(0, split_position)
            else:
                # 窗口未渲染,延迟重试
                self.root.after(500, self.set_messaging_sash_position)
        except Exception as e:
            pass  # 静默处理错误

        # 窗口关闭时保存配置
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def on_closing(self):
        """窗口关闭时保存配置"""
        self.save_config()
        self.root.destroy()

    def mask_proxy(self, proxy):
        """对代理信息中的账号密码打码"""
        import re
        
        # 匹配格式: protocol://user:pass@ip:port 或 user:pass@ip:port
        # 将 user:pass 替换为 ***:***
        
        # 先尝试匹配 protocol://user:pass@ip:port
        pattern1 = r'((?:socks5|socks4|http)://)([^:]+):([^@]+)@(.+)'
        match1 = re.match(pattern1, proxy)
        if match1:
            protocol, user, password, rest = match1.groups()
            return f"{protocol}***:***@{rest}"
        
        # 再尝试匹配 user:pass@ip:port
        pattern2 = r'([^:]+):([^@]+)@(.+)'
        match2 = re.match(pattern2, proxy)
        if match2:
            user, password, rest = match2.groups()
            return f"***:***@{rest}"
        
        # 如果都不匹配，直接返回（可能是 ip:port 格式，无账号密码）
        return proxy

    def refresh_account_tree(self):
        """刷新账号列表显示"""
        # 清空树
        for item in self.account_tree.get_children():
            self.account_tree.delete(item)

        # 重新填充
        for index, acc in enumerate(self.accounts, start=1):
            # 复选框:☑ (已选) 或 ☐ (未选)
            check = "☑" if acc["selected"] else "☐"

            # 提取姓名(first_name)
            first_name = acc.get("first_name", "-")

            # 代理状态（简化显示：使用代理/直连）
            proxy_used = acc.get("proxy_used", "")
            if proxy_used and proxy_used not in ["", "直连", "False", "false"]:
                proxy_display = "使用代理"
            else:
                proxy_display = "直连"

            # 2FA 状态(直接显示值)
            twofa_display = acc.get("2fa", "")

            self.account_tree.insert("", tk.END, values=(
                index,  # 序号
                check,
                acc["phone"],
                acc["username"],
                first_name,
                acc["status"],
                proxy_display,
                twofa_display
            ))

        self.update_account_stats()
        self.update_selected_count()

    def setup_tab_accounts(self):
        """功能1: 账号管理"""
        tab1 = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab1, text="📂 账号管理")

        # 第一行按钮组
        btn_frame = ttk.Frame(tab1)
        btn_frame.pack(fill=tk.X, pady=(0, 5))

        ttk.Button(btn_frame, text="📁 导入 Session 文件夹", width=20,
                  command=self.import_sessions).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="✅ 全选", width=8,
                  command=self.select_all).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="❌ 清空", width=8,
                  command=self.deselect_all).pack(side=tk.LEFT, padx=2)

        # 删除按钮(点击弹出菜单)
        delete_btn = ttk.Button(btn_frame, text="🗑️ 删除", width=12,
                               command=lambda: self.show_delete_menu(delete_btn))
        delete_btn.pack(side=tk.LEFT, padx=2)

        # 导出按钮(点击弹出菜单)
        export_btn = ttk.Button(btn_frame, text="📤 导出", width=12,
                               command=lambda: self.show_export_menu(export_btn))
        export_btn.pack(side=tk.LEFT, padx=2)

        # 第二行:范围选择
        range_frame = ttk.Frame(tab1)
        range_frame.pack(fill=tk.X, pady=(0, 10))

        # 选择按钮(Menubutton)
        self.select_menubutton = ttk.Menubutton(range_frame, text="🎯 选择 ▼", width=12)
        self.select_menubutton.pack(side=tk.LEFT, padx=5)

        # 创建菜单
        select_menu = tk.Menu(self.select_menubutton, tearoff=0, font=("Microsoft YaHei UI", 10))
        self.select_menubutton.config(menu=select_menu)

        # 范围选择
        select_menu.add_command(label="📍 选中序号范围", command=self.select_by_range)
        select_menu.add_separator()

        # 状态筛选
        select_menu.add_command(label="✅ 选中无限制", command=lambda: self.select_by_status("free"))
        select_menu.add_command(label="🚫 选中冻结", command=lambda: self.select_by_status("frozen"))
        select_menu.add_command(label="⚠️ 选中永久双向限制", command=lambda: self.select_by_status("permanent"))
        select_menu.add_command(label="⚠️ 选中临时限制", command=lambda: self.select_by_status("temporary"))
        select_menu.add_command(label="🚫 选中封禁", command=lambda: self.select_by_status("banned"))
        select_menu.add_command(label="⏱️ 选中检测超时", command=lambda: self.select_by_status("timeout"))
        select_menu.add_command(label="📝 选中未检测", command=lambda: self.select_by_status("unchecked"))
        select_menu.add_command(label="❓ 选中未知/检测失败", command=lambda: self.select_by_status("unknown"))

        # 范围输入框
        ttk.Label(range_frame, text="从").pack(side=tk.LEFT, padx=(10, 2))
        self.range_from = tk.IntVar(value=1)
        ttk.Spinbox(range_frame, from_=1, to=10000, textvariable=self.range_from,
                   width=8).pack(side=tk.LEFT, padx=2)

        ttk.Label(range_frame, text="到").pack(side=tk.LEFT, padx=2)
        self.range_to = tk.IntVar(value=50)
        ttk.Spinbox(range_frame, from_=1, to=10000, textvariable=self.range_to,
                   width=8).pack(side=tk.LEFT, padx=2)

        ttk.Button(range_frame, text="🔄 刷新", width=10,
                  command=self.refresh_accounts).pack(side=tk.LEFT, padx=(20, 2))

        # 账号列表
        tree_frame = ttk.Frame(tab1)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        self.account_tree = ttk.Treeview(tree_frame,
                                         columns=("#", "选择", "手机号", "用户名", "姓名", "状态", "代理", "2FA"),
                                         show="headings", height=25)

        # 设置字体(放大复选框)
        style = ttk.Style()
        style.configure("Treeview", font=("微软雅黑", 11))
        style.configure("Treeview.Heading", font=("微软雅黑", 10, "bold"))

        self.account_tree.heading("#", text="#")
        self.account_tree.heading("选择", text="✓")
        self.account_tree.heading("手机号", text="手机号")
        self.account_tree.heading("用户名", text="用户名")
        self.account_tree.heading("姓名", text="姓名")
        self.account_tree.heading("状态", text="状态")
        self.account_tree.heading("代理", text="代理")
        self.account_tree.heading("2FA", text="2FA")

        self.account_tree.column("#", width=40, anchor=tk.CENTER)
        self.account_tree.column("选择", width=50, anchor=tk.CENTER)
        self.account_tree.column("手机号", width=120)
        self.account_tree.column("用户名", width=120)
        self.account_tree.column("姓名", width=100)
        self.account_tree.column("状态", width=150)
        self.account_tree.column("代理", width=80)
        self.account_tree.column("2FA", width=60, anchor=tk.CENTER)

        self.account_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL,
                                  command=self.account_tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.account_tree.config(yscrollcommand=scrollbar.set)

        # 双击切换选择
        self.account_tree.bind("<Double-1>", self.toggle_account)

        # 右键菜单(复制手机号)
        self.account_tree.bind("<Button-3>", self.show_context_menu)

        # 统计信息
        self.stats_frame = ttk.Frame(tab1)
        self.stats_frame.pack(fill=tk.X, pady=(10, 0))
        self.stats_label = ttk.Label(self.stats_frame, text="📊 统计: 总数 0 | 已选 0 | 正常 0 | 异常 0 | 未检测 0",
                                     font=("微软雅黑", 10))
        self.stats_label.pack(side=tk.LEFT)

    def setup_tab_messaging(self):
        """功能2: 私信广告"""
        tab2 = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab2, text="✉️ 私信广告")

        # 左右分栏(私信广告独立布局)
        paned = ttk.PanedWindow(tab2, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        # ========== 左侧:消息设置(可滚动) ==========
        left_container = ttk.Frame(paned)
        paned.add(left_container, weight=3)  # 左侧占更多空间

        # 创建 Canvas 和滚动条
        left_canvas = tk.Canvas(left_container, highlightthickness=0)
        left_scrollbar = ttk.Scrollbar(left_container, orient=tk.VERTICAL, command=left_canvas.yview)
        left_scrollable_frame = ttk.Frame(left_canvas)

        left_scrollable_frame.bind(
            "<Configure>",
            lambda e: left_canvas.configure(scrollregion=left_canvas.bbox("all"))
        )

        left_canvas.create_window((0, 0), window=left_scrollable_frame, anchor="nw")
        left_canvas.configure(yscrollcommand=left_scrollbar.set)

        left_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        left_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 鼠标滚轮支持
        def on_mousewheel(event):
            left_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        left_canvas.bind_all("<MouseWheel>", on_mousewheel)

        # 使用 left_scrollable_frame 作为实际的左侧容器
        left = left_scrollable_frame

        # 顶部横向布局:选择账号 + 发送类型
        top_frame = ttk.Frame(left)
        top_frame.pack(fill=tk.X, pady=(0, 10))

        # 选择账号(左侧)
        account_frame = ttk.LabelFrame(top_frame, text="📱 选择账号", padding="10")
        account_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

        ttk.Label(account_frame, text="使用「账号管理」中已选的账号",
                 font=("微软雅黑", 9)).pack(anchor=tk.W)
        self.selected_count_label = ttk.Label(account_frame, text="✓ 已选择 0 个账号",
                                              foreground="green", font=("微软雅黑", 10, "bold"))
        self.selected_count_label.pack(anchor=tk.W, pady=(3, 0))

        # 发送类型(右侧)
        type_frame = ttk.LabelFrame(top_frame, text="📝 发送类型", padding="10")
        type_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5, 0))

        self.send_type = tk.StringVar(value="text")
        ttk.Radiobutton(type_frame, text="📝 文本消息", variable=self.send_type,
                       value="text", command=self.on_send_type_change).pack(anchor=tk.W, pady=2)
        ttk.Radiobutton(type_frame, text="🔗 转发贴子", variable=self.send_type,
                       value="forward", command=self.on_send_type_change).pack(anchor=tk.W, pady=2)

        # 文本消息框
        self.text_msg_frame = ttk.LabelFrame(left, text="✉️ 文本消息", padding="10")
        self.text_msg_frame.pack(fill=tk.X, pady=(0, 10))

        self.message_text = scrolledtext.ScrolledText(self.text_msg_frame, height=6,
                                                      font=("微软雅黑", 10), wrap=tk.WORD)
        self.message_text.pack(fill=tk.BOTH, expand=True)
        self.message_text.insert("1.0", "你好 {firstname}!\n\n这是一条测试消息。\n\n支持变量:\n• {username} - 用户名\n• {firstname} - 名字")

        # 绑定内容变化事件
        self.message_text.bind("<<Modified>>", self.on_message_text_change)

        # 转发贴子框(默认隐藏)
        self.forward_msg_frame = ttk.LabelFrame(left, text="🔗 转发贴子", padding="10")
        # 不 pack,等切换时显示

        ttk.Label(self.forward_msg_frame, text="贴子链接 (每行一条,自动随机选择):").pack(anchor=tk.W)
        ttk.Label(self.forward_msg_frame, text="格式: https://t.me/channel/12345",
                 font=("微软雅黑", 8), foreground="gray").pack(anchor=tk.W)

        self.forward_urls_text = scrolledtext.ScrolledText(self.forward_msg_frame, height=8,
                                                           font=("微软雅黑", 9), wrap=tk.WORD)
        self.forward_urls_text.pack(fill=tk.BOTH, expand=True, pady=5)
        self.forward_urls_text.insert("1.0", "https://t.me/channel_name/123\nhttps://t.me/channel_name/456\nhttps://t.me/channel_name/789")

        # 绑定内容变化事件
        self.forward_urls_text.bind("<<Modified>>", self.on_forward_urls_change)

        self.hide_source = tk.BooleanVar(value=False)  # 默认不隐藏
        ttk.Checkbutton(self.forward_msg_frame, text="隐藏来源",
                       variable=self.hide_source, command=self.save_forward_posts).pack(anchor=tk.W, pady=5)

        self.forward_count_label = ttk.Label(self.forward_msg_frame, text="共 3 条贴子",
                                            font=("微软雅黑", 9))
        self.forward_count_label.pack(anchor=tk.W)

        # 保存左侧容器引用(用于切换)
        self.messaging_left = left

        # 目标用户
        target_frame = ttk.LabelFrame(left, text="👥 目标用户", padding="10")
        target_frame.pack(fill=tk.X, pady=(0, 10))

        # 保存目标框引用
        self.target_frame = target_frame

        target_btn_frame = ttk.Frame(target_frame)
        target_btn_frame.pack(fill=tk.X, pady=(0, 5))

        ttk.Button(target_btn_frame, text="📥 从采集导入", width=15,
                  command=self.import_from_scraper).pack(side=tk.LEFT, padx=2)
        ttk.Button(target_btn_frame, text="📄 从文件导入", width=15,
                  command=self.import_from_file).pack(side=tk.LEFT, padx=2)
        ttk.Button(target_btn_frame, text="🗑️ 清空列表", width=12,
                  command=self.clear_targets).pack(side=tk.LEFT, padx=2)

        self.target_text = scrolledtext.ScrolledText(target_frame, height=8,
                                                     font=("微软雅黑", 10), wrap=tk.WORD)
        self.target_text.pack(fill=tk.BOTH, expand=True)
        self.target_text.insert("1.0", "@username1\n@username2\n@username3")

        # 绑定内容变化事件
        self.target_text.bind("<<Modified>>", self.on_target_text_change)

        self.target_count_label = ttk.Label(target_frame, text="共 3 个目标用户",
                                            font=("微软雅黑", 9))
        self.target_count_label.pack(anchor=tk.W, pady=(5, 0))

        # ========== 右侧:发送设置 ==========
        right = ttk.Frame(paned)
        paned.add(right, weight=1)  # 右侧占较少空间

        # 保存 paned 引用,稍后设置分割位置
        self.messaging_paned = paned

        # 第一行:并发控制 + 额度限制
        row1_frame = ttk.Frame(right)
        row1_frame.pack(fill=tk.X, pady=(0, 10))

        # 并发控制(左侧)
        concurrent_frame = ttk.LabelFrame(row1_frame, text="⚡ 并发控制", padding="10")
        concurrent_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

        ttk.Label(concurrent_frame, text="并行线程数:").grid(row=0, column=0, sticky=tk.W, pady=3)
        self.thread_count = tk.IntVar(value=2)
        ttk.Spinbox(concurrent_frame, from_=1, to=50, textvariable=self.thread_count,
                   width=8).grid(row=0, column=1, sticky=tk.EW, padx=(10, 0), pady=3)

        ttk.Label(concurrent_frame, text="启动间隔(秒):").grid(row=1, column=0, sticky=tk.W, pady=3)
        self.thread_interval = tk.IntVar(value=1)
        ttk.Spinbox(concurrent_frame, from_=0, to=60, textvariable=self.thread_interval,
                   width=8).grid(row=1, column=1, sticky=tk.EW, padx=(10, 0), pady=3)

        concurrent_frame.columnconfigure(1, weight=1)

        # 额度限制(右侧)
        limit_frame = ttk.LabelFrame(row1_frame, text="📊 额度限制", padding="10")
        limit_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5, 0))

        ttk.Label(limit_frame, text="单账号上限:").grid(row=0, column=0, sticky=tk.W, pady=3)
        self.per_account_limit = tk.IntVar(value=50)
        ttk.Spinbox(limit_frame, from_=1, to=1000, textvariable=self.per_account_limit,
                   width=8).grid(row=0, column=1, sticky=tk.EW, padx=(10, 0), pady=3)

        ttk.Label(limit_frame, text="任务总上限:").grid(row=1, column=0, sticky=tk.W, pady=3)
        self.total_limit = tk.IntVar(value=1000)
        ttk.Spinbox(limit_frame, from_=1, to=100000, textvariable=self.total_limit,
                   width=8).grid(row=1, column=1, sticky=tk.EW, padx=(10, 0), pady=3)

        ttk.Label(limit_frame, text="无视双向限制:").grid(row=2, column=0, sticky=tk.W, pady=3)
        self.ignore_privacy_limit = tk.IntVar(value=10)
        ttk.Spinbox(limit_frame, from_=1, to=100, textvariable=self.ignore_privacy_limit,
                   width=8).grid(row=2, column=1, sticky=tk.EW, padx=(10, 0), pady=3)

        limit_frame.columnconfigure(1, weight=1)

        # 第二行:发送间隔 + 其他选项
        row2_frame = ttk.Frame(right)
        row2_frame.pack(fill=tk.X, pady=(0, 10))

        # 发送间隔(左侧)
        interval_frame = ttk.LabelFrame(row2_frame, text="⏱️ 发送间隔", padding="10")
        interval_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

        ttk.Label(interval_frame, text="间隔范围:").grid(row=0, column=0, sticky=tk.W, pady=3)
        range_frame = ttk.Frame(interval_frame)
        range_frame.grid(row=0, column=1, sticky=tk.EW, padx=(10, 0), pady=3)

        self.interval_min = tk.IntVar(value=3)
        ttk.Spinbox(range_frame, from_=1, to=60, textvariable=self.interval_min,
                   width=5).pack(side=tk.LEFT)
        ttk.Label(range_frame, text="~").pack(side=tk.LEFT, padx=3)
        self.interval_max = tk.IntVar(value=8)
        ttk.Spinbox(range_frame, from_=1, to=60, textvariable=self.interval_max,
                   width=5).pack(side=tk.LEFT)
        ttk.Label(range_frame, text="秒").pack(side=tk.LEFT, padx=(3, 0))

        interval_frame.columnconfigure(1, weight=1)

        # 其他选项(右侧)
        option_frame = ttk.LabelFrame(row2_frame, text="🔧 其他选项", padding="10")
        option_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5, 0))

        # 消息置顶
        pin_frame = ttk.Frame(option_frame)
        pin_frame.pack(fill=tk.X, pady=2)
        
        ttk.Label(pin_frame, text="消息置顶(秒):").pack(side=tk.LEFT)
        self.pin_delay = tk.IntVar(value=0)
        ttk.Spinbox(pin_frame, from_=0, to=60, textvariable=self.pin_delay,
                   width=5).pack(side=tk.LEFT, padx=(10, 0))
        ttk.Label(pin_frame, text="(0=不置顶)").pack(side=tk.LEFT, padx=(5, 0))

        # 随机emoji
        self.random_emoji = tk.BooleanVar(value=False)
        ttk.Checkbutton(option_frame, text="随机符号emoji",
                       variable=self.random_emoji).pack(anchor=tk.W, pady=2)

    def setup_tab_scraper(self):
        """功能3: 采集用户"""
        tab3 = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab3, text="👥 采集用户")

        # 左右分栏
        paned = ttk.PanedWindow(tab3, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        # ========== 左侧:采集设置（添加滚动） ==========
        # 创建Canvas和滚动条
        left_container = ttk.Frame(paned)
        paned.add(left_container, weight=1)
        
        left_canvas = tk.Canvas(left_container, highlightthickness=0)
        left_scrollbar = ttk.Scrollbar(left_container, orient=tk.VERTICAL, command=left_canvas.yview)
        left_scrollable = ttk.Frame(left_canvas)
        
        left_scrollable.bind(
            "<Configure>",
            lambda e: left_canvas.configure(scrollregion=left_canvas.bbox("all"))
        )
        
        left_canvas.create_window((0, 0), window=left_scrollable, anchor="nw")
        left_canvas.configure(yscrollcommand=left_scrollbar.set)
        
        left_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        left_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 鼠标滚轮绑定
        def _on_mousewheel(event):
            left_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        left_canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        # 使用left_scrollable代替left作为父容器

        # 采集来源
        source_frame = ttk.LabelFrame(left_scrollable, text="📌 采集来源", padding="10")
        source_frame.pack(fill=tk.X, pady=(0, 10))

        self.scrape_type = tk.StringVar(value="group")
        ttk.Radiobutton(source_frame, text="👥 从群组采集成员", variable=self.scrape_type,
                       value="group").pack(anchor=tk.W, pady=2)
        ttk.Radiobutton(source_frame, text="📢 从频道采集订阅者", variable=self.scrape_type,
                       value="channel").pack(anchor=tk.W, pady=2)

        # 采集模式
        mode_frame = ttk.LabelFrame(left_scrollable, text="⚙️ 采集模式", padding="10")
        mode_frame.pack(fill=tk.X, pady=(0, 10))

        self.scrape_mode = tk.StringVar(value="default")
        ttk.Radiobutton(mode_frame, text="🚀 默认采集（快速，仅未隐藏成员群组）", 
                       variable=self.scrape_mode, value="default").pack(anchor=tk.W, pady=2)
        ttk.Radiobutton(mode_frame, text="💬 通过聊天记录采集（慢速，可采集隐藏成员群组）", 
                       variable=self.scrape_mode, value="messages").pack(anchor=tk.W, pady=2)
        
        # 聊天记录限制（仅消息模式）
        msg_limit_frame = ttk.Frame(mode_frame)
        msg_limit_frame.pack(fill=tk.X, pady=(5, 0), padx=(20, 0))
        ttk.Label(msg_limit_frame, text="最多分析消息数:").pack(side=tk.LEFT)
        self.message_limit = tk.IntVar(value=3000)
        ttk.Spinbox(msg_limit_frame, from_=500, to=50000, increment=500,
                   textvariable=self.message_limit, width=8).pack(side=tk.LEFT, padx=(5, 0))
        ttk.Label(msg_limit_frame, text="条 (↓越小越快)", 
                 font=("微软雅黑", 8), foreground="gray").pack(side=tk.LEFT, padx=(5, 0))

        # 采集来源
        source_frame = ttk.LabelFrame(left_scrollable, text="📍 采集来源", padding="10")
        source_frame.pack(fill=tk.X, pady=(0, 10))

        self.scrape_source = tk.StringVar(value="list")
        ttk.Radiobutton(source_frame, text="📋 从群列表采集（需要输入链接）", 
                       variable=self.scrape_source, value="list",
                       command=self.on_scrape_source_change).pack(anchor=tk.W, pady=2)
        ttk.Radiobutton(source_frame, text="👥 从已加入的群采集（无需链接）", 
                       variable=self.scrape_source, value="joined",
                       command=self.on_scrape_source_change).pack(anchor=tk.W, pady=2)
        ttk.Radiobutton(source_frame, text="💬 从对话列表采集（有对话的用户）", 
                       variable=self.scrape_source, value="dialogs",
                       command=self.on_scrape_source_change).pack(anchor=tk.W, pady=2)

        # 目标列表（仅"从群列表采集"时显示）- 直接编辑
        self.targets_frame = ttk.LabelFrame(left_scrollable, text="📋 采集目标列表（每行一个链接或用户名）", padding="10")
        self.targets_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        ttk.Label(self.targets_frame, text="💡 提示：直接在下方输入，每行一个链接或用户名", 
                 foreground="gray", font=("微软雅黑", 9)).pack(anchor=tk.W, pady=(0, 5))

        # 使用 ScrolledText 代替 Listbox，更方便编辑
        self.scrape_targets_text = scrolledtext.ScrolledText(
            self.targets_frame, 
            font=("微软雅黑", 10), 
            height=8,
            wrap=tk.WORD
        )
        self.scrape_targets_text.pack(fill=tk.BOTH, expand=True)
        
        # 添加示例文本
        self.scrape_targets_text.insert("1.0", "https://t.me/group_name\n@channel_name\n")
        
        btn_frame = ttk.Frame(self.targets_frame)
        btn_frame.pack(fill=tk.X, pady=(5, 0))
        ttk.Button(btn_frame, text="🧹 清空列表", width=12,
                  command=lambda: self.scrape_targets_text.delete("1.0", tk.END)).pack(side=tk.LEFT, padx=2)

        # 过滤选项
        filter_frame = ttk.LabelFrame(left_scrollable, text="🔍 过滤条件", padding="10")
        filter_frame.pack(fill=tk.X)

        # 在线时间过滤
        self.filter_online_time = tk.BooleanVar(value=False)
        ttk.Checkbutton(filter_frame, text="按在线时间过滤",
                       variable=self.filter_online_time).pack(anchor=tk.W, pady=2)

        online_frame = ttk.Frame(filter_frame)
        online_frame.pack(fill=tk.X, padx=(20, 0), pady=(0, 5))
        ttk.Label(online_frame, text="最近").pack(side=tk.LEFT)
        self.online_days = tk.IntVar(value=3)
        ttk.Spinbox(online_frame, from_=1, to=30, textvariable=self.online_days,
                   width=5).pack(side=tk.LEFT, padx=(5, 5))
        ttk.Label(online_frame, text="天内在线").pack(side=tk.LEFT)

        # 隐藏在线时间的用户
        hidden_frame = ttk.Frame(filter_frame)
        hidden_frame.pack(fill=tk.X, padx=(20, 0), pady=(0, 5))
        ttk.Label(hidden_frame, text="隐藏在线时间的用户:").pack(anchor=tk.W)

        self.include_recently = tk.BooleanVar(value=True)
        ttk.Checkbutton(filter_frame, text="  包含「最近在线」",
                       variable=self.include_recently).pack(anchor=tk.W, pady=1, padx=(40, 0))

        self.include_online = tk.BooleanVar(value=True)
        ttk.Checkbutton(filter_frame, text="  包含「当前在线」",
                       variable=self.include_online).pack(anchor=tk.W, pady=1, padx=(40, 0))

        ttk.Separator(filter_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)

        # 用户类型过滤
        ttk.Label(filter_frame, text="用户类型:").pack(anchor=tk.W, pady=(5, 2))

        self.filter_admin = tk.BooleanVar(value=False)
        ttk.Checkbutton(filter_frame, text="仅采集群主/管理员",
                       variable=self.filter_admin).pack(anchor=tk.W, pady=1, padx=(20, 0))

        self.filter_premium = tk.BooleanVar(value=False)
        ttk.Checkbutton(filter_frame, text="仅采集 Premium 会员",
                       variable=self.filter_premium).pack(anchor=tk.W, pady=1, padx=(20, 0))

        # 其他过滤
        ttk.Label(filter_frame, text="其他条件:").pack(anchor=tk.W, pady=(5, 2))

        self.filter_bot = tk.BooleanVar(value=True)
        ttk.Checkbutton(filter_frame, text="排除机器人账号",
                       variable=self.filter_bot).pack(anchor=tk.W, pady=1, padx=(20, 0))

        self.filter_username = tk.BooleanVar(value=False)
        ttk.Checkbutton(filter_frame, text="仅采集有用户名的用户",
                       variable=self.filter_username).pack(anchor=tk.W, pady=1, padx=(20, 0))

        self.filter_photo = tk.BooleanVar(value=False)
        ttk.Checkbutton(filter_frame, text="仅采集有头像的用户",
                       variable=self.filter_photo).pack(anchor=tk.W, pady=1, padx=(20, 0))

        self.filter_stories = tk.BooleanVar(value=False)
        ttk.Checkbutton(filter_frame, text="仅采集有动态的用户",
                       variable=self.filter_stories).pack(anchor=tk.W, pady=1, padx=(20, 0))

        ttk.Separator(filter_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)

        # 采集后操作
        ttk.Label(filter_frame, text="采集后操作:").pack(anchor=tk.W, pady=(5, 2))

        self.auto_leave = tk.BooleanVar(value=False)
        ttk.Checkbutton(filter_frame, text="采集完成后自动退群",
                       variable=self.auto_leave).pack(anchor=tk.W, pady=1, padx=(20, 0))

        ttk.Separator(filter_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)

        # 并发设置
        thread_sub_frame = ttk.Frame(filter_frame)
        thread_sub_frame.pack(fill=tk.X, pady=(5, 0))
        ttk.Label(thread_sub_frame, text="并发线程数:").pack(side=tk.LEFT)
        self.scrape_threads = tk.IntVar(value=5)
        ttk.Spinbox(thread_sub_frame, from_=1, to=100, textvariable=self.scrape_threads,
                   width=8).pack(side=tk.LEFT, padx=(10, 0))

        limit_sub_frame = ttk.Frame(filter_frame)
        limit_sub_frame.pack(fill=tk.X, pady=(5, 0))
        ttk.Label(limit_sub_frame, text="每个群组采集数量:").pack(side=tk.LEFT)
        self.scrape_limit = tk.IntVar(value=0)  # 0 = 不限制
        ttk.Spinbox(limit_sub_frame, from_=0, to=999999, textvariable=self.scrape_limit,
                   width=8).pack(side=tk.LEFT, padx=(10, 0))
        ttk.Label(limit_sub_frame, text="(0=不限)", font=("微软雅黑", 8), 
                 foreground="gray").pack(side=tk.LEFT, padx=(5, 0))
        
        groups_per_account_frame = ttk.Frame(filter_frame)
        groups_per_account_frame.pack(fill=tk.X, pady=(5, 0))
        ttk.Label(groups_per_account_frame, text="每个账号采集群组数:").pack(side=tk.LEFT)
        self.groups_per_account = tk.IntVar(value=5)
        ttk.Spinbox(groups_per_account_frame, from_=1, to=100, textvariable=self.groups_per_account,
                   width=8).pack(side=tk.LEFT, padx=(10, 0))

        # ========== 右侧:采集结果 ==========
        right = ttk.Frame(paned)
        paned.add(right, weight=2)

        # 操作按钮（放在顶部）
        action_frame = ttk.Frame(right)
        action_frame.pack(fill=tk.X, pady=(0, 5))

        ttk.Button(action_frame, text="✅ 全选", width=10,
                  command=self.select_all_collected).pack(side=tk.LEFT, padx=2)
        ttk.Button(action_frame, text="❌ 清空", width=10,
                  command=self.deselect_all_collected).pack(side=tk.LEFT, padx=2)
        ttk.Button(action_frame, text="📤 导出到私信", width=15,
                  command=self.export_to_messaging).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="💾 保存JSON", width=12,
                  command=self.save_collected).pack(side=tk.LEFT, padx=2)
        ttk.Button(action_frame, text="📄 导出TXT", width=12,
                  command=self.export_usernames_txt).pack(side=tk.LEFT, padx=2)

        self.collected_stats = ttk.Label(action_frame, text="已采集 0 个用户,已选 0 个",
                                         font=("微软雅黑", 9))
        self.collected_stats.pack(side=tk.RIGHT, padx=10)

        # 结果列表
        result_frame = ttk.LabelFrame(right, text="📊 采集结果", padding="10")
        result_frame.pack(fill=tk.BOTH, expand=True)

        self.result_tree = ttk.Treeview(result_frame,
                                        columns=("选择", "用户名", "名字", "来源"),
                                        show="headings", height=20)

        self.result_tree.heading("选择", text="✓")
        self.result_tree.heading("用户名", text="用户名")
        self.result_tree.heading("名字", text="名字")
        self.result_tree.heading("来源", text="来源")

        self.result_tree.column("选择", width=40, anchor=tk.CENTER)
        self.result_tree.column("用户名", width=180)
        self.result_tree.column("名字", width=180)
        self.result_tree.column("来源", width=200)

        self.result_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        result_scroll = ttk.Scrollbar(result_frame, orient=tk.VERTICAL,
                                      command=self.result_tree.yview)
        result_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.result_tree.config(yscrollcommand=result_scroll.set)

        # 双击切换选择
        self.result_tree.bind("<Double-1>", self.toggle_collected_user)

    def setup_tab_proxy(self):
        """功能4: 代理管理"""
        tab4 = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab4, text="🌐 代理管理")

        # 左右分栏
        paned = ttk.PanedWindow(tab4, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        # ========== 左侧:导入和操作(带滚动条)==========
        left_container = ttk.Frame(paned)
        paned.add(left_container, weight=1)

        # 创建 Canvas 和 Scrollbar
        left_canvas = tk.Canvas(left_container, highlightthickness=0)
        left_scrollbar = ttk.Scrollbar(left_container, orient=tk.VERTICAL, command=left_canvas.yview)
        left_scrollable = ttk.Frame(left_canvas)

        # 配置 Canvas
        left_scrollable.bind(
            "<Configure>",
            lambda e: left_canvas.configure(scrollregion=left_canvas.bbox("all"))
        )

        left_canvas.create_window((0, 0), window=left_scrollable, anchor=tk.NW)
        left_canvas.configure(yscrollcommand=left_scrollbar.set)

        # 绑定鼠标滚轮
        def _on_mousewheel(event):
            left_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        left_canvas.bind_all("<MouseWheel>", _on_mousewheel)

        left_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        left_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 使用 left_scrollable 作为内容容器(替代原来的 left)
        left = left_scrollable

        # 导入代理
        import_frame = ttk.LabelFrame(left_scrollable, text="📥 导入代理", padding="10")
        import_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(import_frame, text="支持格式:").pack(anchor=tk.W)
        ttk.Label(import_frame, text="• http://ip:port", font=("Consolas", 9)).pack(anchor=tk.W)
        ttk.Label(import_frame, text="• http://user:pass@ip:port", font=("Consolas", 9)).pack(anchor=tk.W)
        ttk.Label(import_frame, text="• socks5://ip:port", font=("Consolas", 9)).pack(anchor=tk.W)
        ttk.Label(import_frame, text="• socks5://user:pass@ip:port", font=("Consolas", 9)).pack(anchor=tk.W)
        ttk.Label(import_frame, text="• user:pass@ip:port (自动识别协议)", font=("Consolas", 9)).pack(anchor=tk.W)

        # 协议类型选择
        protocol_frame = ttk.Frame(import_frame)
        protocol_frame.pack(fill=tk.X, pady=(5, 5))
        ttk.Label(protocol_frame, text="默认协议:").pack(side=tk.LEFT, padx=(0, 5))
        self.default_proxy_protocol = tk.StringVar(value="socks5")
        ttk.Radiobutton(protocol_frame, text="SOCKS5", variable=self.default_proxy_protocol,
                       value="socks5").pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(protocol_frame, text="HTTP", variable=self.default_proxy_protocol,
                       value="http").pack(side=tk.LEFT, padx=5)
        ttk.Label(protocol_frame, text="(无协议前缀时使用)",
                 font=("微软雅黑", 8), foreground="gray").pack(side=tk.LEFT, padx=5)

        self.proxy_input = scrolledtext.ScrolledText(import_frame, height=6, font=("Consolas", 9))
        self.proxy_input.pack(fill=tk.BOTH, pady=(5, 0))

        btn_frame1 = ttk.Frame(import_frame)
        btn_frame1.pack(fill=tk.X, pady=(5, 0))
        ttk.Button(btn_frame1, text="📂 从文件导入", width=15,
                  command=self.import_proxy_file).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame1, text="➕ 添加到列表", width=15,
                  command=self.add_proxies).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame1, text="🧹 清空输入框", width=15,
                  command=lambda: self.proxy_input.delete("1.0", tk.END)).pack(side=tk.LEFT, padx=2)

        # 批量操作
        action_frame = ttk.LabelFrame(left_scrollable, text="⚙️ 批量操作", padding="10")
        action_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Button(action_frame, text="🔍 检测所有代理", style='Proxy.TButton',
                  command=self.check_all_proxies).pack(fill=tk.X, pady=2)
        ttk.Button(action_frame, text="✅ 选中可用代理", style='Proxy.TButton',
                  command=self.select_available_proxies).pack(fill=tk.X, pady=2)
        ttk.Button(action_frame, text="🗑️ 删除不可用代理", style='Proxy.TButton',
                  command=self.delete_unavailable_proxies).pack(fill=tk.X, pady=2)
        ttk.Button(action_frame, text="🧹 清空所有代理", style='Proxy.TButton',
                  command=self.clear_all_proxies).pack(fill=tk.X, pady=2)
        ttk.Button(action_frame, text="💾 导出可用代理", style='Proxy.TButton',
                  command=self.export_available_proxies).pack(fill=tk.X, pady=2)

        # ========== 右侧:代理列表 ==========
        right = ttk.Frame(paned)
        paned.add(right, weight=2)

        # 代理列表
        list_frame = ttk.LabelFrame(right, text="📋 代理列表", padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True)

        self.proxy_tree = ttk.Treeview(list_frame,
                                       columns=("选择", "代理地址", "类型", "状态", "延迟"),
                                       show="headings", height=25)

        self.proxy_tree.heading("选择", text="✓")
        self.proxy_tree.heading("代理地址", text="代理地址")
        self.proxy_tree.heading("类型", text="类型")
        self.proxy_tree.heading("状态", text="状态")
        self.proxy_tree.heading("延迟", text="延迟 (ms)")

        self.proxy_tree.column("选择", width=40, anchor=tk.CENTER)
        self.proxy_tree.column("代理地址", width=350)
        self.proxy_tree.column("类型", width=80, anchor=tk.CENTER)
        self.proxy_tree.column("状态", width=100, anchor=tk.CENTER)
        self.proxy_tree.column("延迟", width=100, anchor=tk.CENTER)

        self.proxy_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        proxy_scroll = ttk.Scrollbar(list_frame, orient=tk.VERTICAL,
                                     command=self.proxy_tree.yview)
        proxy_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.proxy_tree.config(yscrollcommand=proxy_scroll.set)

        # 双击切换选择
        self.proxy_tree.bind("<Double-1>", self.toggle_proxy_selection)

        # 统计信息
        stats_frame = ttk.Frame(right)
        stats_frame.pack(fill=tk.X, pady=(10, 0))

        self.proxy_stats = ttk.Label(stats_frame, text="总计: 0 | 可用: 0 | 不可用: 0 | 未检测: 0",
                                      font=("微软雅黑", 10, "bold"))
        self.proxy_stats.pack(side=tk.LEFT)

        # 初始化代理列表
        self.proxies = []  # 存储代理数据: [{"proxy": "...", "type": "http/socks5", "status": "未检测/可用/不可用", "ping": 0, "selected": False}]

    def log(self, message):
        """输出日志"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        self.root.update_idletasks()
        print(message)

    def on_send_type_change(self):
        """切换发送类型"""
        if self.send_type.get() == "text":
            # 显示文本框,隐藏转发框
            self.forward_msg_frame.pack_forget()
            self.text_msg_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10), before=self.target_frame)
        else:
            # 显示转发框,隐藏文本框
            self.text_msg_frame.pack_forget()
            self.forward_msg_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10), before=self.target_frame)

    def on_target_text_change(self, event=None):
        """目标用户内容变化"""
        if self.target_text.edit_modified():
            # 保存到文件
            self.save_targets()
            # 更新统计
            self.update_target_count()
            # 重置修改标志
            self.target_text.edit_modified(False)

    def on_forward_urls_change(self, event=None):
        """转发链接内容变化"""
        if self.forward_urls_text.edit_modified():
            # 保存到文件
            self.save_forward_posts()
            # 更新统计
            self.update_forward_count()
            # 重置修改标志
            self.forward_urls_text.edit_modified(False)

    def on_message_text_change(self, event=None):
        """文本消息内容变化"""
        if self.message_text.edit_modified():
            # 保存到文件
            self.save_message_text()
            # 重置修改标志
            self.message_text.edit_modified(False)

    # ========== 配置管理 ==========

    def save_config(self):
        """保存配置"""
        try:
            config = {
                "thread_count": self.thread_count.get(),
                "thread_interval": self.thread_interval.get(),
                "per_account_limit": self.per_account_limit.get(),
                "total_limit": self.total_limit.get(),
                "ignore_privacy_limit": self.ignore_privacy_limit.get(),
                "interval_min": self.interval_min.get(),
                "interval_max": self.interval_max.get(),
                "pin_delay": self.pin_delay.get(),
                "random_emoji": self.random_emoji.get(),
                "send_type": self.send_type.get(),
                "hide_source": self.hide_source.get(),
                "message_text": self.message_text.get("1.0", tk.END).strip(),
                "forward_urls": self.forward_urls_text.get("1.0", tk.END).strip(),
                "targets": self.target_text.get("1.0", tk.END).strip(),
                
                # 采集设置
                "scrape_mode": self.scrape_mode.get(),
                "scrape_source": self.scrape_source.get(),
                "scrape_limit": self.scrape_limit.get(),
                "message_limit": self.message_limit.get(),
                "groups_per_account": self.groups_per_account.get(),
                "scrape_threads": self.scrape_threads.get(),
                
                # 过滤条件
                "filter_bot": self.filter_bot.get(),
                "filter_username": self.filter_username.get(),
                "filter_premium": self.filter_premium.get() if hasattr(self, 'filter_premium') else False,
                "filter_photo": self.filter_photo.get() if hasattr(self, 'filter_photo') else False,
                "filter_online_time": self.filter_online_time.get() if hasattr(self, 'filter_online_time') else False,
                "online_days": self.online_days.get() if hasattr(self, 'online_days') else 3,
                "include_recently": self.include_recently.get() if hasattr(self, 'include_recently') else False,
                "include_online": self.include_online.get() if hasattr(self, 'include_online') else False,
                "auto_leave": self.auto_leave.get() if hasattr(self, 'auto_leave') else False
            }

            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)

            self.log("💾 配置已保存")
        except Exception as e:
            self.log(f"⚠️ 保存配置失败: {str(e)}")

    def load_config(self):
        """加载配置"""
        try:
            if not os.path.exists(self.config_file):
                self.log("📝 首次运行,使用默认配置")
                return

            with open(self.config_file, "r", encoding="utf-8") as f:
                config = json.load(f)

            # 应用配置(在 UI 创建后)
            self.loaded_config = config
            self.log("✅ 配置已加载")
        except Exception as e:
            self.log(f"⚠️ 加载配置失败: {str(e)}")
            self.loaded_config = None

    def apply_loaded_config(self):
        """应用已加载的配置(在 UI 创建后调用)"""
        if not hasattr(self, 'loaded_config') or not self.loaded_config:
            return

        try:
            config = self.loaded_config

            self.thread_count.set(config.get("thread_count", 2))
            self.thread_interval.set(config.get("thread_interval", 1))
            self.per_account_limit.set(config.get("per_account_limit", 50))
            self.total_limit.set(config.get("total_limit", 1000))
            self.ignore_privacy_limit.set(config.get("ignore_privacy_limit", 10))
            self.interval_min.set(config.get("interval_min", 3))
            self.interval_max.set(config.get("interval_max", 8))
            self.pin_delay.set(config.get("pin_delay", 0))
            self.random_emoji.set(config.get("random_emoji", False))
            self.send_type.set(config.get("send_type", "text"))
            self.hide_source.set(config.get("hide_source", False))

            self.message_text.delete("1.0", tk.END)
            self.message_text.insert("1.0", config.get("message_text", ""))

            self.forward_urls_text.delete("1.0", tk.END)
            self.forward_urls_text.insert("1.0", config.get("forward_urls", ""))

            self.target_text.delete("1.0", tk.END)
            self.target_text.insert("1.0", config.get("targets", ""))

            # 采集设置
            self.scrape_mode.set(config.get("scrape_mode", "default"))
            self.scrape_source.set(config.get("scrape_source", "list"))
            self.scrape_limit.set(config.get("scrape_limit", 0))
            self.message_limit.set(config.get("message_limit", 3000))
            self.groups_per_account.set(config.get("groups_per_account", 5))
            self.scrape_threads.set(config.get("scrape_threads", 5))
            
            # 过滤条件
            self.filter_bot.set(config.get("filter_bot", True))
            self.filter_username.set(config.get("filter_username", False))
            if hasattr(self, 'filter_premium'):
                self.filter_premium.set(config.get("filter_premium", False))
            if hasattr(self, 'filter_photo'):
                self.filter_photo.set(config.get("filter_photo", False))
            if hasattr(self, 'filter_online_time'):
                self.filter_online_time.set(config.get("filter_online_time", False))
            if hasattr(self, 'online_days'):
                self.online_days.set(config.get("online_days", 3))
            if hasattr(self, 'include_recently'):
                self.include_recently.set(config.get("include_recently", False))
            if hasattr(self, 'include_online'):
                self.include_online.set(config.get("include_online", False))
            if hasattr(self, 'auto_leave'):
                self.auto_leave.set(config.get("auto_leave", False))

            # 更新目标用户计数
            targets = [line.strip() for line in config.get("targets", "").split("\n") if line.strip()]
            self.target_count_label.config(text=f"共 {len(targets)} 个目标用户")

            self.log("✅ 配置已应用")
        except Exception as e:
            self.log(f"⚠️ 应用配置失败: {str(e)}")

    def load_accounts(self):
        """自动加载账号文件夹中的账号"""
        try:
            if not os.path.exists(self.accounts_dir):
                return

            session_files = list(Path(self.accounts_dir).glob("*.session"))

            if not session_files:
                self.log("📁 账号文件夹为空")
                return

            for session_file in session_files:
                account = {
                    "path": str(session_file),
                    "selected": True,
                    "status": "未检测",
                    "username": "-",
                    "phone": "-",
                    "first_name": "-",
                    "proxy": "直连",
                    "2fa": "",
                    "last_login": "-"
                }

                # 尝试读取配套的 JSON 文件
                # 123.session → 123.json(不是 123.session.json)
                json_file = session_file.parent / f"{session_file.stem}.json"
                json_data = None

                if json_file.exists():
                    try:
                        import json
                        with open(json_file, 'r', encoding='utf-8') as f:
                            json_data = json.load(f)
                    except Exception:
                        pass  # JSON 读取失败
                else:
                    # 没有 JSON 文件,尝试自动生成
                    json_data = self.generate_json_from_session(session_file)

                # 如果有 JSON 数据,提取信息
                if json_data:
                    # 提取手机号
                    phone = json_data.get('phone')
                    if phone:
                        account["phone"] = str(phone)

                    # 提取用户名
                    username = json_data.get('username')
                    if username:
                        account["username"] = f"@{username}" if not username.startswith('@') else username

                    # 提取姓名(first_name + last_name)
                    first_name = json_data.get('first_name', '')
                    last_name = json_data.get('last_name', '')
                    if first_name:
                        full_name = f"{first_name} {last_name}".strip() if last_name else first_name
                        account["first_name"] = full_name

                    # 不从 JSON 读取代理信息（隐私保护）
                    # 代理信息只在程序运行时通过其他方式配置
                    # JSON 文件中不保存代理地址
                    account["proxy_used"] = ""

                    # 提取 2FA 状态(检测 twoFA 和 passwordFA)
                    twofa = json_data.get('twoFA')
                    passwordfa = json_data.get('passwordFA')

                    # 优先显示 twoFA,如果没有则显示 passwordFA
                    if twofa:
                        account["2fa"] = str(twofa)
                    elif passwordfa:
                        account["2fa"] = str(passwordfa)
                    else:
                        account["2fa"] = ""

                    # 不从 JSON 读取状态，导入时始终显示"未检测"
                    # 用户需要重新检测账号以获取最新状态

                self.accounts.append(account)

            self.log(f"📂 自动加载 {len(session_files)} 个账号")
        except Exception as e:
            self.log(f"⚠️ 加载账号失败: {str(e)}")

    def refresh_accounts(self):
        """刷新账号列表(重新扫描 accounts 文件夹,保留已检测的状态)"""
        try:
            self.log("🔄 刷新账号列表...")

            # 保存当前账号的状态（以手机号为键）
            old_status = {}
            for acc in self.accounts:
                phone = Path(acc['path']).stem
                old_status[phone] = {
                    'status': acc.get('status', '未检测'),
                    'username': acc.get('username', '-'),
                    'first_name': acc.get('first_name', '-'),
                    'proxy_used': str(acc.get('proxy_used', '')) if acc.get('proxy_used') else '',
                }

            # 清空现有账号
            self.accounts.clear()

            # 重新加载文件
            self.load_accounts()

            # 恢复之前的状态
            for acc in self.accounts:
                phone = Path(acc['path']).stem
                if phone in old_status:
                    # 如果之前有状态，恢复它
                    acc['status'] = old_status[phone]['status']
                    # 如果之前有用户名/姓名，也恢复
                    if old_status[phone]['username'] != '-':
                        acc['username'] = old_status[phone]['username']
                    if old_status[phone]['first_name'] != '-':
                        acc['first_name'] = old_status[phone]['first_name']
                    if old_status[phone]['proxy_used']:
                        acc['proxy_used'] = old_status[phone]['proxy_used']

            # 刷新显示
            self.refresh_account_tree()
            self.update_account_stats()

            self.log(f"✅ 刷新完成,当前 {len(self.accounts)} 个账号")
        except Exception as e:
            self.log(f"❌ 刷新失败: {str(e)}")

    # ========== 账号管理功能 ==========

    def import_sessions(self):
        """导入 Session 文件夹（使用完整模块）"""
        folder = filedialog.askdirectory(title="选择 Session 文件夹")
        if not folder:
            return

        self.log(f"📁 正在扫描文件夹: {folder}")
        
        # 使用完整模块导入
        imported = self.account_manager.import_sessions(folder)
        
        if imported:
            self.accounts.extend(imported)
            self.log(f"✅ 新增 {len(imported)} 个账号,当前总数: {len(self.accounts)}")
            self.refresh_account_tree()
            self.save_config()
        else:
            self.log(f"⚠️ 没有新账号被导入")
        
        return  # 下面的旧代码已删除

    def toggle_account(self, event):
        """双击切换账号选择"""
        selection = self.account_tree.selection()
        if not selection:
            return

        item = selection[0]
        index = self.account_tree.index(item)

        self.accounts[index]["selected"] = not self.accounts[index]["selected"]

        # 复选框:☑ (已选) 或 ☐ (未选)
        check = "☑" if self.accounts[index]["selected"] else "☐"
        values = list(self.account_tree.item(item, "values"))
        values[1] = check  # 第二列是复选框(第一列是序号)
        self.account_tree.item(item, values=tuple(values))

        self.update_account_stats()
        self.update_selected_count()

    def select_all(self):
        """全选账号"""
        for i, account in enumerate(self.accounts):
            account["selected"] = True
            item = self.account_tree.get_children()[i]
            values = list(self.account_tree.item(item, "values"))
            values[1] = "☑"  # 第二列是复选框(第一列是序号)
            self.account_tree.item(item, values=tuple(values))

        self.log("✅ 已全选所有账号")
        self.update_account_stats()
        self.update_selected_count()

    def deselect_all(self):
        """清空选择"""
        for i, account in enumerate(self.accounts):
            account["selected"] = False
            item = self.account_tree.get_children()[i]
            values = list(self.account_tree.item(item, "values"))
            values[1] = "☐"  # 第二列是复选框(第一列是序号)
            self.account_tree.item(item, values=tuple(values))

        self.log("❌ 已清空所有选择")
        self.update_account_stats()
        self.update_selected_count()

    def select_by_range(self):
        """按序号范围选择账号"""
        try:
            start = self.range_from.get()
            end = self.range_to.get()

            if start < 1 or end < 1:
                messagebox.showwarning("范围错误", "序号必须大于0")
                return

            if start > end:
                messagebox.showwarning("范围错误", "起始序号不能大于结束序号")
                return

            if end > len(self.accounts):
                messagebox.showwarning("范围错误", f"结束序号超出范围(最大{len(self.accounts)})")
                return

            # 清空所有选择
            for account in self.accounts:
                account["selected"] = False

            # 选中范围内的账号
            count = 0
            for i in range(start - 1, end):  # 序号从1开始,索引从0开始
                if i < len(self.accounts):
                    self.accounts[i]["selected"] = True
                    count += 1

            # 刷新界面
            self.refresh_account_tree()
            self.log(f"✅ 已选中序号 {start}-{end} 的账号,共 {count} 个")
            self.update_account_stats()
            self.update_selected_count()

        except Exception as e:
            messagebox.showerror("错误", f"选择失败: {e}")

    def select_by_status(self, status_filter):
        """按状态筛选账号"""
        status_map = {
            "free": ["✅ 无限制", "free", ""],
            "frozen": ["🚫 冻结", "frozen"],
            "permanent": ["⚠️ 永久双向限制", "permanent"],
            "temporary": ["⚠️ 临时限制", "temporary"],
            "banned": ["🚫 封禁", "banned"],
            "timeout": ["⚠️ 检测超时"],
            "unchecked": ["", None, "未检测"],
            "unknown": [
                "⚠️ 未知状态",
                "⚠️ 检测失败",
                "⚠️ 重复登录",
                "⚠️ 登录失败",
                "⚠️ 其他错误",
                "⚠️ 无回复",
                "⚠️ 文件不存在",
                "⚠️ 文件损坏",
                "⚠️ 转换失败",
                "⚠️ 转换后仍失败",
                "⚠️ 客户端创建失败",
                "⚠️ 代理超时"
            ]
        }

        if status_filter not in status_map:
            return

        allowed_statuses = status_map[status_filter]

        # 清空所有选择
        for account in self.accounts:
            account["selected"] = False

        # 选中匹配状态的账号
        count = 0
        for account in self.accounts:
            acc_status = account.get("status", "")

            # 处理未检测状态
            if status_filter == "unchecked":
                if not acc_status or acc_status in allowed_statuses:
                    account["selected"] = True
                    count += 1
            # 处理未知/失败状态
            elif status_filter == "unknown":
                if any(status_text in str(acc_status) for status_text in allowed_statuses):
                    account["selected"] = True
                    count += 1
            # 处理检测超时状态
            elif status_filter == "timeout":
                if any(status_text in str(acc_status) for status_text in allowed_statuses):
                    account["selected"] = True
                    count += 1
            # 处理其他状态
            else:
                if acc_status in allowed_statuses:
                    account["selected"] = True
                    count += 1

        # 刷新界面
        self.refresh_account_tree()

        status_names = {
            "free": "无限制",
            "frozen": "冻结",
            "permanent": "永久双向限制",
            "temporary": "临时限制",
            "banned": "封禁",
            "timeout": "检测超时",
            "unchecked": "未检测",
            "unknown": "未知/检测失败"
        }

        self.log(f"✅ 已选中状态为「{status_names[status_filter]}」的账号,共 {count} 个")
        self.update_account_stats()
        self.update_selected_count()

    def on_start_button_click(self):
        """开始按钮点击事件 - 根据当前标签页决定行为"""
        current_tab = self.notebook.index(self.notebook.select())

        if current_tab == 0:
            # 账号管理页面 - 显示菜单
            self.show_main_start_menu(self.start_btn)
        elif current_tab == 1:
            # 私信广告页面 - 直接开始发送
            self.start_messaging()
        elif current_tab == 2:
            # 采集用户页面 - 直接开始采集
            self.start_scraping()

    def show_main_start_menu(self, button):
        """显示主界面开始菜单(仅账号管理页面)"""
        menu = tk.Menu(self.root, tearoff=0, font=("Microsoft YaHei UI", 10))
        menu.add_command(label="检查账号限制", command=self.check_accounts)
        menu.add_separator()
        menu.add_command(label="新功能待开发", state=tk.DISABLED)

        # 在按钮下方显示菜单
        x = button.winfo_rootx()
        y = button.winfo_rooty() + button.winfo_height()
        menu.post(x, y)

    def show_start_menu(self, button):
        """显示开始菜单(账号管理页面)"""
        menu = tk.Menu(self.root, tearoff=0, font=("Microsoft YaHei UI", 10))
        menu.add_command(label="检查账号限制", command=self.check_accounts)
        menu.add_separator()
        menu.add_command(label="新功能待开发", state=tk.DISABLED)

        # 在按钮下方显示菜单
        x = button.winfo_rootx()
        y = button.winfo_rooty() + button.winfo_height()
        menu.post(x, y)

    def show_context_menu(self, event):
        """显示右键菜单"""
        # 获取点击的行
        item = self.account_tree.identify_row(event.y)
        if not item:
            return

        # 选中该行
        self.account_tree.selection_set(item)

        # 获取账号信息
        values = self.account_tree.item(item, "values")
        if len(values) < 3:
            return

        phone = values[2]  # 第三列是手机号
        
        # 查找对应的账号对象
        account = None
        for acc in self.accounts:
            if acc.get("phone") == phone:
                account = acc
                break

        # 创建菜单
        menu = tk.Menu(self.root, tearoff=0, font=("Microsoft YaHei UI", 10))
        menu.add_command(label=f"📋 复制手机号: {phone}",
                        command=lambda: self.copy_to_clipboard(phone))
        
        # 添加Web登录选项
        if account:
            menu.add_separator()
            menu.add_command(label="🌐 登录Web版", 
                            command=lambda: self.login_telegram_web(account))

        # 显示菜单
        menu.post(event.x_root, event.y_root)

    def copy_to_clipboard(self, text):
        """复制文本到剪贴板"""
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.log(f"📋 已复制到剪贴板: {text}")

    def show_delete_menu(self, button):
        """显示删除菜单"""
        menu = tk.Menu(self.root, tearoff=0, font=("Microsoft YaHei UI", 10))
        menu.add_command(label="删除选择的账号", command=self.delete_selected)
        menu.add_command(label="删除全部账号", command=self.delete_all)
        menu.add_separator()
        menu.add_command(label="删除重复登录账号", command=self.delete_invalid)
        menu.add_command(label="删除冻结账号", command=self.delete_frozen)
        menu.add_command(label="删除封禁账号", command=self.delete_banned)

        # 在按钮下方显示菜单
        x = button.winfo_rootx()
        y = button.winfo_rooty() + button.winfo_height()
        menu.post(x, y)

    def show_export_menu(self, button):
        """显示导出菜单"""
        menu = tk.Menu(self.root, tearoff=0, font=("Microsoft YaHei UI", 10))
        menu.add_command(label="导出选择的账号", command=self.export_selected)
        menu.add_command(label="导出全部账号", command=self.export_all)
        menu.add_separator()
        menu.add_command(label="导出失效账号", command=self.export_invalid)
        menu.add_command(label="导出冻结账号", command=self.export_frozen)
        menu.add_command(label="导出封禁账号", command=self.export_banned)
        menu.add_command(label="导出永久双向限制", command=self.export_permanent_limited)
        menu.add_command(label="导出临时限制", command=self.export_temp_limited)

        # 在按钮下方显示菜单
        x = button.winfo_rootx()
        y = button.winfo_rooty() + button.winfo_height()
        menu.post(x, y)

    # ========== 辅助函数 ==========


    def convert_session_file(self, session_file):
        """
        转换 session 文件(移除 tmp_auth_key 列)
        返回: True=成功, False=失败
        """
        import sqlite3
        import shutil

        try:
            # 备份原文件
            backup_file = str(session_file) + ".backup"
            shutil.copy2(session_file, backup_file)

            temp_file = str(session_file) + ".converting"

            # 连接原数据库
            conn_old = sqlite3.connect(session_file)
            cursor_old = conn_old.cursor()

            # 创建新数据库
            conn_new = sqlite3.connect(temp_file)
            cursor_new = conn_new.cursor()

            # 1. 复制 version 表
            cursor_old.execute("SELECT version FROM version")
            version = cursor_old.fetchone()
            if version:
                cursor_new.execute("CREATE TABLE version (version INTEGER PRIMARY KEY)")
                cursor_new.execute("INSERT INTO version VALUES (?)", version)

            # 2. 转换 sessions 表(6列 → 5列)
            cursor_old.execute("SELECT dc_id, server_address, port, auth_key, takeout_id FROM sessions")
            sessions_data = cursor_old.fetchall()

            cursor_new.execute("""
                CREATE TABLE sessions (
                    dc_id INTEGER PRIMARY KEY,
                    server_address TEXT,
                    port INTEGER,
                    auth_key BLOB,
                    takeout_id INTEGER
                )
            """)

            for row in sessions_data:
                cursor_new.execute("INSERT INTO sessions VALUES (?, ?, ?, ?, ?)", row)

            # 3. 复制 entities 表
            cursor_old.execute("SELECT * FROM entities")
            entities_data = cursor_old.fetchall()

            cursor_new.execute("""
                CREATE TABLE entities (
                    id INTEGER PRIMARY KEY,
                    hash INTEGER NOT NULL,
                    username TEXT,
                    phone INTEGER,
                    name TEXT,
                    date INTEGER
                )
            """)

            for row in entities_data:
                cursor_new.execute("INSERT INTO entities VALUES (?, ?, ?, ?, ?, ?)", row)

            # 4. 复制 sent_files 表
            cursor_new.execute("""
                CREATE TABLE sent_files (
                    md5_digest BLOB,
                    file_size INTEGER,
                    type INTEGER,
                    id INTEGER,
                    hash INTEGER,
                    PRIMARY KEY (md5_digest, file_size, type)
                )
            """)

            cursor_old.execute("SELECT * FROM sent_files")
            sent_files_data = cursor_old.fetchall()

            for row in sent_files_data:
                cursor_new.execute("INSERT INTO sent_files VALUES (?, ?, ?, ?, ?)", row)

            # 5. 复制 update_state 表
            cursor_old.execute("SELECT * FROM update_state")
            update_state_data = cursor_old.fetchall()

            cursor_new.execute("""
                CREATE TABLE update_state (
                    id INTEGER PRIMARY KEY,
                    pts INTEGER,
                    qts INTEGER,
                    date INTEGER,
                    seq INTEGER
                )
            """)

            for row in update_state_data:
                cursor_new.execute("INSERT INTO update_state VALUES (?, ?, ?, ?, ?)", row)

            # 提交并关闭
            conn_new.commit()
            conn_old.close()
            conn_new.close()

            # 替换原文件
            shutil.move(temp_file, session_file)

            return True

        except Exception as e:
            self.log(f"  ❌ 转换失败: {str(e)[:100]}")
            # 清理临时文件
            if Path(temp_file).exists():
                Path(temp_file).unlink()
            return False

    def translate_to_english(self, text):
        """将任意语言翻译成英文"""
        try:
            from deep_translator import GoogleTranslator
            translator = GoogleTranslator(source='auto', target='en')
            return translator.translate(text)
        except Exception as e:
            self.log(f"  ⚠️ 翻译失败: {str(e)}")
            return text  # 翻译失败返回原文

    def parse_limitation_time(self, response):
        """解析限制到期时间"""
        import re
        from datetime import datetime

        # 匹配模式: "until DD MMM YYYY, HH:MM UTC"
        pattern = r"(?:until|on|до)\s+(\d{1,2})\s+([A-Za-z]+|[а-я]+)\s+(\d{4})(?:,?\s+г\.?)?"
        match = re.search(pattern, response, re.IGNORECASE)

        if match:
            day, month_str, year = match.groups()[:3]

            # 月份映射(英文和俄文)
            months = {
                # 英文
                'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4,
                'may': 5, 'jun': 6, 'jul': 7, 'aug': 8,
                'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12,
                # 俄文
                'января': 1, 'февраля': 2, 'марта': 3, 'апреля': 4,
                'мая': 5, 'июня': 6, 'июля': 7, 'августа': 8,
                'сентября': 9, 'октября': 10, 'ноября': 11, 'декабря': 12,
            }

            month = months.get(month_str[:3].lower(), None)
            if not month:
                return None

            try:
                # 构造时间对象
                release_time = datetime(int(year), month, int(day))
                return release_time
            except:
                return None

        return None

    # ========== 账号检测功能 ==========

    def check_accounts(self):
        """检测账号状态"""
        if not self.accounts:
            messagebox.showwarning("提示", "请先导入账号")
            return

        # 获取选中的账号
        selected_accounts = [acc for acc in self.accounts if acc["selected"]]
        if not selected_accounts:
            messagebox.showwarning("提示", "请先选择要检测的账号")
            return

        # 重置停止标志
        self.stop_flag = False
        self.is_running = True

        # 获取并发配置
        concurrent = self.check_concurrent.get()
        self.log(f"🔍 开始检测账号状态... (选中 {len(selected_accounts)} 个账号,并发: {concurrent})")

        # 禁用所有操作按钮
        self.stop_btn.config(state=tk.NORMAL)
        self.start_btn.config(state=tk.DISABLED)

        thread = threading.Thread(target=self.run_check_accounts, args=(selected_accounts,))
        thread.start()

    def run_check_accounts(self, accounts):
        """运行账号检测"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self.check_accounts_async(accounts))
        finally:
            # 恢复按钮状态
            self.is_running = False
            self.root.after(0, lambda: self.stop_btn.config(state=tk.DISABLED))
            self.root.after(0, lambda: self.start_btn.config(state=tk.NORMAL))

    async def check_single_account(self, account, index, total):
        """检测单个账号(并发调用)"""
        # 检查停止标志
        if self.stop_flag:
            return

        # SpamBot 关键词库(多语言,不翻译)

        # 1. 正常状态(多语言)
        NORMAL_KEYWORDS = [
            # 英文
            "good news", "no limits", "free as a bird", "no restrictions", "all good",
            # 俄语
            "свободен от каких-либо ограничений", "свободен", "ограничений",
            # 葡萄牙语
            "nenhum limite", "livre como",
            # 西班牙语
            "buenas noticias", "no existen limitaciones", "libre como un pájaro",
            # 阿拉伯语
            "رائع", "لاتوجد قيود", "أنت حر طليق",
        ]

        # 2. 地理受限
        GEO_RESTRICTED_KEYWORDS = [
            "phone numbers may trigger",
            "some phone numbers may trigger",
        ]

        # 3. 冻结(包含所有冻结相关的关键词)
        FROZEN_KEYWORDS = [
            # 英文
            "frozen", "account is frozen", "blocked for violations", "terms of service", "user reports confirmed",
            # 俄语
            "заморожен", "аккаунт заморожен",
        ]

        # 4. 永久双向限制
        PERMANENT_LIMITED_KEYWORDS = [
            "some actions can trigger",
            "your account was limited",
            "while the account is limited",
        ]

        # 5. 临时限制(多语言)
        TEMP_LIMITED_KEYWORDS = [
            # 英文
            "limited until", "automatically released on", "account is now limited",
            # 俄语
            "ограничен до", "до",
        ]

        # 提取手机号用于日志
        phone_number = Path(account['path']).stem

        # 格式:[序号/总数] 手机号 - 状态
        log_prefix = f"[{index+1}/{total}]"

        try:
            # 获取并规范化路径
            path = str(Path(account["path"]).resolve())

            # self.log(f"  🔍 规范化路径: {path}")  # 调试日志已隐藏

            # 检查文件是否存在
            if not Path(path).exists():
                self.log(f"{log_prefix} {phone_number} - ❌ 文件不存在")
                account["status"] = "⚠️ 文件不存在"
                self.root.after(0, self.refresh_account_tree)
                return

            # 检查文件大小
            file_size = Path(path).stat().st_size
            # self.log(f"  📏 文件大小: {file_size} bytes")  # 调试日志已隐藏

            if file_size < 1000:
                self.log(f"{log_prefix} {phone_number} - ❌ 文件损坏")
                account["status"] = "⚠️ 文件损坏"
                self.root.after(0, self.refresh_account_tree)
                return

            # self.log(f"  ✅ 开始创建客户端...")  # 调试日志已隐藏

            # 创建 TelegramClient(可能失败)
            # 获取可用代理
            proxy_config = None
            connection_type = None
            proxy_retry_count = 0
            max_proxy_retries = 3
            proxy_used = None  # 记录使用的代理

            while proxy_retry_count < max_proxy_retries:
                try:
                    # 如果有可用代理,随机选择一个(不需要选中状态)
                    available_proxies = [p for p in self.proxies if p["status"] == "可用"]
                    if available_proxies:
                        import random
                        proxy = random.choice(available_proxies)
                        proxy_config, connection_type = self.parse_proxy_for_telethon(proxy["proxy"])
                        proxy_used = proxy["proxy"]  # 记录使用的代理
                        # 打码显示代理信息
                        proxy_masked = self.mask_proxy(proxy["proxy"])
                        self.log(f"{log_prefix} {phone_number} - 🌐 使用代理: {proxy_masked}")
                    else:
                        proxy_used = None  # 没有可用代理
                        if self.proxies:
                            # 有代理但都不可用
                            total_proxies = len(self.proxies)
                            available_count = sum(1 for p in self.proxies if p["status"] == "可用")
                            unchecked_count = sum(1 for p in self.proxies if p["status"] == "未检测")
                            self.log(f"{log_prefix} {phone_number} - ⚠️ 无可用代理(总计:{total_proxies} 可用:{available_count} 未检测:{unchecked_count})")

                    # 创建客户端(带或不带代理)
                    if proxy_config:
                        if connection_type:
                            # HTTP 代理需要指定连接类型
                            client = TelegramClient(path, self.api_id, self.api_hash,
                                                  proxy=proxy_config,
                                                  connection=connection_type)
                        else:
                            # SOCKS 代理使用默认连接类型
                            client = TelegramClient(path, self.api_id, self.api_hash, proxy=proxy_config)
                    else:
                        client = TelegramClient(path, self.api_id, self.api_hash)

                    # 设置异常处理器,抑制 AuthKeyDuplicatedError 堆栈
                    def suppress_auth_error(loop, context):
                        exception = context.get('exception')
                        if exception and 'AuthKeyDuplicatedError' not in str(exception):
                            loop.default_exception_handler(context)

                    try:
                        loop = asyncio.get_running_loop()
                        loop.set_exception_handler(suppress_auth_error)
                    except RuntimeError:
                        pass

                    # 尝试连接(会触发代理超时)
                    await client.connect()
                    break  # 连接成功,跳出重试循环

                except ValueError as ve:
                    # Session 文件格式错误
                    if self.convert_session_file(path):
                        try:
                            if proxy_config:
                                if connection_type:
                                    client = TelegramClient(path, self.api_id, self.api_hash,
                                                          proxy=proxy_config,
                                                          connection=connection_type)
                                else:
                                    client = TelegramClient(path, self.api_id, self.api_hash, proxy=proxy_config)
                            else:
                                client = TelegramClient(path, self.api_id, self.api_hash)

                            # 设置异常处理器
                            def suppress_auth_error(loop, context):
                                exception = context.get('exception')
                                if exception and 'AuthKeyDuplicatedError' not in str(exception):
                                    loop.default_exception_handler(context)
                            try:
                                loop = asyncio.get_running_loop()
                                loop.set_exception_handler(suppress_auth_error)
                            except RuntimeError:
                                pass

                            await client.connect()
                            break
                        except Exception as retry_error:
                            account["status"] = "⚠️ 转换后仍失败"
                            account["username"] = "-"
                            account["phone"] = "-"
                            self.log(f"{log_prefix} {phone_number} - ❌ 转换失败")
                            self.root.after(0, self.refresh_account_tree)
                            return
                    else:
                        account["status"] = "⚠️ 转换失败"
                        account["username"] = "-"
                        account["phone"] = "-"
                        self.log(f"{log_prefix} {phone_number} - ❌ 转换失败")
                        self.root.after(0, self.refresh_account_tree)
                        return

                except Exception as proxy_error:
                    error_str = str(proxy_error).lower()
                    error_type = type(proxy_error).__name__.lower()

                    # 检测 AuthKeyDuplicatedError,直接跳过不重试
                    if "authkey" in error_type and "duplicated" in error_type:
                        account["status"] = "⚠️ 重复登录"
                        account["username"] = "-"
                        account["first_name"] = "-"
                        account["proxy_used"] = proxy_used if proxy_used else ""
                        self.log(f"{log_prefix} {phone_number} - ⚠️ 账号多IP登录(Session在其他地方使用中)")
                        self.root.after(0, self.refresh_account_tree)
                        return  # 直接返回,不重试

                    # 检测代理超时或连接错误
                    if "timeout" in error_str or "connection" in error_str or "proxy" in error_str:
                        proxy_retry_count += 1
                        if proxy_retry_count < max_proxy_retries:
                            self.log(f"{log_prefix} {phone_number} - ⚠️ 代理超时,重试 {proxy_retry_count}/{max_proxy_retries}")
                            proxy_config = None  # 清除当前代理,下次循环会选择新的
                            continue
                        else:
                            self.log(f"{log_prefix} {phone_number} - ❌ 代理连接失败(已重试3次)")
                            account["status"] = "⚠️ 代理超时"
                            self.root.after(0, self.refresh_account_tree)
                            return
                    else:
                        # 其他错误
                        raise

            # if 'client' not in locals():
            #     self.log(f"  ✅ 客户端创建成功")  # 调试日志已隐藏

            # 连接已在上面完成,不需要再次连接

            # 1. 尝试登录
            try:
                me = await client.get_me()
                if not me:
                    account["status"] = "🚫 封禁"
                    account["username"] = "-"
                    # 保留原始手机号,不要设置为 "-"
                    # account["phone"] = "-"
                    account["first_name"] = "-"
                    self.log(f"{log_prefix} {phone_number} - 🚫 封禁")
                    await client.disconnect()
                    self.root.after(0, self.refresh_account_tree)
                    return

                # 更新账号信息(从 Telegram 读取)
                account["username"] = f"@{me.username}" if me.username else "-"
                account["phone"] = me.phone or "-"

                # 更新姓名(first_name + last_name)
                first_name = me.first_name or ""
                last_name = me.last_name or ""
                if first_name:
                    full_name = f"{first_name} {last_name}".strip() if last_name else first_name
                    account["first_name"] = full_name
                else:
                    account["first_name"] = "-"

                # 记录使用的代理
                account["proxy_used"] = proxy_used if proxy_used else ""

            except Exception as e:
                error_type = type(e).__name__
                error_str = str(e).lower()

                # OperationalError: database is locked - SQLite并发冲突
                if error_type == "OperationalError" and "database is locked" in error_str:
                    account["status"] = "⚠️ 数据库锁定"
                    account["username"] = "-"
                    account["first_name"] = "-"
                    self.log(f"{log_prefix} {phone_number} - ⚠️ 数据库锁定(并发检测冲突,请降低并发数)")
                    self.root.after(0, self.refresh_account_tree)
                    return

                # AuthKeyDuplicatedError - 重复登录
                if "authkey" in error_type.lower() and "duplicated" in error_type.lower():
                    account["status"] = "⚠️ 重复登录"
                    account["username"] = "-"
                    # 保留原始手机号
                    # account["phone"] = "-"
                    account["first_name"] = "-"
                    self.log(f"{log_prefix} {phone_number} - ⚠️ 账号多IP登录(Session在其他地方使用中)")
                    await client.disconnect()
                    self.root.after(0, self.refresh_account_tree)
                    return

                if "authkey" in error_str or "unauthorized" in error_str or "banned" in error_str:
                    account["status"] = "🚫 封禁"
                    account["username"] = "-"
                    # 保留原始手机号
                    # account["phone"] = "-"
                    account["first_name"] = "-"
                    self.log(f"{log_prefix} {phone_number} - 🚫 封禁")
                elif "timeout" in error_str or "connection" in error_str or "network" in error_str:
                    account["status"] = "⚠️ 连接错误"
                    account["username"] = "-"
                    # 保留原始手机号
                    # account["phone"] = "-"
                    account["first_name"] = "-"
                    self.log(f"{log_prefix} {phone_number} - ⚠️ 连接错误")
                else:
                    account["status"] = "🚫 封禁"
                    account["username"] = "-"
                    # 保留原始手机号
                    # account["phone"] = "-"
                    account["first_name"] = "-"
                    self.log(f"{log_prefix} {phone_number} - 🚫 封禁")

                await client.disconnect()
                self.root.after(0, self.refresh_account_tree)
                return

            # 2. 向 @spambot 发送消息检测状态
            try:
                # 检查停止标志
                if self.stop_flag:
                    await client.disconnect()
                    return
                
                await client.send_message("@spambot", "/start")
                await asyncio.sleep(2)

                # 检查停止标志
                if self.stop_flag:
                    await client.disconnect()
                    return

                messages = await client.get_messages("@spambot", limit=1)

                if messages and len(messages) > 0:
                    response = (messages[0].message or "").strip().lower()

                    # 优先级判断(多语言关键词,不翻译)
                    # 1. 地理受限
                    if any(keyword in response for keyword in GEO_RESTRICTED_KEYWORDS):
                        account["status"] = "✅ 无限制(地理受限)"
                        self.log(f"{log_prefix} {phone_number} - ✅ 无限制(地理受限)")
                        self.root.after(0, self.refresh_account_tree)

                    # 2. 冻结(包含所有冻结场景)
                    elif any(keyword in response for keyword in FROZEN_KEYWORDS):
                        appeal_time = self.parse_limitation_time(response)
                        if appeal_time:
                            time_str = appeal_time.strftime("%Y-%m-%d")
                            account["status"] = f"🚫 冻结(申诉至 {time_str})"
                            self.log(f"{log_prefix} {phone_number} - 🚫 冻结(申诉至 {time_str})")
                        else:
                            account["status"] = "🚫 冻结"
                            self.log(f"{log_prefix} {phone_number} - 🚫 冻结")
                        # 显示 SpamBot 原始回复(调试用)
                        self.log(f"      SpamBot 回复: {response[:200]}")
                        self.root.after(0, self.refresh_account_tree)

                    # 3. 永久双向限制
                    elif any(keyword in response for keyword in PERMANENT_LIMITED_KEYWORDS):
                        account["status"] = "⚠️ 永久双向限制"
                        self.log(f"{log_prefix} {phone_number} - ⚠️ 永久双向限制")
                        self.root.after(0, self.refresh_account_tree)

                    # 4. 临时限制(有到期时间)
                    elif any(keyword in response for keyword in TEMP_LIMITED_KEYWORDS):
                        release_time = self.parse_limitation_time(response)
                        if release_time:
                            now = datetime.utcnow()
                            remaining = release_time - now
                            if remaining.total_seconds() > 0:
                                days = remaining.days
                                hours = remaining.seconds // 3600
                                account["status"] = f"⚠️ 临时限制(剩余 {days}天{hours}时)"
                                self.log(f"{log_prefix} {phone_number} - ⚠️ 临时限制(剩余 {days}天{hours}时)")
                            else:
                                account["status"] = "⚠️ 临时限制(已过期)"
                                self.log(f"{log_prefix} {phone_number} - ⚠️ 临时限制(已过期)")
                        else:
                            account["status"] = "⚠️ 临时垃圾邮件"
                            self.log(f"{log_prefix} {phone_number} - ⚠️ 临时垃圾邮件")
                        self.root.after(0, self.refresh_account_tree)

                    # 5. 无限制
                    elif any(keyword in response for keyword in NORMAL_KEYWORDS):
                        account["status"] = "✅ 无限制"
                        self.log(f"{log_prefix} {phone_number} - ✅ 无限制")
                        self.root.after(0, self.refresh_account_tree)

                    # 6. 未知
                    else:
                        account["status"] = "⚠️ 未知状态"
                        self.log(f"{log_prefix} {phone_number} - ⚠️ 未知状态")
                        # 显示 SpamBot 原始回复(调试用)
                        self.log(f"      SpamBot 回复: {response[:200]}")
                        self.root.after(0, self.refresh_account_tree)

                    self.root.after(0, self.refresh_account_tree)
                else:
                    account["status"] = "⚠️ 无回复"
                    self.log(f"{log_prefix} {phone_number} - ⚠️ 无回复")
                    self.root.after(0, self.refresh_account_tree)

            except Exception as e:
                error_type = type(e).__name__
                error_str = str(e).lower()

                # AuthKeyDuplicatedError - 重复登录,直接标记并返回
                if "authkey" in error_type.lower() and "duplicated" in error_type.lower():
                    account["status"] = "⚠️ 重复登录"
                    self.log(f"{log_prefix} {phone_number} - ⚠️ 重复登录")
                    self.root.after(0, self.refresh_account_tree)
                    # 不再尝试取消拉黑,直接断开连接并返回
                    try:
                        await client.disconnect()
                    except:
                        pass
                    return

                # YouBlockedUserError - 拉黑了 SpamBot,尝试自动取消拉黑
                if "youblocked" in error_type.lower():
                    # self.log(f"  ⚠️ 已拉黑 SpamBot,自动取消拉黑中...")  # 调试日志已隐藏

                    try:
                        # 取消拉黑 @spambot(使用正确的API)
                        from telethon.tl.functions.contacts import UnblockRequest
                        from telethon.tl.types import InputUser

                        # 先获取 SpamBot 的信息
                        spambot = await client.get_entity("@spambot")

                        # 创建 InputUser 对象
                        input_user = InputUser(user_id=spambot.id, access_hash=spambot.access_hash)

                        # 调用取消拉黑API
                        await client(UnblockRequest(id=input_user))

                        # self.log(f"  ✅ 已取消拉黑 SpamBot")  # 调试日志已隐藏
                        await asyncio.sleep(1)

                        # 重试检测
                        # self.log(f"  🔄 重新检测...")  # 调试日志已隐藏
                        await client.send_message("@spambot", "/start")
                        await asyncio.sleep(2)

                        messages = await client.get_messages("@spambot", limit=1)

                        if messages and len(messages) > 0:
                            response = (messages[0].message or "").strip().lower()

                            # 重新判断状态(使用相同的逻辑)
                            if any(keyword in response for keyword in GEO_RESTRICTED_KEYWORDS):
                                account["status"] = "✅ 无限制(地理受限)"
                                self.log(f"{log_prefix} {phone_number} - ✅ 无限制(地理受限)")
                            elif any(keyword in response for keyword in FROZEN_KEYWORDS):
                                account["status"] = "🚫 冻结"
                                self.log(f"{log_prefix} {phone_number} - 🚫 冻结")
                            elif any(keyword in response for keyword in PERMANENT_LIMITED_KEYWORDS):
                                account["status"] = "⚠️ 永久双向限制"
                                self.log(f"{log_prefix} {phone_number} - ⚠️ 永久双向限制")
                            elif any(keyword in response for keyword in TEMP_LIMITED_KEYWORDS):
                                account["status"] = "⚠️ 临时限制"
                                self.log(f"{log_prefix} {phone_number} - ⚠️ 临时限制")
                            elif any(keyword in response for keyword in NORMAL_KEYWORDS):
                                account["status"] = "✅ 无限制"
                                self.log(f"{log_prefix} {phone_number} - ✅ 无限制")
                            else:
                                account["status"] = "⚠️ 未知状态"
                                self.log(f"{log_prefix} {phone_number} - ⚠️ 未知状态")
                        else:
                            account["status"] = "⚠️ 无回复"
                            self.log(f"{log_prefix} {phone_number} - ⚠️ 无回复")

                    except Exception as retry_error:
                        account["status"] = "⚠️ 取消拉黑失败"
                        self.log(f"{log_prefix} {phone_number} - ❌ 取消拉黑失败")

                # 其他错误
                else:
                    account["status"] = f"⚠️ 检测失败"
                    self.log(f"{log_prefix} {phone_number} - ⚠️ 检测失败")

                self.root.after(0, self.refresh_account_tree)

            account["last_login"] = datetime.now().strftime("%Y-%m-%d %H:%M")

            # 更新 JSON 文件(保存最新信息)
            try:
                session_path = Path(account["path"])
                json_file = session_path.parent / f"{session_path.stem}.json"

                if json_file.exists():
                    import json
                    with open(json_file, 'r', encoding='utf-8') as f:
                        json_data = json.load(f)

                    # 更新姓名
                    if account["first_name"] and account["first_name"] != "-":
                        # 分离 first_name 和 last_name
                        parts = account["first_name"].split(' ', 1)
                        json_data["first_name"] = parts[0]
                        json_data["last_name"] = parts[1] if len(parts) > 1 else None

                    # 更新用户名
                    if account["username"] and account["username"] != "-":
                        json_data["username"] = account["username"].lstrip('@')

                    # 更新手机号
                    if account["phone"] and account["phone"] != "-":
                        json_data["phone"] = account["phone"]

                    # 不保存代理信息到 JSON 文件（隐私保护）
                    # 代理信息只在程序内存中使用
                    # 移除 proxy 字段（如果存在）
                    if "proxy" in json_data:
                        del json_data["proxy"]

                    # 更新状态(映射到 spamblock 字段)
                    status = account.get("status", "")
                    if "无限制" in status:
                        json_data["spamblock"] = "free"
                    elif "永久" in status or "双向限制" in status:
                        json_data["spamblock"] = "permanent"
                    elif "临时" in status:
                        json_data["spamblock"] = "temporary"
                    elif "冻结" in status:
                        json_data["spamblock"] = "frozen"
                    elif "封禁" in status:
                        json_data["spamblock"] = "banned"
                    else:
                        json_data["spamblock"] = None

                    # 保存
                    with open(json_file, 'w', encoding='utf-8') as f:
                        json.dump(json_data, f, indent=2, ensure_ascii=False)
            except:
                pass  # 忽略 JSON 保存错误

            # 确保断开连接并释放文件锁
            try:
                if client.is_connected():
                    await client.disconnect()
                # 等待一小段时间让文件锁完全释放
                await asyncio.sleep(0.1)
            except:
                pass  # 忽略断开连接时的错误

        except Exception as e:
            account["status"] = "⚠️ 检测失败"
            self.log(f"  ⚠️ 检测失败: {type(e).__name__}")
            self.log(f"     错误: {str(e)[:100]}")
            import traceback
            self.log(f"     追踪: {traceback.format_exc()[:200]}")
            self.root.after(0, self.refresh_account_tree)

            # 确保断开连接并释放文件锁
            try:
                if 'client' in locals() and client.is_connected():
                    await client.disconnect()
                # 等待一小段时间让文件锁完全释放
                await asyncio.sleep(0.1)
            except:
                pass  # 忽略断开连接时的错误

    async def check_accounts_async(self, accounts):
        """并发批量检测账号"""
        concurrent = self.check_concurrent.get()  # 并发数量
        batch_delay = self.check_batch_delay.get()  # 批次间隔
        total = len(accounts)

        self.log(f"📊 并发配置: 每批 {concurrent} 个账号,批次间隔 {batch_delay} 秒")

        # 分批处理
        for i in range(0, total, concurrent):
            # 检查是否停止
            if self.stop_flag:
                self.log("⏸️ 检测已停止")
                break

            batch = accounts[i:i+concurrent]
            batch_num = i // concurrent + 1
            total_batches = (total + concurrent - 1) // concurrent

            self.log(f"🔄 批次 {batch_num}/{total_batches}: 检测 {len(batch)} 个账号...")

            # 并发检测一批（每个账号带超时保护）
            async def check_with_timeout(acc, idx, total):
                try:
                    # 定期检查停止标志
                    async def check_cancelable():
                        while True:
                            if self.stop_flag:
                                raise asyncio.CancelledError("用户停止")
                            await asyncio.sleep(0.1)
                    
                    # 同时运行检测和停止检查
                    check_task = asyncio.create_task(self.check_single_account(acc, idx, total))
                    cancel_task = asyncio.create_task(check_cancelable())
                    
                    done, pending = await asyncio.wait(
                        [check_task, cancel_task],
                        timeout=10,  # 超时时间：10秒
                        return_when=asyncio.FIRST_COMPLETED
                    )
                    
                    # 取消未完成的任务
                    for task in pending:
                        task.cancel()
                    
                    # 检查结果
                    if check_task.done() and not check_task.cancelled():
                        # 正常完成
                        pass
                    elif self.stop_flag:
                        # 用户停止
                        phone_number = Path(acc['path']).stem
                        self.log(f"⏸️ [{idx+1}/{total}] {phone_number} - 检测已停止")
                    else:
                        # 超时
                        phone_number = Path(acc['path']).stem
                        acc["status"] = "⚠️ 检测超时"
                        self.log(f"⏱️ [{idx+1}/{total}] {phone_number} - ⚠️ 检测超时（超过 10 秒，跳过）")
                        self.root.after(0, self.refresh_account_tree)
                        
                except asyncio.CancelledError:
                    phone_number = Path(acc['path']).stem
                    self.log(f"⏸️ [{idx+1}/{total}] {phone_number} - 检测已取消")
                except Exception as e:
                    phone_number = Path(acc['path']).stem
                    acc["status"] = "⚠️ 检测异常"
                    self.log(f"❌ [{idx+1}/{total}] {phone_number} - ⚠️ 检测异常: {type(e).__name__}")
                    self.root.after(0, self.refresh_account_tree)
            
            tasks = [check_with_timeout(acc, i+j, total) for j, acc in enumerate(batch)]
            await asyncio.gather(*tasks, return_exceptions=True)

            # 检查停止标志（批次完成后）
            if self.stop_flag:
                self.log("⏸️ 检测已停止")
                break

            # 批次间隔
            if i + concurrent < total:
                self.log(f"⏳ 等待 {batch_delay} 秒后继续下一批...")
                # 分段等待，每秒检查停止标志
                for _ in range(batch_delay):
                    if self.stop_flag:
                        self.log("⏸️ 检测已停止")
                        break
                    await asyncio.sleep(1)
                
                # 再次检查停止标志
                if self.stop_flag:
                    break

        if not self.stop_flag:
            self.log("✅ 账号检测完成")

        # 统计各状态数量(只统计本次检测的账号)
        normal_count = sum(1 for acc in accounts if "✅ 无限制" in acc["status"])
        limited_count = sum(1 for acc in accounts if "⚠️ 永久双向限制" in acc["status"])
        frozen_count = sum(1 for acc in accounts if "🚫 冻结" in acc["status"])
        banned_count = sum(1 for acc in accounts if "🚫 封禁" in acc["status"])
        temp_limited_count = sum(1 for acc in accounts if "⚠️ 临时限制" in acc["status"])
        other_count = total - normal_count - limited_count - frozen_count - banned_count - temp_limited_count

        self.log("=" * 50)
        self.log("📊 检测结果统计:")
        self.log(f"  ✅ 无限制: {normal_count} 个")
        self.log(f"  ⚠️ 永久双向限制: {limited_count} 个")
        self.log(f"  🚫 冻结: {frozen_count} 个")
        self.log(f"  🚫 封禁: {banned_count} 个")
        self.log(f"  ⚠️ 临时限制: {temp_limited_count} 个")
        if other_count > 0:
            self.log(f"  ⚠️ 其他: {other_count} 个")
        self.log(f"  📝 总计: {total} 个")
        self.log("=" * 50)

        self.root.after(0, self.update_account_stats)

        # 等待所有客户端断开连接并释放文件锁
        self.log("⏳ 等待所有连接断开并释放文件...")
        await asyncio.sleep(5)  # 增加到 5 秒

        # 清理所有异步任务
        await self.cleanup_async_tasks()

    async def cleanup_async_tasks(self):
        """清理所有异步任务,确保程序可以停止"""
        try:
            # 获取当前任务
            current_task = asyncio.current_task()
            
            # 获取所有未完成的任务（排除当前任务）
            tasks = [task for task in asyncio.all_tasks() 
                    if not task.done() and task is not current_task]
            
            if tasks:
                self.log(f"🧹 清理 {len(tasks)} 个后台任务...")
                # 取消所有任务
                for task in tasks:
                    task.cancel()
                
                # 等待所有任务完成或被取消（忽略错误）
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # 统计结果
                cancelled = sum(1 for r in results if isinstance(r, asyncio.CancelledError))
                self.log(f"✅ 后台任务已清理（取消 {cancelled} 个）")
            else:
                self.log("✅ 没有后台任务需要清理")
        except Exception as e:
            # 忽略清理错误
            self.log(f"⚠️ 清理任务时出错: {e}")

    def delete_invalid(self):
        """删除重复登录账号(同步删除文件)"""
        # 检查是否正在检测
        if self.is_running:
            messagebox.showwarning("提示", "正在检测账号，无法删除！请先停止检测")
            return
        
        self._delete_by_status("重复登录", ["重复登录"])

    def delete_selected(self):
        """删除选择的账号"""
        # 检查是否正在检测
        if self.is_running:
            messagebox.showwarning("提示", "正在检测账号，无法删除！请先停止检测")
            return
        
        selected_accounts = [acc for acc in self.accounts if acc["selected"]]

        if not selected_accounts:
            messagebox.showinfo("提示", "没有选择任何账号")
            return

        confirm = messagebox.askyesno("确认删除",
            f"确定要删除 {len(selected_accounts)} 个选择的账号吗?\n"
            f"(同时删除文件)")
        if not confirm:
            return

        # 强制垃圾回收，释放文件句柄
        import gc
        gc.collect()
        
        # 等待文件锁释放
        import time
        time.sleep(1)

        deleted_count = 0
        for acc in selected_accounts:
            if self._delete_account_files(acc):
                deleted_count += 1

        self.accounts = [acc for acc in self.accounts if not acc["selected"]]

        self.log(f"🗑️ 已删除 {deleted_count} 个选择的账号(含文件)")
        self.refresh_account_tree()
        self.save_config()

    def delete_all(self):
        """删除全部账号"""
        if not self.accounts:
            messagebox.showinfo("提示", "没有账号")
            return

        confirm = messagebox.askyesno("⚠️ 危险操作",
            f"确定要删除全部 {len(self.accounts)} 个账号吗?\n"
            f"(同时删除文件)\n\n"
            f"此操作不可恢复!")
        if not confirm:
            return

        deleted_count = 0
        for acc in self.accounts:
            if self._delete_account_files(acc):
                deleted_count += 1

        self.accounts = []

        self.log(f"🗑️ 已删除全部 {deleted_count} 个账号(含文件)")
        self.refresh_account_tree()
        self.save_config()

    def delete_frozen(self):
        """删除冻结账号"""
        self._delete_by_status("冻结", ["🚫 冻结"])

    def delete_banned(self):
        """删除封禁账号"""
        self._delete_by_status("封禁", ["🚫 封禁"])

    def _delete_by_status(self, status_name, status_keywords):
        """通用删除函数"""
        target_accounts = [acc for acc in self.accounts
                          if any(keyword in acc["status"] for keyword in status_keywords)]

        if not target_accounts:
            messagebox.showinfo("提示", f"没有{status_name}账号")
            return

        confirm = messagebox.askyesno("确认删除",
            f"确定要删除 {len(target_accounts)} 个{status_name}账号吗?\n"
            f"(同时删除文件)")
        if not confirm:
            return

        deleted_count = 0
        for acc in target_accounts:
            if self._delete_account_files(acc):
                deleted_count += 1

        self.accounts = [acc for acc in self.accounts
                        if not any(keyword in acc["status"] for keyword in status_keywords)]

        self.log(f"🗑️ 已删除 {deleted_count} 个{status_name}账号(含文件)")
        self.refresh_account_tree()
        self.save_config()

    def _delete_account_files(self, acc):
        """删除账号文件"""
        try:
            session_path = Path(acc["path"])

            # 删除 session 文件
            if session_path.exists():
                os.remove(session_path)

            # 删除 session-journal 文件(如果存在)
            journal_path = session_path.with_suffix('.session-journal')
            if journal_path.exists():
                os.remove(journal_path)

            # 删除 json 文件(如果存在)
            # 123.session → 123.json(不是 123.session.json)
            json_path = session_path.parent / f"{session_path.stem}.json"
            if json_path.exists():
                os.remove(json_path)

            self.log(f"  🗑️ 已删除: {session_path.name}")
            return True
        except Exception as e:
            self.log(f"  ⚠️ 删除失败: {session_path.name} - {str(e)}")
            return False

    # ========== 导出功能 ==========

    def export_selected(self):
        """导出选择的账号"""
        selected_accounts = [acc for acc in self.accounts if acc["selected"]]
        self._export_accounts(selected_accounts, "选择的账号")

    def export_all(self):
        """导出全部账号"""
        self._export_accounts(self.accounts, "全部账号")

    def export_invalid(self):
        """导出失效账号"""
        invalid_accounts = [acc for acc in self.accounts if "❌" in acc["status"]]
        self._export_accounts(invalid_accounts, "失效账号")

    def export_frozen(self):
        """导出冻结账号"""
        frozen_accounts = [acc for acc in self.accounts if "🚫 冻结" in acc["status"]]
        self._export_accounts(frozen_accounts, "冻结账号")

    def export_banned(self):
        """导出封禁账号"""
        banned_accounts = [acc for acc in self.accounts if "🚫 封禁" in acc["status"]]
        self._export_accounts(banned_accounts, "封禁账号")

    def export_permanent_limited(self):
        """导出永久双向限制账号"""
        permanent_accounts = [acc for acc in self.accounts if "永久双向限制" in acc["status"]]
        self._export_and_remove_accounts(permanent_accounts, "永久双向限制账号")

    def export_temp_limited(self):
        """导出临时限制账号"""
        temp_accounts = [acc for acc in self.accounts if "临时限制" in acc["status"] or "临时垃圾邮件" in acc["status"]]
        self._export_and_remove_accounts(temp_accounts, "临时限制账号")

    def _export_and_remove_accounts(self, accounts, export_name):
        """导出账号并从程序中删除(移动文件)"""
        if not accounts:
            messagebox.showinfo("提示", f"没有{export_name}")
            return

        # 选择导出文件夹
        export_folder = filedialog.askdirectory(title=f"选择导出文件夹({export_name})")
        if not export_folder:
            return

        export_path = Path(export_folder)
        exported_count = 0
        removed_accounts = []

        for acc in accounts:
            try:
                import shutil
                session_path = Path(acc["path"])

                # 移动 session 文件
                if session_path.exists():
                    dest_session = export_path / session_path.name
                    shutil.move(str(session_path), str(dest_session))
                    exported_count += 1

                    # 移动对应的 JSON 文件
                    json_file = session_path.parent / f"{session_path.stem}.json"
                    if json_file.exists():
                        dest_json = export_path / json_file.name
                        shutil.move(str(json_file), str(dest_json))

                    # 标记为待删除
                    removed_accounts.append(acc)

            except Exception as e:
                self.log(f"❌ 导出失败: {session_path.name} - {str(e)}")

        # 从账号列表中删除
        for acc in removed_accounts:
            self.accounts.remove(acc)

        self.log(f"✅ 导出 {exported_count} 个{export_name}到: {export_folder}")
        self.log(f"✅ 已从程序中删除 {len(removed_accounts)} 个账号")
        self.refresh_account_tree()
        self.save_config()
        messagebox.showinfo("导出成功", f"成功导出 {exported_count} 个{export_name}\n并从程序中删除")

    def _export_accounts(self, accounts, export_name):
        """通用导出函数"""
        if not accounts:
            messagebox.showinfo("提示", f"没有{export_name}")
            return

        # 选择导出文件夹
        export_folder = filedialog.askdirectory(title=f"选择导出文件夹({export_name})")
        if not export_folder:
            return

        export_path = Path(export_folder)
        exported_count = 0
        removed_accounts = []

        for acc in accounts:
            try:
                import shutil
                session_path = Path(acc["path"])

                # 移动 session 文件
                if session_path.exists():
                    dest_session = export_path / session_path.name
                    shutil.move(str(session_path), str(dest_session))
                    exported_count += 1

                # 移动 session-journal 文件(如果存在)
                journal_path = session_path.with_suffix('.session-journal')
                if journal_path.exists():
                    dest_journal = export_path / journal_path.name
                    shutil.move(str(journal_path), str(dest_journal))

                # 移动 json 文件(如果存在)
                # 123.session → 123.json(不是 123.session.json)
                json_path = session_path.parent / f"{session_path.stem}.json"
                if json_path.exists():
                    dest_json = export_path / json_path.name
                    shutil.move(str(json_path), str(dest_json))
                    self.log(f"  📤 已导出: {session_path.name} (含JSON)")
                else:
                    self.log(f"  📤 已导出: {session_path.name}")

                # 标记为待删除
                removed_accounts.append(acc)

            except Exception as e:
                self.log(f"  ⚠️ 导出失败: {session_path.name} - {str(e)}")

        # 从账号列表中删除
        for acc in removed_accounts:
            self.accounts.remove(acc)

        self.log(f"📤 导出完成: {exported_count}/{len(accounts)} 个{export_name}")
        self.log(f"✅ 已从程序中删除 {len(removed_accounts)} 个账号")
        self.refresh_account_tree()
        self.save_config()
        messagebox.showinfo("导出完成", f"成功导出 {exported_count} 个账号到:\n{export_folder}\n\n已从程序中删除")

    def update_account_stats(self):
        """更新账号统计"""
        total = len(self.accounts)
        selected = sum(1 for acc in self.accounts if acc["selected"])
        normal = sum(1 for acc in self.accounts if "✅" in acc["status"])
        error = sum(1 for acc in self.accounts if "❌" in acc["status"])
        unchecked = sum(1 for acc in self.accounts if acc["status"] == "未检测")

        self.stats_label.config(
            text=f"📊 统计: 总数 {total} | 已选 {selected} | 正常 {normal} | 异常 {error} | 未检测 {unchecked}"
        )

    def update_selected_count(self):
        """更新已选账号数量和表头"""
        selected = sum(1 for acc in self.accounts if acc["selected"])
        total = len(self.accounts)

        # 更新底部标签
        self.selected_count_label.config(text=f"✓ 已选择 {selected} 个账号")

        # 更新表头显示 选中/总数
        self.account_tree.heading("选择", text=f"{selected}/{total}")

    def update_progress(self):
        """更新私信进度显示(顶部三色标签)"""
        # 优先从发送模块读取实时数据（发送过程中）
        if hasattr(self, 'message_sender') and hasattr(self.message_sender, 'total_sent'):
            total = self.message_sender.total_sent + self.message_sender.total_failed
            success = self.message_sender.total_sent
            failed = self.message_sender.total_failed
        else:
            # 后备：从主程序读取（发送完成后）
            total = getattr(self, 'total_sent', 0) + getattr(self, 'total_failed', 0)
            success = getattr(self, 'total_sent', 0)
            failed = getattr(self, 'total_failed', 0)

        # 始终显示进度(运行中和停止后都显示)
        if hasattr(self, 'progress_total_label'):
            self.progress_total_label.config(text=f"总计: {total} 条")
        if hasattr(self, 'progress_success_label'):
            self.progress_success_label.config(text=f"成功: {success} 条")
        if hasattr(self, 'progress_failed_label'):
            self.progress_failed_label.config(text=f"失败: {failed} 条")

    # ========== 私信广告功能 ==========

    def import_from_scraper(self):
        """从采集导入"""
        selected_users = [user for user in self.collected_users if user.get("selected", False)]

        if not selected_users:
            messagebox.showwarning("提示", "请先在「采集用户」中选择要导入的用户")
            return

        # 获取当前目标
        current = self.target_text.get("1.0", tk.END).strip()
        lines = [line.strip() for line in current.split("\n") if line.strip()]

        # 添加采集的用户
        for user in selected_users:
            username = user["username"]
            if username not in lines:
                lines.append(username)

        # 更新显示
        self.target_text.delete("1.0", tk.END)
        self.target_text.insert("1.0", "\n".join(lines))

        # 自动保存和更新统计
        self.save_targets()
        self.update_target_count()
        self.log(f"📥 已导入 {len(selected_users)} 个用户")

    def import_from_file(self):
        """从文件导入"""
        filename = filedialog.askopenfilename(
            title="选择用户列表文件",
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")]
        )

        if not filename:
            return

        try:
            with open(filename, "r", encoding="utf-8") as f:
                users = [line.strip() for line in f if line.strip() and not line.startswith("#")]

            # 获取当前目标
            current = self.target_text.get("1.0", tk.END).strip()
            lines = [line.strip() for line in current.split("\n") if line.strip()]

            # 合并去重
            for user in users:
                if user not in lines:
                    lines.append(user)

            # 更新显示
            self.target_text.delete("1.0", tk.END)
            self.target_text.insert("1.0", "\n".join(lines))

            # 自动保存和更新统计
            self.save_targets()
            self.update_target_count()
            self.log(f"📄 从文件导入 {len(users)} 个用户")

        except Exception as e:
            messagebox.showerror("错误", f"导入失败: {str(e)}")

    def clear_targets(self):
        """清空目标列表"""
        self.target_text.delete("1.0", tk.END)
        self.save_targets()  # 保存空列表
        self.update_target_count()
        self.log("🗑️ 已清空目标用户列表")

    # ========== 采集用户功能 ==========

    def on_scrape_source_change(self):
        """采集来源切换时的UI更新"""
        source = self.scrape_source.get()
        
        if source == "list":
            # 显示目标列表
            self.targets_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        else:
            # 隐藏目标列表
            self.targets_frame.pack_forget()

    def toggle_collected_user(self, event):
        """双击切换采集用户选择"""
        selection = self.result_tree.selection()
        if not selection:
            return

        item = selection[0]
        index = self.result_tree.index(item)

        if index >= len(self.collected_users):
            return

        self.collected_users[index]["selected"] = not self.collected_users[index].get("selected", False)

        check = "✓" if self.collected_users[index]["selected"] else ""
        values = list(self.result_tree.item(item, "values"))
        values[0] = check
        self.result_tree.item(item, values=tuple(values))

        self.update_collected_stats()

    def select_all_collected(self):
        """全选采集用户"""
        for i, user in enumerate(self.collected_users):
            user["selected"] = True
            item = self.result_tree.get_children()[i]
            values = list(self.result_tree.item(item, "values"))
            values[0] = "✓"
            self.result_tree.item(item, values=tuple(values))

        self.update_collected_stats()
        self.log("✅ 已全选所有采集用户")

    def deselect_all_collected(self):
        """清空采集用户选择"""
        for i, user in enumerate(self.collected_users):
            user["selected"] = False
            item = self.result_tree.get_children()[i]
            values = list(self.result_tree.item(item, "values"))
            values[0] = ""
            self.result_tree.item(item, values=tuple(values))

        self.update_collected_stats()
        self.log("❌ 已清空所有选择")

    def export_to_messaging(self):
        """导出到私信广告"""
        selected = [user for user in self.collected_users if user.get("selected", False)]

        if not selected:
            messagebox.showwarning("提示", "请先选择要导出的用户")
            return

        # 切换到私信广告标签页
        self.notebook.select(1)

        # 获取当前目标
        current = self.target_text.get("1.0", tk.END).strip()
        lines = [line.strip() for line in current.split("\n") if line.strip()]

        # 添加采集的用户
        for user in selected:
            username = user["username"]
            if username not in lines:
                lines.append(username)

        # 更新显示
        self.target_text.delete("1.0", tk.END)
        self.target_text.insert("1.0", "\n".join(lines))

        self.target_count_label.config(text=f"共 {len(lines)} 个目标用户")
        self.log(f"📤 已导出 {len(selected)} 个用户到私信广告")

    def save_collected(self):
        """保存采集结果到JSON（手动导出选中用户）"""
        selected = [user for user in self.collected_users if user.get("selected", False)]

        if not selected:
            messagebox.showwarning("提示", "请先选择要保存的用户")
            return

        filename = filedialog.asksaveasfilename(
            title="保存用户列表",
            defaultextension=".json",
            filetypes=[("JSON文件", "*.json"), ("所有文件", "*.*")]
        )

        if not filename:
            return

        try:
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(selected, f, ensure_ascii=False, indent=2)

            self.log(f"💾 已保存 {len(selected)} 个用户到JSON")
            messagebox.showinfo("成功", f"已保存 {len(selected)} 个用户")

        except Exception as e:
            messagebox.showerror("错误", f"保存失败: {str(e)}")
    
    def auto_save_collected(self):
        """自动保存采集结果到collected_users.json（后台静默）"""
        if not self.collected_users:
            return
        
        try:
            filename = "collected_users.json"
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(self.collected_users, f, ensure_ascii=False, indent=2)
            
            self.log(f"💾 已自动保存 {len(self.collected_users)} 个用户到 {filename}")
        
        except Exception as e:
            self.log(f"⚠️ 自动保存失败: {str(e)}")
    
    def export_usernames_txt(self):
        """导出用户名到TXT（仅用户名，不含昵称）"""
        if not self.collected_users:
            messagebox.showwarning("提示", "没有采集结果可导出")
            return
        
        filename = filedialog.asksaveasfilename(
            title="导出用户名列表",
            defaultextension=".txt",
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")],
            initialfile="usernames.txt"
        )
        
        if not filename:
            return
        
        try:
            with open(filename, "w", encoding="utf-8") as f:
                for user in self.collected_users:
                    f.write(f"{user['username']}\n")
            
            self.log(f"📄 已导出 {len(self.collected_users)} 个用户名到 TXT")
            messagebox.showinfo("成功", f"已导出 {len(self.collected_users)} 个用户名")
        
        except Exception as e:
            messagebox.showerror("错误", f"导出失败: {str(e)}")

    def update_collected_stats(self):
        """更新采集统计"""
        total = len(self.collected_users)
        selected = sum(1 for user in self.collected_users if user.get("selected", False))
        self.collected_stats.config(text=f"已采集 {total} 个用户,已选 {selected} 个")

    # ========== 任务控制 ==========

    def start_task(self):
        """开始任务"""
        current_tab = self.notebook.index(self.notebook.select())

        if current_tab == 0:
            # 账号管理页,执行检测
            self.check_accounts()
        elif current_tab == 1:
            # 私信广告页,执行发送
            self.start_messaging()
        elif current_tab == 2:
            # 采集用户页,执行采集
            self.start_scraping()

    def stop_task(self):
        """停止任务"""
        self.is_running = False
        self.stop_flag = True  # 同时设置停止标志
        self.log("⏸️ 正在停止...")
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)

    def start_messaging(self):
        """开始发送私信"""
        # 获取选中的账号
        selected_accounts = [acc for acc in self.accounts if acc["selected"]]

        if not selected_accounts:
            messagebox.showerror("错误", "请先在「账号管理」中选择账号")
            return

        # 获取目标用户
        target_text = self.target_text.get("1.0", tk.END).strip()
        targets = [line.strip() for line in target_text.split("\n")
                  if line.strip() and not line.startswith("#")]

        if not targets:
            messagebox.showerror("错误", "请输入目标用户")
            return

        # 获取消息内容
        message = self.message_text.get("1.0", tk.END).strip()
        if not message:
            messagebox.showerror("错误", "请输入消息内容")
            return

        # 确认发送
        confirm = messagebox.askyesno(
            "确认发送",
            f"将使用 {len(selected_accounts)} 个账号\n"
            f"向 {len(targets)} 个用户发送消息\n\n"
            f"并发: {self.thread_count.get()} 线程\n"
            f"是否继续?"
        )

        if not confirm:
            return

        # 更新按钮状态
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.is_running = True

        self.targets = targets

        self.log("🚀 开始发送任务...")

        # 在新线程中运行
        thread = threading.Thread(target=self.run_messaging_task, args=(selected_accounts,))
        thread.start()

    def run_messaging_task(self, selected_accounts):
        """运行发送任务"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.send_messages_async(selected_accounts))

    async def send_messages_async(self, selected_accounts):
        """异步发送消息（使用完整模块）"""
        try:
            # 获取发送类型
            send_type = self.send_type.get()
            
            # 构建配置
            config_dict = {
                "send_type": send_type,
                "thread_count": self.thread_count.get(),
                "thread_interval": self.thread_interval.get(),
                "send_delay_min": self.interval_min.get(),
                "send_delay_max": self.interval_max.get(),
                "per_account_limit": self.per_account_limit.get(),
                "total_limit": self.total_limit.get()
            }
            
            # 根据发送类型添加不同配置
            if send_type == "forward":
                # 转发模式
                forward_text = self.forward_urls_text.get("1.0", tk.END)
                forward_urls = [line.strip() for line in forward_text.strip().split('\n')
                               if line.strip() and line.strip().startswith('http')]
                
                if not forward_urls:
                    self.log("❌ 请添加转发链接")
                    return
                
                config_dict["forward_urls"] = forward_urls
                config_dict["hide_source"] = self.hide_source.get()
                config_dict["pin_delay"] = self.pin_delay.get()
            else:
                # 文本模式
                message_text = self.message_text.get("1.0", tk.END).strip()
                
                if not message_text:
                    self.log("❌ 请输入文本消息")
                    return
                
                config_dict["message_text"] = message_text
            
            # 回调函数
            def on_update():
                self.update_progress()
            
            def on_remove_target(target):
                self.remove_successful_target(target)
            
            def is_running():
                return self.is_running
            
            def set_running(value):
                self.is_running = value
            
            callbacks = {
                "on_update": on_update,
                "on_remove_target": on_remove_target,
                "is_running": is_running,
                "set_running": set_running
            }
            
            # 调用完整模块发送
            self.message_sender.stop_flag = False
            result = await self.message_sender.send_messages(
                selected_accounts,
                self.targets,  # 共享列表，会被修改
                config_dict,
                callbacks
            )
            
            if result:
                self.total_sent = result["success"]
                self.total_failed = result["failed"]
                self.account_stats = result.get("account_stats", {})
        
        except Exception as e:
            self.log(f"❌ 发送错误: {type(e).__name__}: {str(e)}")

        self.log("="*50)

        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.is_running = False

        # 任务完成后保持显示最终统计(不清空)
        # update_progress 会在 is_running=False 时清空,所以这里手动设置
        total = self.total_sent + self.total_failed
        if hasattr(self, 'progress_total_label'):
            self.progress_total_label.config(text=f"总计: {total} 条")
        if hasattr(self, 'progress_success_label'):
            self.progress_success_label.config(text=f"成功: {self.total_sent} 条")
        if hasattr(self, 'progress_failed_label'):
            self.progress_failed_label.config(text=f"失败: {self.total_failed} 条")

    async def countdown_wait(self, wait_time, account_name):
        """倒计时等待(显示剩余时间)"""
        try:
            for remaining in range(wait_time, 0, -1):
                if not self.is_running:
                    self.log(f"  ⏸️ [{account_name}] 等待被中断")
                    break

                # 每60秒显示一次,或最后10秒每5秒显示,最后5秒每秒显示
                if remaining % 60 == 0 or (remaining <= 10 and remaining % 5 == 0) or remaining <= 5:
                    minutes = remaining // 60
                    seconds = remaining % 60
                    if minutes > 0:
                        time_str = f"{minutes}分{seconds}秒"
                    else:
                        time_str = f"{seconds}秒"

                    self.log(f"  ⏳ [{account_name}] 剩余等待时间: {time_str}")

                await asyncio.sleep(1)
        except Exception as e:
            self.log(f"  ⚠️ [{account_name}] 倒计时错误: {e}")

    async def check_spambot_status(self, client, account_name):
        """检查 SpamBot 状态"""
        try:
            self.log(f"  🤖 [{account_name}] 正在检查 SpamBot 状态...")

            # 发送 /start 给 @SpamBot
            await client.send_message("SpamBot", "/start")

            # 等待回复
            await asyncio.sleep(3)

            # 获取最近的消息
            messages = await client.get_messages("SpamBot", limit=1)

            if messages and len(messages) > 0:
                reply_text = messages[0].text or messages[0].message or ""

                # 检测限制关键词
                restriction_keywords = [
                    "限制", "restriction", "spam", "flood", "banned", "限流",
                    "temporarily", "暂时", "永久", "permanent"
                ]

                has_restriction = any(keyword in reply_text.lower() for keyword in restriction_keywords)

                if has_restriction:
                    self.log(f"  ⚠️ [{account_name}] SpamBot 检测到限制:")
                    self.log(f"      {reply_text[:100]}")
                    return True  # 有限制
                else:
                    self.log(f"  ✅ [{account_name}] SpamBot 无限制,可以继续发送")
                    return False  # 无限制
            else:
                self.log(f"  ⚠️ [{account_name}] SpamBot 未回复")
                return True  # 安全起见,认为有限制

        except Exception as e:
            self.log(f"  ⚠️ [{account_name}] 检查 SpamBot 失败: {e}")
            return True  # 出错时安全起见,认为有限制


    def remove_successful_target(self, target):
        """从目标列表中删除单个成功发送的用户"""
        try:
            # 获取当前列表
            current = self.target_text.get("1.0", tk.END).strip()
            lines = [line.strip() for line in current.split("\n") if line.strip()]

            # 删除该用户
            remaining = [line for line in lines if line != target]

            # 更新显示
            self.target_text.delete("1.0", tk.END)
            self.target_text.insert("1.0", "\n".join(remaining))

            # 更新计数
            self.target_count_label.config(text=f"共 {len(remaining)} 个目标用户")

        except Exception as e:
            self.log(f"  ⚠️ 更新目标列表失败: {type(e).__name__}")

    def start_scraping(self):
        """开始采集用户"""
        # 获取选中的账号(用于采集)
        selected_accounts = [acc for acc in self.accounts if acc["selected"]]

        if not selected_accounts:
            messagebox.showerror("错误", "请先在「账号管理」中选择账号")
            return

        # 获取采集来源
        source = self.scrape_source.get()
        
        # 根据不同来源获取目标
        if source == "list":
            # 从文本框获取目标列表
            text = self.scrape_targets_text.get("1.0", tk.END)
            raw_targets = [line.strip() for line in text.strip().split('\n') 
                          if line.strip() and not line.strip().startswith('#')]
            
            if not raw_targets:
                messagebox.showerror("错误", "请添加采集目标")
                return
            
            # 验证和去重
            targets = []
            seen = set()
            invalid_count = 0
            
            for target in raw_targets:
                # 基本验证：必须是链接或@开头的用户名
                is_valid = (
                    target.startswith('https://t.me/') or 
                    target.startswith('http://t.me/') or
                    target.startswith('@')
                )
                
                if not is_valid:
                    self.log(f"  ⚠️ 跳过无效格式: {target}")
                    invalid_count += 1
                    continue
                
                # 去重
                if target in seen:
                    self.log(f"  ⚠️ 跳过重复项: {target}")
                    continue
                
                seen.add(target)
                targets.append(target)
            
            if not targets:
                messagebox.showerror("错误", "没有有效的采集目标")
                return
            
            if invalid_count > 0:
                self.log(f"⚠️ 已跳过 {invalid_count} 个无效目标")
            
            self.log(f"✅ 有效目标: {len(targets)} 个")
            source_text = f"{len(targets)} 个群组/频道"
        elif source == "joined":
            targets = ["joined_groups"]  # 特殊标记
            source_text = "已加入的群组"
        else:  # dialogs
            targets = ["dialogs"]  # 特殊标记
            source_text = "对话列表"

        # 确认采集
        mode_text = "💬 聊天记录模式" if self.scrape_mode.get() == "messages" else "🚀 默认模式"
        confirm = messagebox.askyesno(
            "确认采集",
            f"将使用 {len(selected_accounts)} 个账号\n"
            f"采集来源: {source_text}\n\n"
            f"采集模式: {mode_text}\n"
            f"并发线程: {self.scrape_threads.get()}\n"
            f"采集限制: {self.scrape_limit.get()} 个\n"
            f"自动退群: {'是' if self.auto_leave.get() else '否'}\n\n"
            f"是否继续?"
        )

        if not confirm:
            return

        # 更新按钮状态
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.is_running = True
        self.is_scraping = True  # 标记正在采集

        self.log("🚀 开始采集任务...")
        self.log(f"📊 使用 {len(selected_accounts)} 个账号")
        self.log(f"🎯 采集来源: {source_text}")
        self.log(f"⚙️ 模式: {mode_text}")
        self.log(f"🔀 并发: {self.scrape_threads.get()} 线程")
        
        # 显示采集进度
        self.update_scrape_progress(0, len(targets))
        if not self.scrape_progress_label.winfo_ismapped():
            self.scrape_progress_label.pack(side=tk.LEFT, padx=20)

        # 在新线程中运行
        thread = threading.Thread(target=self.run_scraping_task,
                                  args=(selected_accounts, targets, source))
        thread.start()
    
    def update_scrape_progress(self, current, total):
        """更新采集进度"""
        if total > 0:
            percentage = int((current / total) * 100)
            text = f"📊 采集进度: {current}/{total} ({percentage}%)"
        else:
            text = ""
        
        self.scrape_progress_label.config(text=text)

    def run_scraping_task(self, accounts, targets, source):
        """运行采集任务"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.scrape_users_async(accounts, targets, source))

    async def scrape_users_async(self, accounts, targets, source):
        """异步采集用户（使用完整模块）"""
        try:
            # 构建配置
            config_dict = {
                "source": source,
                "mode": self.scrape_mode.get(),
                "threads": self.scrape_threads.get(),
                "limit": self.scrape_limit.get(),
                "message_limit": self.message_limit.get(),
                "groups_per_account": self.groups_per_account.get(),
                "filter_online_time": self.filter_online_time.get(),
                "online_days": self.online_days.get(),
                "include_recently": self.include_recently.get(),
                "include_online": self.include_online.get(),
                "filter_bot": self.filter_bot.get(),
                "filter_username": self.filter_username.get(),
                "filter_premium": self.filter_premium.get() if hasattr(self, 'filter_premium') else False,
                "filter_photo": self.filter_photo.get() if hasattr(self, 'filter_photo') else False,
                "filter_admin": self.filter_admin.get() if hasattr(self, 'filter_admin') else False,
                "auto_leave": self.auto_leave.get()
            }
            
            # UI回调函数
            ui_callbacks = {
                "insert_row": lambda u: self.result_tree.insert("", tk.END, values=(
                    "",
                    u["username"],
                    u["name"],
                    u["source"]
                )),
                "is_running": lambda: self.is_running,
                "update_progress": lambda current, total: self.update_scrape_progress(current, total)
            }
            
            # 调用完整模块采集
            self.user_scraper.stop_flag = False
            self.user_scraper.collected_users = []  # 重置
            users = await self.user_scraper.scrape(accounts, targets, config_dict, ui_callbacks)
            
            # 更新采集结果
            if users:
                self.collected_users.extend(users)
                self.auto_save_collected()  # 自动静默保存
            
            self.update_collected_stats()

        except Exception as e:
            self.log(f"❌ 采集错误: {type(e).__name__}: {str(e)[:50]}")

        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.is_running = False
        self.is_scraping = False
        
        # 隐藏采集进度
        if self.scrape_progress_label.winfo_ismapped():
            self.scrape_progress_label.pack_forget()






    def load_targets(self):
        """加载目标用户列表"""
        try:
            if not os.path.exists(self.targets_file):
                return

            with open(self.targets_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            targets = data.get("targets", [])
            # 只加载待发送的用户
            pending_targets = [t["username"] for t in targets if t.get("status") == "pending"]

            if pending_targets:
                self.target_text.delete("1.0", tk.END)
                self.target_text.insert("1.0", "\n".join(pending_targets))
                self.update_target_count()
                self.log(f"✅ 自动加载 {len(pending_targets)} 个目标用户")
        except Exception as e:
            self.log(f"⚠️ 加载目标用户失败: {e}")

    def save_targets(self):
        """保存目标用户列表"""
        try:
            text = self.target_text.get("1.0", tk.END)
            lines = [line.strip() for line in text.strip().split('\n') if line.strip()]

            targets = []
            for username in lines:
                targets.append({
                    "username": username,
                    "status": "pending",
                    "added_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })

            data = {"targets": targets}

            with open(self.targets_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.log(f"⚠️ 保存目标用户失败: {e}")

    def update_target_count(self):
        """更新目标用户数量"""
        text = self.target_text.get("1.0", tk.END)
        lines = [line.strip() for line in text.strip().split('\n') if line.strip()]
        count = len(lines)
        self.target_count_label.config(text=f"共 {count} 个目标用户")

    def load_forward_posts(self):
        """加载转发链接列表"""
        try:
            if not os.path.exists(self.forward_posts_file):
                return

            with open(self.forward_posts_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            urls = data.get("urls", [])
            hide_source = data.get("hide_source", False)

            if urls:
                self.forward_urls_text.delete("1.0", tk.END)
                self.forward_urls_text.insert("1.0", "\n".join(urls))
                self.update_forward_count()

            self.hide_source.set(hide_source)

            if urls:
                self.log(f"✅ 自动加载 {len(urls)} 条转发链接")
        except Exception as e:
            self.log(f"⚠️ 加载转发链接失败: {e}")

    def save_forward_posts(self):
        """保存转发链接列表"""
        try:
            text = self.forward_urls_text.get("1.0", tk.END)
            lines = [line.strip() for line in text.strip().split('\n')
                    if line.strip() and line.strip().startswith('http')]

            data = {
                "urls": lines,
                "hide_source": self.hide_source.get()
            }

            with open(self.forward_posts_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.log(f"⚠️ 保存转发链接失败: {e}")

    def update_forward_count(self):
        """更新转发贴子数量"""
        text = self.forward_urls_text.get("1.0", tk.END)
        lines = [line.strip() for line in text.strip().split('\n')
                if line.strip() and line.strip().startswith('http')]
        count = len(lines)
        self.forward_count_label.config(text=f"共 {count} 条贴子")

    def load_message_text(self):
        """加载文本消息内容"""
        try:
            if not os.path.exists(self.message_text_file):
                return

            with open(self.message_text_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            text = data.get("text", "")

            if text:
                self.message_text.delete("1.0", tk.END)
                self.message_text.insert("1.0", text)
                self.log(f"✅ 自动加载文本消息")
        except Exception as e:
            self.log(f"⚠️ 加载文本消息失败: {e}")

    def save_message_text(self):
        """保存文本消息内容"""
        try:
            text = self.message_text.get("1.0", tk.END).strip()

            data = {"text": text}

            with open(self.message_text_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.log(f"⚠️ 保存文本消息失败: {e}")

    # ==================== 代理管理功能 ====================

    def import_proxy_file(self):
        """从文件导入代理"""
        from tkinter import filedialog

        filename = filedialog.askopenfilename(
            title="选择代理文件",
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")]
        )

        if filename:
            try:
                with open(filename, "r", encoding="utf-8") as f:
                    content = f.read()
                    self.proxy_input.delete("1.0", tk.END)
                    self.proxy_input.insert("1.0", content)
                    self.log(f"✅ 已导入代理文件: {filename}")
            except Exception as e:
                self.log(f"❌ 导入代理文件失败: {e}")

    def add_proxies(self):
        """添加代理到列表"""
        content = self.proxy_input.get("1.0", tk.END).strip()

        if not content:
            messagebox.showwarning("警告", "请先输入或导入代理")
            return

        lines = [line.strip() for line in content.split("\n") if line.strip()]
        added = 0

        for line in lines:
            # 解析代理格式
            proxy_info = self.parse_proxy(line)
            if proxy_info:
                # 检查是否已存在
                if not any(p["proxy"] == proxy_info["proxy"] for p in self.proxies):
                    self.proxies.append(proxy_info)
                    added += 1

        self.refresh_proxy_tree()
        self.save_proxies()  # 自动保存
        self.log(f"✅ 添加了 {added} 个代理到列表")
        self.proxy_input.delete("1.0", tk.END)

    def parse_proxy(self, line):
        """解析代理格式,使用用户选择的默认协议"""
        import re

        # 支持的格式:
        # http://ip:port
        # http://user:pass@ip:port
        # socks5://ip:port
        # socks5://user:pass@ip:port
        # ip:port (使用默认协议)
        # user:pass@ip:port (使用默认协议)

        line = line.strip()
        if not line:
            return None

        # 匹配完整格式(明确指定协议)
        match = re.match(r'^(https?|socks[45])://(.+)$', line)
        if match:
            proxy_type = match.group(1)
            proxy_addr = match.group(2)
            return {
                "proxy": line,
                "type": proxy_type,
                "status": "未检测",
                "ping": 0,
                "selected": False
            }

        # 匹配 ip:port 或 user:pass@ip:port(没有协议前缀)
        # 使用用户选择的默认协议
        if ':' in line:
            default_protocol = self.default_proxy_protocol.get()
            return {
                "proxy": f"{default_protocol}://{line}",
                "type": default_protocol,
                "status": "未检测",
                "ping": 0,
                "selected": False
            }

        return None

    def refresh_proxy_tree(self):
        """刷新代理列表显示"""
        # 清空树
        for item in self.proxy_tree.get_children():
            self.proxy_tree.delete(item)

        # 重新填充
        for proxy in self.proxies:
            check = "☑" if proxy["selected"] else "☐"
            ping_display = f"{proxy['ping']}" if proxy['ping'] > 0 else "-"

            self.proxy_tree.insert("", tk.END, values=(
                check,
                proxy["proxy"],
                proxy["type"],
                proxy["status"],
                ping_display
            ))

        # 更新统计
        self.update_proxy_stats()

    def update_proxy_stats(self):
        """更新代理统计"""
        total = len(self.proxies)
        available = sum(1 for p in self.proxies if p["status"] == "可用")
        unavailable = sum(1 for p in self.proxies if p["status"] == "不可用")
        unchecked = sum(1 for p in self.proxies if p["status"] == "未检测")

        self.proxy_stats.config(
            text=f"总计: {total} | 可用: {available} | 不可用: {unavailable} | 未检测: {unchecked}"
        )

    def toggle_proxy_selection(self, event):
        """双击切换代理选择"""
        item = self.proxy_tree.selection()
        if item:
            index = self.proxy_tree.index(item[0])
            self.proxies[index]["selected"] = not self.proxies[index]["selected"]
            self.refresh_proxy_tree()
            self.save_proxies()  # 自动保存选择状态

    def check_all_proxies(self):
        """批量检测所有代理"""
        if not self.proxies:
            messagebox.showwarning("警告", "代理列表为空")
            return

        self.log(f"🔍 开始检测 {len(self.proxies)} 个代理... (并发检测,速度更快)")

        # 使用异步检测
        import threading
        thread = threading.Thread(target=self._check_proxies_thread, daemon=True)
        thread.start()

    def _check_proxies_thread(self):
        """代理检测线程(使用线程池并发)"""
        import requests
        import time
        import urllib3
        from concurrent.futures import ThreadPoolExecutor, as_completed

        # 禁用 SSL 警告
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        def check_single_proxy(index, proxy):
            """检测单个代理"""
            try:
                # 测试 URL(使用简单的 HTTP 网站)
                test_url = "http://httpbin.org/ip"

                # 构造代理字典
                proxies = {
                    "http": proxy["proxy"],
                    "https": proxy["proxy"]
                }

                # 测试连接(缩短超时时间)
                start_time = time.time()
                response = requests.get(test_url, proxies=proxies, timeout=5)  # 5秒超时
                end_time = time.time()

                if response.status_code == 200:
                    ping = int((end_time - start_time) * 1000)
                    proxy["status"] = "可用"
                    proxy["ping"] = ping
                    return (index, True, f"✅ [{index+1}/{len(self.proxies)}] {proxy['proxy'][:60]}... - 可用 ({ping}ms)")
                else:
                    proxy["status"] = "不可用"
                    proxy["ping"] = 0
                    return (index, False, f"❌ [{index+1}/{len(self.proxies)}] {proxy['proxy'][:60]}... - HTTP {response.status_code}")

            except Exception as e:
                proxy["status"] = "不可用"
                proxy["ping"] = 0
                error_msg = str(e)[:80]
                return (index, False, f"❌ [{index+1}/{len(self.proxies)}] {proxy['proxy'][:60]}... - {error_msg}")

        # 使用线程池并发检测(50个线程)
        with ThreadPoolExecutor(max_workers=50) as executor:
            futures = {executor.submit(check_single_proxy, i, proxy): i for i, proxy in enumerate(self.proxies)}

            for future in as_completed(futures):
                index, success, message = future.result()
                self.root.after(0, lambda msg=message: self.log(msg))
                self.root.after(0, self.refresh_proxy_tree)

        self.root.after(0, lambda: self.log(f"✅ 代理检测完成"))

    def select_available_proxies(self):
        """选中所有可用代理"""
        for proxy in self.proxies:
            if proxy["status"] == "可用":
                proxy["selected"] = True
        self.refresh_proxy_tree()
        self.save_proxies()  # 自动保存
        self.log(f"✅ 已选中所有可用代理")

    def delete_unavailable_proxies(self):
        """删除所有不可用代理"""
        before = len(self.proxies)
        self.proxies = [p for p in self.proxies if p["status"] != "不可用"]
        after = len(self.proxies)
        deleted = before - after

        self.refresh_proxy_tree()
        self.save_proxies()  # 自动保存
        self.log(f"✅ 删除了 {deleted} 个不可用代理")

    def clear_all_proxies(self):
        """清空所有代理"""
        if not self.proxies:
            return

        if messagebox.askyesno("确认", f"确定要清空所有 {len(self.proxies)} 个代理吗?"):
            self.proxies = []
            self.refresh_proxy_tree()
            self.save_proxies()  # 自动保存
            self.log(f"✅ 已清空代理列表")

    def export_available_proxies(self):
        """导出可用代理到文件"""
        from tkinter import filedialog

        available = [p for p in self.proxies if p["status"] == "可用"]

        if not available:
            messagebox.showwarning("警告", "没有可用代理")
            return

        filename = filedialog.asksaveasfilename(
            title="保存可用代理",
            defaultextension=".txt",
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")]
        )

        if filename:
            try:
                with open(filename, "w", encoding="utf-8") as f:
                    for proxy in available:
                        f.write(f"{proxy['proxy']}\n")
                self.log(f"✅ 导出了 {len(available)} 个可用代理到: {filename}")
            except Exception as e:
                self.log(f"❌ 导出代理失败: {e}")

    def parse_proxy_for_telethon(self, proxy_url):
        """将代理 URL 转换为 Telethon 所需的格式
        返回: (proxy_config, connection_type)
        """
        import re
        from telethon import connection

        # 解析代理 URL
        # 格式: http://ip:port 或 http://user:pass@ip:port
        # 格式: socks5://ip:port 或 socks5://user:pass@ip:port

        match = re.match(r'^(https?|socks[45])://(?:(.+):(.+)@)?(.+):(\d+)$', proxy_url)
        if not match:
            return None, None

        proxy_type = match.group(1)
        username = match.group(2)
        password = match.group(3)
        addr = match.group(4)
        port = int(match.group(5))

        # Telethon 代理格式
        if proxy_type in ['socks4', 'socks5']:
            import socks
            proxy = (socks.SOCKS5 if proxy_type == 'socks5' else socks.SOCKS4, addr, port, True, username, password)
            # SOCKS 代理使用默认连接类型
            return proxy, None
        else:
            # HTTP/HTTPS 代理
            # Telethon HTTP 代理格式: (addr, port, username, password)
            proxy = (addr, port, username, password)
            # HTTP 代理必须使用 ConnectionHttp
            return proxy, connection.ConnectionHttp

    def save_proxies(self):
        """保存代理列表到文件"""
        try:
            proxy_file = "proxies.json"
            with open(proxy_file, "w", encoding="utf-8") as f:
                json.dump(self.proxies, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.log(f"⚠️ 保存代理列表失败: {e}")

    def load_proxies(self):
        """从文件加载代理列表"""
        try:
            proxy_file = "proxies.json"
            if os.path.exists(proxy_file):
                with open(proxy_file, "r", encoding="utf-8") as f:
                    self.proxies = json.load(f)
                    self.refresh_proxy_tree()
                    self.log(f"✅ 自动加载了 {len(self.proxies)} 个代理")
        except Exception as e:
            self.log(f"⚠️ 加载代理列表失败: {e}")
    
    def login_telegram_web(self, account):
        """打开Telegram Web并自动登录"""
        try:
            from modules.web_login import TelegramWebLogin
            
            phone = account.get("phone", "")
            session_file = account.get("path", "")  # 使用 path 字段，不是 session
            
            if not session_file:
                self.log(f"❌ 账号 {phone} 没有session文件路径")
                messagebox.showerror("错误", "该账号没有session文件路径")
                return
            
            if not os.path.exists(session_file):
                self.log(f"❌ Session文件不存在: {session_file}")
                messagebox.showerror("错误", f"Session文件不存在:\n{session_file}")
                return
            
            self.log(f"🌐 正在为账号 {phone} 打开 Telegram Web...")
            
            # 创建Web登录实例
            web_login = TelegramWebLogin(logger=self.log)
            
            # 在新线程中打开浏览器（避免阻塞UI）
            def open_browser():
                driver = web_login.open_telegram_web(session_file)
                if driver:
                    # 保持浏览器打开，直到用户关闭
                    # driver会在用户关闭浏览器时自动释放
                    pass
            
            thread = threading.Thread(target=open_browser, daemon=True)
            thread.start()
            
        except ImportError:
            self.log("❌ 缺少依赖库")
            messagebox.showerror("缺少依赖", 
                               "请先安装依赖库:\n\npip install selenium webdriver-manager")
        except Exception as e:
            self.log(f"❌ 打开Web版失败: {str(e)}")
            messagebox.showerror("错误", f"打开Web版失败:\n{str(e)}")


def main():
    root = tk.Tk()
    app = TGMassDM(root)
    root.mainloop()


if __name__ == "__main__":
    main()
