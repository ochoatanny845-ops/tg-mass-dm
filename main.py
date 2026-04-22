"""
TG 批量私信系统 - 简化版
功能：批量发送私信/转发消息
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
        self.root.title("TG 批量私信系统 v1.0")
        self.root.geometry("900x700")
        
        # Telegram API 配置
        self.api_id = 2040
        self.api_hash = "b18441a1ff607e10a989891a5462e627"
        
        # 数据存储
        self.accounts = []  # Session 文件列表
        self.targets = []   # 目标用户列表
        self.is_running = False
        
        self.setup_ui()
    
    def setup_ui(self):
        """设置界面"""
        
        # ========== 顶部：标题 ==========
        title_frame = ttk.Frame(self.root, padding="10")
        title_frame.pack(fill=tk.X)
        
        ttk.Label(title_frame, text="📱 TG 批量私信系统", 
                 font=("微软雅黑", 16, "bold")).pack(side=tk.LEFT)
        
        # ========== 左侧：账号管理 ==========
        left_frame = ttk.LabelFrame(self.root, text="📂 账号管理", padding="10")
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 导入账号按钮
        btn_frame = ttk.Frame(left_frame)
        btn_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(btn_frame, text="📁 导入 Session 文件夹", 
                  command=self.import_sessions).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="🔄 刷新", 
                  command=self.refresh_accounts).pack(side=tk.LEFT)
        
        # 账号列表
        ttk.Label(left_frame, text="已导入账号:").pack(anchor=tk.W, pady=5)
        
        self.account_tree = ttk.Treeview(left_frame, columns=("文件名",), 
                                         show="headings", height=10)
        self.account_tree.heading("文件名", text="Session 文件")
        self.account_tree.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # 滚动条
        scrollbar = ttk.Scrollbar(left_frame, orient=tk.VERTICAL, 
                                  command=self.account_tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.account_tree.config(yscrollcommand=scrollbar.set)
        
        # ========== 中间：消息内容 ==========
        middle_frame = ttk.LabelFrame(self.root, text="✉️ 消息内容", padding="10")
        middle_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        
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
        self.text_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        ttk.Label(self.text_frame, text="消息内容:").pack(anchor=tk.W)
        self.message_text = scrolledtext.ScrolledText(self.text_frame, height=10, 
                                                      font=("微软雅黑", 10))
        self.message_text.pack(fill=tk.BOTH, expand=True, pady=5)
        self.message_text.insert("1.0", "你好！这是一条测试消息。\n\n支持变量：\n{username} - 用户名\n{firstname} - 名字")
        
        # 转发贴子输入（默认隐藏）
        self.forward_frame = ttk.Frame(middle_frame)
        
        ttk.Label(self.forward_frame, text="贴子链接:").pack(anchor=tk.W)
        self.forward_url = ttk.Entry(self.forward_frame, font=("微软雅黑", 10))
        self.forward_url.pack(fill=tk.X, pady=5)
        self.forward_url.insert(0, "https://t.me/channel/123")
        
        self.hide_source = tk.BooleanVar(value=True)
        ttk.Checkbutton(self.forward_frame, text="隐藏来源", 
                       variable=self.hide_source).pack(anchor=tk.W)
        
        # 目标用户
        ttk.Label(middle_frame, text="目标用户 (每行一个用户名):").pack(anchor=tk.W, pady=(10,0))
        self.target_text = scrolledtext.ScrolledText(middle_frame, height=6, 
                                                     font=("微软雅黑", 10))
        self.target_text.pack(fill=tk.BOTH, expand=True, pady=5)
        self.target_text.insert("1.0", "@username1\n@username2\n@username3")
        
        # ========== 右侧：控制配置 ==========
        right_frame = ttk.LabelFrame(self.root, text="⚙️ 发送设置", padding="10")
        right_frame.pack(side=tk.LEFT, fill=tk.BOTH, padx=10, pady=10)
        
        # 并发设置
        ttk.Label(right_frame, text="⚡ 并发设置", 
                 font=("微软雅黑", 10, "bold")).pack(anchor=tk.W, pady=(0,10))
        
        ttk.Label(right_frame, text="并行线程数:").pack(anchor=tk.W)
        self.thread_count = tk.IntVar(value=5)
        ttk.Spinbox(right_frame, from_=1, to=50, textvariable=self.thread_count, 
                   width=20).pack(anchor=tk.W, pady=5)
        
        ttk.Label(right_frame, text="线程启动间隔(秒):").pack(anchor=tk.W)
        self.thread_interval = tk.IntVar(value=1)
        ttk.Spinbox(right_frame, from_=0, to=60, textvariable=self.thread_interval, 
                   width=20).pack(anchor=tk.W, pady=5)
        
        # 额度设置
        ttk.Separator(right_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)
        ttk.Label(right_frame, text="📊 额度限制", 
                 font=("微软雅黑", 10, "bold")).pack(anchor=tk.W, pady=(0,10))
        
        ttk.Label(right_frame, text="单账号上限:").pack(anchor=tk.W)
        self.per_account_limit = tk.IntVar(value=50)
        ttk.Spinbox(right_frame, from_=1, to=1000, textvariable=self.per_account_limit, 
                   width=20).pack(anchor=tk.W, pady=5)
        
        ttk.Label(right_frame, text="任务总上限:").pack(anchor=tk.W)
        self.total_limit = tk.IntVar(value=1000)
        ttk.Spinbox(right_frame, from_=1, to=100000, textvariable=self.total_limit, 
                   width=20).pack(anchor=tk.W, pady=5)
        
        # 发送间隔
        ttk.Separator(right_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)
        ttk.Label(right_frame, text="⏱️ 发送间隔", 
                 font=("微软雅黑", 10, "bold")).pack(anchor=tk.W, pady=(0,10))
        
        interval_frame = ttk.Frame(right_frame)
        interval_frame.pack(anchor=tk.W)
        
        ttk.Label(interval_frame, text="间隔范围:").pack(side=tk.LEFT)
        self.interval_min = tk.IntVar(value=3)
        ttk.Spinbox(interval_frame, from_=1, to=60, textvariable=self.interval_min, 
                   width=8).pack(side=tk.LEFT, padx=5)
        ttk.Label(interval_frame, text="~").pack(side=tk.LEFT)
        self.interval_max = tk.IntVar(value=8)
        ttk.Spinbox(interval_frame, from_=1, to=60, textvariable=self.interval_max, 
                   width=8).pack(side=tk.LEFT, padx=5)
        ttk.Label(interval_frame, text="秒").pack(side=tk.LEFT)
        
        # 控制按钮
        ttk.Separator(right_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)
        
        self.start_btn = ttk.Button(right_frame, text="🚀 开始发送", 
                                    command=self.start_sending)
        self.start_btn.pack(fill=tk.X, pady=5)
        
        self.stop_btn = ttk.Button(right_frame, text="⏸️ 停止", 
                                   command=self.stop_sending, state=tk.DISABLED)
        self.stop_btn.pack(fill=tk.X, pady=5)
        
        # ========== 底部：日志输出 ==========
        log_frame = ttk.LabelFrame(self.root, text="📝 运行日志", padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=10, 
                                                  font=("Consolas", 9))
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
        # 欢迎日志
        self.log("✅ TG 批量私信系统已启动")
        self.log("📋 请先导入 Session 账号文件")
    
    def on_type_change(self):
        """切换发送类型"""
        if self.send_type.get() == "text":
            self.forward_frame.pack_forget()
            self.text_frame.pack(fill=tk.BOTH, expand=True, pady=10, before=self.target_text)
        else:
            self.text_frame.pack_forget()
            self.forward_frame.pack(fill=tk.BOTH, expand=True, pady=10, before=self.target_text)
    
    def log(self, message):
        """输出日志"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
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
            self.accounts.append(str(session_file))
            self.account_tree.insert("", tk.END, values=(session_file.name,))
        
        self.log(f"✅ 找到 {len(self.accounts)} 个 Session 账号")
    
    def refresh_accounts(self):
        """刷新账号列表"""
        if not self.accounts:
            self.log("⚠️ 请先导入 Session 文件夹")
            return
        
        self.log(f"🔄 当前已导入 {len(self.accounts)} 个账号")
    
    def start_sending(self):
        """开始发送"""
        # 验证输入
        if not self.accounts:
            messagebox.showerror("错误", "请先导入 Session 账号")
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
        else:
            forward_url = self.forward_url.get().strip()
            if not forward_url:
                messagebox.showerror("错误", "请输入贴子链接")
                return
        
        # 确认发送
        confirm = messagebox.askyesno(
            "确认发送", 
            f"将使用 {len(self.accounts)} 个账号\n"
            f"向 {len(self.targets)} 个用户发送消息\n\n"
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
        thread = threading.Thread(target=self.run_sending_task)
        thread.start()
    
    def stop_sending(self):
        """停止发送"""
        self.is_running = False
        self.log("⏸️ 正在停止...")
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
    
    def run_sending_task(self):
        """运行发送任务（异步）"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.send_messages_async())
    
    async def send_messages_async(self):
        """异步发送消息"""
        total_sent = 0
        total_failed = 0
        
        for i, session_path in enumerate(self.accounts):
            if not self.is_running:
                self.log("⏸️ 任务已停止")
                break
            
            self.log(f"\n[{i+1}/{len(self.accounts)}] 使用账号: {Path(session_path).stem}")
            
            # 线程启动间隔
            if i > 0:
                await asyncio.sleep(self.thread_interval.get())
            
            try:
                # 连接 Telegram
                client = TelegramClient(session_path, self.api_id, self.api_hash)
                await client.connect()
                
                # 获取当前账号信息
                me = await client.get_me()
                account_name = me.username or me.phone or me.id
                self.log(f"  ✅ 已登录: @{account_name}")
                
                # 发送消息
                account_sent = 0
                for target in self.targets:
                    if not self.is_running:
                        break
                    
                    if account_sent >= self.per_account_limit.get():
                        self.log(f"  ⚠️ 达到单账号上限 ({self.per_account_limit.get()})")
                        break
                    
                    if total_sent >= self.total_limit.get():
                        self.log(f"  ⚠️ 达到任务总上限 ({self.total_limit.get()})")
                        self.is_running = False
                        break
                    
                    try:
                        # 移除 @ 符号
                        username = target.lstrip("@")
                        
                        # 发送消息
                        if self.send_type.get() == "text":
                            # 文本消息
                            message = self.message_text.get("1.0", tk.END).strip()
                            message = message.replace("{username}", username)
                            
                            # 获取用户信息并替换变量
                            try:
                                user = await client.get_entity(username)
                                message = message.replace("{firstname}", user.first_name or "")
                            except:
                                pass
                            
                            await client.send_message(username, message)
                        else:
                            # 转发贴子
                            forward_url = self.forward_url.get().strip()
                            # TODO: 解析贴子链接并转发
                            await client.send_message(username, f"[转发功能待实现] {forward_url}")
                        
                        account_sent += 1
                        total_sent += 1
                        self.log(f"  ✅ 发送成功: @{username} [{total_sent}]")
                        
                        # 随机间隔
                        interval = random.uniform(
                            self.interval_min.get(), 
                            self.interval_max.get()
                        )
                        await asyncio.sleep(interval)
                        
                    except errors.FloodWaitError as e:
                        self.log(f"  ⚠️ 触发频率限制，需等待 {e.seconds} 秒")
                        await asyncio.sleep(e.seconds)
                    except errors.UserPrivacyRestrictedError:
                        self.log(f"  ❌ 用户隐私限制: @{username}")
                        total_failed += 1
                    except errors.UserIsBlockedError:
                        self.log(f"  ❌ 已被用户拉黑: @{username}")
                        total_failed += 1
                    except Exception as e:
                        self.log(f"  ❌ 发送失败: @{username} - {type(e).__name__}")
                        total_failed += 1
                
                await client.disconnect()
                self.log(f"  📊 本账号发送: {account_sent} 条")
                
            except Exception as e:
                self.log(f"  ❌ 账号错误: {type(e).__name__}: {str(e)[:50]}")
        
        # 任务完成
        self.log(f"\n" + "="*50)
        self.log(f"✅ 任务完成！")
        self.log(f"📊 成功: {total_sent} 条")
        self.log(f"❌ 失败: {total_failed} 条")
        self.log("="*50)
        
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.is_running = False


def main():
    root = tk.Tk()
    app = TGMassDM(root)
    root.mainloop()


if __name__ == "__main__":
    main()
