"""
代理管理模块
功能：
1. 导入代理列表
2. 测试代理连通性
3. 为账号分配代理
"""

import asyncio
import aiohttp
from urllib.parse import urlparse

class ProxyManager:
    def __init__(self, logger):
        self.logger = logger
        self.proxies = []
    
    def log(self, message):
        """输出日志"""
        if self.logger:
            self.logger(message)
    
    def import_proxies(self, proxy_list):
        """
        导入代理列表
        
        Args:
            proxy_list: 代理列表（每行一个代理）
                格式：socks5://user:pass@host:port
        
        Returns:
            导入的代理数量
        """
        proxies = []
        
        for line in proxy_list.strip().split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            try:
                # 验证代理格式
                parsed = urlparse(line)
                if parsed.scheme in ['socks5', 'socks4', 'http', 'https']:
                    proxies.append(line)
            except:
                self.log(f"⚠️ 跳过无效代理: {line}")
        
        self.proxies = proxies
        self.log(f"✅ 导入 {len(proxies)} 个代理")
        return len(proxies)
    
    async def test_proxy(self, proxy, timeout=10):
        """
        测试单个代理
        
        Returns:
            True/False
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    'https://api.telegram.org',
                    proxy=proxy,
                    timeout=aiohttp.ClientTimeout(total=timeout)
                ) as response:
                    return response.status == 200
        except:
            return False
    
    async def test_all_proxies(self, callback=None):
        """
        测试所有代理
        
        Args:
            callback: 回调函数（每个代理测试完成后调用）
        
        Returns:
            可用代理列表
        """
        self.log(f"🔄 开始测试 {len(self.proxies)} 个代理...")
        
        working_proxies = []
        
        for i, proxy in enumerate(self.proxies):
            if callback:
                callback(i, len(self.proxies), proxy)
            
            is_working = await self.test_proxy(proxy)
            
            if is_working:
                working_proxies.append(proxy)
                self.log(f"[{i+1}/{len(self.proxies)}] ✅ {proxy}")
            else:
                self.log(f"[{i+1}/{len(self.proxies)}] ❌ {proxy}")
        
        self.log(f"✅ 可用代理: {len(working_proxies)}/{len(self.proxies)}")
        return working_proxies
    
    def assign_proxies(self, accounts, proxies):
        """
        为账号分配代理
        
        Args:
            accounts: 账号列表
            proxies: 可用代理列表
        
        Returns:
            更新后的账号列表
        """
        if not proxies:
            self.log("⚠️ 没有可用代理")
            return accounts
        
        for i, account in enumerate(accounts):
            proxy = proxies[i % len(proxies)]
            account["proxy"] = proxy
        
        self.log(f"✅ 为 {len(accounts)} 个账号分配代理")
        return accounts
