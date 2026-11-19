@echo off
chcp 65001 >nul
cd /d "%~dp0"

where node >nul 2>&1
if errorlevel 1 (
  echo [!] 先安装 Node.js LTS: https://nodejs.org
  echo     安装时勾选 Add to PATH，然后重新打开这个脚本。
  pause
  exit /b 1
)

echo [1/2] npm install ...
call npm install
if errorlevel 1 (
  echo [!] npm install 失败，请检查网络后重试。
  pause
  exit /b 1
)

echo [2/2] 启动桌宠
call npm start
if errorlevel 1 (
  echo [!] 启动失败。
  pause
  exit /b 1
)
