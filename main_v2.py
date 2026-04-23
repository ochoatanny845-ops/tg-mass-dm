"""
TG 批量私信系统 - 模块化版本 v2.0.0
主程序 - 整合所有模块

使用方法：
python main_v2.py
"""

import sys
import asyncio
import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox
from pathlib import Path
import threading
import json

# 导入配置
import config

# 导入模块
from modules.user_scraper import UserScraper
from modules.message_sender import MessageSender
from modules.account_manager import AccountManager
from modules.proxy_manager import ProxyManager

class TelegramMassDM:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title(f"TG 批量私信系统 {config.VERSION}")
        self.root.geometry("1200x800")
        
        # 初始化模块
        self.account_manager = AccountManager(
            config.API_ID,
            config.API_HASH,
            config.SESSIONS_DIR,
            config.ACCOUNTS_FILE,
            self.log
        )
        
        self.user_scraper = UserScraper(
            config.API_ID,
            config.API_HASH,
            self.log
        )
        
        self.message_sender = MessageSender(
            config.API_ID,
            config.API_HASH,
            self.log
        )
        
        self.proxy_manager = ProxyManager(self.log)
        
        # 数据
        self.accounts = []
        self.targets = []
        self.collected_users = []
        
        # 标志
        self.is_running = False
        self.stop_flag = False
        
        # 创建界面
        self.setup_ui()
        
        # 加载数据
        self.load_data()
    
    def setup_ui(self):
        """创建界面"""
        # 创建 Notebook
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 创建各个标签页
        self.setup_tab_accounts()
        self.setup_tab_messaging()
        self.setup_tab_scraping()
        self.setup_tab_proxy()
        self.setup_tab_log()
    
    def setup_tab_accounts(self):
        """账号管理标签页"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="📱 账号管理")
        
        # 简化版界面
        ttk.Label(tab, text="账号管理功能", font=("微软雅黑", 16)).pack(pady=20)
        
        # 导入按钮
        ttk.Button(tab, text="导入 Session 文件", command=self.import_sessions).pack(pady=10)
        
        # 账号列表
        frame = ttk.LabelFrame(tab, text="账号列表", padding="10")
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.account_tree = ttk.Treeview(frame,
                                         columns=("选择", "手机号", "状态"),
                                         show="headings",
                                         height=20)
        
        self.account_tree.heading("选择", text="✓")
        self.account_tree.heading("手机号", text="手机号")
        self.account_tree.heading("状态", text="状态")
        
        self.account_tree.column("选择", width=40, anchor=tk.CENTER)
        self.account_tree.column("手机号", width=200)
        self.account_tree.column("状态", width=150)
        
        self.account_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self.account_tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.account_tree.config(yscrollcommand=scrollbar.set)
        
        # 双击切换选择
        self.account_tree.bind("<Double-1>", self.toggle_account_selection)
        
        # 按钮
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Button(btn_frame, text="✅ 全选", command=self.select_all_accounts).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="❌ 清空", command=self.deselect_all_accounts).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="🔄 刷新状态", command=self.refresh_accounts).pack(side=tk.LEFT, padx=2)
    
    def setup_tab_messaging(self):
        """私信广告标签页"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="💬 私信广告")
        
        ttk.Label(tab, text="私信广告功能", font=("微软雅黑", 16)).pack(pady=20)
        
        # 消息URL
        frame = ttk.LabelFrame(tab, text="消息来源", padding="10")
        frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(frame, text="消息URL（格式：https://t.me/channel/msgid）:").pack(anchor=tk.W)
        self.message_url = ttk.Entry(frame, font=("微软雅黑", 10))
        self.message_url.pack(fill=tk.X, pady=5)
        
        # 目标用户
        frame = ttk.LabelFrame(tab, text="目标用户", padding="10")
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.target_text = scrolledtext.ScrolledText(frame, height=15, font=("微软雅黑", 10))
        self.target_text.pack(fill=tk.BOTH, expand=True)
        
        # 按钮
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.send_btn = ttk.Button(btn_frame, text="🚀 开始发送", command=self.start_sending)
        self.send_btn.pack(side=tk.LEFT, padx=2)
        
        self.stop_send_btn = ttk.Button(btn_frame, text="⏸️ 停止", command=self.stop_sending, state=tk.DISABLED)
        self.stop_send_btn.pack(side=tk.LEFT, padx=2)
    
    def setup_tab_scraping(self):
        """采集用户标签页"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="👥 采集用户")
        
        ttk.Label(tab, text="用户采集功能", font=("微软雅黑", 16)).pack(pady=20)
        
        # 采集来源
        frame = ttk.LabelFrame(tab, text="采集来源", padding="10")
        frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.scrape_source = tk.StringVar(value="list")
        ttk.Radiobutton(frame, text="📋 从群列表采集", variable=self.scrape_source, value="list").pack(anchor=tk.W)
        ttk.Radiobutton(frame, text="👥 从已加入的群采集", variable=self.scrape_source, value="joined").pack(anchor=tk.W)
        ttk.Radiobutton(frame, text="💬 从对话列表采集", variable=self.scrape_source, value="dialogs").pack(anchor=tk.W)
        
        # 群组列表
        frame = ttk.LabelFrame(tab, text="群组列表", padding="10")
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.scrape_targets = scrolledtext.ScrolledText(frame, height=10, font=("微软雅黑", 10))
        self.scrape_targets.pack(fill=tk.BOTH, expand=True)
        
        # 按钮
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.scrape_btn = ttk.Button(btn_frame, text="🚀 开始采集", command=self.start_scraping)
        self.scrape_btn.pack(side=tk.LEFT, padx=2)
        
        self.stop_scrape_btn = ttk.Button(btn_frame, text="⏸️ 停止", command=self.stop_scraping, state=tk.DISABLED)
        self.stop_scrape_btn.pack(side=tk.LEFT, padx=2)
    
    def setup_tab_proxy(self):
        """代理管理标签页"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="🌐 代理管理")
        
        ttk.Label(tab, text="代理管理功能", font=("微软雅黑", 16)).pack(pady=20)
        
        # 代理列表
        frame = ttk.LabelFrame(tab, text="代理列表", padding="10")
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.proxy_text = scrolledtext.ScrolledText(frame, height=15, font=("Consolas", 10))
        self.proxy_text.pack(fill=tk.BOTH, expand=True)
        
        # 按钮
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Button(btn_frame, text="导入代理", command=self.import_proxies).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="测试代理", command=self.test_proxies).pack(side=tk.LEFT, padx=2)
    
    def setup_tab_log(self):
        """日志标签页"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="📋 日志")
        
        self.log_text = scrolledtext.ScrolledText(tab, font=("Consolas", 9))
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 清空按钮
        ttk.Button(tab, text="🧹 清空日志", command=lambda: self.log_text.delete("1.0", tk.END)).pack(pady=5)
    
    # ========== 数据加载/保存 ==========
    
    def load_data(self):
        """加载数据"""
        self.accounts = self.account_manager.load_accounts()
        self.update_account_tree()
        self.log(f"✅ 系统启动完成 - {config.VERSION}")
    
    def update_account_tree(self):
        """更新账号列表显示"""
        # 清空
        for item in self.account_tree.get_children():
            self.account_tree.delete(item)
        
        # 插入
        for account in self.accounts:
            selected = "✓" if account.get("selected", False) else ""
            self.account_tree.insert("", tk.END, values=(
                selected,
                account.get("phone", ""),
                account.get("status", "未知")
            ))
    
    # ========== 账号管理 ==========
    
    def import_sessions(self):
        """导入 Session 文件"""
        folder = filedialog.askdirectory(title="选择 Session 文件所在目录")
        if not folder:
            return
        
        imported = self.account_manager.import_sessions(folder)
        if imported:
            self.accounts.extend(imported)
            self.account_manager.save_accounts(self.accounts)
            self.update_account_tree()
    
    def toggle_account_selection(self, event):
        """双击切换账号选择"""
        selection = self.account_tree.selection()
        if not selection:
            return
        
        index = self.account_tree.index(selection[0])
        self.accounts[index]["selected"] = not self.accounts[index].get("selected", False)
        self.update_account_tree()
    
    def select_all_accounts(self):
        """全选账号"""
        for account in self.accounts:
            account["selected"] = True
        self.update_account_tree()
    
    def deselect_all_accounts(self):
        """取消全选"""
        for account in self.accounts:
            account["selected"] = False
        self.update_account_tree()
    
    def refresh_accounts(self):
        """刷新账号状态"""
        if not self.accounts:
            messagebox.showwarning("提示", "请先导入账号")
            return
        
        def run():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(
                self.account_manager.refresh_accounts(
                    self.accounts,
                    callback=lambda i, total, phone: self.log(f"[{i+1}/{total}] 检查: {phone}")
                )
            )
            self.root.after(0, self.update_account_tree)
            self.root.after(0, lambda: self.account_manager.save_accounts(self.accounts))
        
        threading.Thread(target=run, daemon=True).start()
    
    # ========== 私信发送 ==========
    
    def start_sending(self):
        """开始发送"""
        selected_accounts = [acc for acc in self.accounts if acc.get("selected", False)]
        if not selected_accounts:
            messagebox.showerror("错误", "请先选择账号")
            return
        
        message_url = self.message_url.get().strip()
        if not message_url:
            messagebox.showerror("错误", "请输入消息URL")
            return
        
        targets = [line.strip() for line in self.target_text.get("1.0", tk.END).strip().split('\n') if line.strip()]
        if not targets:
            messagebox.showerror("错误", "请输入目标用户")
            return
        
        confirm = messagebox.askyesno(
            "确认发送",
            f"将使用 {len(selected_accounts)} 个账号\n"
            f"向 {len(targets)} 个用户发送消息\n\n"
            f"是否继续?"
        )
        
        if not confirm:
            return
        
        self.send_btn.config(state=tk.DISABLED)
        self.stop_send_btn.config(state=tk.NORMAL)
        self.is_running = True
        
        def run():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            config_dict = config.DEFAULT_CONFIG.copy()
            
            loop.run_until_complete(
                self.message_sender.send_messages(
                    selected_accounts,
                    targets,
                    message_url,
                    config_dict
                )
            )
            
            self.root.after(0, lambda: self.send_btn.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.stop_send_btn.config(state=tk.DISABLED))
        
        threading.Thread(target=run, daemon=True).start()
    
    def stop_sending(self):
        """停止发送"""
        self.message_sender.stop()
        self.log("⏸️ 停止发送")
    
    # ========== 用户采集 ==========
    
    def start_scraping(self):
        """开始采集"""
        selected_accounts = [acc for acc in self.accounts if acc.get("selected", False)]
        if not selected_accounts:
            messagebox.showerror("错误", "请先选择账号")
            return
        
        source = self.scrape_source.get()
        
        if source == "list":
            targets = [line.strip() for line in self.scrape_targets.get("1.0", tk.END).strip().split('\n') if line.strip()]
            if not targets:
                messagebox.showerror("错误", "请输入群组列表")
                return
        else:
            targets = []
        
        source_text = {"list": "群列表", "joined": "已加入的群", "dialogs": "对话列表"}[source]
        
        confirm = messagebox.askyesno(
            "确认采集",
            f"将使用 {len(selected_accounts)} 个账号\n"
            f"采集来源: {source_text}\n\n"
            f"是否继续?"
        )
        
        if not confirm:
            return
        
        self.scrape_btn.config(state=tk.DISABLED)
        self.stop_scrape_btn.config(state=tk.NORMAL)
        self.is_running = True
        
        def run():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            config_dict = {
                "source": source,
                "mode": "default",
                "threads": 5,
                "limit": 500,
                "filter_online_time": True,
                "online_days": 3,
                "include_recently": True,
                "include_online": True,
                "filter_bot": True,
                "filter_username": False,
                "filter_premium": False,
                "filter_photo": False,
                "auto_leave": False
            }
            
            users = loop.run_until_complete(
                self.user_scraper.scrape(
                    selected_accounts,
                    targets,
                    config_dict
                )
            )
            
            self.log(f"✅ 采集到 {len(users)} 个用户")
            
            self.root.after(0, lambda: self.scrape_btn.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.stop_scrape_btn.config(state=tk.DISABLED))
        
        threading.Thread(target=run, daemon=True).start()
    
    def stop_scraping(self):
        """停止采集"""
        self.user_scraper.stop()
        self.log("⏸️ 停止采集")
    
    # ========== 代理管理 ==========
    
    def import_proxies(self):
        """导入代理"""
        proxy_list = self.proxy_text.get("1.0", tk.END).strip()
        if not proxy_list:
            messagebox.showwarning("提示", "请先输入代理列表")
            return
        
        count = self.proxy_manager.import_proxies(proxy_list)
        messagebox.showinfo("成功", f"导入 {count} 个代理")
    
    def test_proxies(self):
        """测试代理"""
        if not self.proxy_manager.proxies:
            messagebox.showwarning("提示", "请先导入代理")
            return
        
        def run():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            working = loop.run_until_complete(
                self.proxy_manager.test_all_proxies(
                    callback=lambda i, total, proxy: self.log(f"[{i+1}/{total}] 测试: {proxy}")
                )
            )
            
            self.root.after(0, lambda: messagebox.showinfo("测试完成", f"可用代理: {len(working)}/{len(self.proxy_manager.proxies)}"))
        
        threading.Thread(target=run, daemon=True).start()
    
    # ========== 日志 ==========
    
    def log(self, message):
        """输出日志"""
        timestamp = datetime.now().strftime("[%H:%M:%S]")
        self.log_text.insert(tk.END, f"{timestamp} {message}\n")
        self.log_text.see(tk.END)
    
    # ========== 运行 ==========
    
    def run(self):
        """运行程序"""
        self.root.mainloop()

# ========== 主程序入口 ==========

if __name__ == "__main__":
    from datetime import datetime
    
    app = TelegramMassDM()
    app.run()
