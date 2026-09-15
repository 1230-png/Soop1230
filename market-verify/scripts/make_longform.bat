@echo off
chcp 65001 >nul
REM ============================================================
REM  머니로직 롱폼 자동 생성 (Windows 작업 스케줄러용)
REM
REM  업로드는 하지 않는다. 지정한 폴더에 영상만 쌓아 두고,
REM  결과를 눈으로 본 뒤 사람이 직접 올린다.
REM
REM  등록 방법은 NOTES.md "윈도우에서 자동으로 만들기" 참고.
REM ============================================================
setlocal

REM ===== 여기 세 줄만 고치면 된다 =====
REM  비워 두면 바탕화면\클로드\머니로직 으로 간다.
REM  (원드라이브로 바탕화면이 옮겨져 있어도 실제 위치를 따라간다)
set "OUTDIR="
set "COUNT=1"
REM  cli = 이미 깔린 Claude Code 구독으로 대본을 쓴다 (API 크레딧 불필요)
REM  api = ANTHROPIC_API_KEY 로 쓴다 (API 크레딧 필요)
set "MARKET_VERIFY_LLM=cli"
REM ====================================

REM 인자로 넘기면 그쪽이 이긴다:  make_longform.bat "E:\다른폴더" 2
if not "%~1"=="" set "OUTDIR=%~1"
if not "%~2"=="" set "COUNT=%~2"

REM 저장 폴더를 안 정했으면 바탕화면 아래로 보낸다. 바탕화면 실제 경로는
REM 원드라이브로 옮겨져 있을 수 있어서 박아 두지 않고 윈도우에 물어본다.
for /f "usebackq delims=" %%i in (`powershell -NoProfile -Command "[Environment]::GetFolderPath('Desktop')"`) do set "DESKTOP=%%i"
if "%OUTDIR%"=="" set "OUTDIR=%DESKTOP%\클로드\머니로직"

REM 이 파일은 market-verify\scripts\ 에 있다. 한 칸 위가 프로젝트 폴더다.
set "REPO=%~dp0.."
cd /d "%REPO%" || (echo 프로젝트 폴더로 이동하지 못했다: "%REPO%" & exit /b 1)

REM 가상환경이 있으면 그걸 쓴다. 없으면 시스템 파이썬.
set "PY=python"
if exist "%REPO%\.venv\Scripts\python.exe" set "PY=%REPO%\.venv\Scripts\python.exe"

REM --- 준비물 확인. 다 만들고 나서 실패하면 시간만 버린다. ---
"%PY%" --version >nul 2>&1 || (echo 실패: 파이썬을 찾지 못했다. & exit /b 1)
where ffmpeg >nul 2>&1 || (echo 실패: ffmpeg 을 PATH 에서 찾지 못했다. & exit /b 1)
if /i "%MARKET_VERIFY_LLM%"=="cli" (
  where claude >nul 2>&1 || (echo 실패: claude 를 PATH 에서 찾지 못했다. npm install -g @anthropic-ai/claude-code & exit /b 1)
) else (
  if "%ANTHROPIC_API_KEY%"=="" (echo 실패: ANTHROPIC_API_KEY 가 설정되지 않았다. & exit /b 1)
)

REM --- 로그 파일. 무인 실행이라 남기지 않으면 왜 실패했는지 알 수 없다. ---
if not exist "%OUTDIR%\_log" mkdir "%OUTDIR%\_log"
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd-HHmmss"') do set "STAMP=%%i"
set "LOGFILE=%OUTDIR%\_log\run_%STAMP%.log"

echo [%STAMP%] %COUNT%편 생성 시작 -^> "%OUTDIR%"
echo [%STAMP%] %COUNT%편 생성 시작 -^> "%OUTDIR%" > "%LOGFILE%"

"%PY%" -m src.daily_pipeline --outdir "%OUTDIR%" --repeat %COUNT% >> "%LOGFILE%" 2>&1
set "CODE=%ERRORLEVEL%"

if "%CODE%"=="0" (
  echo 완료. 로그: "%LOGFILE%"
) else (
  echo 실패(종료코드 %CODE%^). 로그를 볼 것: "%LOGFILE%"
)
exit /b %CODE%
