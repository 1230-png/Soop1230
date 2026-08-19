@echo off
chcp 65001 >nul
echo.
echo 🌙 감성힙합 자동화 스튜디오 시작...
echo.

REM 패키지 설치 확인
echo ⏳ 필수 패키지 설치 중...
pip install -r requirements.txt -q

echo.
echo ✅ 준비 완료!
echo.
echo 🚀 Streamlit 앱 실행 중...
echo 📱 브라우저에서 http://localhost:8501 로 접속하세요
echo.

streamlit run app.py
