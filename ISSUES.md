# TG 批量私信系统 - 问题清单

## 当前版本
v1.5.4

## 待修复问题

### 🐛 问题 1：登录失败时界面不更新
**状态**: ✅ 已修复（v1.5.4）
**描述**: 
- 检测账号时，如果 `me = None`，日志显示"登录失败(死号)"
- 但界面状态栏还是显示"未检测"
**原因**: 
- `if not me:` 分支中，`continue` 前没有调用 `refresh_account_tree()`
**修复**: 
- 在 `continue` 前添加 `self.root.after(0, self.refresh_account_tree)`

---

## 新问题记录

### 🆕 问题 2：SpamBot 回复未正确识别为冻结账号
**描述**: 
- SpamBot 回复包含 "blocked for violations"
- 当前判断为"未知状态"
- 应该识别为"永久冻结"

**SpamBot 回复内容**:
```
your account was blocked for violations of the telegram terms of service 
based on user reports confirmed by our moderators.
```

**当前行为**: 
- 状态显示：⚠️ 未知状态
- 日志显示完整回复

**预期行为**: 
- 状态显示：🚫 永久冻结
- 如果有冻结时间，显示到期时间

**关键词扩展**:
- "blocked for violations" → 永久冻结
- "terms of service" → 永久冻结
- "user reports confirmed" → 永久冻结

**增强需求**:
- 解析冻结时间（如果有）
- 显示到期时间
- 临时冻结 vs 永久冻结的区分

---

### 🆕 问题 3：SpamBot 回复未正确识别永久双向冻结
**描述**: 
- SpamBot 回复包含 "some actions can trigger a harsh response"
- 当前判断为"未知状态"
- 应该识别为"🚫 永久冻结"

**SpamBot 回复内容**:
```
hello olivia!

i'm very sorry that you had to contact me. unfortunately, 
some actions can trigger a harsh response from our anti-spam 
systems. if you think your account was limited by mistake, you can
```

**用户确认**: 
- ✅ 这是永久双向冻结
- ❌ 不是地理受限（之前理解错误）

**关键特征**:
- "some actions can trigger a harsh response"
- "anti-spam systems"
- "if you think your account was limited by mistake"（关键！）
- 注意："limited by mistake" 说明账号已经被限制了

**当前行为**: 
- 状态显示：⚠️ 未知状态

**预期行为**: 
- 状态显示：🚫 永久冻结
- 说明：账号被永久限制，无法恢复

**关键词扩展**:
- "some actions can trigger a harsh response" → 永久冻结
- "limited by mistake" → 永久冻结
- "anti-spam systems" + "limited" → 永久冻结

**与地理受限的区别**:
```
地理受限：
- 回复包含 "some phone numbers may trigger"
- 强调"手机号"而非"行为"
- 账号本身没问题

永久冻结：
- 回复包含 "some actions can trigger"
- 强调"操作/行为"触发了系统
- "limited by mistake" 说明已经被限制
- 账号已经不能正常使用
```

---

### 🆕 问题 4：账号检测速度太慢，需要并发检测
**描述**: 
- 当前账号检测是一个一个顺序执行
- 如果有 30 个账号，需要等很久
- 需要支持并发检测（例如同时检测 5-10 个）

**当前行为**: 
```python
for account in accounts:
    检测账号 1  # 耗时 5-10 秒
    检测账号 2  # 耗时 5-10 秒
    ...
    检测账号 30 # 总耗时：150-300 秒（2.5-5分钟）
```

**预期行为**: 
```python
# 并发检测（例如每批 5 个）
批次 1: 检测账号 1-5   # 耗时 5-10 秒
批次 2: 检测账号 6-10  # 耗时 5-10 秒
...
批次 6: 检测账号 26-30 # 总耗时：30-60 秒（0.5-1分钟）
```

**技术方案**:
- 使用 `asyncio.gather()` 并发执行
- 添加并发数量控制（默认 5-10 个）
- 保持线程安全（已有 `root.after()` 机制）
- 添加批次间隔（避免触发 Telegram 限制）

**配置参数**:
- 并发数量：可配置（建议 5-10）
- 批次间隔：可配置（建议 2-5 秒）
- 单账号超时：可配置（建议 30 秒）

**界面改进**:
- 显示检测进度：已完成 / 总数
- 显示当前批次：批次 N / 总批次
- 显示剩余时间估算

**参考实现**:
- 参考私信发送功能的并发逻辑
- 已有的 `send_messages_async()` 就是批次并发

---

### 🆕 问题 5：SpamBot 回复需要区分"地理受限"和"永久冻结"
**描述**: 
- 需要准确区分两种不同的 SpamBot 回复
- 地理受限：账号正常，部分手机号受限
- 永久冻结：账号已被限制，无法恢复

**两种回复对比**:

#### 1️⃣ 地理受限（账号正常）
```
SpamBot 回复:
"unfortunately, some phone numbers may trigger a harsh 
response from our anti-spam systems. if you think this 
is the case with you, you can submit a complaint to our 
moderators or subscribe to telegram"
```

**关键词**:
- ✅ "phone numbers may trigger"（手机号可能触发）
- ✅ "if you think this is the case with you"（如果是你的情况）
- ✅ 没有说账号已被限制
- ✅ 可以提交申诉或订阅 Premium

**状态**: ✅ 正常（地理受限）或 ⚠️ 地理受限

#### 2️⃣ 永久冻结（账号已限制）
```
SpamBot 回复:
"unfortunately, some actions can trigger a harsh response 
from our anti-spam systems. if you think your account was 
limited by mistake, you can"
```

**关键词**:
- ❌ "actions can trigger"（操作触发，不是手机号）
- ❌ "your account was limited"（你的账号已被限制）
- ❌ "limited by mistake"（错误限制）
- ❌ 明确说账号被限制了

**状态**: 🚫 永久冻结

---

**关键区别**:
```
地理受限：
- 关键词：phone numbers（手机号）
- 状态：if you think this is the case（如果是你的情况）
- 账号：没有被限制
- 建议：正常使用，可申诉

永久冻结：
- 关键词：actions（操作/行为）
- 状态：account was limited（账号已被限制）
- 账号：已经不能正常使用
- 建议：账号作废
```

**优先级判断**:
```python
# 1. 先检测地理受限（因为有明确的 "phone numbers"）
if "phone numbers may trigger" in response:
    status = "✅ 正常（地理受限）"

# 2. 再检测行为触发的冻结
elif "actions can trigger" in response and "limited" in response:
    status = "🚫 永久冻结"

# 3. 其他明确的冻结关键词
elif "blocked for violations" in response:
    status = "🚫 永久冻结"
```

---

### 🆕 问题 6：SpamBot 多语言回复支持
**描述**: 
- SpamBot 会根据账号地区回复不同语言
- 当前关键词库只支持英文
- 需要将所有回复统一翻译成英文再判断

**实际案例**:

#### 俄语回复（正常状态）
```
Ваш аккаунт свободен от каких-либо ограничений.
```
**翻译**: Your account is free from any restrictions.
**应判断为**: ✅ 正常

#### 葡萄牙语回复（正常状态）
```
Boas notícias, nenhum limite foi aplicado à sua conta. 
Você está livre como um pássaro.
```
**翻译**: Good news, no limits applied to your account. You are free as a bird.
**应判断为**: ✅ 正常

**当前行为**: 
- 非英文回复被判断为"未知状态"
- 关键词匹配失败

**预期行为**: 
- 自动翻译成英文
- 使用英文关键词库判断
- 准确识别状态

---

**技术方案**:

#### 方案 1：使用翻译 API（推荐）
```python
from deep_translator import GoogleTranslator

async def translate_to_english(text):
    """将任意语言翻译成英文"""
    try:
        translator = GoogleTranslator(source='auto', target='en')
        return translator.translate(text)
    except:
        return text  # 翻译失败返回原文

# 检测流程
response = messages[0].message  # SpamBot 原始回复
response_en = await translate_to_english(response)  # 翻译成英文
# 使用英文关键词库判断
```

#### 方案 2：多语言关键词库
```python
NORMAL_KEYWORDS = [
    # 英文
    "good news", "no limits", "free as a bird",
    
    # 俄语
    "свободен от каких-либо ограничений",
    
    # 葡萄牙语
    "nenhum limite foi aplicado",
    "livre como um pássaro",
    
    # 西班牙语
    "sin límites", "libre como un pájaro",
    
    # ... 太多了，不推荐
]
```

#### 方案 3：混合方案（最佳）
```python
# 1. 先尝试英文关键词匹配
if any(keyword in response.lower() for keyword in ENGLISH_KEYWORDS):
    # 直接判断
    status = determine_status(response)
else:
    # 2. 非英文，翻译后再判断
    response_en = await translate_to_english(response)
    status = determine_status(response_en)
    
    # 3. 记录原始回复和翻译（调试用）
    self.log(f"  原始: {response[:100]}")
    self.log(f"  翻译: {response_en[:100]}")
```

---

**依赖库**:
```bash
pip install deep-translator
```

**优点**:
- 支持 100+ 种语言
- 免费使用 Google Translate
- 自动检测源语言
- 无需 API Key

---

### 🆕 问题 7：确认冻结账号回复示例（验证问题 2）
**描述**: 
- 用户提供了真实的冻结账号回复
- 验证问题 2 的关键词是正确的

**SpamBot 回复**:
```
Your account was blocked for violations of the Telegram Terms 
of Service based on user reports confirmed by our moderators.
```

**关键词验证**:
- ✅ "blocked for violations" - 匹配！
- ✅ "Telegram Terms of Service" - 匹配！
- ✅ "user reports confirmed" - 匹配！
- ✅ "moderators" - 额外关键词

**应判断为**: 🚫 永久冻结

**状态**: ✅ 问题 2 的关键词库正确！修复后可以识别这种回复！

---

### 🆕 问题 8：临时限制需要解析到期时间
**描述**: 
- SpamBot 回复包含明确的到期时间
- 当前只显示"临时垃圾邮件"
- 应该解析并显示到期时间

**SpamBot 回复**:
```
I'm afraid some Telegram users found your messages annoying and 
forwarded them to our team of moderators for inspection. The 
moderators have confirmed the report and your account is now 
limited until 24 Apr 2026, 04:03 UTC.

While the account is limited, you will not be able to do certain 
things on Telegram, like writing to strangers who haven't 
contacted you first or adding them to groups and channels.

Your account will be automatically released on 24 Apr 2026, 
04:03 UTC. Please note that if you repeat what got you limited 
and users report you again, the limitations will last longer next 
time. Subscribers of Telegram Premium have reduced times for 
initial limitations.
```

**关键信息**:
- ✅ "limited until 24 Apr 2026, 04:03 UTC"
- ✅ "automatically released on 24 Apr 2026, 04:03 UTC"
- ✅ 两次提到到期时间（更可靠）

**当前行为**: 
- 状态显示：⚠️ 临时垃圾邮件
- 没有显示到期时间

**预期行为**: 
- 状态显示：⚠️ 临时限制（至 2026-04-24 04:03 UTC）
- 或：⚠️ 临时限制（剩余 2 天 5 小时）

**技术方案**:

#### 1️⃣ 解析时间
```python
import re
from datetime import datetime

def parse_limitation_time(response):
    """解析限制到期时间"""
    # 匹配模式: "until DD MMM YYYY, HH:MM UTC"
    pattern = r"(?:until|on)\s+(\d{1,2})\s+([A-Za-z]+)\s+(\d{4}),\s+(\d{2}):(\d{2})\s+UTC"
    match = re.search(pattern, response)
    
    if match:
        day, month_str, year, hour, minute = match.groups()
        
        # 月份映射
        months = {
            'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 
            'May': 5, 'Jun': 6, 'Jul': 7, 'Aug': 8,
            'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12
        }
        
        month = months.get(month_str, 1)
        
        # 构造时间对象
        release_time = datetime(
            int(year), month, int(day), 
            int(hour), int(minute)
        )
        
        return release_time
    
    return None
```

#### 2️⃣ 显示格式
```python
if is_spam_temp:
    # 尝试解析时间
    release_time = parse_limitation_time(response)
    
    if release_time:
        # 格式化显示
        time_str = release_time.strftime("%Y-%m-%d %H:%M UTC")
        
        # 计算剩余时间
        now = datetime.utcnow()
        remaining = release_time - now
        
        if remaining.total_seconds() > 0:
            days = remaining.days
            hours = remaining.seconds // 3600
            account["status"] = f"⚠️ 临时限制（剩余 {days}天{hours}时）"
        else:
            account["status"] = f"⚠️ 临时限制（已过期）"
    else:
        account["status"] = "⚠️ 临时垃圾邮件"
```

#### 3️⃣ 界面显示
```
状态栏：⚠️ 临时限制（剩余 2天5时）
日志：
  ⚠️ 临时限制: @username
     到期时间: 2026-04-24 04:03 UTC
     剩余时间: 2 天 5 小时
```

---

**关键词验证**:
```python
SPAM_TEMP_KEYWORDS = [
    "limited until",              # ✅ 匹配！
    "account is now limited",     # ✅ 匹配！
    "automatically released on",  # ✅ 可以新增
]
```

---

### 🆕 问题 9：确认永久双向限制回复（验证问题 3）
**描述**: 
- 用户提供了真实的永久双向限制回复
- 验证问题 3 的关键词是正确的
- 与临时限制的区别：没有"until"和到期时间

**SpamBot 回复**:
```
Hello Jennifer!

I'm very sorry that you had to contact me. Unfortunately, some 
actions can trigger a harsh response from our anti-spam systems. 
If you think your account was limited by mistake, you can submit 
a complaint to our moderators.

While the account is limited, you will not be able to send 
messages to people who do not have your number in their phone 
contacts or add them to groups and channels. Of course, when 
people contact you first, you can always reply to them.
```

**关键词验证**:
- ✅ "some actions can trigger" - 匹配！
- ✅ "your account was limited" - 匹配！
- ✅ "limited by mistake" - 匹配！
- ✅ "harsh response from our anti-spam systems" - 匹配！
- ❌ 没有 "until" - 说明是永久限制！
- ❌ 没有时间 - 说明是永久限制！

**与临时限制的区别**:

#### 临时限制（问题 8）
```
"limited until 24 Apr 2026, 04:03 UTC"
"automatically released on"
→ 有明确到期时间
→ 状态：⚠️ 临时限制（剩余 X 天）
```

#### 永久限制（问题 9）
```
"your account was limited by mistake"
"some actions can trigger"
没有 "until"
没有时间
→ 无到期时间
→ 状态：🚫 永久冻结
```

**判断逻辑优化**:
```python
# 检测是否包含时间（临时限制）
has_time = "until" in response or "released on" in response

if "limited" in response:
    if has_time:
        # 有时间 → 临时限制
        account["status"] = "⚠️ 临时限制（剩余 X 天）"
    else:
        # 没有时间 → 永久限制
        account["status"] = "🚫 永久冻结"
```

**应判断为**: 🚫 永久冻结

**状态**: ✅ 问题 3 的关键词库正确！修复后可以识别这种回复！

---

### 🆕 问题 10：冻结账户需要显示申诉期限
**描述**: 
- 冻结账户（frozen）只有一种状态：🚫 冻结
- 不区分"临时冻结"和"永久冻结"
- 如果有申诉期限，显示时间；没有则不显示

**SpamBot 回复（俄语）**:
```
Ваш аккаунт заморожен

Ограничение можно оспорить в @SpamBot до 19 мая 2026 г.; 
в противном случае аккаунт будет удалён.
```

**翻译**:
```
Your account is frozen

The restriction can be appealed in @SpamBot until May 19, 2026; 
otherwise the account will be deleted.
```

**关键信息**:
- ✅ "frozen" / "заморожен" - 冻结
- ✅ "до 19 мая 2026 г." (until May 19, 2026) - 申诉期限

**当前行为**: 
- 可能显示：⚠️ 未知状态

**预期行为**: 
- 有申诉期限：🚫 冻结（申诉至 2026-05-19）
- 无申诉期限：🚫 冻结

---

**关键词扩展**:
```python
FROZEN_KEYWORDS = [
    # 英文
    "frozen",
    "account is frozen",
    
    # 俄语
    "заморожен",
    "аккаунт заморожен",
]
```

**时间解析**:
```python
# 俄语日期格式: "до 19 мая 2026 г."
# 翻译后: "until May 19, 2026"

if "frozen" in response or "заморожен" in response:
    # 尝试解析申诉期限
    appeal_time = parse_time(response)
    
    if appeal_time:
        account["status"] = f"🚫 冻结（申诉至 {appeal_time}）"
    else:
        account["status"] = "🚫 冻结"
```

---

**正确的状态分类**:

#### 1. ✅ 正常
- 无任何限制

#### 2. ✅ 正常（地理受限）
- "phone numbers may trigger"
- 账号正常，部分地区可能触发警告

#### 3. ⚠️ 临时限制
- "limited until XX"
- 发消息受限，到期自动恢复
- 显示：⚠️ 临时限制（剩余 X 天）

#### 4. 🚫 冻结
- "frozen" 或 "заморожен"
- 有申诉期限：🚫 冻结（申诉至 XX）
- 无申诉期限：🚫 冻结

#### 5. 🚫 永久冻结
- "blocked for violations"
- "permanently banned"
- 显示：🚫 永久冻结

---

### 🆕 问题 11：日志窗口被挤压，看不到内容（UI 布局问题）
**描述**: 
- 账号列表区域占满了整个界面
- 日志窗口被挤压到底部，看不到内容
- 用户无法查看运行日志

**当前问题**:
```
┌─────────────────────────────────────┐
│  账号列表区域（占据 90% 高度）      │
│                                     │
│                                     │
│                                     │
│                                     │
│                                     │
└─────────────────────────────────────┘
┌─────────────────────────────────────┐
│  日志区域（只有 10% 高度）❌        │ ← 看不到内容
└─────────────────────────────────────┘
```

**预期布局**:
```
┌─────────────────────────────────────┐
│  账号列表区域（50-60% 高度）✅      │
│                                     │
└─────────────────────────────────────┘
┌─────────────────────────────────────┐
│  日志区域（40-50% 高度）✅          │
│  [19:32:15] 🔄 开始检测...          │
│  [1/30] 检测: 85270904746           │
│  ✅ 正常: @username                 │
└─────────────────────────────────────┘
```

---

**原因分析**:

#### 代码位置
`setup_tab_accounts()` 函数中的布局代码

#### 问题代码
```python
# 账号列表
tree_frame = ttk.Frame(tab1)
tree_frame.pack(fill=tk.BOTH, expand=True)  # ❌ expand=True 占满所有空间

# 日志区域
log_frame = ttk.LabelFrame(tab1, text="📋 运行日志", padding="5")
log_frame.pack(fill=tk.BOTH, pady=(10, 0))  # ❌ 没有 expand，只能显示最小高度
```

#### 修复代码
```python
# 方案 1：固定比例（推荐）
tree_frame = ttk.Frame(tab1)
tree_frame.pack(fill=tk.BOTH, expand=True)  # 占 60%
tree_frame.pack_propagate(False)
tree_frame.config(height=500)  # 固定高度

# 日志区域
log_frame = ttk.LabelFrame(tab1, text="📋 运行日志", padding="5")
log_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))  # 占剩余空间

# 方案 2：PanedWindow（可调节）
paned = ttk.PanedWindow(tab1, orient=tk.VERTICAL)
paned.pack(fill=tk.BOTH, expand=True)

# 账号列表
tree_frame = ttk.Frame(paned)
paned.add(tree_frame, weight=3)  # 占 60%

# 日志区域
log_frame = ttk.LabelFrame(paned, text="📋 运行日志")
paned.add(log_frame, weight=2)  # 占 40%
```

---

**修复方案**:

### 选项 A：固定比例
```
账号列表：固定高度 500px
日志区域：占剩余空间
优点：简单
缺点：不能调节
```

### 选项 B：可调节分隔栏（推荐）
```
使用 PanedWindow
用户可以拖动分隔线调节比例
优点：灵活
缺点：代码稍复杂
```

---

**其他标签页检查**:

需要检查"私信广告"和"采集用户"标签页是否也有同样问题：

#### 私信广告标签页
```python
# 目标列表 vs 日志
# 需要确保日志可见
```

#### 采集用户标签页
```python
# 采集列表 vs 日志
# 需要确保日志可见
```

---

### 🆕 问题 12：（等待用户反馈）
**描述**: 
（待补充）

**重现步骤**: 
（待补充）

**预期行为**: 
（待补充）

**实际行为**: 
（待补充）

---

## 已修复问题历史

### ✅ v1.5.3 - 线程安全问题
- 异步线程直接更新 Tkinter 界面
- 修复：使用 `root.after()` 调度到主线程

### ✅ v1.5.2 - 状态分类优化
- 区分"封禁"和"网络错误"
- 实时更新状态显示

### ✅ v1.5.1 - 添加刷新按钮
- 新增刷新按钮，重新扫描 accounts 文件夹

### ✅ v1.5.0 - 账号发送统计
- 显示每个账号的发送成功/失败数量
- 计算成功率

---

## 笔记

**工作流程**：
1. 用户提出问题 → 记录到这个文件
2. 收集所有问题 → 分析优先级
3. 批量修复 → 一次提交
4. 测试验证 → 更新版本号

**好处**：
- 避免频繁提交
- 避免多次重启测试
- 一次性解决多个问题
- Git 历史更清晰
