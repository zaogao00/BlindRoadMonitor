@echo off
setlocal

set "PROJECT_DIR=D:\BlindRoadMonitor"
set "VENV_PY=D:\BlindRoadMonitor.venv\Scripts\python.exe"
set "PORT=8000"

cd /d "%PROJECT_DIR%" || (echo 无法进入项目目录: %PROJECT_DIR% & pause & exit /b 1)

echo ============================================================
echo   BlindRoadMonitor - 智能盲道障碍物监测与预警系统
echo ============================================================
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

echo [1/2] 环境检查通过
echo        项目目录 = %PROJECT_DIR%
echo        解释器   = %VENV_PY%
echo.
echo [2/2] 正在启动 Web 服务 (首次加载模型约需 10~30 秒)...
echo        浏览器访问: http://127.0.0.1:%PORT%
echo        停止服务:   在本窗口按 Ctrl+C，或直接关闭本窗口
echo.
echo ------------------------------------------------------------

"%VENV_PY%" scripts\run_web.py --source 0 --conf 0.20 --port %PORT%
set "EXITCODE=%ERRORLEVEL%"

echo ------------------------------------------------------------
echo.
if not "%EXITCODE%"=="0" (
  echo [错误] 服务异常退出，退出码 %EXITCODE%
  echo.
  echo   常见原因:
  echo     1. 摄像头被其他程序占用 (如相机应用、会议软件) -> 关掉后重试
  echo     2. 显卡驱动 / CUDA 异常 -> 查看上方错误，参考 docs\deployment_guide.md
  echo     3. 端口 %PORT% 被占用 -> 换端口: scripts\run_web.py --port 8010
  echo.
  echo   详细排障见 docs\deployment_guide.md 常见错误 一节
) else (
  echo 服务已正常停止。
)
echo.
pause
endlocal
