"""
Clean up old code: remove unused functions
"""
import re
import sys
import io

# Fix Windows console encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Read file
with open("main_v2_full.py", "r", encoding="utf-8") as f:
    content = f.read()

print(f"Original file: {len(content)} chars")

# 要删除的函数列表（按行号找到后删除整个函数）
functions_to_remove = [
    "async def send_with_account",
    "def scrape_single_target_sync",
    "async def scrape_single_target",
    "async def scrape_from_participants",
    "async def scrape_from_messages",
    "def check_user_filters",
    "def generate_json_from_session"
]

# Simple strategy: find function definitions and remove until next function
for func_name in functions_to_remove:
    # Find function definition
    pattern = rf'^    {re.escape(func_name)}\(.*?\):$'
    match = re.search(pattern, content, re.MULTILINE)
    
    if match:
        start = match.start()
        # Find next same-level function (4 spaces indent)
        next_func = re.search(r'\n    (def |async def )', content[start+len(match.group(0)):])
        
        if next_func:
            end = start + len(match.group(0)) + next_func.start()
        else:
            # If no next function, remove to end (unlikely)
            end = len(content)
        
        # Remove this function
        removed_text = content[start:end]
        print(f"\nRemoving: {func_name}")
        print(f"  Removed {len(removed_text)} chars")
        
        content = content[:start] + content[end:]

print(f"\nFinal file: {len(content)} chars")

# Write back
with open("main_v2_full.py", "w", encoding="utf-8") as f:
    f.write(content)

print("\nDone!")
