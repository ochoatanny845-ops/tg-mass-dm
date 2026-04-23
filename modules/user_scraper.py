"""
用户采集模块
功能：
1. 默认采集
2. 聊天记录采集
3. 从已加入群采集
4. 从对话列表采集
5. 在线时间过滤
6. 多账号并发
7. 自动退群
8. Premium/头像/管理员过滤
"""

import asyncio
from datetime import datetime, timedelta
from telethon import TelegramClient, types, functions
from concurrent.futures import ThreadPoolExecutor

class UserScraper:
    def __init__(self, api_id, api_hash, logger):
        self.api_id = api_id
        self.api_hash = api_hash
        self.logger = logger
        self.stop_flag = False
        self.collected_users = []
    
    def log(self, message):
        """输出日志"""
        if self.logger:
            self.logger(message)
    
    async def scrape(self, accounts, targets, config):
        """
        主采集函数
        
        Args:
            accounts: 账号列表
            targets: 目标列表（群组链接或特殊标记）
            config: 配置字典
                - source: "list" | "joined" | "dialogs"
                - mode: "default" | "messages"
                - threads: 并发线程数
                - limit: 采集数量限制
                - filter_online_time: 是否过滤在线时间
                - online_days: 天数
                - include_recently: 包含最近在线
                - include_online: 包含当前在线
                - filter_bot: 排除机器人
                - filter_username: 仅有用户名
                - filter_premium: 仅 Premium
                - filter_photo: 仅有头像
                - filter_admin: 仅管理员
                - auto_leave: 自动退群
        """
        from concurrent.futures import ThreadPoolExecutor
        
        try:
            # 创建线程池
            max_workers = min(config.get("threads", 5), len(accounts))
            executor = ThreadPoolExecutor(max_workers=max_workers)
            
            tasks = []
            source = config.get("source", "list")
            
            # 根据采集来源处理
            if source == "joined":
                # 从已加入群采集
                self.log("📋 获取已加入的群组列表...")
                for account in accounts:
                    future = executor.submit(self._scrape_joined_groups_sync, account, config)
                    tasks.append(future)
            
            elif source == "dialogs":
                # 从对话列表采集
                self.log("💬 获取对话列表...")
                for account in accounts:
                    future = executor.submit(self._scrape_dialogs_sync, account, config)
                    tasks.append(future)
            
            else:
                # 从群列表采集
                for i, target in enumerate(targets):
                    if self.stop_flag:
                        break
                    
                    account = accounts[i % len(accounts)]
                    future = executor.submit(self._scrape_single_target_sync, account, target, i+1, len(targets), config)
                    tasks.append(future)
            
            # 等待所有任务完成
            collected_count = 0
            for future in tasks:
                if self.stop_flag:
                    break
                try:
                    users = future.result()
                    if users:
                        collected_count += len(users)
                except Exception as e:
                    self.log(f"❌ 任务失败: {str(e)[:50]}")
            
            executor.shutdown(wait=True)
            
            self.log(f"\n" + "="*50)
            self.log(f"✅ 采集完成!")
            self.log(f"📊 总共采集 {collected_count} 个用户")
            self.log("="*50)
            
            return self.collected_users

        except Exception as e:
            self.log(f"❌ 采集错误: {type(e).__name__}: {str(e)[:50]}")
            return []
    
    # ========== 同步包装函数 ==========
    
    def _scrape_single_target_sync(self, account, target, current, total, config):
        """同步方式采集单个目标（在线程池中运行）"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(self._scrape_single_target(account, target, current, total, config))
        finally:
            loop.close()
    
    def _scrape_joined_groups_sync(self, account, config):
        """同步方式采集已加入的群（在线程池中运行）"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(self._scrape_joined_groups(account, config))
        finally:
            loop.close()
    
    def _scrape_dialogs_sync(self, account, config):
        """同步方式采集对话列表（在线程池中运行）"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(self._scrape_dialogs(account, config))
        finally:
            loop.close()
    
    # ========== 异步采集函数 ==========
    
    async def _scrape_single_target(self, account, target, current, total, config):
        """采集单个目标"""
        try:
            client = TelegramClient(account["path"], self.api_id, self.api_hash)
            await client.connect()

            me = await client.get_me()
            account_name = f"@{me.username or me.phone}"
            
            self.log(f"\n[{current}/{total}] 📌 采集: {target} (账号: {account_name})")

            # 获取群组/频道实体
            entity = await client.get_entity(target)
            
            # 根据采集模式选择不同的方法
            mode = config.get("mode", "default")
            if mode == "messages":
                self.log(f"  💬 使用聊天记录模式")
                users_collected = await self._scrape_from_messages(client, entity, target, config)
            else:
                self.log(f"  🚀 使用默认模式")
                users_collected = await self._scrape_from_participants(client, entity, target, config)
            
            # 自动退群
            if config.get("auto_leave", False) and users_collected:
                try:
                    await client(functions.channels.LeaveChannelRequest(channel=entity))
                    self.log(f"  🚪 已退出群组")
                except:
                    pass
            
            await client.disconnect()
            
            self.log(f"  ✅ 完成: 采集 {len(users_collected)} 个用户")
            return users_collected

        except Exception as e:
            self.log(f"  ❌ 失败: {target} - {type(e).__name__}: {str(e)[:50]}")
            return []
    
    async def _scrape_from_participants(self, client, entity, target, config):
        """默认模式：从成员列表采集"""
        users_collected = []
        
        try:
            # 获取成员
            limit = config.get("limit", 500)
            participants = await client.get_participants(entity, limit=limit)
            
            for user in participants:
                if self.stop_flag:
                    break
                
                # 应用过滤条件
                if not self._check_user_filters(user, config):
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
                    users_collected.append(user_data)
        
        except Exception as e:
            self.log(f"    ⚠️ 采集成员失败: {str(e)[:50]}")
        
        return users_collected
    
    async def _scrape_from_messages(self, client, entity, target, config):
        """通过聊天记录采集（可采集隐藏成员群组）"""
        users_collected = []
        user_ids = set()
        
        try:
            self.log(f"    📨 获取聊天记录...")
            
            # 获取最近的消息（最多3000条）
            messages = await client.get_messages(entity, limit=3000)
            
            self.log(f"    📊 分析 {len(messages)} 条消息")
            
            limit = config.get("limit", 500)
            
            for msg in messages:
                if self.stop_flag:
                    break
                
                if not msg.sender:
                    continue
                
                # 避免重复
                if msg.sender_id in user_ids:
                    continue
                
                user_ids.add(msg.sender_id)
                
                # 获取完整用户信息
                try:
                    user = await client.get_entity(msg.sender_id)
                    
                    # 应用过滤条件
                    if not self._check_user_filters(user, config):
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
                        users_collected.append(user_data)
                        
                        # 达到限制后停止
                        if len(users_collected) >= limit:
                            break
                
                except Exception:
                    continue
        
        except Exception as e:
            self.log(f"    ⚠️ 获取消息失败: {str(e)[:50]}")
        
        return users_collected
    
    async def _scrape_joined_groups(self, account, config):
        """从已加入的群采集"""
        try:
            client = TelegramClient(account["path"], self.api_id, self.api_hash)
            await client.connect()

            me = await client.get_me()
            account_name = f"@{me.username or me.phone}"
            
            self.log(f"\n📌 账号: {account_name} - 获取已加入的群组...")

            # 获取所有对话
            dialogs = await client.get_dialogs()
            groups = [d for d in dialogs if d.is_group or d.is_channel]
            
            self.log(f"  📊 找到 {len(groups)} 个群组/频道")
            
            all_users = []
            limit = config.get("limit", 500)
            
            for i, dialog in enumerate(groups):
                if self.stop_flag:
                    break
                
                try:
                    entity = dialog.entity
                    entity_name = getattr(entity, 'title', '未知群组')
                    
                    self.log(f"  [{i+1}/{len(groups)}] 采集: {entity_name}")
                    
                    # 根据模式采集
                    mode = config.get("mode", "default")
                    if mode == "messages":
                        users = await self._scrape_from_messages(client, entity, entity_name, config)
                    else:
                        users = await self._scrape_from_participants(client, entity, entity_name, config)
                    
                    all_users.extend(users)
                    
                    # 自动退群
                    if config.get("auto_leave", False):
                        try:
                            await client(functions.channels.LeaveChannelRequest(channel=entity))
                            self.log(f"    🚪 已退出群组")
                        except:
                            pass
                    
                    # 达到限制
                    if len(all_users) >= limit:
                        break
                
                except Exception as e:
                    self.log(f"    ❌ 失败: {str(e)[:50]}")
            
            await client.disconnect()
            return all_users

        except Exception as e:
            self.log(f"❌ 账号失败: {str(e)[:50]}")
            return []
    
    async def _scrape_dialogs(self, account, config):
        """从对话列表采集（有对话的用户）"""
        try:
            client = TelegramClient(account["path"], self.api_id, self.api_hash)
            await client.connect()

            me = await client.get_me()
            account_name = f"@{me.username or me.phone}"
            
            self.log(f"\n📌 账号: {account_name} - 获取对话列表...")

            # 获取所有对话
            dialogs = await client.get_dialogs()
            users_dialogs = [d for d in dialogs if d.is_user and not d.entity.bot]
            
            self.log(f"  📊 找到 {len(users_dialogs)} 个用户对话")
            
            all_users = []
            limit = config.get("limit", 500)
            
            for i, dialog in enumerate(users_dialogs):
                if self.stop_flag:
                    break
                
                try:
                    user = dialog.entity
                    
                    # 应用过滤条件
                    if not self._check_user_filters(user, config):
                        continue
                    
                    # 添加到结果
                    user_data = {
                        "username": f"@{user.username}" if user.username else f"user_{user.id}",
                        "name": f"{user.first_name or ''} {user.last_name or ''}".strip() or "未知",
                        "source": "对话列表",
                        "selected": False
                    }
                    
                    # 检查是否已存在
                    if not any(u["username"] == user_data["username"] for u in self.collected_users):
                        self.collected_users.append(user_data)
                        all_users.append(user_data)
                    
                    # 达到限制
                    if len(all_users) >= limit:
                        break
                
                except Exception as e:
                    continue
            
            await client.disconnect()
            return all_users

        except Exception as e:
            self.log(f"❌ 账号失败: {str(e)[:50]}")
            return []
    
    # ========== 过滤函数 ==========
    
    def _check_user_filters(self, user, config):
        """检查用户是否符合过滤条件"""
        # 排除机器人
        if config.get("filter_bot", True) and user.bot:
            return False
        
        # 仅有用户名
        if config.get("filter_username", False) and not user.username:
            return False
        
        # 仅 Premium 会员
        if config.get("filter_premium", False) and not user.premium:
            return False
        
        # 仅有头像
        if config.get("filter_photo", False) and not user.photo:
            return False
        
        # 在线时间过滤
        if config.get("filter_online_time", False):
            online_days = config.get("online_days", 3)
            cutoff_time = datetime.now() - timedelta(days=online_days)
            
            if user.status:
                # 当前在线
                if isinstance(user.status, types.UserStatusOnline):
                    if config.get("include_online", True):
                        return True
                # 最近在线（隐藏具体时间）
                elif isinstance(user.status, types.UserStatusRecently):
                    if config.get("include_recently", True):
                        return True
                # 离线，检查离线时间
                elif isinstance(user.status, types.UserStatusOffline):
                    if hasattr(user.status, 'was_online'):
                        if user.status.was_online >= cutoff_time:
                            return True
                        else:
                            return False
                # 一周内/一个月内/很久未上线（隐藏时间）
                elif isinstance(user.status, (types.UserStatusLastWeek, types.UserStatusLastMonth, types.UserStatusEmpty)):
                    # 这些状态无法精确判断，默认排除
                    return False
            else:
                # 没有状态信息，默认排除
                return False
        
        return True
    
    def stop(self):
        """停止采集"""
        self.stop_flag = True
