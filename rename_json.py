"""
批量重命名 JSON 文件
将 123.json 重命名为 123.session.json
"""
from pathlib import Path
import os

def rename_json_files(folder_path):
    """批量重命名 JSON 文件"""
    folder = Path(folder_path)
    
    if not folder.exists():
        print(f"❌ 文件夹不存在: {folder_path}")
        return
    
    # 找到所有 .json 文件（不包括 .session.json）
    json_files = [f for f in folder.glob("*.json") if not f.name.endswith(".session.json")]
    
    if not json_files:
        print(f"📁 没有需要重命名的 JSON 文件")
        return
    
    print(f"📂 找到 {len(json_files)} 个 JSON 文件需要重命名")
    print("=" * 60)
    
    renamed = 0
    for json_file in json_files:
        try:
            # 原文件名: 123.json
            # 新文件名: 123.session.json
            old_name = json_file.name
            base_name = json_file.stem  # 123
            new_name = f"{base_name}.session.json"
            new_path = json_file.parent / new_name
            
            # 重命名
            json_file.rename(new_path)
            
            print(f"✅ {old_name} → {new_name}")
            renamed += 1
            
        except Exception as e:
            print(f"❌ 重命名失败: {json_file.name} - {str(e)}")
    
    print("=" * 60)
    print(f"📊 重命名完成:")
    print(f"  ✅ 成功: {renamed} 个")
    print(f"  ❌ 失败: {len(json_files) - renamed} 个")
    print(f"  📝 总计: {len(json_files)} 个")

if __name__ == "__main__":
    # 你的 session 文件夹路径
    folder_path = input("请输入文件夹路径（例如: D:\\sessions）: ").strip()
    
    if not folder_path:
        print("❌ 路径不能为空")
    else:
        rename_json_files(folder_path)
        
    print("\n按 Enter 键退出...")
    input()
