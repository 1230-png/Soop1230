#!/bin/bash
# 쇼츠 자동 생성 및 업로드 스크립트 (generate_video.py가 업로드까지 내부적으로 처리)

set -e

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

if [ -z "$ELEVENLABS_API_KEY" ]; then
    echo "❌ ELEVENLABS_API_KEY 설정 필요"
    exit 1
fi

echo "================================"
echo "🎬 쇼츠 생성 및 업로드 시작 ($(date))"
echo "================================"

python scripts/generate_video.py

echo -e "\n================================"
echo "✅ 쇼츠 완성! ($(date))"
echo "================================"
