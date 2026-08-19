import subprocess
import sys
import os

# 현재 디렉토리
current_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(current_dir)

# 패키지 설치
subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt", "-q"], 
               capture_output=True)

# Streamlit 실행
subprocess.Popen([sys.executable, "-m", "streamlit", "run", "app.py"])

# 브라우저 자동 오픈
import time
time.sleep(2)
import webbrowser
webbrowser.open("http://localhost:8501")
