#!/bin/bash
# 로컬 환경에서 실행할 자동화 테스트 스크립트

echo "================================"
echo "로컬 환경 자동화 테스트 시작"
echo "================================"

# 1. Python 버전 확인
echo -e "\n[1/6] Python 버전 확인..."
python3 --version || { echo "❌ Python3 설치 필요"; exit 1; }

# 2. 라이브러리 확인
echo "[2/6] 라이브러리 확인..."
python3 -c "import requests, PIL; print('✅ requests, Pillow OK')" || { echo "❌ 라이브러리 설치 필요: pip install -r scripts/requirements.txt"; exit 1; }

# 3. ffmpeg 확인
echo "[3/6] ffmpeg 확인..."
ffmpeg -version > /dev/null 2>&1 || { echo "❌ ffmpeg 설치 필요"; exit 1; }
echo "✅ ffmpeg OK"

# 4. 한글 폰트 확인
echo "[4/6] 한글 폰트 확인..."
ls /usr/share/fonts/opentype/noto/NotoSansCJK* 2>/dev/null || \
ls /usr/share/fonts/truetype/noto/NotoSansCJK* 2>/dev/null || \
ls /System/Library/Fonts/PingFang* 2>/dev/null || \
{ echo "❌ 한글 폰트 설치 필요"; exit 1; }
echo "✅ 한글 폰트 OK"

# 5. 환경 변수 확인
echo "[5/6] 환경 변수 확인..."
if [ -z "$ELEVENLABS_API_KEY" ]; then
    echo "❌ ELEVENLABS_API_KEY 설정 필요"
    echo "   export ELEVENLABS_API_KEY='your_key'"
    exit 1
fi
echo "✅ ELEVENLABS_API_KEY 설정됨"

if [ -z "$YT_CLIENT_ID" ] || [ -z "$YT_CLIENT_SECRET" ] || [ -z "$YT_REFRESH_TOKEN" ]; then
    echo "⚠️  YouTube API 환경 변수 미설정 (upload는 안됨, 영상 생성만 테스트)"
else
    echo "✅ YouTube API 환경 변수 설정됨"
fi

# 6. 생성 테스트
echo "[6/6] 쇼츠 생성 테스트..."
cd "$(dirname "$0")"
python3 scripts/generate_video.py

if [ $? -eq 0 ]; then
    echo -e "\n================================"
    echo "✅✅✅ 모든 테스트 통과!"
    echo "================================"
    echo ""
    echo "생성된 파일:"
    ls -lh output/*.mp4 output/*.png 2>/dev/null | tail -5
else
    echo "❌ 생성 실패"
    exit 1
fi
