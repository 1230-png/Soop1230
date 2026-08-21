#!/bin/bash
# 쇼츠 자동 생성 및 업로드 스크립트

set -e

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

# 환경 변수 확인
if [ -z "$ELEVENLABS_API_KEY" ]; then
    echo "❌ ELEVENLABS_API_KEY 설정 필요"
    exit 1
fi

echo "================================"
echo "🎬 쇼츠 생성 시작 ($(date))"
echo "================================"

# 1. 영상 생성
echo -e "\n[1/2] 영상 생성 중..."
python3 scripts/generate_video.py
if [ $? -ne 0 ]; then
    echo "❌ 영상 생성 실패"
    exit 1
fi
echo "✅ 영상 생성 완료"

# 2. YouTube 업로드 (YouTube API 설정되어 있으면)
if [ -n "$YT_CLIENT_ID" ] && [ -n "$YT_CLIENT_SECRET" ] && [ -n "$YT_REFRESH_TOKEN" ]; then
    echo -e "\n[2/2] YouTube 업로드 중..."
    python3 scripts/upload_video.py
    if [ $? -ne 0 ]; then
        echo "⚠️  업로드 실패했지만 영상은 생성됨"
        exit 1
    fi
    echo "✅ YouTube 업로드 완료"
else
    echo "⚠️  YouTube API 설정 안됨 (로컬 저장만 함)"
fi

echo -e "\n================================"
echo "✅ 쇼츠 완성! ($(date))"
echo "================================"
