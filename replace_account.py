"""
替换账号管理逻辑 - 使用 AccountManager 模块
"""

import sys

sys.stdout.reconfigure(encoding='utf-8')

# 读取文件
with open('main_v2_full.py', 'r', encoding='utf-8') as f:
    content = f.read()

print("Original file size:", len(content), "chars")

# 1. 简化 import_sessions 函数
old_import = '''    def import_sessions(self):
        """导入 Session 文件夹"""
        folder = filedialog.askdirectory(title="选择 Session 文件夹")
        if not folder:
            return

        self.log(f"📁 正在扫描文件夹: {folder}")

        # 扫描 .session 文件
        folder_path = Path(folder)
        session_files = list(folder_path.glob("*.session"))

        added = 0
        for session_file in session_files:
            # 检查是否已存在
            if any(Path(acc["path"]).name == session_file.name for acc in self.accounts):
                self.log(f"  ⚠️ 跳过已存在: {session_file.name}")
                continue

            # 复制到 accounts 文件夹
            try:
                import shutil
                dest_path = Path(self.accounts_dir) / session_file.name
                shutil.copy2(session_file, dest_path)

                # 同时复制 .session-journal 文件(如果存在)
                journal_file = session_file.with_suffix('.session-journal')
                if journal_file.exists():
                    dest_journal = Path(self.accounts_dir) / journal_file.name
                    shutil.copy2(journal_file, dest_journal)

                # 同时复制 .json 文件(如果存在) - 账号信息文件
                # 123.session → 123.json(不是 123.session.json)
                json_file = session_file.parent / f"{session_file.stem}.json"
                json_data = None

                if json_file.exists():
                    dest_json = Path(self.accounts_dir) / json_file.name
                    shutil.copy2(json_file, dest_json)
                    self.log(f"    📄 已复制配套 JSON 文件")

                    # 读取 JSON
                    try:
                        import json
                        with open(json_file, 'r', encoding='utf-8') as f:
                            json_data = json.load(f)
                    except:
                        pass
                else:
                    # 没有 JSON 文件,尝试自动生成
                    self.log(f"    ⚠️ 未找到 JSON 文件,正在自动生成...")
                    json_data = self.generate_json_from_session(dest_path)'''

new_import = '''    def import_sessions(self):
        """导入 Session 文件夹（使用模块）"""
        folder = filedialog.askdirectory(title="选择 Session 文件夹")
        if not folder:
            return

        self.log(f"📁 正在扫描文件夹: {folder}")

        # 调用模块导入
        imported = self.account_manager.import_sessions(folder)
        
        if imported:
            # 合并到现有账号列表
            for acc in imported:
                # 检查是否已存在
                if any(Path(existing["path"]).name == Path(acc["path"]).name for existing in self.accounts):
                    continue
                self.accounts.append(acc)
            
            added = len(imported)'''

# 替换
if old_import in content:
    content = content.replace(old_import, new_import)
    print("✅ Replaced import_sessions")
else:
    print("⚠️ Could not find import_sessions pattern")

# 保存文件
with open('main_v2_full.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Done! New size:", len(content), "chars")
