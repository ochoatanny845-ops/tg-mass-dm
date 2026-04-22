"""
Telegram Session 文件转换工具
将 6 列 sessions 表转换为 5 列（移除 tmp_auth_key）
"""
import sqlite3
import shutil
from pathlib import Path

def convert_session(input_file, output_file=None, backup=True):
    """
    转换 session 文件，移除 tmp_auth_key 列
    
    参数:
        input_file: 输入的 session 文件路径
        output_file: 输出文件路径（默认覆盖原文件）
        backup: 是否备份原文件（默认 True）
    """
    input_path = Path(input_file)
    
    if not input_path.exists():
        print(f"❌ 文件不存在: {input_file}")
        return False
    
    # 如果没有指定输出文件，覆盖原文件
    if output_file is None:
        output_file = input_file
        temp_file = str(input_path) + ".converting"
    else:
        temp_file = output_file
    
    # 备份原文件
    if backup and output_file == input_file:
        backup_file = str(input_path) + ".backup"
        print(f"📋 备份原文件: {backup_file}")
        shutil.copy2(input_file, backup_file)
    
    try:
        print(f"🔧 转换文件: {input_file}")
        
        # 连接原数据库
        conn_old = sqlite3.connect(input_file)
        cursor_old = conn_old.cursor()
        
        # 创建新数据库
        conn_new = sqlite3.connect(temp_file)
        cursor_new = conn_new.cursor()
        
        # 1. 复制 version 表
        cursor_old.execute("SELECT version FROM version")
        version = cursor_old.fetchone()
        if version:
            cursor_new.execute("CREATE TABLE version (version INTEGER PRIMARY KEY)")
            cursor_new.execute("INSERT INTO version VALUES (?)", version)
            print(f"  ✅ 复制 version 表")
        
        # 2. 转换 sessions 表（6列 → 5列）
        cursor_old.execute("SELECT dc_id, server_address, port, auth_key, takeout_id FROM sessions")
        sessions_data = cursor_old.fetchall()
        
        cursor_new.execute("""
            CREATE TABLE sessions (
                dc_id INTEGER PRIMARY KEY,
                server_address TEXT,
                port INTEGER,
                auth_key BLOB,
                takeout_id INTEGER
            )
        """)
        
        for row in sessions_data:
            cursor_new.execute("INSERT INTO sessions VALUES (?, ?, ?, ?, ?)", row)
        
        print(f"  ✅ 转换 sessions 表 (6列 → 5列)")
        
        # 3. 复制 entities 表
        cursor_old.execute("SELECT * FROM entities")
        entities_data = cursor_old.fetchall()
        
        cursor_new.execute("""
            CREATE TABLE entities (
                id INTEGER PRIMARY KEY,
                hash INTEGER NOT NULL,
                username TEXT,
                phone INTEGER,
                name TEXT,
                date INTEGER
            )
        """)
        
        for row in entities_data:
            cursor_new.execute("INSERT INTO entities VALUES (?, ?, ?, ?, ?, ?)", row)
        
        print(f"  ✅ 复制 entities 表 ({len(entities_data)} 行)")
        
        # 4. 复制 sent_files 表
        cursor_new.execute("""
            CREATE TABLE sent_files (
                md5_digest BLOB,
                file_size INTEGER,
                type INTEGER,
                id INTEGER,
                hash INTEGER,
                PRIMARY KEY (md5_digest, file_size, type)
            )
        """)
        
        cursor_old.execute("SELECT * FROM sent_files")
        sent_files_data = cursor_old.fetchall()
        
        for row in sent_files_data:
            cursor_new.execute("INSERT INTO sent_files VALUES (?, ?, ?, ?, ?)", row)
        
        print(f"  ✅ 复制 sent_files 表 ({len(sent_files_data)} 行)")
        
        # 5. 复制 update_state 表
        cursor_old.execute("SELECT * FROM update_state")
        update_state_data = cursor_old.fetchall()
        
        cursor_new.execute("""
            CREATE TABLE update_state (
                id INTEGER PRIMARY KEY,
                pts INTEGER,
                qts INTEGER,
                date INTEGER,
                seq INTEGER
            )
        """)
        
        for row in update_state_data:
            cursor_new.execute("INSERT INTO update_state VALUES (?, ?, ?, ?, ?)", row)
        
        print(f"  ✅ 复制 update_state 表 ({len(update_state_data)} 行)")
        
        # 提交并关闭
        conn_new.commit()
        conn_old.close()
        conn_new.close()
        
        # 如果是覆盖模式，替换原文件
        if output_file == input_file:
            shutil.move(temp_file, input_file)
        
        print(f"✅ 转换完成！")
        return True
        
    except Exception as e:
        print(f"❌ 转换失败: {e}")
        import traceback
        traceback.print_exc()
        
        # 清理临时文件
        if Path(temp_file).exists() and temp_file != output_file:
            Path(temp_file).unlink()
        
        return False

def convert_folder(folder_path, pattern="*.session"):
    """
    批量转换文件夹中的所有 session 文件
    """
    folder = Path(folder_path)
    if not folder.exists():
        print(f"❌ 文件夹不存在: {folder_path}")
        return
    
    session_files = list(folder.glob(pattern))
    if not session_files:
        print(f"📁 文件夹为空: {folder_path}")
        return
    
    print(f"📂 找到 {len(session_files)} 个 session 文件")
    print("=" * 60)
    
    success_count = 0
    failed_count = 0
    
    for i, session_file in enumerate(session_files, 1):
        print(f"\n[{i}/{len(session_files)}] {session_file.name}")
        print("-" * 60)
        
        if convert_session(session_file):
            success_count += 1
        else:
            failed_count += 1
    
    print("\n" + "=" * 60)
    print(f"📊 转换完成:")
    print(f"  ✅ 成功: {success_count} 个")
    print(f"  ❌ 失败: {failed_count} 个")
    print(f"  📝 总计: {len(session_files)} 个")

if __name__ == "__main__":
    import sys
    
    print("=" * 60)
    print("Telegram Session 文件转换工具 v1.0")
    print("功能: 移除 sessions 表的 tmp_auth_key 列 (6列→5列)")
    print("=" * 60)
    
    # 批量转换模式
    accounts_folder = r"E:\工具\私信\tg-mass-dm\accounts"
    
    print(f"\n📂 转换文件夹: {accounts_folder}")
    print(f"⚠️  备份文件将保存为: *.session.backup")
    print("\n按 Enter 继续，Ctrl+C 取消...")
    input()
    
    convert_folder(accounts_folder)
