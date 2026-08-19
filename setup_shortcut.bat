@echo off
chcp 65001 >nul
echo.
echo 🌙 감성힙합 자동화 스튜디오 - 바탕화면 단축키 생성 중...
echo.

REM 현재 디렉토리 확인
set "SCRIPT_DIR=%~dp0"
set "LAUNCHER=%SCRIPT_DIR%launcher.pyw"
set "ICON=%SCRIPT_DIR%icon.png"

REM PowerShell로 바탕화면 경로 가져오기
for /f "tokens=*" %%A in ('powershell -Command "[Environment]::GetFolderPath('Desktop')"') do set "DESKTOP=%%A"

REM 바탕화면에 단축키 생성
powershell -Command ^
  "$WshShell = New-Object -ComObject WScript.Shell; " ^
  "$Shortcut = $WshShell.CreateShortcut('%DESKTOP%\감성힙합 스튜디오.lnk'); " ^
  "$Shortcut.TargetPath = '%LAUNCHER%'; " ^
  "$Shortcut.WorkingDirectory = '%SCRIPT_DIR:~0,-1%'; " ^
  "$Shortcut.IconLocation = '%ICON%'; " ^
  "$Shortcut.Save()"

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ✅ 완료! 바탕화면에 "감성힙합 스튜디오" 단축키가 생성되었습니다.
    echo 🎵 단축키를 더블클릭하면 앱이 자동으로 실행됩니다!
    echo.
) else (
    echo.
    echo ❌ 오류 발생! 다시 시도해주세요.
    echo.
)

pause
