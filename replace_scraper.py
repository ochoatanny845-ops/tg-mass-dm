"""
批量替换脚本 - 用模块替换内部实现
"""

import re
import sys

# 设置输出编码
sys.stdout.reconfigure(encoding='utf-8')

# 读取文件
with open('main_v2_full.py', 'r', encoding='utf-8') as f:
    content = f.read()

print("File size:", len(content), "chars")

# 1. 删除旧的采集函数（scrape_single_target_sync 到 stop_scraping 之间的所有内容）
# 找到函数开始和结束位置
pattern = r'    def scrape_single_target_sync.*?(?=    def stop_scraping)'
content = re.sub(pattern, '', content, flags=re.DOTALL)

print("After removing old functions:", len(content), "chars")

# 2. 修改 stop_scraping 函数
old_stop = '''    def stop_scraping(self):
        """停止采集"""
        self.is_running = False
        self.log("⏸️ 停止采集任务")'''

new_stop = '''    def stop_scraping(self):
        """停止采集"""
        self.is_running = False
        self.user_scraper.stop()
        self.log("⏸️ 停止采集任务")'''

content = content.replace(old_stop, new_stop)

# 保存文件
with open('main_v2_full.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Done! New size:", len(content), "chars")
