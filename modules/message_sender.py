"""
消息发送模块
功能：
1. 批量私信
2. 随机 Emoji
3. 频率限制处理
4. 错误处理
5. 自动删除无法发送的用户
"""

import asyncio
import random
from datetime import datetime
from telethon import TelegramClient, errors, functions
from config import RANDOM_EMOJIS

class MessageSender:
    def __init__(self, api_id, api_hash, logger):
        self.api_id = api_id
        self.api_hash = api_hash
        self.logger = logger
        self.stop_flag = False
        
        # 统计
        self.total_success = 0
        self.total_failed = 0
        self.account_stats = {}
    
    def log(self, message):
        """输出日志"""
        if self.logger:
            self.logger(message)
    
    async def send_messages(self, accounts, targets, message_url, config, callbacks=None):
        """
        批量发送消息
        
        Args:
            accounts: 账号列表
            targets: 目标用户列表
            message_url: 消息URL（格式：https://t.me/channel/msgid）
            config: 配置字典
                - parallel_threads: 并发线程数
                - start_delay: 启动间隔
                - send_delay_min: 发送间隔最小值
                - send_delay_max: 发送间隔最大值
                - consecutive_fails_threshold: 连续失败阈值
                - ignore_mutual: 是否无视双向限制
            callbacks: 回调函数字典
                - on_update: 更新进度回调
                - on_remove_target: 删除目标回调
        
        Returns:
            统计结果字典
        """
        try:
            # 解析消息URL
            parts = message_url.split('/')
            channel_username = parts[-2]
            msg_id = int(parts[-1])
            
            self.log(f"📨 消息来源: @{channel_username} (ID: {msg_id})")
            
            # 启动多个账号
            tasks = []
            for i, account in enumerate(accounts):
                if self.stop_flag:
                    break
                
                # 启动间隔
                if i > 0:
                    await asyncio.sleep(config.get("start_delay", 1))
                
                task = asyncio.create_task(
                    self._send_with_account(
                        account, 
                        targets, 
                        channel_username, 
                        msg_id, 
                        config,
                        callbacks
                    )
                )
                tasks.append(task)
            
            # 等待所有任务完成
            await asyncio.gather(*tasks)
            
            self.log(f"\n" + "="*50)
            self.log(f"✅ 全部完成!")
            self.log(f"📊 成功: {self.total_success} | 失败: {self.total_failed}")
            self.log("="*50)
            
            return {
                "success": self.total_success,
                "failed": self.total_failed,
                "account_stats": self.account_stats
            }

        except Exception as e:
            self.log(f"❌ 发送错误: {type(e).__name__}: {str(e)[:50]}")
            return None
    
    async def _send_with_account(self, account, targets, channel_username, msg_id, config, callbacks):
        """使用单个账号发送"""
        try:
            client = TelegramClient(account["path"], self.api_id, self.api_hash)
            
            # 设置代理
            if account.get("proxy"):
                # 代理逻辑（如果需要）
                pass
            
            await client.connect()
            
            me = await client.get_me()
            account_name = account.get("phone", me.phone)
            
            self.log(f"\n[{len(self.account_stats)+1}/{len(targets)}] 📱 启动账号: {account_name}")
            
            # 初始化统计
            self.account_stats[account_name] = {
                "success": 0,
                "failed": 0
            }
            
            consecutive_fails = 0
            threshold = config.get("consecutive_fails_threshold", 10)
            
            for target_username in targets:
                if self.stop_flag:
                    break
                
                try:
                    # 添加随机 Emoji
                    emoji_count = random.randint(1, 2)
                    position_mode = random.randint(1, 5)
                    
                    if emoji_count == 1:
                        emoji = random.choice(RANDOM_EMOJIS)
                        if position_mode <= 2:
                            caption = f"{emoji} "
                        else:
                            caption = f" {emoji}"
                    else:
                        emoji1 = random.choice(RANDOM_EMOJIS)
                        emoji2 = random.choice(RANDOM_EMOJIS)
                        if position_mode == 1:
                            caption = f"{emoji1}{emoji2} "
                        elif position_mode == 2:
                            caption = f" {emoji1}{emoji2}"
                        else:
                            caption = f"{emoji1} {emoji2}"
                    
                    # 转发消息
                    await client.forward_messages(
                        entity=target_username,
                        messages=msg_id,
                        from_peer=channel_username
                    )
                    
                    self.log(f"  ✅ [{account_name}] 成功发送给: {target_username}")
                    
                    self.account_stats[account_name]["success"] += 1
                    self.total_success += 1
                    consecutive_fails = 0  # 重置连续失败
                    
                    # 回调更新进度
                    if callbacks and "on_update" in callbacks:
                        callbacks["on_update"]()
                    
                    # 发送间隔
                    delay_min = config.get("send_delay_min", 3)
                    delay_max = config.get("send_delay_max", 8)
                    await asyncio.sleep(random.uniform(delay_min, delay_max))
                
                except errors.FloodWaitError as e:
                    # 频率限制（不计入连续失败）
                    self.log(f"  ⏳ [{account_name}] 触发频率限制（{e.seconds}秒）")
                    self.log(f"     目标用户 {target_username} 标记为失败，跳过")
                    self.account_stats[account_name]["failed"] += 1
                    self.total_failed += 1
                    # 不增加 consecutive_fails
                    continue
                
                except Exception as e:
                    error_str = str(e).lower()
                    
                    # You can't write in this chat
                    if "can't write" in error_str or "you can't write" in error_str:
                        self.log(f"  ⚠️ [{account_name}] 用户禁止陌生人发消息: {target_username} - 已从列表删除")
                        self.account_stats[account_name]["failed"] += 1
                        self.total_failed += 1
                        # 不计入连续失败
                        # 删除用户
                        if callbacks and "on_remove_target" in callbacks:
                            callbacks["on_remove_target"](target_username)
                        continue
                    
                    # Premium required
                    elif "premium" in error_str and "required" in error_str:
                        self.log(f"  ⚠️ [{account_name}] 目标用户需要 Premium: {target_username} - 已从列表删除")
                        self.account_stats[account_name]["failed"] += 1
                        self.total_failed += 1
                        if callbacks and "on_remove_target" in callbacks:
                            callbacks["on_remove_target"](target_username)
                        continue
                    
                    # Payment required
                    elif "payment" in error_str and "required" in error_str:
                        self.log(f"  ⚠️ [{account_name}] 目标用户需要绑定支付: {target_username} - 已从列表删除")
                        self.account_stats[account_name]["failed"] += 1
                        self.total_failed += 1
                        if callbacks and "on_remove_target" in callbacks:
                            callbacks["on_remove_target"](target_username)
                        continue
                    
                    # Cannot find entity
                    elif "cannot find" in error_str or "no user has" in error_str:
                        self.log(f"  ❌ [{account_name}] 用户不存在: {target_username} - 已从列表删除")
                        self.account_stats[account_name]["failed"] += 1
                        self.total_failed += 1
                        if callbacks and "on_remove_target" in callbacks:
                            callbacks["on_remove_target"](target_username)
                        continue
                    
                    # Too many requests (频率限制，不计入连续失败)
                    elif "too many requests" in error_str or "flood" in error_str:
                        self.log(f"  ⏳ [{account_name}] 触发频率限制")
                        self.log(f"     目标用户 {target_username} 标记为失败，跳过")
                        self.account_stats[account_name]["failed"] += 1
                        self.total_failed += 1
                        # 不增加 consecutive_fails
                        continue
                    
                    # 其他错误（真正的失败）
                    else:
                        self.log(f"  ❌ [{account_name}] 发送失败: {target_username} - {type(e).__name__}")
                        self.account_stats[account_name]["failed"] += 1
                        self.total_failed += 1
                        consecutive_fails += 1
                        
                        if callbacks and "on_update" in callbacks:
                            callbacks["on_update"]()
                
                # 检查连续失败
                if consecutive_fails >= threshold:
                    self.log(f"\n⚠️ [{account_name}] 连续失败 {consecutive_fails} 次")
                    
                    # 检查 SpamBot
                    if not config.get("ignore_mutual", False):
                        self.log(f"  🤖 检查 SpamBot 限制状态...")
                        try:
                            spambot = await client.get_entity("@SpamBot")
                            await client.send_message(spambot, "/start")
                            await asyncio.sleep(2)
                            
                            messages = await client.get_messages(spambot, limit=1)
                            if messages:
                                reply = messages[0].message
                                if "you're free" in reply.lower() or "good news" in reply.lower():
                                    self.log(f"  ✅ 账号正常，继续发送")
                                    consecutive_fails = 0
                                    continue
                                else:
                                    self.log(f"  ⚠️ 账号受限，停止该账号")
                                    break
                        except:
                            pass
                    
                    self.log(f"  ⚠️ 停止该账号")
                    break
            
            await client.disconnect()

        except Exception as e:
            self.log(f"❌ 账号错误: {type(e).__name__}: {str(e)[:50]}")
    
    def stop(self):
        """停止发送"""
        self.stop_flag = True
