"""
分析 Telegram Session 文件结构
"""
import sqlite3
import sys
from pathlib import Path

def analyze_session(session_file):
    """分析 session 文件的表结构"""
    print(f"📁 分析文件: {session_file}")
    print("=" * 60)
    
    try:
        conn = sqlite3.connect(session_file)
        cursor = conn.cursor()
        
        # 1. 列出所有表
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        print(f"\n📋 数据库表列表 ({len(tables)} 个):")
        for table in tables:
            print(f"  - {table[0]}")
        
        # 2. 分析每个表的结构
        for table_name in [t[0] for t in tables]:
            print(f"\n📊 表: {table_name}")
            print("-" * 60)
            
            # 获取表结构
            cursor.execute(f"PRAGMA table_info({table_name});")
            columns = cursor.fetchall()
            
            print(f"  列数: {len(columns)}")
            for col in columns:
                col_id, name, type_, notnull, default, pk = col
                print(f"    [{col_id}] {name} ({type_}) {'NOT NULL' if notnull else ''} {'PRIMARY KEY' if pk else ''}")
            
            # 获取数据样本
            try:
                cursor.execute(f"SELECT * FROM {table_name} LIMIT 3;")
                rows = cursor.fetchall()
                if rows:
                    print(f"\n  数据样本 ({len(rows)} 行):")
                    for i, row in enumerate(rows):
                        print(f"    行 {i+1}: {len(row)} 个值")
                        # 只显示前 5 个值
                        preview = row[:5]
                        print(f"      前5个值: {preview}")
                else:
                    print(f"\n  (表为空)")
            except Exception as e:
                print(f"\n  ⚠️ 无法读取数据: {e}")
        
        conn.close()
        print("\n" + "=" * 60)
        print("✅ 分析完成！")
        
    except Exception as e:
        print(f"❌ 分析失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # 使用第一个不兼容的 session 文件
    # 你需要替换为实际的文件路径
    session_file = r"E:\工具\私信\tg-mass-dm\accounts\817022942239.session"
    
    if not Path(session_file).exists():
        print(f"❌ 文件不存在: {session_file}")
        print("\n请修改脚本中的 session_file 路径为实际的不兼容文件")
    else:
        analyze_session(session_file)
