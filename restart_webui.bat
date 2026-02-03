@echo off
echo ============================================
echo 重启 WebUI 服务
echo ============================================
echo.

echo [1/4] 停止旧服务...
taskkill /F /FI "WINDOWTITLE eq *webui-only*" 2>nul
taskkill /F /FI "COMMANDLINE eq *main.py*--webui-only*" 2>nul
echo.

echo [2/4] 等待进程完全退出...
timeout /t 2 /nobreak >nul
echo.

echo [3/4] 启动新服务...
start "股票分析WebUI" python main.py --webui-only
echo.

echo [4/4] 等待服务启动...
timeout /t 3 /nobreak >nul
echo.

echo ============================================
echo ✅ 服务已重启!
echo ============================================
echo.
echo 📱 访问地址:
echo    http://127.0.0.1:8000/portfolio.html
echo.
echo 📊 功能页面:
echo    持仓管理: http://127.0.0.1:8000/portfolio.html
echo    配置页面: http://127.0.0.1:8000/
echo.
pause
