@echo off
chcp 65001 >nul
echo ========================================
echo TG 批量私信系统 - 重新启动
echo ========================================
echo.

echo [1/3] 检查更新...
git pull

echo.
echo [2/3] 关闭旧进程...
taskkill /F /IM python.exe /FI "WINDOWTITLE eq TG*" 2>nul
timeout /t 2 >nul

echo.
echo [3/3] 启动程序...
start pythonw main_v1.3.py

echo.
echo ✅ 启动完成！
echo.
pause
