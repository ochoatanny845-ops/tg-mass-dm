@echo off
chcp 65001 >nul
echo ================================
echo   TG 批量私信系统 启动器
echo ================================
echo.

REM 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ 未找到 Python，请先安装 Python 3.8+
    pause
    exit /b 1
)

echo ✅ Python 已安装
echo.

REM 检查依赖
echo 📦 检查依赖库...
python -c "import telethon" >nul 2>&1
if errorlevel 1 (
    echo ⚠️ 缺少 telethon 库，正在安装...
    pip install -r requirements.txt
)

echo ✅ 依赖库完整
echo.

REM 启动程序
echo 🚀 启动程序...
echo.
python main.py

pause
