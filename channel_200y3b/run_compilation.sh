#!/bin/bash
# 주간 롱폼 컴파일 생성 및 업로드 스크립트 (generate_compilation.py가 업로드까지 내부적으로 처리)

set -e

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

if [ -z "$ELEVENLABS_API_KEY" ]; then
    echo "❌ ELEVENLABS_API_KEY 설정 필요"
    exit 1
fi

echo "================================"
echo "🎥 주간 컴파일 생성 및 업로드 시작 ($(date))"
echo "================================"

python scripts/generate_compilation.py

echo -e "\n================================"
echo "✅ 주간 컴파일 완성! ($(date))"
echo "================================"
