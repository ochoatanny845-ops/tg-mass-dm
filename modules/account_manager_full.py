"""
账号管理模块 - 完整版
保留原有所有功能：JSON处理、2FA、代理、SpamBot检测
"""

import os
import json
import shutil
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
        """加载账号列表（完整版）"""
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
        """保存账号列表（完整版，隐私保护）"""
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
        导入 Session 文件（完整版）
        
        功能：
        - 复制 session 文件
        - 复制 session-journal 文件
        - 复制配套 JSON 文件
        - 解析 JSON 信息（手机号、用户名、2FA、状态等）
        - 自动生成 JSON（如果不存在）
        """
        try:
            session_dir = Path(session_dir)
            session_files = list(session_dir.glob("*.session"))
            
            if not session_files:
                self.log("⚠️ 未找到 .session 文件")
                return []
            
            imported = []
            
            for session_file in session_files:
                # 复制session文件
                dest_path = self.sessions_dir / session_file.name
                
                if dest_path.exists():
                    self.log(f"⚠️ 跳过（已存在）: {session_file.name}")
                    continue
                
                shutil.copy2(session_file, dest_path)
                
                # 复制 journal 文件
                journal_file = session_file.with_suffix('.session-journal')
                if journal_file.exists():
                    dest_journal = self.sessions_dir / journal_file.name
                    shutil.copy2(journal_file, dest_journal)
                
                # 处理 JSON 文件
                json_file = session_file.parent / f"{session_file.stem}.json"
                json_data = None
                
                if json_file.exists():
                    dest_json = self.sessions_dir / json_file.name
                    shutil.copy2(json_file, dest_json)
                    self.log(f"    📄 已复制配套 JSON 文件")
                    
                    try:
                        with open(json_file, 'r', encoding='utf-8') as f:
                            json_data = json.load(f)
                    except:
                        pass
                else:
                    self.log(f"    ⚠️ 未找到 JSON 文件,正在自动生成...")
                    json_data = self._generate_json_from_session(dest_path)
                
                # 创建账号记录
                account = {
                    "path": str(dest_path),
                    "selected": True,
                    "status": "未检测",
                    "username": "-",
                    "phone": "-",
                    "first_name": "-",
                    "proxy": "直连",
                    "2fa": "",
                    "last_login": "-"
                }
                
                # 如果有 JSON 数据，提取信息
                if json_data:
                    # 提取手机号
                    phone = json_data.get('phone')
                    if phone:
                        account["phone"] = str(phone)
                    
                    # 提取用户名
                    username = json_data.get('username')
                    if username:
                        account["username"] = f"@{username}" if not username.startswith('@') else username
                    
                    # 提取姓名
                    first_name = json_data.get('first_name', '')
                    last_name = json_data.get('last_name', '')
                    if first_name:
                        full_name = f"{first_name} {last_name}".strip() if last_name else first_name
                        account["first_name"] = full_name
                    
                    # 提取 2FA 状态
                    twofa = json_data.get('twoFA')
                    passwordfa = json_data.get('passwordFA')
                    
                    if twofa:
                        account["2fa"] = str(twofa)
                    elif passwordfa:
                        account["2fa"] = str(passwordfa)
                    else:
                        account["2fa"] = ""
                    
                    # 提取状态
                    spamblock = str(json_data.get('spamblock', '')).lower()
                    
                    if spamblock == 'free':
                        account["status"] = "✅ 无限制"
                    elif spamblock == 'permanent':
                        account["status"] = "⚠️ 永久双向限制"
                    elif spamblock == 'temporary':
                        account["status"] = "⚠️ 临时限制"
                    elif spamblock == 'frozen':
                        account["status"] = "🚫 冻结"
                    elif spamblock == 'banned':
                        account["status"] = "🚫 封禁"
                    
                    self.log(f"    📋 已读取 JSON 信息: {account['username']} ({account['phone']})")
                
                imported.append(account)
                self.log(f"  ✅ 已导入: {session_file.name}")
            
            self.log(f"\n导入完成: {len(imported)} 个账号")
            return imported
        
        except Exception as e:
            self.log(f"❌ 导入失败: {e}")
            return []
    
    def _generate_json_from_session(self, session_path):
        """自动生成 JSON（如果不存在）"""
        try:
            # 从 session 文件名提取手机号
            phone = Path(session_path).stem
            
            # 创建基本 JSON 数据
            json_data = {
                "phone": phone,
                "username": "",
                "first_name": "",
                "last_name": "",
                "spamblock": "未检测"
            }
            
            # 保存 JSON 文件
            json_path = session_path.parent / f"{phone}.json"
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, ensure_ascii=False, indent=2)
            
            self.log(f"    ✅ 已自动生成 JSON 文件")
            return json_data
        
        except Exception as e:
            self.log(f"    ⚠️ 生成 JSON 失败: {e}")
            return None
    
    async def check_account(self, account):
        """
        检查单个账号状态（完整版）
        
        功能：
        - 登录检测
        - SpamBot 检测
        - 状态分类（无限制/双向限制/封禁等）
        
        Returns:
            状态字符串
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
                    reply = messages[0].message.lower()
                    
                    # 分析回复
                    if "you're free" in reply or "good news" in reply:
                        status = "✅ 无限制"
                    elif "限制" in reply or "restriction" in reply:
                        if "永久" in reply or "permanent" in reply:
                            status = "⚠️ 永久双向限制"
                        else:
                            status = "⚠️ 临时限制"
                    elif "limited" in reply:
                        status = "⚠️ 双向限制"
                    else:
                        status = "未知"
                else:
                    status = "未知"
            except:
                status = "未知"
            
            await client.disconnect()
            return status
        
        except errors.UserDeactivatedBanError:
            return "🚫 已封禁"
        except Exception as e:
            return f"错误: {type(e).__name__}"
    
    async def refresh_accounts(self, accounts, callback=None):
        """
        批量刷新账号状态（完整版）
        
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
