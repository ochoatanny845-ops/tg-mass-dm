"""
批量修改采集功能
添加：
1. 从已加入群采集
2. 从对话列表采集
3. 自动退群
4. 更多过滤条件
"""

# 读取文件
with open("main_v1.3.py", "r", encoding="utf-8") as f:
    content = f.read()

# 1. 修改 scrape_users_async 函数中的循环逻辑
old_loop = """            # 为每个目标分配账号（轮换）
            for i, target in enumerate(targets):
                if not self.is_running:
                    break
                
                account = accounts[i % len(accounts)]
                # 提交任务到线程池
                future = executor.submit(self.scrape_single_target_sync, account, target, i+1, len(targets))
                tasks.append(future)"""

new_loop = """            # 根据采集来源处理
            if source == "joined":
                # 从已加入群采集
                self.log("📋 获取已加入的群组列表...")
                for account in accounts:
                    future = executor.submit(self.scrape_joined_groups_sync, account)
                    tasks.append(future)
            
            elif source == "dialogs":
                # 从对话列表采集
                self.log("💬 获取对话列表...")
                for account in accounts:
                    future = executor.submit(self.scrape_dialogs_sync, account)
                    tasks.append(future)
            
            else:
                # 从群列表采集
                for i, target in enumerate(targets):
                    if not self.is_running:
                        break
                    
                    account = accounts[i % len(accounts)]
                    # 提交任务到线程池
                    future = executor.submit(self.scrape_single_target_sync, account, target, i+1, len(targets))
                    tasks.append(future)"""

content = content.replace(old_loop, new_loop)

# 2. 在 scrape_single_target 函数中添加自动退群
old_disconnect = """            await client.disconnect()
            
            self.log(f"  ✅ 完成: 采集 {len(users_collected)} 个用户")
            return users_collected"""

new_disconnect = """            # 自动退群
            if self.auto_leave.get() and users_collected:
                try:
                    from telethon import functions
                    await client(functions.channels.LeaveChannelRequest(channel=entity))
                    self.log(f"  🚪 已退出群组")
                except:
                    pass
            
            await client.disconnect()
            
            self.log(f"  ✅ 完成: 采集 {len(users_collected)} 个用户")
            return users_collected"""

content = content.replace(old_disconnect, new_disconnect)

# 3. 在 check_user_filters 函数之前添加新函数
insert_position = content.find("    def check_user_filters(self, user):")

new_functions = '''    def scrape_joined_groups_sync(self, account):
        """同步方式采集已加入的群（在线程池中运行）"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(self.scrape_joined_groups(account))
        finally:
            loop.close()

    async def scrape_joined_groups(self, account):
        """从已加入的群采集"""
        from telethon import functions
        
        try:
            client = TelegramClient(account["path"], self.api_id, self.api_hash)
            await client.connect()

            me = await client.get_me()
            account_name = f"@{me.username or me.phone}"
            
            self.log(f"\\n📌 账号: {account_name} - 获取已加入的群组...")

            # 获取所有对话
            dialogs = await client.get_dialogs()
            groups = [d for d in dialogs if d.is_group or d.is_channel]
            
            self.log(f"  📊 找到 {len(groups)} 个群组/频道")
            
            all_users = []
            
            for i, dialog in enumerate(groups):
                if not self.is_running:
                    break
                
                try:
                    entity = dialog.entity
                    entity_name = getattr(entity, 'title', '未知群组')
                    
                    self.log(f"  [{i+1}/{len(groups)}] 采集: {entity_name}")
                    
                    # 根据模式采集
                    if self.scrape_mode.get() == "messages":
                        users = await self.scrape_from_messages(client, entity, entity_name)
                    else:
                        users = await self.scrape_from_participants(client, entity, entity_name)
                    
                    all_users.extend(users)
                    
                    # 自动退群
                    if self.auto_leave.get():
                        try:
                            await client(functions.channels.LeaveChannelRequest(channel=entity))
                            self.log(f"    🚪 已退出群组")
                        except:
                            pass
                    
                    # 达到限制
                    if len(all_users) >= self.scrape_limit.get():
                        break
                
                except Exception as e:
                    self.log(f"    ❌ 失败: {str(e)[:50]}")
            
            await client.disconnect()
            return all_users

        except Exception as e:
            self.log(f"❌ 账号失败: {str(e)[:50]}")
            return []

    def scrape_dialogs_sync(self, account):
        """同步方式采集对话列表（在线程池中运行）"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(self.scrape_dialogs(account))
        finally:
            loop.close()

    async def scrape_dialogs(self, account):
        """从对话列表采集（有对话的用户）"""
        try:
            client = TelegramClient(account["path"], self.api_id, self.api_hash)
            await client.connect()

            me = await client.get_me()
            account_name = f"@{me.username or me.phone}"
            
            self.log(f"\\n📌 账号: {account_name} - 获取对话列表...")

            # 获取所有对话
            dialogs = await client.get_dialogs()
            users_dialogs = [d for d in dialogs if d.is_user and not d.entity.bot]
            
            self.log(f"  📊 找到 {len(users_dialogs)} 个用户对话")
            
            all_users = []
            
            for i, dialog in enumerate(users_dialogs):
                if not self.is_running:
                    break
                
                try:
                    user = dialog.entity
                    
                    # 应用过滤条件
                    if not self.check_user_filters(user):
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
                        
                        # 在主线程中更新 UI
                        self.root.after(0, lambda u=user_data: self.result_tree.insert("", tk.END, values=(
                            "",
                            u["username"],
                            u["name"],
                            u["source"]
                        )))
                    
                    # 达到限制
                    if len(all_users) >= self.scrape_limit.get():
                        break
                
                except Exception as e:
                    continue
            
            await client.disconnect()
            return all_users

        except Exception as e:
            self.log(f"❌ 账号失败: {str(e)[:50]}")
            return []

    '''

content = content[:insert_position] + new_functions + content[insert_position:]

# 4. 更新 check_user_filters 函数，添加新的过滤条件
old_filter_check = """        # 排除机器人
        if self.filter_bot.get() and user.bot:
            return False
        
        # 仅有用户名
        if self.filter_username.get() and not user.username:
            return False"""

new_filter_check = """        # 排除机器人
        if self.filter_bot.get() and user.bot:
            return False
        
        # 仅有用户名
        if self.filter_username.get() and not user.username:
            return False
        
        # 仅 Premium 会员
        if self.filter_premium.get() and not user.premium:
            return False
        
        # 仅有头像
        if self.filter_photo.get() and not user.photo:
            return False"""

content = content.replace(old_filter_check, new_filter_check)

# 写回文件
with open("main_v1.3.py", "w", encoding="utf-8") as f:
    f.write(content)

print("Patch applied successfully!")
print("Added features:")
print("1. Scrape from joined groups")
print("2. Scrape from dialogs")
print("3. Auto leave groups")
print("4. Premium filter")
print("5. Photo filter")
