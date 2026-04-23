"""
账号管理模块
功能：
1. 导入账号（Session文件）
2. 加载/保存账号列表
3. 账号验证
4. 刷新账号状态
"""

import os
import json
import asyncio
from pathlib import Path
from telethon import TelegramClient, errors

class AccountManager:
    def __init__(self, api_id, api_hash, sessions_dir, accounts_file, logger):
        self.api_id = api_id
        self.api_hash = api_hash
        self.sessions_dir = Path(sessions_dir)
        self.accounts_file = Path(accounts_file)
        self.logger = logger
        
        # 确保目录存在
        self.sessions_dir.mkdir(exist_ok=True)
        self.accounts_file.parent.mkdir(exist_ok=True)
    
    def log(self, message):
        """输出日志"""
        if self.logger:
            self.logger(message)
    
    def load_accounts(self):
        """加载账号列表"""
        try:
            if not self.accounts_file.exists():
                return []
            
            with open(self.accounts_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            accounts = data.get("accounts", [])
            self.log(f"✅ 加载 {len(accounts)} 个账号")
            return accounts
        
        except Exception as e:
            self.log(f"⚠️ 加载账号失败: {e}")
            return []
    
    def save_accounts(self, accounts):
        """保存账号列表"""
        try:
            # 移除代理信息（隐私保护）
            accounts_to_save = []
            for acc in accounts:
                acc_copy = acc.copy()
                acc_copy.pop("proxy", None)  # 不保存代理
                accounts_to_save.append(acc_copy)
            
            data = {"accounts": accounts_to_save}
            
            with open(self.accounts_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            self.log(f"✅ 保存 {len(accounts)} 个账号")
        
        except Exception as e:
            self.log(f"❌ 保存账号失败: {e}")
    
    def import_sessions(self, session_dir):
        """
        导入 Session 文件
        
        Args:
            session_dir: Session文件所在目录
        
        Returns:
            导入的账号列表
        """
        try:
            session_dir = Path(session_dir)
            session_files = list(session_dir.glob("*.session"))
            
            if not session_files:
                self.log("⚠️ 未找到 .session 文件")
                return []
            
            imported = []
            
            for session_file in session_files:
                # 复制到 sessions 目录
                target_path = self.sessions_dir / session_file.name
                
                if target_path.exists():
                    self.log(f"⚠️ 跳过（已存在）: {session_file.name}")
                    continue
                
                import shutil
                shutil.copy2(session_file, target_path)
                
                # 提取手机号
                phone = session_file.stem
                
                account = {
                    "phone": phone,
                    "path": str(target_path),
                    "status": "未知",
                    "selected": False
                }
                
                imported.append(account)
                self.log(f"✅ 导入: {phone}")
            
            self.log(f"\n导入完成: {len(imported)} 个账号")
            return imported
        
        except Exception as e:
            self.log(f"❌ 导入失败: {e}")
            return []
    
    async def check_account(self, account):
        """
        检查单个账号状态
        
        Returns:
            状态字符串: "正常" | "双向限制" | "已封禁" | "未知"
        """
        try:
            client = TelegramClient(account["path"], self.api_id, self.api_hash)
            await client.connect()
            
            if not await client.is_user_authorized():
                await client.disconnect()
                return "未登录"
            
            me = await client.get_me()
            
            # 检查 SpamBot
            try:
                spambot = await client.get_entity("@SpamBot")
                await client.send_message(spambot, "/start")
                await asyncio.sleep(2)
                
                messages = await client.get_messages(spambot, limit=1)
                if messages:
                    reply = messages[0].message
                    if "you're free" in reply.lower() or "good news" in reply.lower():
                        status = "正常"
                    elif "limited" in reply.lower():
                        status = "双向限制"
                    else:
                        status = "未知"
                else:
                    status = "未知"
            except:
                status = "未知"
            
            await client.disconnect()
            return status
        
        except errors.UserDeactivatedBanError:
            return "已封禁"
        except Exception as e:
            return f"错误: {type(e).__name__}"
    
    async def refresh_accounts(self, accounts, callback=None):
        """
        批量刷新账号状态
        
        Args:
            accounts: 账号列表
            callback: 回调函数（每个账号完成后调用）
        
        Returns:
            更新后的账号列表
        """
        self.log("🔄 开始刷新账号状态...")
        
        for i, account in enumerate(accounts):
            if callback:
                callback(i, len(accounts), account["phone"])
            
            status = await self.check_account(account)
            account["status"] = status
            
            self.log(f"[{i+1}/{len(accounts)}] {account['phone']}: {status}")
        
        self.log("✅ 刷新完成")
        return accounts
