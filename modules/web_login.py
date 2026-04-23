"""
Telegram Web 自动登录模块 - GramJS方案
从 Telethon session 转换为 GramJS StringSession 并注入到浏览器

独立模块，可单独运行:
    python modules/web_login.py <session_file> --api-id <id> --api-hash <hash>

也可作为库导入:
    from modules.web_login import TelegramWebLogin
    login = TelegramWebLogin(api_id, api_hash)
    await login.open_telegram_web_async("session.session")
"""

import os
import time
import asyncio
from pathlib import Path

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

try:
    from telethon import TelegramClient
    from telethon.sessions import StringSession
    TELETHON_AVAILABLE = True
except ImportError:
    TELETHON_AVAILABLE = False


class TelegramWebLogin:
    """Telegram Web 自动登录类（使用GramJS格式）"""
    
    def __init__(self, api_id, api_hash, logger=None):
        """
        初始化
        
        Args:
            api_id: Telegram API ID（必需）
            api_hash: Telegram API Hash（必需）
            logger: 日志函数，如果为None则使用print
        """
        self.api_id = api_id
        self.api_hash = api_hash
        self.logger = logger
    
    def log(self, message):
        """输出日志"""
        if self.logger:
            self.logger(message)
        else:
            print(message)
    
    def check_dependencies(self):
        """检查依赖是否安装"""
        if not SELENIUM_AVAILABLE:
            return False, "未安装 selenium 库\n请运行: pip install selenium webdriver-manager"
        
        if not TELETHON_AVAILABLE:
            return False, "未安装 telethon 库\n请运行: pip install telethon"
        
        try:
            from webdriver_manager.chrome import ChromeDriverManager
            return True, "依赖已安装"
        except ImportError:
            return False, "未安装 webdriver-manager 库\n请运行: pip install webdriver-manager"
    
    async def convert_to_gramjs_session(self, session_file):
        """
        将Telethon session转换为Telegram Web localStorage格式
        
        Args:
            session_file: .session 文件路径
        
        Returns:
            dict: localStorage格式的数据 {dc_id, auth_key_hex, user_id}
        """
        try:
            self.log("🔄 正在读取session数据...")
            
            # 去掉.session后缀（Telethon会自动添加）
            session_name = str(session_file).replace('.session', '')
            
            # 创建临时的Telethon client
            client = TelegramClient(session_name, self.api_id, self.api_hash)
            
            # 连接（不需要登录，只读取session）
            await client.connect()
            
            if not await client.is_user_authorized():
                await client.disconnect()
                raise ValueError("Session未授权或已过期，请重新登录")
            
            # 获取用户信息
            me = await client.get_me()
            user_id = me.id
            
            # 读取session的auth_key和dc_id
            import sqlite3
            conn = sqlite3.connect(session_file)
            cursor = conn.cursor()
            cursor.execute("SELECT dc_id, server_address, port, auth_key FROM sessions")
            row = cursor.fetchone()
            
            if not row:
                conn.close()
                await client.disconnect()
                raise ValueError("Session文件损坏，无法读取auth_key")
            
            dc_id, server_address, port, auth_key_bytes = row
            
            # 读取server_salt（如果有）
            server_salt = None
            try:
                cursor.execute("SELECT server_salt FROM sent_files LIMIT 1")
                salt_row = cursor.fetchone()
                if salt_row and salt_row[0]:
                    server_salt = salt_row[0].hex()
            except:
                # 如果没有server_salt表或字段，使用默认值
                server_salt = "0" * 16  # 16个0
            
            conn.close()
            
            # 转换为16进制字符串（Telegram Web格式）
            auth_key_hex = auth_key_bytes.hex()
            
            # 计算auth_key_fingerprint（前8个字节的hex）
            fingerprint = auth_key_bytes[:4].hex()
            
            await client.disconnect()
            
            self.log(f"✅ 成功读取session: DC{dc_id}, User ID: {user_id}")
            
            return {
                'dc_id': dc_id,
                'auth_key_hex': auth_key_hex,
                'fingerprint': fingerprint,
                'user_id': user_id,
                'server_salt': server_salt,
                'server_address': server_address,
                'port': port
            }
            
        except Exception as e:
            self.log(f"❌ 读取session失败: {str(e)}")
            raise
    
    async def open_telegram_web_async(self, session_file, headless=False, keep_open=True):
        """
        打开Telegram Web并自动登录（异步版本）
        
        Args:
            session_file: .session 文件路径
            headless: 是否无头模式
            keep_open: 是否保持浏览器打开
        
        Returns:
            WebDriver 实例 或 None
        """
        try:
            ok, msg = self.check_dependencies()
            if not ok:
                self.log(f"❌ {msg}")
                raise ImportError(msg)
            
            if not os.path.exists(session_file):
                raise FileNotFoundError(f"Session文件不存在: {session_file}")
            
            # 读取session数据
            session_data = await self.convert_to_gramjs_session(session_file)
            
            # 配置Chrome选项
            chrome_options = Options()
            if headless:
                chrome_options.add_argument('--headless')
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--incognito')
            
            # 启动Chrome（优先使用本地驱动，避免网络下载卡住）
            self.log("🌐 正在启动浏览器...")
            
            # 尝试多种方式启动Chrome
            driver = None
            
            # 方式1：尝试本地ChromeDriver路径
            local_paths = [
                "C:\\chromedriver\\chromedriver.exe",
                "chromedriver.exe",
                os.path.join(os.getcwd(), "chromedriver.exe"),
            ]
            
            for path in local_paths:
                if os.path.exists(path):
                    try:
                        from selenium.webdriver.chrome.service import Service
                        service = Service(path)
                        driver = webdriver.Chrome(service=service, options=chrome_options)
                        self.log(f"✅ 使用本地驱动: {path}")
                        break
                    except Exception as e:
                        self.log(f"⚠️ 本地驱动失败 ({path}): {str(e)}")
                        continue
            
            # 方式2：使用系统PATH中的chromedriver
            if not driver:
                try:
                    driver = webdriver.Chrome(options=chrome_options)
                    self.log("✅ 使用系统PATH中的驱动")
                except Exception as e:
                    self.log(f"⚠️ 系统驱动失败: {str(e)}")
            
            # 方式3：使用webdriver-manager（可能网络下载，最后尝试）
            if not driver:
                try:
                    self.log("⏳ 尝试自动下载驱动（可能较慢）...")
                    from webdriver_manager.chrome import ChromeDriverManager
                    from selenium.webdriver.chrome.service import Service
                    service = Service(ChromeDriverManager().install())
                    driver = webdriver.Chrome(service=service, options=chrome_options)
                    self.log("✅ 自动下载驱动成功")
                except Exception as e:
                    self.log(f"❌ 自动下载失败: {str(e)}")
                    raise Exception("无法启动Chrome浏览器，请手动下载ChromeDriver")
            
            if not driver:
                raise Exception("所有启动方式都失败了")
            
            # 打开Telegram Web
            self.log("📱 正在打开 Telegram Web...")
            driver.get("https://web.telegram.org/a/")
            time.sleep(2)
            
            # 注入Telegram Web localStorage（真实格式）
            self.log("🔑 正在注入认证数据...")
            
            dc_id = session_data['dc_id']
            auth_key_hex = session_data['auth_key_hex']
            fingerprint = session_data['fingerprint']
            user_id = session_data['user_id']
            server_salt = session_data['server_salt']
            
            # 使用真实的localStorage格式（从已登录的Telegram Web获取）
            script = f"""
            // 不清空！直接覆盖当前DC的数据
            
            // 核心认证数据（Telegram Web真实格式）
            localStorage.setItem('dc', '{dc_id}');
            localStorage.setItem('dc{dc_id}_auth_key', '{auth_key_hex}');
            localStorage.setItem('dc{dc_id}_server_salt', '{server_salt}');
            localStorage.setItem('auth_key_fingerprint', '{fingerprint}');
            
            // 用户认证信息
            const userAuth = {{
                dcID: {dc_id},
                id: "{user_id}"
            }};
            localStorage.setItem('user_auth', JSON.stringify(userAuth));
            
            // 其他必要字段
            localStorage.setItem('k_build', '626');
            localStorage.setItem('kz_version', 'K');
            localStorage.setItem('number_of_accounts', '0');
            
            console.log('[TG-Login] Injected auth data: DC{dc_id}, User {user_id}');
            """
            driver.execute_script(script)
            
            # 刷新页面让session生效
            self.log("♻️ 正在刷新页面...")
            driver.refresh()
            time.sleep(4)
            
            # 检查登录状态
            try:
                qr_elements = driver.find_elements("xpath", "//*[contains(@class, 'qr')]")
                if qr_elements:
                    self.log("⚠️ 首次注入未生效，尝试第二次...")
                    driver.execute_script(script)
                    driver.refresh()
                    time.sleep(4)
                    
                    qr_elements = driver.find_elements("xpath", "//*[contains(@class, 'qr')]")
                    if qr_elements:
                        self.log("⚠️ 注入可能失败，但浏览器已打开")
                        self.log("💡 可能原因：")
                        self.log("   1. auth_key已过期")
                        self.log("   2. DC服务器变更")
                        self.log("   3. 需要重新登录")
                    else:
                        self.log("✅ 第二次注入成功！")
                else:
                    self.log("✅ 注入成功，已自动登录！")
                    
            except Exception as check_error:
                self.log(f"⚠️ 无法检查登录状态: {str(check_error)}")
            
            if keep_open:
                self.log("💡 浏览器将保持打开，手动关闭窗口即可退出")
                return driver
            else:
                self.log("⏳ 5秒后自动关闭浏览器...")
                time.sleep(5)
                driver.quit()
                return None
            
        except Exception as e:
            self.log(f"❌ 打开Web版失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return None
    
    def open_telegram_web(self, session_file, headless=False, keep_open=True):
        """
        打开Telegram Web并自动登录（同步包装）
        
        Args:
            session_file: .session 文件路径
            headless: 是否无头模式
            keep_open: 是否保持浏览器打开
        
        Returns:
            WebDriver 实例 或 None
        """
        # 在新事件循环中运行异步函数
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(
                self.open_telegram_web_async(session_file, headless, keep_open)
            )
        finally:
            loop.close()


def main():
    """命令行主函数"""
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Telegram Web 自动登录工具（GramJS方案）',
        epilog='示例: python modules/web_login.py account.session --api-id 12345 --api-hash abc123'
    )
    
    parser.add_argument('session_file', help='.session 文件路径')
    parser.add_argument('--api-id', type=int, required=True, help='Telegram API ID')
    parser.add_argument('--api-hash', required=True, help='Telegram API Hash')
    parser.add_argument('--headless', action='store_true', help='无头模式')
    parser.add_argument('--auto-close', action='store_true', help='5秒后自动关闭')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.session_file):
        print(f"❌ 文件不存在: {args.session_file}")
        sys.exit(1)
    
    login = TelegramWebLogin(args.api_id, args.api_hash)
    driver = login.open_telegram_web(
        session_file=args.session_file,
        headless=args.headless,
        keep_open=not args.auto_close
    )
    
    if driver:
        try:
            input("\n按 Enter 键关闭浏览器...")
        except KeyboardInterrupt:
            print("\n\n退出中...")
        finally:
            driver.quit()
            print("✅ 浏览器已关闭")


if __name__ == "__main__":
    main()
