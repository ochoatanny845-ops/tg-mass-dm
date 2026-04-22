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
