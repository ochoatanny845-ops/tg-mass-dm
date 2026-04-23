# Telegram Web Auto-Login Module

独立的 Telegram Web 自动登录模块，可以单独使用或集成到其他项目。

## 功能

- ✅ 从 Telethon session 文件提取认证密钥
- ✅ 自动注入到浏览器 localStorage
- ✅ 打开 Telegram Web 并自动登录
- ✅ 支持命令行工具和Python库两种使用方式
- ✅ 无需手动扫码或输入验证码

## 安装依赖

```bash
pip install selenium webdriver-manager
```

## 使用方法

### 1. 作为命令行工具

```bash
# 基本用法
python modules/web_login.py sessions/account1.session

# 无头模式（不显示浏览器窗口）
python modules/web_login.py sessions/account1.session --headless

# 自动关闭（5秒后）
python modules/web_login.py sessions/account1.session --auto-close

# 组合使用
python modules/web_login.py sessions/account1.session --headless --auto-close
```

### 2. 作为 Python 库

```python
from modules.web_login import TelegramWebLogin

# 创建实例
login = TelegramWebLogin()

# 方式1：保持浏览器打开（默认）
driver = login.open_telegram_web("sessions/account1.session")
# 手动关闭：driver.quit()

# 方式2：自动关闭
login.open_telegram_web("sessions/account1.session", keep_open=False)

# 方式3：无头模式
driver = login.open_telegram_web("sessions/account1.session", headless=True)

# 方式4：自定义日志
def my_logger(msg):
    print(f"[LOG] {msg}")

login = TelegramWebLogin(logger=my_logger)
driver = login.open_telegram_web("sessions/account1.session")
```

## 工作原理

1. **提取认证密钥**
   ```python
   # 从 .session SQLite 文件读取
   SELECT dc_id, auth_key FROM sessions
   ```

2. **转换格式**
   ```python
   # auth_key (binary) → base64
   auth_key_b64 = base64.b64encode(auth_key)
   ```

3. **注入浏览器**
   ```javascript
   // 设置 localStorage
   localStorage.setItem('dc{X}_auth_key', '<base64_key>');
   localStorage.setItem('dc', '{X}');
   ```

4. **自动登录**
   ```
   刷新页面 → Telegram Web 识别认证 → 登录成功
   ```

## 技术细节

### Session 文件结构

Telethon session 是 SQLite 数据库，包含：

| 字段           | 类型   | 说明                |
|--------------|------|-------------------|
| dc_id        | INT  | 数据中心ID (1-5)      |
| server_address | TEXT | 服务器地址             |
| port         | INT  | 端口                |
| auth_key     | BLOB | 认证密钥（二进制）         |

### Telegram Web localStorage

Telegram Web 使用以下键值存储认证：

```javascript
// 主认证密钥（每个DC一个）
dc1_auth_key: "base64_encoded_key"
dc2_auth_key: "base64_encoded_key"
...

// 当前使用的DC
dc: "2"
```

### 浏览器配置

使用无痕模式 + 反检测参数：

```python
chrome_options.add_argument('--incognito')
chrome_options.add_argument('--disable-blink-features=AutomationControlled')
chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
```

## API 参考

### TelegramWebLogin

#### `__init__(logger=None)`

创建实例。

**参数：**
- `logger` (callable, optional): 自定义日志函数，默认使用 `print()`

#### `check_dependencies()`

检查依赖是否安装。

**返回：**
- `tuple`: `(bool, str)` - (是否成功, 消息)

#### `extract_session_data(session_file)`

从 session 文件提取认证数据。

**参数：**
- `session_file` (str): .session 文件路径

**返回：**
- `dict`: `{'dc_id', 'auth_key', 'server', 'port'}`

**异常：**
- `FileNotFoundError`: session 文件不存在
- `ValueError`: session 无效或未登录

#### `open_telegram_web(session_file, headless=False, keep_open=True)`

打开 Telegram Web 并自动登录。

**参数：**
- `session_file` (str): .session 文件路径
- `headless` (bool): 无头模式，默认 `False`
- `keep_open` (bool): 保持浏览器打开，默认 `True`

**返回：**
- `WebDriver` 或 `None`

## 安全性

- ✅ 使用无痕模式，不污染主浏览器配置
- ✅ 独立浏览器实例，不影响已登录账号
- ✅ 不修改原 session 文件
- ✅ 关闭浏览器后自动清除 localStorage

## 注意事项

1. **Telegram Web 版本**
   - ✅ 支持：`web.telegram.org/a/` (A版)
   - ❌ 不支持：`web.telegram.org/k/` (K版)

2. **ChromeDriver**
   - 使用 `webdriver-manager` 自动下载
   - 无需手动配置

3. **Session 有效期**
   - Session 过期后无法登录
   - 需要重新通过手机验证

## 故障排查

### 依赖问题

```bash
# 错误：ModuleNotFoundError: No module named 'selenium'
pip install selenium webdriver-manager

# 错误：webdriver-manager 不存在
pip install webdriver-manager
```

### Session 问题

```bash
# 错误：Session 文件中没有认证数据
# 原因：session 未登录或已过期
# 解决：重新登录生成 session

# 错误：Session 文件不存在
# 原因：文件路径错误
# 解决：检查文件路径是否正确
```

### 浏览器问题

```bash
# 错误：chromedriver 版本不匹配
# 解决：删除缓存重新下载
rm -rf ~/.wdm
python modules/web_login.py <session_file>

# 错误：Chrome 未安装
# 解决：安装 Chrome 浏览器
```

## License

MIT

## 作者

TG Mass DM Project
