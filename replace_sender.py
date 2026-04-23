"""
替换发送逻辑 - 使用 MessageSender 模块
策略：保留 UI 回调，只替换核心发送逻辑
"""

import sys
import re

sys.stdout.reconfigure(encoding='utf-8')

# 读取文件
with open('main_v2_full.py', 'r', encoding='utf-8') as f:
    content = f.read()

print("Original file size:", len(content), "chars")

# 1. 替换 send_messages_async 函数
# 找到函数并替换为简化版本
old_send_async = '''    async def send_messages_async(self, selected_accounts):
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

            # 修复2: 检查是否还有可用账号
            available_accounts = [acc for acc in selected_accounts if acc.get("selected", False)]
            if not available_accounts:
                self.log("⚠️ 所有选中的账号都已不可用,自动停止任务")
                self.is_running = False
                break

            batch = selected_accounts[batch_start:batch_start + thread_count]

            self.log(f"\\n🔄 启动批次 {batch_start//thread_count + 1}: {len(batch)} 个账号并发")

            tasks = []
            for i, account in enumerate(batch):
                task = self.send_with_account(account, batch_start + i + 1, len(selected_accounts))
                tasks.append(task)

            await asyncio.gather(*tasks, return_exceptions=True)

            if batch_start + thread_count < len(selected_accounts):
                self.log(f"⏱️ 批次完成,等待 {self.thread_interval.get()} 秒启动下一批...")
                await asyncio.sleep(self.thread_interval.get())'''

new_send_async = '''    async def send_messages_async(self, selected_accounts):
        """异步发送消息（使用模块）"""
        try:
            # 获取消息URL
            message_url = self.forward_link.get().strip()
            
            # 构建配置
            config_dict = {
                "parallel_threads": self.thread_count.get(),
                "start_delay": self.thread_interval.get(),
                "send_delay_min": self.send_delay_min.get(),
                "send_delay_max": self.send_delay_max.get(),
                "consecutive_fails_threshold": 10,
                "ignore_mutual": False
            }
            
            # 回调函数
            def on_update():
                self.update_progress()
            
            def on_remove_target(target):
                self.remove_successful_target(target)
            
            callbacks = {
                "on_update": on_update,
                "on_remove_target": on_remove_target
            }
            
            # 调用模块发送
            self.message_sender.stop_flag = False
            result = await self.message_sender.send_messages(
                selected_accounts,
                self.targets,
                message_url,
                config_dict,
                callbacks
            )
            
            if result:
                self.total_sent = result["success"]
                self.total_failed = result["failed"]
                self.account_stats = result["account_stats"]
                
                # 显示统计
                self.log(f"\\n" + "="*50)
                self.log(f"✅ 任务完成!")
                self.log(f"📊 总计: {self.total_sent + self.total_failed} 条")
                self.log(f"✅ 成功: {self.total_sent} 条")
                self.log(f"❌ 失败: {self.total_failed} 条")
                
                total = self.total_sent + self.total_failed
                if total > 0:
                    success_rate = (self.total_sent / total * 100)
                    self.log(f"📈 成功率: {success_rate:.1f}%")
                
                self.log("="*50)
        
        except Exception as e:
            self.log(f"❌ 发送错误: {type(e).__name__}: {str(e)}")'''

# 替换
content = content.replace(old_send_async, new_send_async)

print("After replacing send_messages_async")

# 保存文件
with open('main_v2_full.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Done! New size:", len(content), "chars")
