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

echo [2/2] 打包 Windows exe ...
set CSC_IDENTITY_AUTO_DISCOVERY=false
call npm run dist:win
if errorlevel 1 (
  echo [!] 打包失败。
  pause
  exit /b 1
)

echo.
echo 完成。exe 在 dist 文件夹里：
echo   - 便携版：双击即可运行，不用安装
echo   - 安装包：Setup 结尾的文件
echo.
if exist dist explorer dist
pause
