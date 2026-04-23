# TG 批量私信系统 v2.0.0

## 🎉 全新模块化架构

### 📁 项目结构

```
tg-mass-dm/
├── main_v2.py              # 新主程序（模块化）
├── main_v1.3.py            # 旧主程序（单文件，已废弃）
├── config.py               # 配置管理
├── modules/                # 功能模块
│   ├── user_scraper.py     # 用户采集（10+功能）
│   ├── message_sender.py   # 消息发送
│   ├── account_manager.py  # 账号管理
│   └── proxy_manager.py    # 代理管理
├── ui/                     # UI 组件（待扩展）
├── data/                   # 数据存储
│   ├── accounts.json       # 账号列表
│   ├── targets.json        # 目标用户
│   └── collected_users.json # 采集的用户
└── sessions/               # Telegram session 文件
```

---

## ✨ 新功能一览

### **用户采集模块 (user_scraper.py)**

#### **1️⃣ 采集来源（3种）**
- 📋 **从群列表采集**：输入群组链接，采集成员
- 👥 **从已加入的群采集**：无需链接，自动采集所有已加入的群
- 💬 **从对话列表采集**：采集有对话的用户

#### **2️⃣ 采集模式（2种）**
- 🚀 **默认采集**：快速，直接获取成员列表（仅适用于未隐藏成员的群）
- 💬 **聊天记录采集**：慢速，分析聊天记录（可采集隐藏成员的群）

#### **3️⃣ 过滤条件（7种）**
- ⏰ **在线时间过滤**：只采集最近 N 天内在线的用户
- 🤖 **排除机器人**：自动排除 bot 账号
- 📝 **仅有用户名**：只采集有用户名的用户
- 👑 **仅 Premium 会员**：只采集 Premium 用户
- 🖼️ **仅有头像**：只采集有头像的用户
- 👨‍💼 **仅群主/管理员**：只采集管理员（待实现）
- 📱 **仅有动态**：只采集有动态的用户（待实现）

#### **4️⃣ 其他功能**
- 🔀 **多账号并发**：同时使用多个账号采集，速度提升 N 倍
- 🚪 **自动退群**：采集完成后自动退出群组
- 📊 **采集限制**：设置最大采集数量

---

### **消息发送模块 (message_sender.py)**

#### **功能特点**
- 📨 **批量私信**：向多个用户发送消息
- 😊 **随机 Emoji**：每条消息随机添加 1-2 个 Emoji，位置随机
- ⏳ **频率限制处理**：自动跳过频率限制的用户（不计入连续失败）
- 🗑️ **自动删除无效用户**：
  - You can't write（禁止陌生人发消息）
  - Premium required（需要 Premium）
  - Payment required（需要绑定支付）
  - Cannot find entity（用户不存在）
- 🤖 **SpamBot 检测**：连续失败后自动检查账号状态

---

### **账号管理模块 (account_manager.py)**

#### **功能特点**
- 📥 **导入 Session 文件**：自动导入 Telegram session
- 🔄 **刷新账号状态**：批量检查账号状态
  - 正常
  - 双向限制
  - 已封禁
  - 未登录
- 💾 **自动保存**：账号列表自动保存到 JSON
- 🔒 **隐私保护**：代理信息不保存到 JSON

---

### **代理管理模块 (proxy_manager.py)**

#### **功能特点**
- 📥 **导入代理**：支持 socks5/socks4/http/https
- ✅ **测试代理**：批量测试代理连通性
- 🔀 **自动分配**：为账号自动分配可用代理

---

## 🚀 快速开始

### **1️⃣ 安装依赖**

```bash
pip install telethon aiohttp
```

### **2️⃣ 运行程序**

```bash
python main_v2.py
```

### **3️⃣ 导入账号**

1. 点击「账号管理」标签页
2. 点击「导入 Session 文件」
3. 选择包含 `.session` 文件的目录
4. 等待导入完成

### **4️⃣ 刷新账号状态**

1. 点击「刷新状态」按钮
2. 等待检查完成
3. 查看每个账号的状态

### **5️⃣ 采集用户**

1. 点击「采集用户」标签页
2. 选择采集来源：
   - 从群列表：输入群组链接
   - 从已加入的群：无需输入
   - 从对话列表：无需输入
3. 选择采集模式
4. 设置过滤条件
5. 点击「开始采集」

### **6️⃣ 发送私信**

1. 点击「私信广告」标签页
2. 输入消息 URL（格式：https://t.me/channel/msgid）
3. 输入目标用户列表（每行一个 @username）
4. 点击「开始发送」

---

## 📊 模块化架构的优势

### **对比单文件版本**

| 对比项 | v1.3（单文件） | v2.0（模块化） |
|--------|---------------|---------------|
| 文件大小 | 4600+ 行 | 每个模块 <600 行 |
| 可维护性 | ❌ 难以维护 | ✅ 易于维护 |
| 可测试性 | ❌ 难以测试 | ✅ 独立测试 |
| 可扩展性 | ❌ 难以扩展 | ✅ 易于扩展 |
| 代码复用 | ❌ 低 | ✅ 高 |
| 协作开发 | ❌ 冲突频繁 | ✅ 无冲突 |

### **具体优势**

#### **1️⃣ 易于维护**
- 每个模块功能明确
- 修改某个功能不影响其他功能
- 代码清晰易读

#### **2️⃣ 易于测试**
- 可以单独测试每个模块
- 不需要启动整个程序

#### **3️⃣ 易于扩展**
- 添加新功能只需创建新模块
- 不需要修改现有代码

#### **4️⃣ 易于协作**
- 多人可以同时开发不同模块
- 不会产生 Git 冲突

---

## 🔧 开发指南

### **添加新功能**

#### **方法1：创建新模块**

```python
# modules/new_feature.py

class NewFeature:
    def __init__(self, api_id, api_hash, logger):
        self.api_id = api_id
        self.api_hash = api_hash
        self.logger = logger
    
    def do_something(self):
        # 实现功能
        pass
```

#### **方法2：扩展现有模块**

```python
# modules/user_scraper.py

class UserScraper:
    # ... 现有代码 ...
    
    def new_method(self):
        # 添加新方法
        pass
```

### **集成到主程序**

```python
# main_v2.py

from modules.new_feature import NewFeature

class TelegramMassDM:
    def __init__(self):
        # ... 现有代码 ...
        
        # 初始化新模块
        self.new_feature = NewFeature(
            config.API_ID,
            config.API_HASH,
            self.log
        )
```

---

## 📝 使用示例

### **示例1：采集隐藏成员群组**

```python
from modules.user_scraper import UserScraper

scraper = UserScraper(api_id, api_hash, logger)

config = {
    "source": "list",           # 从群列表
    "mode": "messages",         # 聊天记录模式
    "threads": 5,
    "limit": 500,
    "filter_online_time": True,
    "online_days": 3,
    "include_recently": True,
    "include_online": True,
    "filter_bot": True,
    "auto_leave": False
}

targets = ["https://t.me/group1", "https://t.me/group2"]

users = await scraper.scrape(accounts, targets, config)
print(f"采集到 {len(users)} 个用户")
```

### **示例2：从已加入的群采集**

```python
config = {
    "source": "joined",         # 从已加入的群
    "mode": "default",          # 默认模式
    "threads": 10,
    "limit": 1000,
    "filter_online_time": True,
    "online_days": 7,
    "auto_leave": True          # 自动退群
}

users = await scraper.scrape(accounts, [], config)
```

### **示例3：批量发送私信**

```python
from modules.message_sender import MessageSender

sender = MessageSender(api_id, api_hash, logger)

config = {
    "parallel_threads": 2,
    "start_delay": 1,
    "send_delay_min": 3,
    "send_delay_max": 8,
    "consecutive_fails_threshold": 10,
    "ignore_mutual": False
}

targets = ["@user1", "@user2", "@user3"]
message_url = "https://t.me/channel/123"

result = await sender.send_messages(
    accounts,
    targets,
    message_url,
    config
)

print(f"成功: {result['success']}, 失败: {result['failed']}")
```

---

## 🐛 故障排除

### **问题1：导入 Session 失败**

**原因：** Session 文件格式不正确或路径错误

**解决：**
1. 确保 Session 文件是 `.session` 格式
2. 确保文件名是手机号（如 `916301745881.session`）
3. 确保文件没有损坏

### **问题2：采集失败**

**原因：** 账号权限不足或群组设置了限制

**解决：**
1. 使用「聊天记录模式」采集隐藏成员的群
2. 确保账号已加入目标群组
3. 检查账号状态是否正常

### **问题3：发送失败**

**原因：** 频率限制或用户设置了隐私

**解决：**
1. 程序会自动跳过频率限制的用户
2. 程序会自动删除无法发送的用户
3. 检查账号是否被限制

---

## 🔄 版本更新

### **v2.0.0 (2026-04-23)**
- ✅ 全新模块化架构
- ✅ 10+ 采集功能
- ✅ 智能错误处理
- ✅ 多账号并发
- ✅ 自动退群
- ✅ Premium/头像过滤

### **v1.71.0 (2026-04-23)**
- ✅ 通过聊天记录采集
- ✅ 在线时间过滤
- ✅ 多账号并发

### **v1.70.0 (2026-04-23)**
- ✅ 优化连续失败计数
- ✅ 自动删除无法发送的用户

### **v1.69.0 (2026-04-23)**
- ✅ 移除 FloodWait 等待
- ✅ 直接跳过频率限制用户

---

## 📞 联系方式

- **GitHub**: https://github.com/ochoatanny845-ops/tg-mass-dm
- **版本**: v2.0.0
- **最后更新**: 2026-04-23

---

**🎉 模块化架构让开发更轻松，代码更清晰，功能更强大！**
