"""
TG 批量私信系统 - 多功能版
功能：账号管理、私信广告、采集用户
"""

# 版本号（每次更新修改这里）
VERSION = "v1.8.0"

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

try:
    from telethon import TelegramClient, errors
    from telethon.tl.types import InputPeerUser, User
    from telethon.tl.functions.messages import GetDialogsRequest
    from telethon.tl.types import InputPeerEmpty, UserStatusOnline, UserStatusRecently
except ImportError:
    print("❌ 缺少 telethon 库，请运行: pip install telethon")
    sys.exit(1)


class TGMassDM:
    def __init__(self, root):
        self.root = root
        self.root.title(f"TG 批量私信系统 {VERSION}")
        self.root.geometry("1200x800")

        # Telegram API 配置
        self.api_id = 2040
        self.api_hash = "b18441a1ff607e10a989891a5462e627"

        # 数据存储
        self.accounts = []  # {path, selected, status, username, phone, first_name, proxy, 2fa}
        self.targets = []   # 目标用户列表
        self.collected_users = []  # 采集的用户
        self.is_running = False

        # 检测配置（问题 4：并发优化）
        self.check_concurrent = tk.IntVar(value=30)  # 并发数量（默认 30）
        self.check_batch_delay = tk.IntVar(value=2)  # 批次间隔(秒)
        self.check_timeout = tk.IntVar(value=30)  # 超时时间(秒)

        # 配置文件路径
        self.config_file = "config.json"
        self.accounts_dir = "accounts"

        # 创建账号文件夹
        if not os.path.exists(self.accounts_dir):
            os.makedirs(self.accounts_dir)

        self.setup_ui()

        # 加载配置和账号
        self.load_config()
        self.load_accounts()

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

        # 使用 PanedWindow 可拖动分隔栏（问题 11：UI 布局优化）
        main_paned = ttk.PanedWindow(tab_frame, orient=tk.VERTICAL)
        main_paned.pack(fill=tk.BOTH, expand=True)

        # 上方：标签页区域（50%）
        notebook_frame = ttk.Frame(main_paned)
        main_paned.add(notebook_frame, weight=1)

        self.notebook = ttk.Notebook(notebook_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # 设置标签字体
        style = ttk.Style()
        style.configure('TNotebook.Tab', font=('微软雅黑', 12, 'bold'), padding=[20, 10])
        
        # 设置 Menubutton 样式，让它看起来像普通按钮
        style.configure('TMenubutton', 
                       relief='raised',
                       borderwidth=2,
                       padding=6)

        # 创建三个功能标签页
        self.setup_tab_accounts()
        self.setup_tab_messaging()
        self.setup_tab_scraper()

        # 下方：日志区域（50%）
        log_container = ttk.Frame(main_paned)
        main_paned.add(log_container, weight=1)

        # 控制按钮
        control_frame = ttk.Frame(log_container, padding="5")
        control_frame.pack(fill=tk.X)

        self.start_btn = ttk.Button(control_frame, text="🚀 开始", width=15,
                                    command=self.start_task)
        self.start_btn.pack(side=tk.LEFT, padx=5)

        self.stop_btn = ttk.Button(control_frame, text="⏸️ 停止", width=15,
                                   command=self.stop_task, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=5)

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
        
        # 延迟设置分割位置（确保窗口完全渲染后）
        self.root.after(100, self.set_initial_sash_position)

        # 应用加载的配置
        self.apply_loaded_config()

        # 显示自动加载的账号
        self.refresh_account_tree()

    def set_initial_sash_position(self):
        """设置初始分割位置（延迟执行）"""
        try:
            # 强制更新窗口
            self.root.update()
            
            window_height = self.root.winfo_height()
            self.log(f"🔍 窗口高度: {window_height}px")
            
            if window_height > 100:
                split_position = int(window_height * 0.5)  # 50% 位置
                self.log(f"🔧 设置分割位置: {split_position}px")
                
                # 设置分割位置
                self.main_paned.sashpos(0, split_position)
                
                # 验证是否设置成功
                actual_pos = self.main_paned.sashpos(0)
                self.log(f"✅ 实际分割位置: {actual_pos}px")
                
                if actual_pos != split_position:
                    self.log(f"⚠️ 位置不匹配，重试...")
                    self.root.after(200, lambda: self.main_paned.sashpos(0, split_position))
            else:
                self.log(f"⚠️ 窗口高度异常: {window_height}px")
        except Exception as e:
            self.log(f"❌ 设置布局失败: {e}")

        # 窗口关闭时保存配置
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def on_closing(self):
        """窗口关闭时保存配置"""
        self.save_config()
        self.root.destroy()

    def refresh_account_tree(self):
        """刷新账号列表显示"""
        # 清空树
        for item in self.account_tree.get_children():
            self.account_tree.delete(item)

        # 重新填充
        for acc in self.accounts:
            # 复选框：☑ (已选) 或 ☐ (未选)
            check = "☑" if acc["selected"] else "☐"
            
            # 提取姓名（first_name）
            first_name = acc.get("first_name", "-")
            
            # 代理状态
            proxy_status = acc.get("proxy", "直连")
            if proxy_status and proxy_status != "直连":
                proxy_display = "代理已连接"
            else:
                proxy_display = "直连"
            
            # 2FA 状态（直接显示值）
            twofa_display = acc.get("2fa", "")
            
            self.account_tree.insert("", tk.END, values=(
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

        # 按钮组
        btn_frame = ttk.Frame(tab1)
        btn_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(btn_frame, text="📁 导入 Session 文件夹", width=20,
                  command=self.import_sessions).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="✅ 全选", width=8,
                  command=self.select_all).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="❌ 清空", width=8,
                  command=self.deselect_all).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="🔍 检测状态", width=12,
                  command=self.check_accounts).pack(side=tk.LEFT, padx=5)
        
        # 删除按钮（点击弹出菜单）
        delete_btn = ttk.Button(btn_frame, text="🗑️ 删除", width=12,
                               command=lambda: self.show_delete_menu(delete_btn))
        delete_btn.pack(side=tk.LEFT, padx=2)
        
        # 导出按钮（点击弹出菜单）
        export_btn = ttk.Button(btn_frame, text="📤 导出", width=12,
                               command=lambda: self.show_export_menu(export_btn))
        export_btn.pack(side=tk.LEFT, padx=2)
        
        ttk.Button(btn_frame, text="🔄 刷新", width=10,
                  command=self.refresh_accounts).pack(side=tk.LEFT, padx=2)

        # 账号列表
        tree_frame = ttk.Frame(tab1)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        self.account_tree = ttk.Treeview(tree_frame,
                                         columns=("选择", "手机号", "用户名", "姓名", "状态", "代理", "2FA"),
                                         show="headings", height=25)

        self.account_tree.heading("选择", text="✓")
        self.account_tree.heading("手机号", text="手机号")
        self.account_tree.heading("用户名", text="用户名")
        self.account_tree.heading("姓名", text="姓名")
        self.account_tree.heading("状态", text="状态")
        self.account_tree.heading("代理", text="代理")
        self.account_tree.heading("2FA", text="2FA")

        self.account_tree.column("选择", width=40, anchor=tk.CENTER)
        self.account_tree.column("手机号", width=120)
        self.account_tree.column("用户名", width=120)
        self.account_tree.column("姓名", width=100)
        self.account_tree.column("状态", width=150)
        self.account_tree.column("代理", width=100)
        self.account_tree.column("2FA", width=60, anchor=tk.CENTER)

        self.account_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL,
                                  command=self.account_tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.account_tree.config(yscrollcommand=scrollbar.set)

        # 双击切换选择
        self.account_tree.bind("<Double-1>", self.toggle_account)

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

        # 左右分栏
        paned = ttk.PanedWindow(tab2, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        # ========== 左侧:消息设置 ==========
        left = ttk.Frame(paned)
        paned.add(left, weight=2)

        # 选择账号提示
        account_frame = ttk.LabelFrame(left, text="📱 选择账号", padding="10")
        account_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(account_frame, text="使用「账号管理」中已选的账号").pack(anchor=tk.W)
        self.selected_count_label = ttk.Label(account_frame, text="✓ 已选择 0 个账号",
                                              foreground="green", font=("微软雅黑", 10, "bold"))
        self.selected_count_label.pack(anchor=tk.W, pady=5)

        # 发送类型
        type_frame = ttk.LabelFrame(left, text="📝 发送类型", padding="10")
        type_frame.pack(fill=tk.X, pady=(0, 10))

        self.send_type = tk.StringVar(value="text")
        ttk.Radiobutton(type_frame, text="📝 文本消息", variable=self.send_type,
                       value="text", command=self.on_send_type_change).pack(anchor=tk.W, pady=2)
        ttk.Radiobutton(type_frame, text="🔗 转发贴子", variable=self.send_type,
                       value="forward", command=self.on_send_type_change).pack(anchor=tk.W, pady=2)

        # 文本消息框
        self.text_msg_frame = ttk.LabelFrame(left, text="✉️ 文本消息", padding="10")
        self.text_msg_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        self.message_text = scrolledtext.ScrolledText(self.text_msg_frame, height=8,
                                                      font=("微软雅黑", 10), wrap=tk.WORD)
        self.message_text.pack(fill=tk.BOTH, expand=True)
        self.message_text.insert("1.0", "你好 {firstname}!\n\n这是一条测试消息。\n\n支持变量:\n• {username} - 用户名\n• {firstname} - 名字")

        # 转发贴子框(默认隐藏)
        self.forward_msg_frame = ttk.LabelFrame(left, text="🔗 转发贴子", padding="10")
        # 不 pack,等切换时显示

        ttk.Label(self.forward_msg_frame, text="贴子链接 (每行一条,自动随机选择):").pack(anchor=tk.W)
        ttk.Label(self.forward_msg_frame, text="格式: https://t.me/channel/12345",
                 font=("微软雅黑", 8), foreground="gray").pack(anchor=tk.W)

        self.forward_urls_text = scrolledtext.ScrolledText(self.forward_msg_frame, height=6,
                                                           font=("微软雅黑", 9), wrap=tk.WORD)
        self.forward_urls_text.pack(fill=tk.BOTH, expand=True, pady=5)
        self.forward_urls_text.insert("1.0", "https://t.me/channel_name/123\nhttps://t.me/channel_name/456\nhttps://t.me/channel_name/789")

        self.hide_source = tk.BooleanVar(value=False)  # 默认不隐藏
        ttk.Checkbutton(self.forward_msg_frame, text="隐藏来源",
                       variable=self.hide_source).pack(anchor=tk.W, pady=5)

        self.forward_count_label = ttk.Label(self.forward_msg_frame, text="共 3 条贴子",
                                            font=("微软雅黑", 9))
        self.forward_count_label.pack(anchor=tk.W)

        # 保存左侧容器引用(用于切换)
        self.messaging_left = left

        # 目标用户
        target_frame = ttk.LabelFrame(left, text="👥 目标用户", padding="10")
        target_frame.pack(fill=tk.BOTH, expand=True)

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

        self.target_text = scrolledtext.ScrolledText(target_frame, height=6,
                                                     font=("微软雅黑", 10), wrap=tk.WORD)
        self.target_text.pack(fill=tk.BOTH, expand=True)
        self.target_text.insert("1.0", "@username1\n@username2\n@username3")

        self.target_count_label = ttk.Label(target_frame, text="共 3 个目标用户",
                                            font=("微软雅黑", 9))
        self.target_count_label.pack(anchor=tk.W, pady=(5, 0))

        # ========== 右侧:发送设置 ==========
        right = ttk.Frame(paned)
        paned.add(right, weight=1)

        # 并发控制
        concurrent_frame = ttk.LabelFrame(right, text="⚡ 并发控制", padding="10")
        concurrent_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(concurrent_frame, text="并行线程数:").grid(row=0, column=0, sticky=tk.W, pady=3)
        self.thread_count = tk.IntVar(value=2)
        ttk.Spinbox(concurrent_frame, from_=1, to=50, textvariable=self.thread_count,
                   width=12).grid(row=0, column=1, sticky=tk.EW, padx=(10, 0), pady=3)

        ttk.Label(concurrent_frame, text="启动间隔(秒):").grid(row=1, column=0, sticky=tk.W, pady=3)
        self.thread_interval = tk.IntVar(value=1)
        ttk.Spinbox(concurrent_frame, from_=0, to=60, textvariable=self.thread_interval,
                   width=12).grid(row=1, column=1, sticky=tk.EW, padx=(10, 0), pady=3)

        concurrent_frame.columnconfigure(1, weight=1)

        # 额度限制
        limit_frame = ttk.LabelFrame(right, text="📊 额度限制", padding="10")
        limit_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(limit_frame, text="单账号上限:").grid(row=0, column=0, sticky=tk.W, pady=3)
        self.per_account_limit = tk.IntVar(value=50)
        ttk.Spinbox(limit_frame, from_=1, to=1000, textvariable=self.per_account_limit,
                   width=12).grid(row=0, column=1, sticky=tk.EW, padx=(10, 0), pady=3)

        ttk.Label(limit_frame, text="任务总上限:").grid(row=1, column=0, sticky=tk.W, pady=3)
        self.total_limit = tk.IntVar(value=1000)
        ttk.Spinbox(limit_frame, from_=1, to=100000, textvariable=self.total_limit,
                   width=12).grid(row=1, column=1, sticky=tk.EW, padx=(10, 0), pady=3)

        limit_frame.columnconfigure(1, weight=1)

        # 发送间隔
        interval_frame = ttk.LabelFrame(right, text="⏱️ 发送间隔", padding="10")
        interval_frame.pack(fill=tk.X, pady=(0, 10))

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

        # 其他选项
        option_frame = ttk.LabelFrame(right, text="🔧 其他选项", padding="10")
        option_frame.pack(fill=tk.X)

        self.auto_switch = tk.BooleanVar(value=True)
        ttk.Checkbutton(option_frame, text="遇到限制自动切换账号",
                       variable=self.auto_switch).pack(anchor=tk.W, pady=2)

        self.auto_retry = tk.BooleanVar(value=False)
        ttk.Checkbutton(option_frame, text="发送失败自动重试",
                       variable=self.auto_retry).pack(anchor=tk.W, pady=2)

    def setup_tab_scraper(self):
        """功能3: 采集用户"""
        tab3 = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab3, text="👥 采集用户")

        # 左右分栏
        paned = ttk.PanedWindow(tab3, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        # ========== 左侧:采集设置 ==========
        left = ttk.Frame(paned)
        paned.add(left, weight=1)

        # 采集来源
        source_frame = ttk.LabelFrame(left, text="📌 采集来源", padding="10")
        source_frame.pack(fill=tk.X, pady=(0, 10))

        self.scrape_type = tk.StringVar(value="group")
        ttk.Radiobutton(source_frame, text="👥 从群组采集成员", variable=self.scrape_type,
                       value="group").pack(anchor=tk.W, pady=2)
        ttk.Radiobutton(source_frame, text="📢 从频道采集订阅者", variable=self.scrape_type,
                       value="channel").pack(anchor=tk.W, pady=2)

        # 目标链接
        link_frame = ttk.LabelFrame(left, text="🔗 目标链接", padding="10")
        link_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(link_frame, text="输入群组/频道链接或用户名:").pack(anchor=tk.W)
        self.scrape_link = ttk.Entry(link_frame, font=("微软雅黑", 10))
        self.scrape_link.pack(fill=tk.X, pady=5)
        self.scrape_link.insert(0, "https://t.me/group_name 或 @group_name")

        ttk.Button(link_frame, text="➕ 添加到列表", width=15,
                  command=self.add_scrape_target).pack(anchor=tk.W)

        # 目标列表
        targets_frame = ttk.LabelFrame(left, text="📋 采集目标列表", padding="10")
        targets_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        list_frame = ttk.Frame(targets_frame)
        list_frame.pack(fill=tk.BOTH, expand=True)

        self.scrape_targets = tk.Listbox(list_frame, font=("微软雅黑", 10), height=8)
        self.scrape_targets.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)

        targets_scroll = ttk.Scrollbar(list_frame, orient=tk.VERTICAL,
                                       command=self.scrape_targets.yview)
        targets_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.scrape_targets.config(yscrollcommand=targets_scroll.set)

        btn_frame = ttk.Frame(targets_frame)
        btn_frame.pack(fill=tk.X, pady=(5, 0))
        ttk.Button(btn_frame, text="🗑️ 删除选中", width=12,
                  command=self.remove_scrape_target).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="🧹 清空列表", width=12,
                  command=self.clear_scrape_targets).pack(side=tk.LEFT, padx=2)

        # 过滤选项
        filter_frame = ttk.LabelFrame(left, text="🔍 过滤条件", padding="10")
        filter_frame.pack(fill=tk.X)

        self.filter_active = tk.BooleanVar(value=True)
        ttk.Checkbutton(filter_frame, text="仅采集活跃用户(7天内发言)",
                       variable=self.filter_active).pack(anchor=tk.W, pady=2)

        self.filter_bot = tk.BooleanVar(value=True)
        ttk.Checkbutton(filter_frame, text="排除机器人账号",
                       variable=self.filter_bot).pack(anchor=tk.W, pady=2)

        self.filter_username = tk.BooleanVar(value=False)
        ttk.Checkbutton(filter_frame, text="仅采集有用户名的用户",
                       variable=self.filter_username).pack(anchor=tk.W, pady=2)

        limit_sub_frame = ttk.Frame(filter_frame)
        limit_sub_frame.pack(fill=tk.X, pady=(10, 0))
        ttk.Label(limit_sub_frame, text="采集数量限制:").pack(side=tk.LEFT)
        self.scrape_limit = tk.IntVar(value=500)
        ttk.Spinbox(limit_sub_frame, from_=10, to=10000, textvariable=self.scrape_limit,
                   width=12).pack(side=tk.LEFT, padx=(10, 0))

        # ========== 右侧:采集结果 ==========
        right = ttk.Frame(paned)
        paned.add(right, weight=2)

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

        # 操作按钮
        action_frame = ttk.Frame(right)
        action_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Button(action_frame, text="✅ 全选", width=10,
                  command=self.select_all_collected).pack(side=tk.LEFT, padx=2)
        ttk.Button(action_frame, text="❌ 清空", width=10,
                  command=self.deselect_all_collected).pack(side=tk.LEFT, padx=2)
        ttk.Button(action_frame, text="📤 导出到私信广告", width=18,
                  command=self.export_to_messaging).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="💾 保存为文件", width=15,
                  command=self.save_collected).pack(side=tk.LEFT, padx=2)

        self.collected_stats = ttk.Label(action_frame, text="已采集 0 个用户,已选 0 个",
                                         font=("微软雅黑", 9))
        self.collected_stats.pack(side=tk.RIGHT, padx=10)

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

    # ========== 配置管理 ==========

    def save_config(self):
        """保存配置"""
        try:
            config = {
                "thread_count": self.thread_count.get(),
                "thread_interval": self.thread_interval.get(),
                "per_account_limit": self.per_account_limit.get(),
                "total_limit": self.total_limit.get(),
                "interval_min": self.interval_min.get(),
                "interval_max": self.interval_max.get(),
                "auto_switch": self.auto_switch.get(),
                "auto_retry": self.auto_retry.get(),
                "send_type": self.send_type.get(),
                "hide_source": self.hide_source.get(),
                "message_text": self.message_text.get("1.0", tk.END).strip(),
                "forward_urls": self.forward_urls_text.get("1.0", tk.END).strip(),
                "targets": self.target_text.get("1.0", tk.END).strip(),
                "scrape_limit": self.scrape_limit.get(),
                "filter_active": self.filter_active.get(),
                "filter_bot": self.filter_bot.get(),
                "filter_username": self.filter_username.get()
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
            self.interval_min.set(config.get("interval_min", 3))
            self.interval_max.set(config.get("interval_max", 8))
            self.auto_switch.set(config.get("auto_switch", True))
            self.auto_retry.set(config.get("auto_retry", False))
            self.send_type.set(config.get("send_type", "text"))
            self.hide_source.set(config.get("hide_source", False))

            self.message_text.delete("1.0", tk.END)
            self.message_text.insert("1.0", config.get("message_text", ""))

            self.forward_urls_text.delete("1.0", tk.END)
            self.forward_urls_text.insert("1.0", config.get("forward_urls", ""))

            self.target_text.delete("1.0", tk.END)
            self.target_text.insert("1.0", config.get("targets", ""))

            self.scrape_limit.set(config.get("scrape_limit", 500))
            self.filter_active.set(config.get("filter_active", True))
            self.filter_bot.set(config.get("filter_bot", True))
            self.filter_username.set(config.get("filter_username", False))

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
                # 123.session → 123.json（不是 123.session.json）
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
                    # 没有 JSON 文件，尝试自动生成
                    json_data = self.generate_json_from_session(session_file)
                
                # 如果有 JSON 数据，提取信息
                if json_data:
                    # 提取手机号
                    phone = json_data.get('phone')
                    if phone:
                        account["phone"] = str(phone)
                    
                    # 提取用户名
                    username = json_data.get('username')
                    if username:
                        account["username"] = f"@{username}" if not username.startswith('@') else username
                    
                    # 提取姓名（first_name + last_name）
                    first_name = json_data.get('first_name', '')
                    last_name = json_data.get('last_name', '')
                    if first_name:
                        full_name = f"{first_name} {last_name}".strip() if last_name else first_name
                        account["first_name"] = full_name
                    
                    # 提取代理信息
                    proxy = json_data.get('proxy')
                    if proxy:
                        account["proxy"] = proxy
                    
                    # 提取 2FA 状态（检测 twoFA 和 passwordFA）
                    twofa = json_data.get('twoFA')
                    passwordfa = json_data.get('passwordFA')
                    
                    # 优先显示 twoFA，如果没有则显示 passwordFA
                    if twofa:
                        account["2fa"] = str(twofa)
                    elif passwordfa:
                        account["2fa"] = str(passwordfa)
                    else:
                        account["2fa"] = ""
                    
                    # 提取状态
                    spamblock = json_data.get('spamblock', '').lower()
                    if spamblock == 'free':
                        account["status"] = "✅ 无限制（来自JSON）"
                    elif spamblock == 'permanent':
                        account["status"] = "⚠️ 永久双向限制（来自JSON）"
                    elif spamblock:
                        account["status"] = f"⚠️ {spamblock}（来自JSON）"
                
                self.accounts.append(account)

            self.log(f"📂 自动加载 {len(session_files)} 个账号")
        except Exception as e:
            self.log(f"⚠️ 加载账号失败: {str(e)}")

    def refresh_accounts(self):
        """刷新账号列表(重新扫描 accounts 文件夹)"""
        try:
            self.log("🔄 刷新账号列表...")

            # 清空现有账号
            self.accounts.clear()

            # 重新加载
            self.load_accounts()

            # 刷新显示
            self.refresh_account_tree()
            self.update_account_stats()

            self.log(f"✅ 刷新完成,当前 {len(self.accounts)} 个账号")
        except Exception as e:
            self.log(f"❌ 刷新失败: {str(e)}")

    # ========== 账号管理功能 ==========

    def import_sessions(self):
        """导入 Session 文件夹"""
        folder = filedialog.askdirectory(title="选择 Session 文件夹")
        if not folder:
            return

        self.log(f"📁 正在扫描文件夹: {folder}")

        # 扫描 .session 文件
        folder_path = Path(folder)
        session_files = list(folder_path.glob("*.session"))

        added = 0
        for session_file in session_files:
            # 检查是否已存在
            if any(Path(acc["path"]).name == session_file.name for acc in self.accounts):
                self.log(f"  ⚠️ 跳过已存在: {session_file.name}")
                continue

            # 复制到 accounts 文件夹
            try:
                import shutil
                dest_path = Path(self.accounts_dir) / session_file.name
                shutil.copy2(session_file, dest_path)

                # 同时复制 .session-journal 文件(如果存在)
                journal_file = session_file.with_suffix('.session-journal')
                if journal_file.exists():
                    dest_journal = Path(self.accounts_dir) / journal_file.name
                    shutil.copy2(journal_file, dest_journal)
                
                # 同时复制 .json 文件(如果存在) - 账号信息文件
                # 123.session → 123.json（不是 123.session.json）
                json_file = session_file.parent / f"{session_file.stem}.json"
                json_data = None
                
                if json_file.exists():
                    dest_json = Path(self.accounts_dir) / json_file.name
                    shutil.copy2(json_file, dest_json)
                    self.log(f"    📄 已复制配套 JSON 文件")
                    
                    # 读取 JSON
                    try:
                        import json
                        with open(json_file, 'r', encoding='utf-8') as f:
                            json_data = json.load(f)
                    except:
                        pass
                else:
                    # 没有 JSON 文件，尝试自动生成
                    self.log(f"    ⚠️ 未找到 JSON 文件，正在自动生成...")
                    json_data = self.generate_json_from_session(dest_path)

                # 创建账号记录（import_sessions）
                account = {
                    "path": str(dest_path),
                    "selected": True,
                    "status": "未检测",
                    "username": "-",
                    "phone": "-",
                    "first_name": "-",
                    "proxy": "直连",
                    "2fa": "",
                    "last_login": "-"
                }
                
                # 如果有 JSON 数据，提取信息
                if json_data:
                    # 提取手机号
                    phone = json_data.get('phone')
                    if phone:
                        account["phone"] = str(phone)
                    
                    # 提取用户名
                    username = json_data.get('username')
                    if username:
                        account["username"] = f"@{username}" if not username.startswith('@') else username
                    
                    # 提取姓名（first_name + last_name）
                    first_name = json_data.get('first_name', '')
                    last_name = json_data.get('last_name', '')
                    if first_name:
                        full_name = f"{first_name} {last_name}".strip() if last_name else first_name
                        account["first_name"] = full_name
                    
                    # 提取代理信息
                    proxy = json_data.get('proxy')
                    if proxy:
                        account["proxy"] = proxy
                    
                    # 提取 2FA 状态（检测 twoFA 和 passwordFA）
                    twofa = json_data.get('twoFA')
                    passwordfa = json_data.get('passwordFA')
                    
                    # 优先显示 twoFA，如果没有则显示 passwordFA
                    if twofa:
                        account["2fa"] = str(twofa)
                    elif passwordfa:
                        account["2fa"] = str(passwordfa)
                    else:
                        account["2fa"] = ""
                    
                    # 提取状态
                    spamblock = json_data.get('spamblock', '').lower()
                    if spamblock == 'free':
                        account["status"] = "✅ 无限制（来自JSON）"
                    elif spamblock == 'permanent':
                        account["status"] = "⚠️ 永久双向限制（来自JSON）"
                    elif spamblock:
                        account["status"] = f"⚠️ {spamblock}（来自JSON）"
                    
                    self.log(f"    📋 已读取 JSON 信息: {account['username']} ({account['phone']})")
                
                self.accounts.append(account)
                added += 1

                self.log(f"  ✅ 已导入: {session_file.name}")

            except Exception as e:
                self.log(f"  ❌ 复制失败: {session_file.name} - {str(e)}")

        self.log(f"✅ 新增 {added} 个账号,当前总数: {len(self.accounts)}")
        self.refresh_account_tree()
        self.save_config()

    def toggle_account(self, event):
        """双击切换账号选择"""
        selection = self.account_tree.selection()
        if not selection:
            return

        item = selection[0]
        index = self.account_tree.index(item)

        self.accounts[index]["selected"] = not self.accounts[index]["selected"]

        # 复选框：☑ (已选) 或 ☐ (未选)
        check = "☑" if self.accounts[index]["selected"] else "☐"
        values = list(self.account_tree.item(item, "values"))
        values[0] = check
        self.account_tree.item(item, values=tuple(values))

        self.update_account_stats()
        self.update_selected_count()

    def select_all(self):
        """全选账号"""
        for i, account in enumerate(self.accounts):
            account["selected"] = True
            item = self.account_tree.get_children()[i]
            values = list(self.account_tree.item(item, "values"))
            values[0] = "☑"
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
            values[0] = "☐"
            self.account_tree.item(item, values=tuple(values))

        self.log("❌ 已清空所有选择")
        self.update_account_stats()
        self.update_selected_count()
    
    def show_delete_menu(self, button):
        """显示删除菜单"""
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="删除选择的账号", command=self.delete_selected)
        menu.add_command(label="删除全部账号", command=self.delete_all)
        menu.add_separator()
        menu.add_command(label="删除失效账号", command=self.delete_invalid)
        menu.add_command(label="删除冻结账号", command=self.delete_frozen)
        menu.add_command(label="删除封禁账号", command=self.delete_banned)
        
        # 在按钮下方显示菜单
        x = button.winfo_rootx()
        y = button.winfo_rooty() + button.winfo_height()
        menu.post(x, y)
    
    def show_export_menu(self, button):
        """显示导出菜单"""
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="导出选择的账号", command=self.export_selected)
        menu.add_command(label="导出全部账号", command=self.export_all)
        menu.add_separator()
        menu.add_command(label="导出失效账号", command=self.export_invalid)
        menu.add_command(label="导出冻结账号", command=self.export_frozen)
        menu.add_command(label="导出封禁账号", command=self.export_banned)
        
        # 在按钮下方显示菜单
        x = button.winfo_rootx()
        y = button.winfo_rooty() + button.winfo_height()
        menu.post(x, y)

    # ========== 辅助函数 ==========
    
    def generate_json_from_session(self, session_file):
        """
        从 session 文件生成基础 JSON 文件
        返回: JSON 数据字典，失败返回 None
        """
        import sqlite3
        
        try:
            conn = sqlite3.connect(session_file)
            cursor = conn.cursor()
            
            # 尝试从 entities 表读取自己的信息
            # entities 表可能包含用户自己的记录
            cursor.execute("SELECT id, username, phone, name FROM entities ORDER BY id LIMIT 1")
            row = cursor.fetchone()
            
            conn.close()
            
            if row:
                entity_id, username, phone, name = row
                
                # 生成基础 JSON
                json_data = {
                    "app_id": self.api_id,
                    "app_hash": self.api_hash,
                    "id": entity_id if entity_id > 0 else None,
                    "phone": str(phone) if phone else None,
                    "username": username,
                    "first_name": name if name else None,
                    "last_name": None,
                    "twoFA": None,
                    "proxy": None,
                    "spamblock": None,
                    "session_file": session_file.stem,
                    "session_created_date": None,
                    "last_connect_date": None
                }
                
                # 保存 JSON 文件
                json_file = session_file.parent / f"{session_file.stem}.json"
                import json
                with open(json_file, 'w', encoding='utf-8') as f:
                    json.dump(json_data, f, indent=2, ensure_ascii=False)
                
                self.log(f"    ✨ 已生成 JSON 文件")
                return json_data
            
            return None
            
        except Exception as e:
            self.log(f"    ⚠️ 生成 JSON 失败: {str(e)[:50]}")
            return None
    
    def convert_session_file(self, session_file):
        """
        转换 session 文件（移除 tmp_auth_key 列）
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
            
            # 2. 转换 sessions 表（6列 → 5列）
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
            
            # 月份映射（英文和俄文）
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

        # 获取并发配置
        concurrent = self.check_concurrent.get()
        self.log(f"🔍 开始检测账号状态... (并发: {concurrent})")
        
        thread = threading.Thread(target=self.run_check_accounts)
        thread.start()

    def run_check_accounts(self):
        """运行账号检测"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.check_accounts_async())

    async def check_single_account(self, account, index, total):
        """检测单个账号（并发调用）"""
        # SpamBot 关键词库（多语言，不翻译）
        
        # 1. 正常状态（多语言）
        NORMAL_KEYWORDS = [
            # 英文
            "good news", "no limits", "free as a bird", "no restrictions", "all good",
            # 俄语
            "свободен от каких-либо ограничений", "свободен", "ограничений",
            # 葡萄牙语
            "nenhum limite", "livre como",
        ]
        
        # 2. 地理受限
        GEO_RESTRICTED_KEYWORDS = [
            "phone numbers may trigger",
            "some phone numbers may trigger",
        ]
        
        # 3. 冻结（包含所有冻结相关的关键词）
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
        
        # 5. 临时限制（多语言）
        TEMP_LIMITED_KEYWORDS = [
            # 英文
            "limited until", "automatically released on", "account is now limited",
            # 俄语
            "ограничен до", "до",
        ]

        self.log(f"[{index+1}/{total}] 检测: {Path(account['path']).stem}")

        try:
            # 获取并规范化路径
            path = str(Path(account["path"]).resolve())
            
            self.log(f"  🔍 规范化路径: {path}")
            
            # 检查文件是否存在
            if not Path(path).exists():
                self.log(f"  ❌ 文件不存在")
                account["status"] = "⚠️ 文件不存在"
                self.root.after(0, self.refresh_account_tree)
                return
            
            # 检查文件大小
            file_size = Path(path).stat().st_size
            self.log(f"  📏 文件大小: {file_size} bytes")
            
            if file_size < 1000:
                self.log(f"  ❌ 文件太小，可能损坏")
                account["status"] = "⚠️ 文件损坏"
                self.root.after(0, self.refresh_account_tree)
                return
            
            self.log(f"  ✅ 开始创建客户端...")
            
            # 创建 TelegramClient（可能失败）
            try:
                client = TelegramClient(path, self.api_id, self.api_hash)
            except ValueError as ve:
                # Session 文件格式错误，尝试自动转换
                self.log(f"  ⚠️ 检测到格式错误，正在自动转换...")
                
                if self.convert_session_file(path):
                    self.log(f"  ✅ 转换成功，重新创建客户端...")
                    try:
                        client = TelegramClient(path, self.api_id, self.api_hash)
                        self.log(f"  ✅ 客户端创建成功（已转换）")
                    except Exception as retry_error:
                        account["status"] = "⚠️ 转换后仍失败"
                        account["username"] = "-"
                        account["phone"] = "-"
                        self.log(f"  ❌ 转换后仍然失败: {type(retry_error).__name__}")
                        self.root.after(0, self.refresh_account_tree)
                        return
                else:
                    account["status"] = "⚠️ 转换失败"
                    account["username"] = "-"
                    account["phone"] = "-"
                    self.log(f"  ❌ 自动转换失败")
                    self.root.after(0, self.refresh_account_tree)
                    return
                    
            except Exception as ce:
                # 其他创建错误
                account["status"] = "⚠️ 客户端创建失败"
                account["username"] = "-"
                account["phone"] = "-"
                self.log(f"  ❌ 客户端创建失败: {type(ce).__name__}")
                self.root.after(0, self.refresh_account_tree)
                return
            
            if 'client' not in locals():
                self.log(f"  ✅ 客户端创建成功")
            
            try:
                await client.connect()
            except Exception as e:
                error_type = type(e).__name__
                error_str = str(e).lower()
                
                # AuthKeyDuplicatedError - 重复登录
                if "authkey" in error_type.lower() and "duplicated" in error_type.lower():
                    account["status"] = "⚠️ 重复登录"
                    account["username"] = "-"
                    account["phone"] = "-"
                    self.log(f"  ⚠️ 重复登录（同一账号在其他地方使用中）")
                    self.root.after(0, self.refresh_account_tree)
                    return
                else:
                    raise  # 其他连接错误继续抛出

            # 1. 尝试登录
            try:
                me = await client.get_me()
                if not me:
                    account["status"] = "🚫 封禁"
                    account["username"] = "-"
                    account["phone"] = "-"
                    self.log(f"  🚫 封禁")
                    await client.disconnect()
                    self.root.after(0, self.refresh_account_tree)
                    return

                account["username"] = f"@{me.username}" if me.username else "-"
                account["phone"] = me.phone or "-"

            except Exception as e:
                error_type = type(e).__name__
                error_str = str(e).lower()

                if "authkey" in error_str or "unauthorized" in error_str or "banned" in error_str:
                    account["status"] = "🚫 封禁"
                    account["username"] = "-"
                    account["phone"] = "-"
                    self.log(f"  🚫 封禁")
                elif "timeout" in error_str or "connection" in error_str or "network" in error_str:
                    account["status"] = "⚠️ 连接错误"
                    account["username"] = "-"
                    account["phone"] = "-"
                    self.log(f"  ⚠️ 连接错误")
                else:
                    account["status"] = "🚫 封禁"
                    account["username"] = "-"
                    account["phone"] = "-"
                    self.log(f"  🚫 封禁")

                await client.disconnect()
                self.root.after(0, self.refresh_account_tree)
                return

            # 2. 向 @spambot 发送消息检测状态
            try:
                await client.send_message("@spambot", "/start")
                await asyncio.sleep(2)

                messages = await client.get_messages("@spambot", limit=1)

                if messages and len(messages) > 0:
                    response = (messages[0].message or "").strip().lower()
                    
                    # 优先级判断（多语言关键词，不翻译）
                    # 1. 地理受限
                    if any(keyword in response for keyword in GEO_RESTRICTED_KEYWORDS):
                        account["status"] = "✅ 无限制（地理受限）"
                        self.log(f"  ✅ 无限制（地理受限）: {account['username']}")
                    
                    # 2. 冻结（包含所有冻结场景）
                    elif any(keyword in response for keyword in FROZEN_KEYWORDS):
                        appeal_time = self.parse_limitation_time(response)
                        if appeal_time:
                            time_str = appeal_time.strftime("%Y-%m-%d")
                            account["status"] = f"🚫 冻结（申诉至 {time_str}）"
                            self.log(f"  🚫 冻结: {account['username']}, 申诉至: {time_str}")
                        else:
                            account["status"] = "🚫 冻结"
                            self.log(f"  🚫 冻结: {account['username']}")
                    
                    # 3. 永久双向限制
                    elif any(keyword in response for keyword in PERMANENT_LIMITED_KEYWORDS):
                        account["status"] = "⚠️ 永久双向限制"
                        self.log(f"  ⚠️ 永久双向限制: {account['username']}")
                        self.log(f"     说明: 不能给陌生人发消息，但可以回复")
                    
                    # 4. 临时限制（有到期时间）
                    elif any(keyword in response for keyword in TEMP_LIMITED_KEYWORDS):
                        release_time = self.parse_limitation_time(response)
                        if release_time:
                            now = datetime.utcnow()
                            remaining = release_time - now
                            if remaining.total_seconds() > 0:
                                days = remaining.days
                                hours = remaining.seconds // 3600
                                account["status"] = f"⚠️ 临时限制（剩余 {days}天{hours}时）"
                                self.log(f"  ⚠️ 临时限制: {account['username']}, 剩余: {days}天{hours}时")
                            else:
                                account["status"] = "⚠️ 临时限制（已过期）"
                                self.log(f"  ⚠️ 临时限制（已过期）: {account['username']}")
                        else:
                            account["status"] = "⚠️ 临时垃圾邮件"
                            self.log(f"  ⚠️ 临时垃圾邮件: {account['username']}")
                    
                    # 5. 无限制
                    elif any(keyword in response for keyword in NORMAL_KEYWORDS):
                        account["status"] = "✅ 无限制"
                        self.log(f"  ✅ 无限制: {account['username']}")
                    
                    # 6. 未知
                    else:
                        account["status"] = "⚠️ 未知状态"
                        self.log(f"  ⚠️ 未知状态: {account['username']}")
                        self.log(f"     SpamBot 回复: {response[:100]}")
                    
                    self.root.after(0, self.refresh_account_tree)
                else:
                    account["status"] = "⚠️ 无回复"
                    self.log(f"  ⚠️ SpamBot 无回复")
                    self.root.after(0, self.refresh_account_tree)

            except Exception as e:
                error_type = type(e).__name__
                
                # YouBlockedUserError - 拉黑了 SpamBot，尝试自动取消拉黑
                if "youblocked" in error_type.lower():
                    self.log(f"  ⚠️ 检测到已拉黑 SpamBot，正在自动取消拉黑...")
                    
                    try:
                        # 取消拉黑 @spambot
                        await client.unblock_user("@spambot")
                        self.log(f"  ✅ 已取消拉黑 SpamBot")
                        await asyncio.sleep(1)
                        
                        # 重试检测
                        self.log(f"  🔄 重新检测...")
                        await client.send_message("@spambot", "/start")
                        await asyncio.sleep(2)
                        
                        messages = await client.get_messages("@spambot", limit=1)
                        
                        if messages and len(messages) > 0:
                            response = (messages[0].message or "").strip().lower()
                            
                            # 重新判断状态（使用相同的逻辑）
                            if any(keyword in response for keyword in GEO_RESTRICTED_KEYWORDS):
                                account["status"] = "✅ 无限制（地理受限）"
                                self.log(f"  ✅ 无限制（地理受限）: {account['username']}")
                            elif any(keyword in response for keyword in FROZEN_KEYWORDS):
                                account["status"] = "🚫 冻结"
                                self.log(f"  🚫 冻结: {account['username']}")
                            elif any(keyword in response for keyword in PERMANENT_LIMITED_KEYWORDS):
                                account["status"] = "⚠️ 永久双向限制"
                                self.log(f"  ⚠️ 永久双向限制: {account['username']}")
                            elif any(keyword in response for keyword in TEMP_LIMITED_KEYWORDS):
                                account["status"] = "⚠️ 临时限制"
                                self.log(f"  ⚠️ 临时限制: {account['username']}")
                            elif any(keyword in response for keyword in NORMAL_KEYWORDS):
                                account["status"] = "✅ 无限制"
                                self.log(f"  ✅ 无限制: {account['username']}")
                            else:
                                account["status"] = "⚠️ 未知状态"
                                self.log(f"  ⚠️ 未知状态: {account['username']}")
                        else:
                            account["status"] = "⚠️ 无回复"
                            self.log(f"  ⚠️ SpamBot 无回复")
                        
                    except Exception as retry_error:
                        account["status"] = "⚠️ 取消拉黑失败"
                        self.log(f"  ❌ 取消拉黑失败: {type(retry_error).__name__}")
                
                # 其他错误
                else:
                    account["status"] = f"⚠️ 检测失败"
                    self.log(f"  ⚠️ SpamBot 检测失败: {error_type}")
                
                self.root.after(0, self.refresh_account_tree)

            account["last_login"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            
            # 确保断开连接
            try:
                await client.disconnect()
            except:
                pass  # 忽略断开连接时的错误

        except Exception as e:
            account["status"] = "⚠️ 检测失败"
            self.log(f"  ⚠️ 检测失败: {type(e).__name__}")
            self.log(f"     错误: {str(e)[:100]}")
            import traceback
            self.log(f"     追踪: {traceback.format_exc()[:200]}")
            self.root.after(0, self.refresh_account_tree)
            
            # 确保断开连接
            try:
                if 'client' in locals():
                    await client.disconnect()
            except:
                pass  # 忽略断开连接时的错误

    async def check_accounts_async(self):
        """并发批量检测账号"""
        concurrent = self.check_concurrent.get()  # 并发数量
        batch_delay = self.check_batch_delay.get()  # 批次间隔
        total = len(self.accounts)
        
        self.log(f"📊 并发配置: 每批 {concurrent} 个账号，批次间隔 {batch_delay} 秒")
        
        # 分批处理
        for i in range(0, total, concurrent):
            batch = self.accounts[i:i+concurrent]
            batch_num = i // concurrent + 1
            total_batches = (total + concurrent - 1) // concurrent
            
            self.log(f"🔄 批次 {batch_num}/{total_batches}: 检测 {len(batch)} 个账号...")
            
            # 并发检测一批
            tasks = [self.check_single_account(acc, i+j, total) for j, acc in enumerate(batch)]
            await asyncio.gather(*tasks)
            
            # 批次间隔
            if i + concurrent < total:
                self.log(f"⏳ 等待 {batch_delay} 秒后继续下一批...")
                await asyncio.sleep(batch_delay)
        
        self.log("✅ 账号检测完成")
        
        # 统计各状态数量
        normal_count = sum(1 for acc in self.accounts if "✅ 无限制" in acc["status"])
        limited_count = sum(1 for acc in self.accounts if "⚠️ 永久双向限制" in acc["status"])
        frozen_count = sum(1 for acc in self.accounts if "🚫 冻结" in acc["status"])
        banned_count = sum(1 for acc in self.accounts if "🚫 封禁" in acc["status"])
        temp_limited_count = sum(1 for acc in self.accounts if "⚠️ 临时限制" in acc["status"])
        other_count = total - normal_count - limited_count - frozen_count - banned_count - temp_limited_count
        
        self.log("=" * 50)
        self.log("📊 检测结果统计：")
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

    def delete_invalid(self):
        """删除失效账号(同步删除文件)"""
        self._delete_by_status("失效", ["❌"])

    def delete_selected(self):
        """删除选择的账号"""
        selected_accounts = [acc for acc in self.accounts if acc["selected"]]
        
        if not selected_accounts:
            messagebox.showinfo("提示", "没有选择任何账号")
            return
        
        confirm = messagebox.askyesno("确认删除",
            f"确定要删除 {len(selected_accounts)} 个选择的账号吗?\n"
            f"(同时删除文件)")
        if not confirm:
            return
        
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
            f"此操作不可恢复！")
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
            # 123.session → 123.json（不是 123.session.json）
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
    
    def _export_accounts(self, accounts, export_name):
        """通用导出函数"""
        if not accounts:
            messagebox.showinfo("提示", f"没有{export_name}")
            return
        
        # 选择导出文件夹
        export_folder = filedialog.askdirectory(title=f"选择导出文件夹（{export_name}）")
        if not export_folder:
            return
        
        export_path = Path(export_folder)
        exported_count = 0
        
        for acc in accounts:
            try:
                import shutil
                session_path = Path(acc["path"])
                
                # 复制 session 文件
                if session_path.exists():
                    dest_session = export_path / session_path.name
                    shutil.copy2(session_path, dest_session)
                    exported_count += 1
                
                # 复制 session-journal 文件(如果存在)
                journal_path = session_path.with_suffix('.session-journal')
                if journal_path.exists():
                    dest_journal = export_path / journal_path.name
                    shutil.copy2(journal_path, dest_journal)
                
                # 复制 json 文件(如果存在)
                # 123.session → 123.json（不是 123.session.json）
                json_path = session_path.parent / f"{session_path.stem}.json"
                if json_path.exists():
                    dest_json = export_path / json_path.name
                    shutil.copy2(json_path, dest_json)
                    self.log(f"  📤 已导出: {session_path.name} (含JSON)")
                else:
                    self.log(f"  📤 已导出: {session_path.name}")
                
            except Exception as e:
                self.log(f"  ⚠️ 导出失败: {session_path.name} - {str(e)}")
        
        self.log(f"📤 导出完成: {exported_count}/{len(accounts)} 个{export_name}")
        messagebox.showinfo("导出完成", f"成功导出 {exported_count} 个账号到:\n{export_folder}")

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
        """更新已选账号数量"""
        selected = sum(1 for acc in self.accounts if acc["selected"])
        self.selected_count_label.config(text=f"✓ 已选择 {selected} 个账号")

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

        self.target_count_label.config(text=f"共 {len(lines)} 个目标用户")
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

            self.target_count_label.config(text=f"共 {len(lines)} 个目标用户")
            self.log(f"📄 从文件导入 {len(users)} 个用户")

        except Exception as e:
            messagebox.showerror("错误", f"导入失败: {str(e)}")

    def clear_targets(self):
        """清空目标列表"""
        self.target_text.delete("1.0", tk.END)
        self.target_count_label.config(text="共 0 个目标用户")
        self.log("🗑️ 已清空目标用户列表")

    # ========== 采集用户功能 ==========

    def add_scrape_target(self):
        """添加采集目标"""
        link = self.scrape_link.get().strip()

        if not link or link.startswith("https://t.me/") and len(link) <= 15:
            messagebox.showwarning("提示", "请输入有效的群组/频道链接或用户名")
            return

        # 检查是否已存在
        existing = [self.scrape_targets.get(i) for i in range(self.scrape_targets.size())]
        if link in existing:
            messagebox.showinfo("提示", "该目标已存在")
            return

        self.scrape_targets.insert(tk.END, link)
        self.log(f"➕ 添加采集目标: {link}")

    def remove_scrape_target(self):
        """删除选中的采集目标"""
        selection = self.scrape_targets.curselection()
        if not selection:
            messagebox.showwarning("提示", "请先选择要删除的目标")
            return

        for index in reversed(selection):
            self.scrape_targets.delete(index)

        self.log("🗑️ 已删除选中的采集目标")

    def clear_scrape_targets(self):
        """清空采集目标列表"""
        self.scrape_targets.delete(0, tk.END)
        self.log("🧹 已清空采集目标列表")

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
        """保存采集结果"""
        selected = [user for user in self.collected_users if user.get("selected", False)]

        if not selected:
            messagebox.showwarning("提示", "请先选择要保存的用户")
            return

        filename = filedialog.asksaveasfilename(
            title="保存用户列表",
            defaultextension=".txt",
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")]
        )

        if not filename:
            return

        try:
            with open(filename, "w", encoding="utf-8") as f:
                for user in selected:
                    f.write(f"{user['username']}\n")

            self.log(f"💾 已保存 {len(selected)} 个用户到文件")
            messagebox.showinfo("成功", f"已保存 {len(selected)} 个用户")

        except Exception as e:
            messagebox.showerror("错误", f"保存失败: {str(e)}")

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
            f"自动切换: {'是' if self.auto_switch.get() else '否'}\n\n"
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
        """异步发送消息(真正并发)"""
        self.total_sent = 0
        self.total_failed = 0
        self.send_lock = asyncio.Lock()

        # 记录每个账号的发送统计
        self.account_stats = {}  # {account_name: {"sent": 0, "failed": 0}}

        thread_count = self.thread_count.get()

        for batch_start in range(0, len(selected_accounts), thread_count):
            if not self.is_running:
                self.log("⏸️ 任务已停止")
                break

            batch = selected_accounts[batch_start:batch_start + thread_count]

            self.log(f"\n🔄 启动批次 {batch_start//thread_count + 1}: {len(batch)} 个账号并发")

            tasks = []
            for i, account in enumerate(batch):
                task = self.send_with_account(account, batch_start + i + 1, len(selected_accounts))
                tasks.append(task)

            await asyncio.gather(*tasks, return_exceptions=True)

            if batch_start + thread_count < len(selected_accounts):
                self.log(f"⏱️ 批次完成,等待 {self.thread_interval.get()} 秒启动下一批...")
                await asyncio.sleep(self.thread_interval.get())

        # 显示总体统计
        self.log(f"\n" + "="*50)
        self.log(f"✅ 任务完成!")
        self.log(f"📊 总计成功: {self.total_sent} 条")
        self.log(f"❌ 总计失败: {self.total_failed} 条")
        self.log("="*50)

        # 显示每个账号的统计
        if self.account_stats:
            self.log(f"\n📈 各账号发送统计:")
            for account_name, stats in sorted(self.account_stats.items()):
                success = stats.get("sent", 0)
                failed = stats.get("failed", 0)
                total = success + failed
                success_rate = (success / total * 100) if total > 0 else 0
                self.log(f"  📱 {account_name}: ✅ {success} 条 | ❌ {failed} 条 | 成功率 {success_rate:.1f}%")

        self.log("="*50)

        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.is_running = False

    async def send_with_account(self, account, index, total):
        """使用单个账号发送"""
        self.log(f"\n[{index}/{total}] 📱 启动账号: {Path(account['path']).stem}")

        try:
            client = TelegramClient(account["path"], self.api_id, self.api_hash)
            await client.connect()

            me = await client.get_me()
            account_name = me.username or me.phone or str(me.id)
            self.log(f"  ✅ 已登录: @{account_name}")

            # 初始化账号统计
            if account_name not in self.account_stats:
                self.account_stats[account_name] = {"sent": 0, "failed": 0}

            account_sent = 0
            success_targets = []  # 记录发送成功的用户

            for target in self.targets[:]:  # 复制列表避免修改时出错
                if not self.is_running:
                    break

                if account_sent >= self.per_account_limit.get():
                    self.log(f"  ⚠️ [{account_name}] 达到单账号上限 ({self.per_account_limit.get()})")
                    break

                async with self.send_lock:
                    if self.total_sent >= self.total_limit.get():
                        self.log(f"  ⚠️ 达到任务总上限 ({self.total_limit.get()})")
                        self.is_running = False
                        break

                try:
                    username = target.lstrip("@")

                    # 根据发送类型执行不同操作
                    if self.send_type.get() == "forward":
                        # 转发贴子模式 - 从多条链接中随机选择
                        forward_urls_text = self.forward_urls_text.get("1.0", tk.END).strip()
                        forward_urls = [line.strip() for line in forward_urls_text.split("\n")
                                       if line.strip() and line.strip().startswith("http")]

                        if not forward_urls:
                            self.log(f"  ⚠️ [{account_name}] 未设置转发链接,跳过: @{username}")
                            continue

                        # 随机选择一条链接
                        forward_url = random.choice(forward_urls)

                        # 解析转发链接
                        if "t.me/" in forward_url:
                            try:
                                # 提取频道/群组和消息ID
                                parts = forward_url.split("/")
                                if len(parts) >= 2:
                                    channel_username = parts[-2]
                                    message_id = int(parts[-1])

                                    # 获取原始消息
                                    channel = await client.get_entity(channel_username)
                                    message_obj = await client.get_messages(channel, ids=message_id)

                                    if message_obj:
                                        # 根据勾选状态决定转发方式
                                        if self.hide_source.get():
                                            # 隐藏来源:重新发送消息内容
                                            sent_msg = await client.send_message(
                                                username,
                                                message_obj.text or message_obj.message,
                                                file=message_obj.media if message_obj.media else None,
                                                silent=True
                                            )
                                        else:
                                            # 不隐藏来源:直接转发
                                            sent_msg = await client.forward_messages(
                                                username,
                                                message_obj
                                            )

                                        # 验证发送成功
                                        if not sent_msg or not sent_msg.id:
                                            raise Exception("发送失败,未收到消息ID")

                                        hide_text = "(隐藏来源)" if self.hide_source.get() else "(显示来源)"
                                        self.log(f"  ✅ [{account_name}] 转发成功: @{username} {hide_text} (msg_id: {sent_msg.id})")
                                    else:
                                        raise Exception("无法获取原始消息")
                                else:
                                    raise Exception("链接格式错误")
                            except ValueError:
                                self.log(f"  ❌ [{account_name}] 转发失败: @{username}")
                                self.log(f"      链接格式错误: {forward_url}")
                                async with self.send_lock:
                                    self.total_failed += 1
                                    self.account_stats[account_name]["failed"] += 1  # 账号统计
                                continue
                            except Exception as e:
                                self.log(f"  ❌ [{account_name}] 转发失败: @{username}")
                                self.log(f"      错误: {str(e)}")
                                async with self.send_lock:
                                    self.total_failed += 1
                                    self.account_stats[account_name]["failed"] += 1  # 账号统计
                                continue
                        else:
                            self.log(f"  ❌ [{account_name}] 转发失败: @{username} - 无效链接: {forward_url}")
                            async with self.send_lock:
                                self.total_failed += 1
                                self.account_stats[account_name]["failed"] += 1  # 账号统计
                            continue
                    else:
                        # 文本消息模式
                        message = self.message_text.get("1.0", tk.END).strip()
                        message = message.replace("{username}", username)

                        try:
                            user = await client.get_entity(username)
                            message = message.replace("{firstname}", user.first_name or "")
                        except:
                            pass

                        # 发送文本消息并确认
                        sent_msg = await client.send_message(username, message)

                        # 验证发送成功(检查返回的消息对象)
                        if not sent_msg or not sent_msg.id:
                            raise Exception("发送失败,未收到消息ID")

                        self.log(f"  ✅ [{account_name}] 发送成功: @{username} (msg_id: {sent_msg.id})")

                    account_sent += 1
                    success_targets.append(target)  # 记录成功

                    async with self.send_lock:
                        self.total_sent += 1
                        self.account_stats[account_name]["sent"] += 1  # 账号统计
                        current_total = self.total_sent

                    self.log(f"  📊 [{account_name}] 总计: {current_total} 条")

                    interval = random.uniform(self.interval_min.get(), self.interval_max.get())
                    await asyncio.sleep(interval)

                except errors.FloodWaitError as e:
                    wait_time = min(e.seconds, 300)  # 最多等待 5 分钟
                    self.log(f"  ⚠️ [{account_name}] 触发频率限制: @{username} - 需等待 {wait_time} 秒")
                    self.log(f"      详细: FloodWaitError - Telegram 要求等待 {e.seconds} 秒后再发送")
                    async with self.send_lock:
                        self.total_failed += 1
                        self.account_stats[account_name]["failed"] += 1  # 账号统计

                    if self.auto_switch.get():
                        self.log(f"  🔄 [{account_name}] 触发限制,切换下一个账号")
                        break  # 切换账号
                    else:
                        # 等待后重试当前用户
                        self.log(f"  ⏳ [{account_name}] 等待 {wait_time} 秒后重试...")
                        await asyncio.sleep(wait_time)
                        # 不增加计数,下次循环会重试这个用户
                        continue

                except errors.UserPrivacyRestrictedError as e:
                    self.log(f"  ❌ [{account_name}] 用户隐私限制: @{username}")
                    self.log(f"      详细: {str(e)}")
                    async with self.send_lock:
                        self.total_failed += 1
                        self.account_stats[account_name]["failed"] += 1  # 账号统计

                except errors.UserIsBlockedError as e:
                    self.log(f"  ❌ [{account_name}] 已被用户拉黑: @{username}")
                    self.log(f"      详细: {str(e)}")
                    async with self.send_lock:
                        self.total_failed += 1
                        self.account_stats[account_name]["failed"] += 1  # 账号统计

                except errors.PeerIdInvalidError as e:
                    self.log(f"  ❌ [{account_name}] 用户不存在或无效: @{username}")
                    self.log(f"      详细: {str(e)}")
                    async with self.send_lock:
                        self.total_failed += 1
                        self.account_stats[account_name]["failed"] += 1  # 账号统计

                except errors.ChatWriteForbiddenError as e:
                    self.log(f"  ❌ [{account_name}] 无权限发送消息: @{username}")
                    self.log(f"      详细: {str(e)}")
                    async with self.send_lock:
                        self.total_failed += 1
                        self.account_stats[account_name]["failed"] += 1  # 账号统计

                except errors.AuthKeyUnregisteredError as e:
                    self.log(f"  ❌ [{account_name}] 账号未授权(死号): {str(e)}")
                    async with self.send_lock:
                        self.total_failed += 1
                        self.account_stats[account_name]["failed"] += 1  # 账号统计
                    break  # 账号失效,切换账号

                except Exception as e:
                    error_str = str(e).lower()

                    # 检测 "Too many requests" 错误
                    if "too many requests" in error_str or "flood" in error_str:
                        # 尝试从错误信息中提取等待时间
                        import re
                        wait_match = re.search(r'(\d+)\s*second', error_str)
                        if wait_match:
                            wait_time = min(int(wait_match.group(1)), 300)  # 最多等待 5 分钟
                        else:
                            wait_time = 60  # 默认等待 60 秒

                        self.log(f"  ⚠️ [{account_name}] 触发请求限制: @{username}")
                        self.log(f"      错误: {str(e)}")
                        self.log(f"      自动等待: {wait_time} 秒")
                        async with self.send_lock:
                            self.total_failed += 1
                            self.account_stats[account_name]["failed"] += 1  # 账号统计

                        if self.auto_switch.get():
                            self.log(f"  🔄 [{account_name}] 触发限制,切换下一个账号")
                            break  # 切换账号
                        else:
                            # 自动等待后重试
                            self.log(f"  ⏳ [{account_name}] 等待 {wait_time} 秒后自动重试...")
                            await asyncio.sleep(wait_time)
                            continue

                    self.log(f"  ❌ [{account_name}] 发送失败: @{username}")
                    self.log(f"      错误类型: {type(e).__name__}")
                    self.log(f"      错误详情: {str(e)}")
                    async with self.send_lock:
                        self.total_failed += 1
                        self.account_stats[account_name]["failed"] += 1  # 账号统计

            # 从目标列表中删除发送成功的用户
            if success_targets:
                self.remove_successful_targets(success_targets)
                self.log(f"  🗑️ [{account_name}] 已从列表删除 {len(success_targets)} 个成功发送的用户")

            await client.disconnect()
            self.log(f"  📊 [{account_name}] 完成,本账号发送: {account_sent} 条")

        except Exception as e:
            self.log(f"  ❌ 账号错误: {type(e).__name__}")
            self.log(f"      详细: {str(e)}")

    def remove_successful_targets(self, success_targets):
        """从目标列表中删除成功发送的用户"""
        try:
            # 获取当前列表
            current = self.target_text.get("1.0", tk.END).strip()
            lines = [line.strip() for line in current.split("\n") if line.strip()]

            # 删除成功的
            remaining = [line for line in lines if line not in success_targets]

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

        # 获取采集目标
        targets = [self.scrape_targets.get(i) for i in range(self.scrape_targets.size())]

        if not targets:
            messagebox.showerror("错误", "请添加采集目标")
            return

        # 确认采集
        confirm = messagebox.askyesno(
            "确认采集",
            f"将使用 {len(selected_accounts)} 个账号\n"
            f"从 {len(targets)} 个目标采集用户\n\n"
            f"采集限制: {self.scrape_limit.get()} 个\n\n"
            f"是否继续?"
        )

        if not confirm:
            return

        # 更新按钮状态
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.is_running = True

        self.log("🚀 开始采集任务...")

        # 在新线程中运行
        thread = threading.Thread(target=self.run_scraping_task,
                                  args=(selected_accounts[0], targets))
        thread.start()

    def run_scraping_task(self, account, targets):
        """运行采集任务"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.scrape_users_async(account, targets))

    async def scrape_users_async(self, account, targets):
        """异步采集用户"""
        try:
            client = TelegramClient(account["path"], self.api_id, self.api_hash)
            await client.connect()

            me = await client.get_me()
            self.log(f"✅ 使用账号: @{me.username or me.phone}")

            collected_count = 0

            for target in targets:
                if not self.is_running:
                    break

                self.log(f"\n📌 采集目标: {target}")

                try:
                    # 获取群组/频道实体
                    entity = await client.get_entity(target)

                    # 获取成员
                    participants = await client.get_participants(entity, limit=self.scrape_limit.get())

                    for user in participants:
                        if not self.is_running:
                            break

                        # 应用过滤条件
                        if self.filter_bot.get() and user.bot:
                            continue

                        if self.filter_username.get() and not user.username:
                            continue

                        # 添加到结果
                        user_data = {
                            "username": f"@{user.username}" if user.username else f"user_{user.id}",
                            "name": f"{user.first_name or ''} {user.last_name or ''}".strip() or "未知",
                            "source": target,
                            "selected": False
                        }

                        # 检查是否已存在
                        if not any(u["username"] == user_data["username"] for u in self.collected_users):
                            self.collected_users.append(user_data)

                            self.result_tree.insert("", tk.END, values=(
                                "",
                                user_data["username"],
                                user_data["name"],
                                user_data["source"]
                            ))

                            collected_count += 1

                            if collected_count >= self.scrape_limit.get():
                                self.log(f"⚠️ 达到采集上限 ({self.scrape_limit.get()})")
                                break

                    self.log(f"✅ 从 {target} 采集 {len(participants)} 个用户")

                except Exception as e:
                    self.log(f"❌ 采集失败: {target} - {type(e).__name__}")

            await client.disconnect()

            self.log(f"\n" + "="*50)
            self.log(f"✅ 采集完成!")
            self.log(f"📊 总共采集 {collected_count} 个用户")
            self.log("="*50)

            self.update_collected_stats()

        except Exception as e:
            self.log(f"❌ 采集错误: {type(e).__name__}: {str(e)[:50]}")

        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.is_running = False


def main():
    root = tk.Tk()
    app = TGMassDM(root)
    root.mainloop()


if __name__ == "__main__":
    main()
