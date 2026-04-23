"""
消息发送模块 - 完整版
保留原有所有功能和逻辑
"""

import asyncio
import random
from datetime import datetime
from pathlib import Path
from telethon import TelegramClient, errors, functions
from config import RANDOM_EMOJIS

class MessageSender:
    def __init__(self, api_id, api_hash, logger):
        self.api_id = api_id
        self.api_hash = api_hash
        self.logger = logger
        self.stop_flag = False
        
        # 统计
        self.total_sent = 0
        self.total_failed = 0
        self.account_stats = {}
        self.send_lock = None
    
    def log(self, message):
        """输出日志"""
        if self.logger:
            self.logger(message)
    
    async def send_messages(self, accounts, targets, config, callbacks=None):
        """
        批量发送消息（完整版，保留所有原有逻辑）
        
        Args:
            accounts: 账号列表
            targets: 目标用户列表（共享列表，会被修改）
            config: 配置字典
                - send_type: "forward" | "text"
                - forward_urls: [转发链接列表]
                - hide_source: 是否隐藏来源
                - pin_delay: 置顶延迟（秒）
                - message_text: 文本消息内容
                - thread_count: 并发账号数
                - thread_interval: 批次间隔
                - send_delay_min: 发送间隔最小值
                - send_delay_max: 发送间隔最大值
                - per_account_limit: 单账号上限
                - total_limit: 任务总上限
            callbacks: 回调函数字典
                - on_update: 更新进度回调
                - on_remove_target: 删除目标回调
                - is_running: 运行状态检查函数
        
        Returns:
            统计结果字典
        """
        try:
            self.total_sent = 0
            self.total_failed = 0
            self.send_lock = asyncio.Lock()
            self.account_stats = {}
            
            thread_count = config.get("thread_count", 2)
            
            # 批次发送
            for batch_start in range(0, len(accounts), thread_count):
                if self.stop_flag or (callbacks and not callbacks.get("is_running", lambda: True)()):
                    self.log("⏸️ 任务已停止")
                    break
                
                # 检查是否还有可用账号
                available_accounts = [acc for acc in accounts if acc.get("selected", False)]
                if not available_accounts:
                    self.log("⚠️ 所有选中的账号都已不可用,自动停止任务")
                    break
                
                batch = accounts[batch_start:batch_start + thread_count]
                
                self.log(f"\n🔄 启动批次 {batch_start//thread_count + 1}: {len(batch)} 个账号并发")
                
                tasks = []
                for i, account in enumerate(batch):
                    task = self._send_with_account(
                        account,
                        batch_start + i + 1,
                        len(accounts),
                        targets,
                        config,
                        callbacks
                    )
                    tasks.append(task)
                
                await asyncio.gather(*tasks, return_exceptions=True)
                
                if batch_start + thread_count < len(accounts):
                    interval = config.get("thread_interval", 1)
                    self.log(f"⏱️ 批次完成,等待 {interval} 秒启动下一批...")
                    await asyncio.sleep(interval)
            
            # 显示总体统计
            self.log(f"\n" + "="*50)
            self.log(f"✅ 任务完成!")
            self.log(f"📊 总计: {self.total_sent + self.total_failed} 条")
            self.log(f"✅ 成功: {self.total_sent} 条")
            self.log(f"❌ 失败: {self.total_failed} 条")
            
            # 计算成功率
            total = self.total_sent + self.total_failed
            if total > 0:
                success_rate = (self.total_sent / total * 100)
                self.log(f"📈 成功率: {success_rate:.1f}%")
                
                # 根据成功率给出建议
                if success_rate < 10:
                    self.log(f"\n⚠️ 成功率过低 ({success_rate:.1f}%),建议检查:")
                    self.log(f"   1. 大量账号已被封禁 → 删除封禁账号")
                    self.log(f"   2. 转发链接无效 → 检查链接是否正确")
                    self.log(f"   3. 目标用户名错误 → 检查用户名列表")
                elif success_rate < 30:
                    self.log(f"\n⚠️ 成功率较低 ({success_rate:.1f}%),建议:")
                    self.log(f"   1. 检查部分账号是否被封禁")
                    self.log(f"   2. 增加发送间隔(避免请求限制)")
                elif success_rate < 60:
                    self.log(f"\n💡 成功率中等 ({success_rate:.1f}%),可优化:")
                    self.log(f"   1. 调整发送间隔")
                    self.log(f"   2. 检查目标用户质量")
                else:
                    self.log(f"\n✅ 成功率良好 ({success_rate:.1f}%)")
            
            self.log("="*50)
            
            # 显示每个账号的统计
            if self.account_stats:
                self.log(f"\n📈 各账号发送统计:")
                for account_name, stats in sorted(self.account_stats.items()):
                    success = stats.get("sent", 0)
                    failed = stats.get("failed", 0)
                    total_acc = success + failed
                    success_rate_acc = (success / total_acc * 100) if total_acc > 0 else 0
                    self.log(f"  📱 {account_name}: ✅ {success} 条 | ❌ {failed} 条 | 成功率 {success_rate_acc:.1f}%")
            
            return {
                "success": self.total_sent,
                "failed": self.total_failed,
                "account_stats": self.account_stats
            }

        except Exception as e:
            self.log(f"❌ 发送错误: {type(e).__name__}: {str(e)}")
            return None
    
    async def _send_with_account(self, account, index, total, targets, config, callbacks):
        """使用单个账号发送（保留所有原有逻辑）"""
        self.log(f"\n[{index}/{total}] 📱 启动账号: {Path(account['path']).stem}")
        
        try:
            client = TelegramClient(account["path"], self.api_id, self.api_hash)
            await client.connect()
            
            me = await client.get_me()
            
            # 检查登录
            if not me:
                self.log(f"  ❌ 登录失败: 账号无效或已失效")
                account["status"] = "⚠️ 登录失败"
                account["selected"] = False
                await client.disconnect()
                return
            
            # 账号名称
            account_name = me.phone or me.username or str(me.id)
            self.log(f"  ✅ 已登录: {account_name}")
            
            # 初始化统计
            if account_name not in self.account_stats:
                self.account_stats[account_name] = {"sent": 0, "failed": 0}
            
            account_sent = 0
            consecutive_fails = 0
            has_spam_restriction = False
            
            # 发送循环
            while not self.stop_flag and (not callbacks or callbacks.get("is_running", lambda: True)()):
                # 检查连续失败
                if consecutive_fails >= 10:
                    self.log(f"  🚫 [{account_name}] 连续失败 {consecutive_fails} 次,停止该账号")
                    
                    # 检查 SpamBot
                    if await self._check_spambot(client, account_name):
                        break
                    else:
                        consecutive_fails = 0
                        continue
                
                # 获取目标
                async with self.send_lock:
                    if not targets or len(targets) == 0:
                        self.log(f"  ✅ [{account_name}] 目标列表已空,完成发送")
                        break
                    
                    target = targets.pop(0)
                
                # 检查限制
                per_account_limit = config.get("per_account_limit", 999999)
                if account_sent >= per_account_limit:
                    self.log(f"  ⚠️ [{account_name}] 达到单账号上限 ({per_account_limit})")
                    break
                
                async with self.send_lock:
                    total_limit = config.get("total_limit", 999999)
                    if self.total_sent >= total_limit:
                        self.log(f"  ⚠️ 达到任务总上限 ({total_limit})")
                        if callbacks and "set_running" in callbacks:
                            callbacks["set_running"](False)
                        break
                
                # 执行发送
                try:
                    username = target.lstrip("@")
                    
                    send_type = config.get("send_type", "forward")
                    
                    if send_type == "forward":
                        # 转发模式
                        success = await self._send_forward(
                            client,
                            account_name,
                            username,
                            config
                        )
                    else:
                        # 文本模式
                        success = await self._send_text(
                            client,
                            account_name,
                            username,
                            config
                        )
                    
                    if success:
                        async with self.send_lock:
                            self.total_sent += 1
                            self.account_stats[account_name]["sent"] += 1
                            account_sent += 1
                            if callbacks and "on_update" in callbacks:
                                callbacks["on_update"]()
                            if callbacks and "on_remove_target" in callbacks:
                                callbacks["on_remove_target"](target)
                        
                        consecutive_fails = 0
                    else:
                        async with self.send_lock:
                            self.total_failed += 1
                            self.account_stats[account_name]["failed"] += 1
                            if callbacks and "on_update" in callbacks:
                                callbacks["on_update"]()
                        
                        consecutive_fails += 1
                    
                    # 发送间隔
                    delay_min = config.get("send_delay_min", 3)
                    delay_max = config.get("send_delay_max", 8)
                    await asyncio.sleep(random.uniform(delay_min, delay_max))
                
                except Exception as e:
                    self.log(f"  ❌ [{account_name}] 发送异常: {str(e)}")
                    consecutive_fails += 1
            
            await client.disconnect()
            self.log(f"  📊 [{account_name}] 完成,本账号发送: {account_sent} 条")

        except Exception as e:
            self.log(f"  ❌ 账号错误: {type(e).__name__}: {str(e)}")
    
    async def _send_forward(self, client, account_name, username, config):
        """转发消息（保留所有原有逻辑）"""
        try:
            # 随机选择转发链接
            forward_urls = config.get("forward_urls", [])
            if not forward_urls:
                self.log(f"  ⚠️ [{account_name}] 未设置转发链接,跳过: @{username}")
                return False
            
            forward_url = random.choice(forward_urls)
            
            # 解析链接
            if "t.me/" not in forward_url:
                self.log(f"  ⚠️ [{account_name}] 无效链接: {forward_url}")
                return False
            
            parts = forward_url.split("/")
            if len(parts) < 2:
                self.log(f"  ⚠️ [{account_name}] 链接格式错误: {forward_url}")
                return False
            
            channel_username = parts[-2]
            message_id_str = parts[-1].split("?")[0].split("#")[0]
            
            self.log(f"  🔍 [{account_name}] 解析链接: {forward_url}")
            self.log(f"      频道: {channel_username}, 消息ID: {message_id_str}")
            
            message_id = int(message_id_str)
            
            # 获取原始消息
            try:
                channel = await client.get_entity(channel_username)
                message_obj = await client.get_messages(channel, ids=message_id)
            except ValueError as channel_error:
                error_msg = str(channel_error).lower()
                if "no user" in error_msg or "no channel" in error_msg:
                    self.log(f"  ❌ [{account_name}] 转发失败: @{username}")
                    self.log(f"      账号无法访问频道 @{channel_username} (可能被封禁或未加入)")
                    return False
                else:
                    self.log(f"  ❌ [{account_name}] 获取频道失败: {channel_error}")
                    return False
            
            if not message_obj:
                self.log(f"  ❌ [{account_name}] 无法获取原始消息")
                return False
            
            # 发送消息
            hide_source = config.get("hide_source", False)
            
            if hide_source:
                # 隐藏来源
                sent_msg = await client.send_message(
                    username,
                    message_obj.text or message_obj.message,
                    file=message_obj.media if message_obj.media else None,
                    silent=True
                )
            else:
                # 显示来源
                sent_msg = await client.forward_messages(
                    username,
                    message_obj
                )
            
            # 验证发送
            if not sent_msg or not sent_msg.id:
                self.log(f"  ❌ [{account_name}] 发送失败,未收到消息ID")
                return False
            
            hide_text = "(隐藏来源)" if hide_source else "(显示来源)"
            self.log(f"  ✅ [{account_name}] 转发成功: @{username} {hide_text} (msg_id: {sent_msg.id})")
            
            # 置顶功能
            pin_delay = config.get("pin_delay", 0)
            if pin_delay > 0:
                self.log(f"      等待 {pin_delay} 秒后置顶消息...")
                await asyncio.sleep(pin_delay)
                
                if not self.stop_flag:
                    try:
                        await client.pin_message(username, sent_msg.id, notify=False)
                        self.log(f"      ✅ 消息已置顶")
                    except Exception as pin_error:
                        self.log(f"      ⚠️ 置顶失败: {str(pin_error)}")
            
            return True
        
        except Exception as e:
            error_str = str(e).lower()
            
            # 详细错误处理
            if "can't write" in error_str or "you can't write" in error_str:
                self.log(f"  ⚠️ [{account_name}] 用户禁止陌生人发消息: @{username}")
                return False
            elif "premium" in error_str and "required" in error_str:
                self.log(f"  ⚠️ [{account_name}] 目标用户需要 Premium: @{username}")
                return False
            elif "cannot find" in error_str or "no user has" in error_str:
                self.log(f"  ❌ [{account_name}] 用户不存在: @{username}")
                return False
            else:
                self.log(f"  ❌ [{account_name}] 转发失败: @{username}")
                self.log(f"      {str(e)}")
                return False
    
    async def _send_text(self, client, account_name, username, config):
        """发送文本消息（保留所有原有逻辑）"""
        try:
            message_text = config.get("message_text", "")
            if not message_text:
                self.log(f"  ⚠️ [{account_name}] 未设置文本消息,跳过: @{username}")
                return False
            
            # 添加随机 Emoji
            emoji_count = random.randint(1, 2)
            position_mode = random.randint(1, 5)
            
            if emoji_count == 1:
                emoji = random.choice(RANDOM_EMOJIS)
                if position_mode <= 2:
                    final_text = f"{emoji} {message_text}"
                else:
                    final_text = f"{message_text} {emoji}"
            else:
                emoji1 = random.choice(RANDOM_EMOJIS)
                emoji2 = random.choice(RANDOM_EMOJIS)
                if position_mode == 1:
                    final_text = f"{emoji1}{emoji2} {message_text}"
                elif position_mode == 2:
                    final_text = f"{message_text} {emoji1}{emoji2}"
                else:
                    final_text = f"{emoji1} {message_text} {emoji2}"
            
            # 发送消息
            sent_msg = await client.send_message(username, final_text)
            
            if not sent_msg or not sent_msg.id:
                self.log(f"  ❌ [{account_name}] 发送失败,未收到消息ID")
                return False
            
            self.log(f"  ✅ [{account_name}] 文本发送成功: @{username}")
            return True
        
        except Exception as e:
            error_str = str(e).lower()
            
            if "can't write" in error_str:
                self.log(f"  ⚠️ [{account_name}] 用户禁止陌生人发消息: @{username}")
            elif "premium" in error_str and "required" in error_str:
                self.log(f"  ⚠️ [{account_name}] 目标用户需要 Premium: @{username}")
            elif "cannot find" in error_str:
                self.log(f"  ❌ [{account_name}] 用户不存在: @{username}")
            else:
                self.log(f"  ❌ [{account_name}] 文本发送失败: @{username}")
                self.log(f"      {str(e)}")
            
            return False
    
    async def _check_spambot(self, client, account_name):
        """检查 SpamBot 限制状态"""
        try:
            self.log(f"  🤖 [{account_name}] 检查 SpamBot 限制状态...")
            
            spambot = await client.get_entity("@SpamBot")
            await client.send_message(spambot, "/start")
            await asyncio.sleep(2)
            
            messages = await client.get_messages(spambot, limit=1)
            if messages:
                reply_text = messages[0].message
                
                restriction_keywords = [
                    "限制", "restriction", "spam", "flood", "banned", "限流",
                    "temporarily", "暂时", "永久", "permanent"
                ]
                
                has_restriction = any(keyword in reply_text.lower() for keyword in restriction_keywords)
                
                if has_restriction:
                    self.log(f"  ⚠️ [{account_name}] SpamBot 检测到限制:")
                    self.log(f"      {reply_text[:100]}")
                    return True
                else:
                    self.log(f"  ✅ [{account_name}] SpamBot 无限制,可以继续发送")
                    return False
            else:
                self.log(f"  ⚠️ [{account_name}] SpamBot 未回复")
                return True
        
        except Exception as e:
            self.log(f"  ⚠️ [{account_name}] 检查 SpamBot 失败: {e}")
            return True
    
    def stop(self):
        """停止发送"""
        self.stop_flag = True
