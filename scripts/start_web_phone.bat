@echo off
setlocal

set "PROJECT_DIR=D:\BlindRoadMonitor"
set "VENV_PY=D:\BlindRoadMonitor.venv\Scripts\python.exe"
set "PORT=8000"
rem ============================================================
rem  手机摄像头地址 (IP Webcam)。若手机 IP 变化, 只需改这一行。
rem  需满足: 手机开 IP Webcam 并点"启动服务器"; 手机与电脑同一 WiFi。
rem ============================================================
set "SOURCE=http://192.168.1.7:8080/video"

cd /d "%PROJECT_DIR%" || (echo 无法进入项目目录: %PROJECT_DIR% & pause & exit /b 1)

echo ============================================================
echo   BlindRoadMonitor - 手机摄像头版 (IP Webcam)
echo ============================================================
echo.
echo   手机源地址 : %SOURCE%
echo   使用提示   : 手机保持 IP Webcam 运行、勿息屏; 电脑与手机同一 WiFi
echo.

if not exist "%VENV_PY%" (
  echo [错误] 找不到虚拟环境 Python: %VENV_PY%
  echo         请参考 docs\deployment_guide.md 的"安装"章节重建虚拟环境。
  echo.
  pause
  exit /b 1
)

if not exist "%PROJECT_DIR%\scripts\run_web.py" (
  echo [错误] 找不到启动脚本: %PROJECT_DIR%\scripts\run_web.py
  echo         请确认项目文件完整。
  echo.
  pause
  exit /b 1
)

echo [1/3] 环境检查通过
echo        项目目录 = %PROJECT_DIR%
echo        解释器   = %VENV_PY%
echo.
echo [2/3] 正在连接手机摄像头并启动 Web 服务 (首次加载模型约需 10~30 秒)...
echo        画面地址: http://127.0.0.1:%PORT%
echo        停止服务:  在本窗口按 Ctrl+C, 或直接关闭本窗口
echo.
echo [3/3] 约 12 秒后将自动打开浏览器 (如未弹出请手动访问上方地址)
echo ------------------------------------------------------------

rem 延迟 12 秒自动打开浏览器 (等待模型加载与服务就绪)
start "" /b powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 12; Start-Process 'http://127.0.0.1:%PORT%'"

"%VENV_PY%" scripts\run_web.py --source "%SOURCE%" --conf 0.20 --port %PORT%
set "EXITCODE=%ERRORLEVEL%"

echo ------------------------------------------------------------
echo.
if not "%EXITCODE%"=="0" (
  echo [错误] 服务异常退出，退出码 %EXITCODE%
  echo.
  echo   常见原因:
  echo     1. 手机 IP Webcam 未启动 / 手机已息屏 / 不在同一 WiFi
  echo        - 手机打开 IP Webcam, 点"启动服务器", 保持屏幕常亮
  echo        - 确认电脑能访问 http://192.168.1.7:8080
  echo     2. 手机 IP 已变化 -^> 把本文件顶部的 SOURCE 改成新地址
  echo        (IP Webcam 启动后画面下方会显示当前地址)
  echo     3. 端口 %PORT% 被占用 -^> 把本文件顶部的 PORT 改成 8010 等
  echo.
  echo   详细排障见 docs\deployment_guide.md 常见错误 一节
) else (
  echo 服务已正常停止。
)
echo.
pause
endlocal
