@echo off
chcp 65001 >nul
echo ============================================
echo 🔄 强制重启 WebUI 服务
echo ============================================
echo.

echo [1/5] 查找8000端口占用...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000 ^| findstr LISTENING') do (
    echo 发现进程: %%a
    taskkill /F /PID %%a 2>nul
)
echo.

echo [2/5] 停止所有相关Python进程...
taskkill /F /IM python.exe 2>nul
echo.

echo [3/5] 等待进程完全退出...
timeout /t 3 /nobreak >nul
echo.

echo [4/5] 启动新服务...
start "股票分析WebUI" cmd /k "python main.py --webui-only"
echo.

echo [5/5] 等待服务启动...
timeout /t 5 /nobreak >nul
echo.

echo ============================================
echo ✅ 服务已重启!
echo ============================================
echo.
echo 📱 访问地址:
echo    💼 持仓管理: http://127.0.0.1:8000/portfolio.html
echo    ⚙️  配置页面: http://127.0.0.1:8000/
echo    📊 API测试: http://127.0.0.1:8000/api/portfolio/summary
echo.
echo 💡 提示: 如果还是404，请稍等几秒后刷新浏览器
echo.
pause
