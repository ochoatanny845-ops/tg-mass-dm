"""
TG 批量私信系统 - 优化版 v1.1
功能：批量发送私信/转发消息
更新：
- 优化窗口布局（支持缩放）
- 账号可选择（勾选框）
- 自动切换账号（遇到限制）
- 账号状态检测
"""

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

try:
    from telethon import TelegramClient, errors
    from telethon.tl.types import InputPeerUser, User
except ImportError:
    print("❌ 缺少 telethon 库，请运行: pip install telethon")
    sys.exit(1)


class TGMassDM:
    def __init__(self, root):
        self.root = root
        self.root.title("TG 批量私信系统 v1.1")
        self.root.geometry("1000x750")
        
        # Telegram API 配置
        self.api_id = 2040
        self.api_hash = "b18441a1ff607e10a989891a5462e627"
        
        # 数据存储
        self.accounts = []  # {path, selected, status}
        self.targets = []   # 目标用户列表
        self.is_running = False
        
        self.setup_ui()
    
    def setup_ui(self):
        """设置界面"""
        
        # ========== 顶部：标题 ==========
        title_frame = ttk.Frame(self.root, padding="10")
        title_frame.pack(fill=tk.X)
        
        ttk.Label(title_frame, text="📱 TG 批量私信系统 v1.1", 
                 font=("微软雅黑", 14, "bold")).pack(side=tk.LEFT)
        
        # ========== 主容器（支持滚动）==========
        main_container = ttk.Frame(self.root)
        main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # 左右分栏
        paned = ttk.PanedWindow(main_container, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)
        
        # ========== 左侧：账号管理 ==========
        left_frame = ttk.LabelFrame(paned, text="📂 账号管理", padding="10")
        paned.add(left_frame, weight=1)
        
        # 导入账号按钮
        btn_frame = ttk.Frame(left_frame)
        btn_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(btn_frame, text="📁 导入账号", 
                  command=self.import_sessions).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="✅ 全选", 
                  command=self.select_all).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="❌ 清空", 
                  command=self.deselect_all).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="🔍 检测", 
                  command=self.check_accounts).pack(side=tk.LEFT, padx=2)
        
        # 账号列表（带勾选框）
        ttk.Label(left_frame, text="已导入账号 (双击勾选/取消):").pack(anchor=tk.W, pady=5)
        
        # 创建 Treeview 容器
        tree_frame = ttk.Frame(left_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.account_tree = ttk.Treeview(tree_frame, columns=("选择", "文件名", "状态"), 
                                         show="headings", height=15)
        self.account_tree.heading("选择", text="✓")
        self.account_tree.heading("文件名", text="账号文件")
        self.account_tree.heading("状态", text="状态")
        
        self.account_tree.column("选择", width=40, anchor=tk.CENTER)
        self.account_tree.column("文件名", width=180)
        self.account_tree.column("状态", width=80)
        
        self.account_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 滚动条
        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, 
                                  command=self.account_tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.account_tree.config(yscrollcommand=scrollbar.set)
        
        # 双击切换选择
        self.account_tree.bind("<Double-1>", self.toggle_account)
        
        # ========== 右侧容器 ==========
        right_container = ttk.Frame(paned)
        paned.add(right_container, weight=2)
        
        # 右侧分为上下两部分
        right_paned = ttk.PanedWindow(right_container, orient=tk.VERTICAL)
        right_paned.pack(fill=tk.BOTH, expand=True)
        
        # ========== 右上：消息内容 ==========
        middle_frame = ttk.LabelFrame(right_paned, text="✉️ 消息内容", padding="10")
        right_paned.add(middle_frame, weight=2)
        
        # 发送类型选择
        type_frame = ttk.Frame(middle_frame)
        type_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(type_frame, text="发送类型:").pack(side=tk.LEFT, padx=5)
        
        self.send_type = tk.StringVar(value="text")
        ttk.Radiobutton(type_frame, text="文本消息", variable=self.send_type, 
                       value="text", command=self.on_type_change).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(type_frame, text="转发贴子", variable=self.send_type, 
                       value="forward", command=self.on_type_change).pack(side=tk.LEFT, padx=5)
        
        # 文本消息输入
        self.text_frame = ttk.Frame(middle_frame)
        self.text_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        ttk.Label(self.text_frame, text="消息内容:").pack(anchor=tk.W)
        self.message_text = scrolledtext.ScrolledText(self.text_frame, height=6, 
                                                      font=("微软雅黑", 9))
        self.message_text.pack(fill=tk.BOTH, expand=True, pady=5)
        self.message_text.insert("1.0", "你好！这是一条测试消息。")
        
        # 转发贴子输入（默认隐藏）
        self.forward_frame = ttk.Frame(middle_frame)
        
        ttk.Label(self.forward_frame, text="贴子链接:").pack(anchor=tk.W)
        self.forward_url = ttk.Entry(self.forward_frame, font=("微软雅黑", 9))
        self.forward_url.pack(fill=tk.X, pady=5)
        
        self.hide_source = tk.BooleanVar(value=True)
        ttk.Checkbutton(self.forward_frame, text="隐藏来源", 
                       variable=self.hide_source).pack(anchor=tk.W)
        
        # 目标用户
        ttk.Label(middle_frame, text="目标用户 (每行一个):").pack(anchor=tk.W, pady=(10,0))
        self.target_text = scrolledtext.ScrolledText(middle_frame, height=5, 
                                                     font=("微软雅黑", 9))
        self.target_text.pack(fill=tk.BOTH, expand=True, pady=5)
        self.target_text.insert("1.0", "@username1\n@username2")
        
        # ========== 右下：控制配置 ==========
        control_frame = ttk.LabelFrame(right_paned, text="⚙️ 发送设置", padding="10")
        right_paned.add(control_frame, weight=1)
        
        # 使用网格布局优化空间
        control_frame.columnconfigure(0, weight=1)
        control_frame.columnconfigure(1, weight=1)
        
        row = 0
        
        # 并发设置
        ttk.Label(control_frame, text="并行线程数:").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.thread_count = tk.IntVar(value=5)
        ttk.Spinbox(control_frame, from_=1, to=50, textvariable=self.thread_count, 
                   width=10).grid(row=row, column=1, sticky=tk.W, padx=5, pady=2)
        row += 1
        
        ttk.Label(control_frame, text="线程启动间隔(秒):").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.thread_interval = tk.IntVar(value=1)
        ttk.Spinbox(control_frame, from_=0, to=60, textvariable=self.thread_interval, 
                   width=10).grid(row=row, column=1, sticky=tk.W, padx=5, pady=2)
        row += 1
        
        # 额度设置
        ttk.Label(control_frame, text="单账号上限:").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.per_account_limit = tk.IntVar(value=50)
        ttk.Spinbox(control_frame, from_=1, to=1000, textvariable=self.per_account_limit, 
                   width=10).grid(row=row, column=1, sticky=tk.W, padx=5, pady=2)
        row += 1
        
        ttk.Label(control_frame, text="任务总上限:").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.total_limit = tk.IntVar(value=1000)
        ttk.Spinbox(control_frame, from_=1, to=100000, textvariable=self.total_limit, 
                   width=10).grid(row=row, column=1, sticky=tk.W, padx=5, pady=2)
        row += 1
        
        # 发送间隔
        ttk.Label(control_frame, text="发送间隔:").grid(row=row, column=0, sticky=tk.W, pady=2)
        interval_frame = ttk.Frame(control_frame)
        interval_frame.grid(row=row, column=1, sticky=tk.W, padx=5, pady=2)
        
        self.interval_min = tk.IntVar(value=3)
        ttk.Spinbox(interval_frame, from_=1, to=60, textvariable=self.interval_min, 
                   width=5).pack(side=tk.LEFT)
        ttk.Label(interval_frame, text="~").pack(side=tk.LEFT, padx=2)
        self.interval_max = tk.IntVar(value=8)
        ttk.Spinbox(interval_frame, from_=1, to=60, textvariable=self.interval_max, 
                   width=5).pack(side=tk.LEFT)
        ttk.Label(interval_frame, text="秒").pack(side=tk.LEFT, padx=2)
        row += 1
        
        # 错误重试
        ttk.Label(control_frame, text="遇到限制:").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.auto_switch = tk.BooleanVar(value=True)
        ttk.Checkbutton(control_frame, text="自动切换账号", 
                       variable=self.auto_switch).grid(row=row, column=1, sticky=tk.W, padx=5, pady=2)
        row += 1
        
        # 控制按钮
        btn_container = ttk.Frame(control_frame)
        btn_container.grid(row=row, column=0, columnspan=2, pady=10, sticky=tk.EW)
        
        self.start_btn = ttk.Button(btn_container, text="🚀 开始发送", 
                                    command=self.start_sending)
        self.start_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        
        self.stop_btn = ttk.Button(btn_container, text="⏸️ 停止", 
                                   command=self.stop_sending, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        
        # ========== 底部：日志输出 ==========
        log_frame = ttk.LabelFrame(self.root, text="📝 运行日志", padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=8, 
                                                  font=("Consolas", 9))
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
        # 欢迎日志
        self.log("✅ TG 批量私信系统 v1.1 已启动")
        self.log("📋 请先导入 Session 账号文件")
        self.log("📌 更新: 支持账号选择、状态检测、自动切换")
    
    def on_type_change(self):
        """切换发送类型"""
        if self.send_type.get() == "text":
            self.forward_frame.pack_forget()
            self.text_frame.pack(fill=tk.BOTH, expand=True, pady=5, before=self.target_text.master)
        else:
            self.text_frame.pack_forget()
            self.forward_frame.pack(fill=tk.BOTH, expand=True, pady=5, before=self.target_text.master)
    
    def log(self, message):
        """输出日志"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        self.root.update_idletasks()  # 强制刷新界面
        print(message)  # 同时输出到终端
    
    def import_sessions(self):
        """导入 Session 文件夹"""
        folder = filedialog.askdirectory(title="选择 Session 文件夹")
        if not folder:
            return
        
        self.log(f"📁 正在扫描文件夹: {folder}")
        
        # 清空现有列表
        for item in self.account_tree.get_children():
            self.account_tree.delete(item)
        self.accounts.clear()
        
        # 扫描 .session 文件
        folder_path = Path(folder)
        session_files = list(folder_path.glob("*.session"))
        
        for session_file in session_files:
            account = {
                "path": str(session_file),
                "selected": True,  # 默认选中
                "status": "未检测"
            }
            self.accounts.append(account)
            self.account_tree.insert("", tk.END, values=(
                "✓",
                session_file.name,
                "未检测"
            ))
        
        self.log(f"✅ 找到 {len(self.accounts)} 个 Session 账号")
    
    def toggle_account(self, event):
        """双击切换账号选择状态"""
        selection = self.account_tree.selection()
        if not selection:
            return
        
        item = selection[0]
        index = self.account_tree.index(item)
        
        # 切换选择状态
        self.accounts[index]["selected"] = not self.accounts[index]["selected"]
        
        # 更新显示
        check = "✓" if self.accounts[index]["selected"] else ""
        values = self.account_tree.item(item, "values")
        self.account_tree.item(item, values=(check, values[1], values[2]))
    
    def select_all(self):
        """全选账号"""
        for i, account in enumerate(self.accounts):
            account["selected"] = True
            item = self.account_tree.get_children()[i]
            values = self.account_tree.item(item, "values")
            self.account_tree.item(item, values=("✓", values[1], values[2]))
        self.log("✅ 已全选所有账号")
    
    def deselect_all(self):
        """清空选择"""
        for i, account in enumerate(self.accounts):
            account["selected"] = False
            item = self.account_tree.get_children()[i]
            values = self.account_tree.item(item, "values")
            self.account_tree.item(item, values=("", values[1], values[2]))
        self.log("❌ 已清空所有选择")
    
    def check_accounts(self):
        """检测账号状态"""
        if not self.accounts:
            messagebox.showwarning("提示", "请先导入账号")
            return
        
        self.log("🔍 开始检测账号状态...")
        
        # 在新线程中运行
        thread = threading.Thread(target=self.run_check_accounts)
        thread.start()
    
    def run_check_accounts(self):
        """运行账号检测"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.check_accounts_async())
    
    async def check_accounts_async(self):
        """异步检测账号"""
        for i, account in enumerate(self.accounts):
            self.log(f"[{i+1}/{len(self.accounts)}] 检测: {Path(account['path']).stem}")
            
            try:
                client = TelegramClient(account["path"], self.api_id, self.api_hash)
                await client.connect()
                
                me = await client.get_me()
                if me:
                    account_name = me.username or me.phone or str(me.id)
                    account["status"] = f"正常 @{account_name}"
                    self.log(f"  ✅ {account['status']}")
                else:
                    account["status"] = "登录失败"
                    self.log(f"  ❌ {account['status']}")
                
                await client.disconnect()
                
            except Exception as e:
                account["status"] = f"错误: {type(e).__name__}"
                self.log(f"  ❌ {account['status']}")
            
            # 更新界面
            item = self.account_tree.get_children()[i]
            values = self.account_tree.item(item, "values")
            self.account_tree.item(item, values=(values[0], values[1], account["status"]))
            
            await asyncio.sleep(0.5)
        
        self.log("✅ 账号检测完成")
    
    def start_sending(self):
        """开始发送"""
        # 获取选中的账号
        selected_accounts = [acc for acc in self.accounts if acc["selected"]]
        
        if not selected_accounts:
            messagebox.showerror("错误", "请至少选择一个账号")
            return
        
        # 获取目标用户
        target_text = self.target_text.get("1.0", tk.END).strip()
        self.targets = [line.strip() for line in target_text.split("\n") 
                       if line.strip() and not line.startswith("#")]
        
        if not self.targets:
            messagebox.showerror("错误", "请输入目标用户")
            return
        
        # 获取消息内容
        if self.send_type.get() == "text":
            message = self.message_text.get("1.0", tk.END).strip()
            if not message:
                messagebox.showerror("错误", "请输入消息内容")
                return
        
        # 确认发送
        confirm = messagebox.askyesno(
            "确认发送", 
            f"将使用 {len(selected_accounts)} 个账号\n"
            f"向 {len(self.targets)} 个用户发送消息\n\n"
            f"自动切换账号: {'是' if self.auto_switch.get() else '否'}\n\n"
            f"是否继续？"
        )
        
        if not confirm:
            return
        
        # 更新按钮状态
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.is_running = True
        
        self.log("🚀 开始发送任务...")
        
        # 在新线程中运行异步任务
        thread = threading.Thread(target=self.run_sending_task, args=(selected_accounts,))
        thread.start()
    
    def stop_sending(self):
        """停止发送"""
        self.is_running = False
        self.log("⏸️ 正在停止...")
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
    
    def run_sending_task(self, selected_accounts):
        """运行发送任务（异步）"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.send_messages_async(selected_accounts))
    
    async def send_messages_async(self, selected_accounts):
        """异步发送消息（真正并发）"""
        # 共享计数器（使用锁保护）
        self.total_sent = 0
        self.total_failed = 0
        self.send_lock = asyncio.Lock()
        
        # 按并发数分批处理
        thread_count = self.thread_count.get()
        
        for batch_start in range(0, len(selected_accounts), thread_count):
            if not self.is_running:
                self.log("⏸️ 任务已停止")
                break
            
            # 当前批次的账号
            batch = selected_accounts[batch_start:batch_start + thread_count]
            
            self.log(f"\n🔄 启动批次 {batch_start//thread_count + 1}: {len(batch)} 个账号并发")
            
            # 创建并发任务
            tasks = []
            for i, account in enumerate(batch):
                task = self.send_with_account(account, batch_start + i + 1, len(selected_accounts))
                tasks.append(task)
            
            # 并发执行
            await asyncio.gather(*tasks, return_exceptions=True)
            
            # 批次间隔
            if batch_start + thread_count < len(selected_accounts):
                self.log(f"⏱️ 批次完成，等待 {self.thread_interval.get()} 秒启动下一批...")
                await asyncio.sleep(self.thread_interval.get())
        
        # 任务完成
        self.log(f"\n" + "="*50)
        self.log(f"✅ 任务完成！")
        self.log(f"📊 成功: {self.total_sent} 条")
        self.log(f"❌ 失败: {self.total_failed} 条")
        self.log("="*50)
        
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.is_running = False
    
    async def send_with_account(self, account, index, total):
        """使用单个账号发送（并发任务）"""
        self.log(f"\n[{index}/{total}] 📱 启动账号: {Path(account['path']).stem}")
        
        try:
            # 连接 Telegram
            client = TelegramClient(account["path"], self.api_id, self.api_hash)
            await client.connect()
            
            # 获取当前账号信息
            me = await client.get_me()
            account_name = me.username or me.phone or str(me.id)
            self.log(f"  ✅ 已登录: @{account_name}")
            
            # 发送消息
            account_sent = 0
            
            for target in self.targets:
                if not self.is_running:
                    break
                
                # 检查单账号上限
                if account_sent >= self.per_account_limit.get():
                    self.log(f"  ⚠️ [{account_name}] 达到单账号上限 ({self.per_account_limit.get()})")
                    break
                
                # 检查任务总上限（使用锁）
                async with self.send_lock:
                    if self.total_sent >= self.total_limit.get():
                        self.log(f"  ⚠️ 达到任务总上限 ({self.total_limit.get()})")
                        self.is_running = False
                        break
                
                try:
                    # 移除 @ 符号
                    username = target.lstrip("@")
                    
                    # 发送消息
                    if self.send_type.get() == "text":
                        message = self.message_text.get("1.0", tk.END).strip()
                        message = message.replace("{username}", username)
                        
                        try:
                            user = await client.get_entity(username)
                            message = message.replace("{firstname}", user.first_name or "")
                        except:
                            pass
                        
                        await client.send_message(username, message)
                    
                    account_sent += 1
                    
                    # 更新总计数（使用锁）
                    async with self.send_lock:
                        self.total_sent += 1
                        current_total = self.total_sent
                    
                    self.log(f"  ✅ [{account_name}] 发送成功: @{username} [总计:{current_total}]")
                    
                    # 随机间隔
                    interval = random.uniform(
                        self.interval_min.get(), 
                        self.interval_max.get()
                    )
                    await asyncio.sleep(interval)
                    
                except errors.FloodWaitError as e:
                    self.log(f"  ⚠️ [{account_name}] 触发频率限制，需等待 {e.seconds} 秒")
                    if self.auto_switch.get():
                        self.log(f"  🔄 [{account_name}] 提前结束，切换下一批")
                        break
                    else:
                        await asyncio.sleep(e.seconds)
                
                except errors.UserPrivacyRestrictedError:
                    self.log(f"  ❌ [{account_name}] 用户隐私限制: @{username}")
                    async with self.send_lock:
                        self.total_failed += 1
                except errors.UserIsBlockedError:
                    self.log(f"  ❌ [{account_name}] 已被用户拉黑: @{username}")
                    async with self.send_lock:
                        self.total_failed += 1
                except Exception as e:
                    self.log(f"  ❌ [{account_name}] 发送失败: @{username} - {type(e).__name__}")
                    async with self.send_lock:
                        self.total_failed += 1
            
            await client.disconnect()
            self.log(f"  📊 [{account_name}] 完成，本账号发送: {account_sent} 条")
            
        except Exception as e:
            self.log(f"  ❌ 账号错误: {type(e).__name__}: {str(e)[:50]}")


def main():
    root = tk.Tk()
    app = TGMassDM(root)
    root.mainloop()


if __name__ == "__main__":
    main()
