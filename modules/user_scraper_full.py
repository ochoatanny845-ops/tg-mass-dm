"""
用户采集模块 - 完整版
保留原有所有功能和逻辑，包括UI更新
"""

import asyncio
from datetime import datetime, timedelta
from telethon import TelegramClient, types
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

class UserScraper:
    def __init__(self, api_id, api_hash, logger, root=None):
        self.api_id = api_id
        self.api_hash = api_hash
        self.logger = logger
        self.root = root  # Tkinter root for UI updates
        self.stop_flag = False
        self.collected_users = []
    
    def log(self, message):
        """输出日志"""
        if self.logger:
            self.logger(message)
    
    async def scrape(self, accounts, targets, config, ui_callbacks=None):
        """
        主采集函数（完整版）
        
        Args:
            accounts: 账号列表
            targets: 目标列表
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
            ui_callbacks: UI回调函数字典
                - insert_row: 插入行回调 lambda user_data: ...
                - is_running: 运行状态检查函数
        
        Returns:
            采集到的用户列表
        """
        from concurrent.futures import ThreadPoolExecutor
        
        try:
            # 创建线程池
            max_workers = min(config.get("threads", 5), len(accounts))
            executor = ThreadPoolExecutor(max_workers=max_workers)
            
            collected_count = 0
            tasks = []
            
            source = config.get("source", "list")
            
            # 根据采集来源处理
            if source == "joined":
                # 从已加入群采集
                self.log("📋 获取已加入的群组列表...")
                for account in accounts:
                    if self.stop_flag or (ui_callbacks and not ui_callbacks.get("is_running", lambda: True)()):
                        break
                    future = executor.submit(
                        self._scrape_joined_groups_sync,
                        account,
                        config,
                        ui_callbacks
                    )
                    tasks.append(future)
            
            elif source == "dialogs":
                # 从对话列表采集
                self.log("💬 获取对话列表...")
                for account in accounts:
                    if self.stop_flag or (ui_callbacks and not ui_callbacks.get("is_running", lambda: True)()):
                        break
                    future = executor.submit(
                        self._scrape_dialogs_sync,
                        account,
                        config,
                        ui_callbacks
                    )
                    tasks.append(future)
            
            else:
                # 从群列表采集
                for i, target in enumerate(targets):
                    if self.stop_flag or (ui_callbacks and not ui_callbacks.get("is_running", lambda: True)()):
                        break
                    
                    # 更新进度
                    if ui_callbacks and "update_progress" in ui_callbacks:
                        ui_callbacks["update_progress"](i, len(targets))
                    
                    account = accounts[i % len(accounts)]
                    future = executor.submit(
                        self._scrape_single_target_sync,
                        account,
                        target,
                        i+1,
                        len(targets),
                        config,
                        ui_callbacks
                    )
                    tasks.append(future)
            
            # 等待所有任务完成
            completed = 0
            for future in tasks:
                if self.stop_flag or (ui_callbacks and not ui_callbacks.get("is_running", lambda: True)()):
                    break
                try:
                    users = future.result()
                    if users:
                        collected_count += len(users)
                    completed += 1
                    
                    # 更新进度
                    if ui_callbacks and "update_progress" in ui_callbacks:
                        ui_callbacks["update_progress"](completed, len(tasks))
                        
                except Exception as e:
                    self.log(f"❌ 任务失败: {str(e)[:50]}")
                    completed += 1
                    
                    # 更新进度（即使失败也更新）
                    if ui_callbacks and "update_progress" in ui_callbacks:
                        ui_callbacks["update_progress"](completed, len(tasks))
            
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
    
    def _scrape_single_target_sync(self, account, target, current, total, config, ui_callbacks):
        """同步方式采集单个目标"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(
                self._scrape_single_target(account, target, current, total, config, ui_callbacks)
            )
        finally:
            loop.close()
    
    def _scrape_joined_groups_sync(self, account, config, ui_callbacks):
        """同步方式采集已加入的群"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(
                self._scrape_joined_groups(account, config, ui_callbacks)
            )
        finally:
            loop.close()
    
    def _scrape_dialogs_sync(self, account, config, ui_callbacks):
        """同步方式采集对话列表"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(
                self._scrape_dialogs(account, config, ui_callbacks)
            )
        finally:
            loop.close()
    
    # ========== 异步采集函数 ==========
    
    async def _scrape_single_target(self, account, target, current, total, config, ui_callbacks):
        """采集单个目标（完整版）"""
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
                users_collected = await self._scrape_from_messages(client, entity, target, config, ui_callbacks)
            else:
                self.log(f"  🚀 使用默认模式")
                users_collected = await self._scrape_from_participants(client, entity, target, config, ui_callbacks)
            
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
    
    async def _scrape_from_participants(self, client, entity, target, config, ui_callbacks):
        """默认模式：从成员列表采集（完整版）"""
        users_collected = []
        
        try:
            # 获取成员（0或999999=不限制，获取所有）
            limit = config.get("limit", 500)
            if limit == 0 or limit >= 999999:
                # 不限制：使用iter_participants获取所有成员
                self.log(f"    📊 获取所有成员（无限制）...")
                participants = []
                async for user in client.iter_participants(entity):
                    participants.append(user)
                    if len(participants) % 1000 == 0:
                        self.log(f"       已获取 {len(participants)} 个成员...")
            else:
                participants = await client.get_participants(entity, limit=limit)
            
            self.log(f"    📊 分析 {len(participants)} 个成员")
            
            for user in participants:
                if self.stop_flag or (ui_callbacks and not ui_callbacks.get("is_running", lambda: True)()):
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
                    
                    # UI更新回调
                    if ui_callbacks and "insert_row" in ui_callbacks and self.root:
                        self.root.after(0, lambda u=user_data: ui_callbacks["insert_row"](u))
        
        except Exception as e:
            self.log(f"    ⚠️ 采集成员失败: {str(e)[:50]}")
        
        return users_collected
    
    async def _scrape_from_messages(self, client, entity, target, config, ui_callbacks):
        """通过聊天记录采集（完整版）- 按时间范围"""
        users_collected = []
        user_ids = set()
        
        # 过滤统计
        filter_stats = {
            "total_messages": 0,
            "has_sender": 0,
            "unique_users": 0,
            "bot": 0,
            "no_username": 0,
            "no_premium": 0,
            "no_photo": 0,
            "online_filtered": 0,
            "passed": 0
        }
        
        try:
            # 使用消息数量限制（如果设置）或时间范围
            message_limit = config.get("message_limit", 0)
            days = None  # 初始化days变量
            
            if message_limit > 0:
                # 按数量限制
                self.log(f"    📨 获取最近 {message_limit} 条消息...")
                
                messages = await client.get_messages(entity, limit=message_limit)
                
                self.log(f"    📊 分析 {len(messages)} 条消息")
            else:
                # 按时间范围（旧逻辑）
                if config.get("filter_online_time", False):
                    days = config.get("online_days", 3)
                else:
                    days = 3
                
                from datetime import datetime, timedelta
                cutoff_time = datetime.now() - timedelta(days=days)
                
                self.log(f"    📨 获取最近 {days} 天的聊天记录...")
                
                # 按时间范围获取消息（优化：减少进度提示频率）
                messages = []
                last_progress = 0
                async for msg in client.iter_messages(entity, offset_date=cutoff_time):
                    messages.append(msg)
                    
                    # 每5000条显示进度
                    if len(messages) % 5000 == 0:
                        self.log(f"       已获取 {len(messages)} 条消息...")
                        last_progress = len(messages)
                    
                    # 安全上限：最多30000条消息
                    if len(messages) >= 30000:
                        self.log(f"       达到消息上限 (30000 条)，停止获取")
                        break
                
                # 显示最终消息数（如果不是5000的倍数）
                if len(messages) % 5000 != 0 and len(messages) != last_progress:
                    self.log(f"       已获取 {len(messages)} 条消息...")
                
                self.log(f"    📊 分析 {len(messages)} 条消息（最近 {days} 天）")
            
            filter_stats["total_messages"] = len(messages)
            
            limit = config.get("limit", 500)
            
            self.log(f"    ⚡ 快速分析用户信息...")
            
            for msg in messages:
                if self.stop_flag or (ui_callbacks and not ui_callbacks.get("is_running", lambda: True)()):
                    break
                
                if not msg.sender:
                    continue
                
                filter_stats["has_sender"] += 1
                
                # 避免重复
                if msg.sender_id in user_ids:
                    continue
                
                user_ids.add(msg.sender_id)
                filter_stats["unique_users"] += 1
                
                # 获取完整用户信息
                try:
                    # 方法1：尝试获取完整用户（包含premium等字段）
                    try:
                        from telethon.tl.functions.users import GetFullUserRequest
                        full_result = await client(GetFullUserRequest(msg.sender_id))
                        user = full_result.users[0]  # 完整用户对象
                    except:
                        # 后备：基本get_entity
                        user = await client.get_entity(msg.sender_id)
                    
                    # 调试：检查premium字段（前5个用户）
                    if filter_stats["unique_users"] <= 5:
                        premium_val = getattr(user, 'premium', None)
                        self.log(f"       DEBUG: user_id={user.id}, username={user.username}, premium={premium_val}, premium==True:{premium_val is True}")
                    
                    # 统计过滤原因
                    if config.get("filter_bot", True) and user.bot:
                        filter_stats["bot"] += 1
                        continue
                    
                    if config.get("filter_username", False) and not user.username:
                        filter_stats["no_username"] += 1
                        continue
                    
                    # Premium过滤：premium=True才是会员，None/False都不是
                    if config.get("filter_premium", False) and not getattr(user, 'premium', False):
                        filter_stats["no_premium"] += 1
                        continue
                    
                    if config.get("filter_photo", False) and not user.photo:
                        filter_stats["no_photo"] += 1
                        continue
                    
                    # 在线时间过滤
                    if config.get("filter_online_time", False):
                        if not self._check_online_time(user, config):
                            filter_stats["online_filtered"] += 1
                            continue
                    
                    filter_stats["passed"] += 1
                    
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
                        
                        # UI更新回调
                        if ui_callbacks and "insert_row" in ui_callbacks and self.root:
                            self.root.after(0, lambda u=user_data: ui_callbacks["insert_row"](u))
                        
                        # 达到限制后停止（0或999999=不限制）
                        if limit > 0 and limit < 999999 and len(users_collected) >= limit:
                            self.log(f"       ⚠️ 已达到数量限制 ({limit})，停止采集")
                            break
                
                except Exception:
                    continue
            
            # 显示过滤统计
            self.log(f"    📊 过滤统计:")
            if days is not None:
                self.log(f"       总消息数: {filter_stats['total_messages']} (最近 {days} 天)")
            else:
                self.log(f"       总消息数: {filter_stats['total_messages']}")
            self.log(f"       有发送者: {filter_stats['has_sender']}")
            self.log(f"       唯一用户: {filter_stats['unique_users']}")
            if filter_stats['bot'] > 0:
                self.log(f"       ❌ 机器人: {filter_stats['bot']}")
            if filter_stats['no_username'] > 0:
                self.log(f"       ❌ 无用户名: {filter_stats['no_username']}")
            if filter_stats['no_premium'] > 0:
                self.log(f"       ❌ 非Premium: {filter_stats['no_premium']}")
            if filter_stats['no_photo'] > 0:
                self.log(f"       ❌ 无头像: {filter_stats['no_photo']}")
            if filter_stats['online_filtered'] > 0:
                self.log(f"       ❌ 在线时间: {filter_stats['online_filtered']}")
            self.log(f"       ✅ 通过过滤: {filter_stats['passed']}")
        
        except Exception as e:
            self.log(f"    ⚠️ 获取消息失败: {str(e)[:50]}")
        
        return users_collected
    
    def _check_online_time(self, user, config):
        """单独检查在线时间（用于统计）"""
        online_days = config.get("online_days", 3)
        cutoff_time = datetime.now() - timedelta(days=online_days)
        
        if user.status:
            # 当前在线
            if isinstance(user.status, types.UserStatusOnline):
                return True
            # 最近在线（隐藏具体时间）
            elif isinstance(user.status, types.UserStatusRecently):
                if config.get("include_recently", True):
                    return True
                else:
                    return False
            # 离线，检查离线时间
            elif isinstance(user.status, types.UserStatusOffline):
                if hasattr(user.status, 'was_online'):
                    if user.status.was_online >= cutoff_time:
                        return True
                    else:
                        return False
                else:
                    # 没有was_online字段，无法判断，默认通过
                    return True
            # 一周内/一个月内/很久未上线（隐藏时间）- 无法精确判断
            elif isinstance(user.status, (types.UserStatusLastWeek, types.UserStatusLastMonth)):
                # 默认排除（太久未上线）
                return False
            elif isinstance(user.status, types.UserStatusEmpty):
                # 状态为空，无法判断，默认通过
                return True
        else:
            # 没有状态信息，默认通过
            return True
        
        return True
    
    async def _scrape_joined_groups(self, account, config, ui_callbacks):
        """从已加入的群采集（完整版）"""
        try:
            client = TelegramClient(account["path"], self.api_id, self.api_hash)
            await client.connect()

            me = await client.get_me()
            account_name = f"@{me.username or me.phone}"
            
            self.log(f"\n📌 账号: {account_name} - 获取已加入的群组...")

            # 获取所有对话
            dialogs = await client.get_dialogs()
            groups = [d for d in dialogs if d.is_group or d.is_channel]
            
            # 限制每个账号采集的群组数量
            groups_per_account = config.get("groups_per_account", 5)
            if len(groups) > groups_per_account:
                groups = groups[:groups_per_account]
                self.log(f"  📊 找到 {len(dialogs)} 个群组，限制采集前 {groups_per_account} 个")
            else:
                self.log(f"  📊 找到 {len(groups)} 个群组/频道")
            
            all_users = []
            limit = config.get("limit", 500)
            
            for i, dialog in enumerate(groups):
                if self.stop_flag or (ui_callbacks and not ui_callbacks.get("is_running", lambda: True)()):
                    break
                
                try:
                    entity = dialog.entity
                    entity_name = getattr(entity, 'title', '未知群组')
                    
                    self.log(f"  [{i+1}/{len(groups)}] 采集: {entity_name}")
                    
                    # 根据模式采集
                    mode = config.get("mode", "default")
                    if mode == "messages":
                        users = await self._scrape_from_messages(client, entity, entity_name, config, ui_callbacks)
                    else:
                        users = await self._scrape_from_participants(client, entity, entity_name, config, ui_callbacks)
                    
                    all_users.extend(users)
                    
                    # 自动退群
                    if config.get("auto_leave", False):
                        try:
                            await client(functions.channels.LeaveChannelRequest(channel=entity))
                            self.log(f"    🚪 已退出群组")
                        except:
                            pass
                    
                    # 达到总限制（0或999999=不限制）
                    if limit > 0 and limit < 999999 and len(all_users) >= limit:
                        self.log(f"  ⚠️ 已达到采集总数限制 ({limit})，停止采集")
                        break
                
                except Exception as e:
                    self.log(f"    ❌ 失败: {str(e)[:50]}")
            
            await client.disconnect()
            return all_users

        except Exception as e:
            self.log(f"❌ 账号失败: {str(e)[:50]}")
            return []
    
    async def _scrape_dialogs(self, account, config, ui_callbacks):
        """从对话列表采集（完整版）"""
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
                if self.stop_flag or (ui_callbacks and not ui_callbacks.get("is_running", lambda: True)()):
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
                        
                        # UI更新回调
                        if ui_callbacks and "insert_row" in ui_callbacks and self.root:
                            self.root.after(0, lambda u=user_data: ui_callbacks["insert_row"](u))
                    
                    # 达到限制（0或999999=不限制）
                    if limit > 0 and limit < 999999 and len(all_users) >= limit:
                        self.log(f"  ⚠️ 已达到采集总数限制 ({limit})，停止采集")
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
        """检查用户是否符合过滤条件（完整版）"""
        # 调试模式：记录过滤原因
        debug = config.get("debug_filters", False)
        
        # 排除机器人
        if config.get("filter_bot", True) and user.bot:
            if debug:
                self.log(f"      ❌ 过滤：机器人")
            return False
        
        # 仅有用户名
        if config.get("filter_username", False) and not user.username:
            if debug:
                self.log(f"      ❌ 过滤：无用户名")
            return False
        
        # 仅 Premium 会员
        if config.get("filter_premium", False) and not user.premium:
            if debug:
                self.log(f"      ❌ 过滤：非Premium")
            return False
        
        # 仅有头像
        if config.get("filter_photo", False) and not user.photo:
            if debug:
                self.log(f"      ❌ 过滤：无头像")
            return False
        
        # 在线时间过滤（修复：只在开启时过滤）
        if config.get("filter_online_time", False):
            online_days = config.get("online_days", 3)
            cutoff_time = datetime.now() - timedelta(days=online_days)
            
            if user.status:
                # 当前在线
                if isinstance(user.status, types.UserStatusOnline):
                    return True
                # 最近在线（隐藏具体时间）
                elif isinstance(user.status, types.UserStatusRecently):
                    if config.get("include_recently", True):
                        return True
                    else:
                        return False
                # 离线，检查离线时间
                elif isinstance(user.status, types.UserStatusOffline):
                    if hasattr(user.status, 'was_online'):
                        if user.status.was_online >= cutoff_time:
                            return True
                        else:
                            return False
                    else:
                        # 没有was_online字段，无法判断，默认通过
                        return True
                # 一周内/一个月内/很久未上线（隐藏时间）- 无法精确判断
                elif isinstance(user.status, (types.UserStatusLastWeek, types.UserStatusLastMonth)):
                    # 默认排除（太久未上线）
                    return False
                elif isinstance(user.status, types.UserStatusEmpty):
                    # 状态为空，无法判断，默认通过
                    return True
            else:
                # 没有状态信息，默认通过
                return True
        
        # 所有过滤通过
        return True
    
    def stop(self):
        """停止采集"""
        self.stop_flag = True
