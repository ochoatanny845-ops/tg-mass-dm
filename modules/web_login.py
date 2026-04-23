"""
Telegram Web 自动登录模块
从 Telethon session 提取 auth_key 并注入到浏览器

独立模块，可单独运行:
    python modules/web_login.py <session_file>

也可作为库导入:
    from modules.web_login import TelegramWebLogin
    login = TelegramWebLogin()
    driver = login.open_telegram_web("session_file.session")
"""

import sqlite3
import base64
import os
import time
from pathlib import Path

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False


class TelegramWebLogin:
    """Telegram Web 自动登录类"""
    
    def __init__(self, logger=None):
        """
        初始化
        
        Args:
            logger: 日志函数，如果为None则使用print
        """
        self.logger = logger
    
    def log(self, message):
        """输出日志"""
        if self.logger:
            self.logger(message)
        else:
            print(message)
    
    def check_dependencies(self):
        """
        检查依赖是否安装
        
        Returns:
            tuple: (是否成功, 消息)
        """
        if not SELENIUM_AVAILABLE:
            return False, "未安装 selenium 库\n请运行: pip install selenium webdriver-manager"
        
        try:
            from webdriver_manager.chrome import ChromeDriverManager
            return True, "依赖已安装"
        except ImportError:
            return False, "未安装 webdriver-manager 库\n请运行: pip install webdriver-manager"
    
    def extract_session_data(self, session_file):
        """
        从 Telethon session 文件提取认证数据
        
        Session文件结构（SQLite）：
        - 表: sessions
        - 字段: dc_id, server_address, port, auth_key
        
        Args:
            session_file: .session 文件路径
        
        Returns:
            dict: {'dc_id', 'auth_key', 'server', 'port'}
        """
        try:
            if not os.path.exists(session_file):
                raise FileNotFoundError(f"Session 文件不存在: {session_file}")
            
            conn = sqlite3.connect(session_file)
            cursor = conn.cursor()
            cursor.execute("SELECT dc_id, server_address, port, auth_key FROM sessions")
            row = cursor.fetchone()
            
            if not row:
                conn.close()
                raise ValueError("Session 文件中没有认证数据（未登录或已过期）")
            
            dc_id, server_address, port, auth_key = row
            conn.close()
            
            auth_key_b64 = base64.b64encode(auth_key).decode('utf-8')
            
            self.log(f"✅ 成功提取session数据: DC{dc_id} ({server_address}:{port})")
            
            return {
                'dc_id': dc_id,
                'auth_key': auth_key_b64,
                'server': server_address,
                'port': port
            }
            
        except Exception as e:
            self.log(f"❌ 提取session失败: {str(e)}")
            raise
    
    def open_telegram_web(self, session_file, headless=False, keep_open=True):
        """
        打开Telegram Web并自动登录
        
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
            
            self.log("📦 正在提取session数据...")
            session_data = self.extract_session_data(session_file)
            
            chrome_options = Options()
            if headless:
                chrome_options.add_argument('--headless')
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--incognito')
            
            self.log("🌐 正在启动浏览器...")
            
            try:
                from webdriver_manager.chrome import ChromeDriverManager
                from selenium.webdriver.chrome.service import Service
                service = Service(ChromeDriverManager().install())
                driver = webdriver.Chrome(service=service, options=chrome_options)
            except:
                driver = webdriver.Chrome(options=chrome_options)
            
            self.log("📱 正在打开 Telegram Web...")
            # 先打开一个空白页面，然后注入localStorage
            self.log("📱 正在打开 Telegram Web...")
            driver.get("https://web.telegram.org/a/")
            
            # 等待页面初始化
            time.sleep(2)
            
            self.log("🔑 正在注入认证数据...")
            dc_id = session_data['dc_id']
            auth_key = session_data['auth_key']
            
            # 注入localStorage（使用正确的格式）
            # 参考：https://github.com/LonamiWebs/Telethon/issues/1967
            script = f"""
            // 清除旧的登录状态
            localStorage.clear();
            
            // 注入auth_key（主要认证信息）
            localStorage.setItem('dc{dc_id}_auth_key', '{auth_key}');
            localStorage.setItem('dc', '{dc_id}');
            
            // 注入server_salt（如果需要）
            localStorage.setItem('dc{dc_id}_server_salt', '0'.repeat(16));
            
            // 标记user_auth（部分版本需要）
            localStorage.setItem('user_auth', '{dc_id}');
            
            console.log('[TG-Login] Injected auth for DC' + {dc_id});
            console.log('[TG-Login] Auth key length: ' + '{auth_key}'.length);
            """
            driver.execute_script(script)
            
            self.log("♻️ 第1次刷新页面...")
            driver.refresh()
            time.sleep(4)
            
            # 检查是否成功登录
            try:
                # 如果还有QR码，说明没登录成功
                qr_elements = driver.find_elements("xpath", "//*[contains(@class, 'qr')]")
                login_button = driver.find_elements("xpath", "//*[contains(text(), 'Log in')]")
                
                if qr_elements or login_button:
                    self.log("⚠️ 首次注入未生效，尝试第二次...")
                    
                    # 再次注入（有时需要多次）
                    driver.execute_script(script)
                    driver.refresh()
                    time.sleep(4)
                    
                    # 再次检查
                    qr_elements = driver.find_elements("xpath", "//*[contains(@class, 'qr')]")
                    if qr_elements:
                        self.log("⚠️ 注入可能失败，但浏览器已打开")
                        self.log("💡 如果未自动登录，可能需要：")
                        self.log("   1. Session文件版本太旧")
                        self.log("   2. Auth key已过期")
                        self.log("   3. 需要重新登录生成新session")
                    else:
                        self.log("✅ 第二次注入成功！")
                else:
                    self.log("✅ 注入成功，已自动登录！")
                    
            except Exception as check_error:
                self.log(f"⚠️ 无法检查登录状态: {str(check_error)}")
                self.log("💡 请手动查看浏览器窗口")
            
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


def main():
    """命令行主函数"""
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Telegram Web 自动登录工具',
        epilog='示例: python modules/web_login.py sessions/account1.session'
    )
    
    parser.add_argument('session_file', help='.session 文件路径')
    parser.add_argument('--headless', action='store_true', help='无头模式')
    parser.add_argument('--auto-close', action='store_true', help='5秒后自动关闭')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.session_file):
        print(f"❌ 文件不存在: {args.session_file}")
        sys.exit(1)
    
    login = TelegramWebLogin()
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
