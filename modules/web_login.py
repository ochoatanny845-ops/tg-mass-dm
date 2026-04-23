"""
Telegram Web 自动登录模块
从 Telethon session 提取 auth_key 并注入到浏览器
"""

import sqlite3
import base64
import os
import time
from pathlib import Path

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False


class TelegramWebLogin:
    def __init__(self, logger=None):
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
            return False, "未安装 selenium 库"
        
        try:
            from webdriver_manager.chrome import ChromeDriverManager
            return True, "依赖已安装"
        except ImportError:
            return False, "未安装 webdriver-manager 库"
    
    def extract_session_data(self, session_file):
        """
        从 Telethon session 文件提取认证数据
        
        Args:
            session_file: .session 文件路径
        
        Returns:
            dict: {dc_id, auth_key_base64, server_address, port}
        """
        try:
            if not os.path.exists(session_file):
                raise FileNotFoundError(f"Session 文件不存在: {session_file}")
            
            # 连接SQLite数据库
            conn = sqlite3.connect(session_file)
            cursor = conn.cursor()
            
            # 查询sessions表
            cursor.execute("SELECT dc_id, server_address, port, auth_key FROM sessions")
            row = cursor.fetchone()
            
            if not row:
                conn.close()
                raise ValueError("Session 文件中没有认证数据")
            
            dc_id, server_address, port, auth_key = row
            conn.close()
            
            # 转换auth_key为base64
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
    
    def open_telegram_web(self, session_file, headless=False):
        """
        打开Telegram Web并自动登录
        
        Args:
            session_file: .session 文件路径
            headless: 是否无头模式
        
        Returns:
            WebDriver 实例（需要手动关闭）
        """
        try:
            # 检查依赖
            ok, msg = self.check_dependencies()
            if not ok:
                self.log(f"❌ {msg}")
                self.log("💡 请安装: pip install selenium webdriver-manager")
                return None
            
            # 提取session数据
            self.log("📦 正在提取session数据...")
            session_data = self.extract_session_data(session_file)
            
            # 配置Chrome选项
            chrome_options = Options()
            if headless:
                chrome_options.add_argument('--headless')
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--no-sandbox')
            # 使用无痕模式（避免冲突）
            chrome_options.add_argument('--incognito')
            
            # 启动Chrome
            self.log("🌐 正在启动浏览器...")
            
            # 自动下载ChromeDriver
            try:
                from webdriver_manager.chrome import ChromeDriverManager
                from selenium.webdriver.chrome.service import Service
                service = Service(ChromeDriverManager().install())
                driver = webdriver.Chrome(service=service, options=chrome_options)
            except:
                # 后备：直接启动（需要系统PATH中有chromedriver）
                driver = webdriver.Chrome(options=chrome_options)
            
            # 打开Telegram Web A版
            self.log("📱 正在打开 Telegram Web...")
            driver.get("https://web.telegram.org/a/")
            
            # 等待页面加载
            time.sleep(2)
            
            # 注入localStorage
            self.log("🔑 正在注入认证数据...")
            dc_id = session_data['dc_id']
            auth_key = session_data['auth_key']
            
            # 注入auth_key到localStorage
            # Telegram Web使用 dc{X}_auth_key 格式
            script = f"""
            localStorage.setItem('dc{dc_id}_auth_key', '{auth_key}');
            localStorage.setItem('dc', '{dc_id}');
            """
            driver.execute_script(script)
            
            self.log("♻️ 正在刷新页面...")
            driver.refresh()
            
            # 等待登录完成
            time.sleep(3)
            
            self.log("✅ Telegram Web 已打开！")
            self.log("💡 浏览器将保持打开，关闭窗口即可退出")
            
            return driver
            
        except Exception as e:
            self.log(f"❌ 打开Web版失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return None


def test_login():
    """测试函数"""
    import sys
    
    if len(sys.argv) < 2:
        print("用法: python web_login.py <session_file>")
        return
    
    session_file = sys.argv[1]
    
    login = TelegramWebLogin()
    driver = login.open_telegram_web(session_file)
    
    if driver:
        input("按Enter键关闭浏览器...")
        driver.quit()


if __name__ == "__main__":
    test_login()
