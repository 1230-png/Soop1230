#!/usr/bin/env python3
"""
auto_pipeline.py — Rush22 자동 생성 및 업로드 파이프라인

1. topic_bank.json에서 아직 사용하지 않은 주제 선택
2. 60개가 모두 소진되면 Gemini로 새로운 60개 생성
3. 선택한 주제로 영상 생성 후 YouTube 업로드
4. used_log.csv에 기록
"""

import json
import csv
import os
import subprocess
from datetime import datetime
from pathlib import Path

# Gemini API (구글 생성형 AI)
try:
    import google.generativeai as genai
except ImportError:
    print("google-generativeai가 필요합니다. pip install google-generativeai")
    exit(1)

SCRIPT_DIR = Path(__file__).parent
TOPIC_BANK_FILE = SCRIPT_DIR / "scripts" / "topic_bank.json"
USED_LOG_FILE = SCRIPT_DIR / "used_log.csv"

# Gemini 설정 (환경변수에서 API 키 읽음)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

def read_topic_bank():
    """topic_bank.json 읽기"""
    if not TOPIC_BANK_FILE.exists():
        return []
    with open(TOPIC_BANK_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def read_used_topics():
    """used_log.csv에서 사용한 주제 ID 읽기"""
    used = set()
    if USED_LOG_FILE.exists():
        with open(USED_LOG_FILE, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            if reader:
                for row in reader:
                    if row.get("topic"):
                        used.add(row["topic"])
    return used

def get_available_topics():
    """아직 사용하지 않은 주제 반환"""
    bank = read_topic_bank()
    used = read_used_topics()
    return [t for t in bank if t["topic"] not in used]

def generate_new_topics(count=60):
    """Gemini를 사용해 새로운 주제 60개 생성"""
    if not GEMINI_API_KEY:
        print("⚠️  GEMINI_API_KEY가 설정되지 않았습니다. 새 주제를 생성할 수 없습니다.")
        return []

    bank = read_topic_bank()
    used_topics = read_used_topics()
    
    # 현재 주제 목록 (중복 방지용)
    existing_topics = {t["topic"] for t in bank} | used_topics
    
    prompt = f"""
개발자/엔지니어 대상의 기술 교육 쇼츠 60개 주제를 JSON 형식으로 생성하세요.

이미 사용한 주제들 (절대 중복하지 마세요):
{json.dumps(list(used_topics), ensure_ascii=False, indent=2)}

각 주제는 다음 형식으로:
{{
  "id": "T0XX",  // T061부터 시작
  "topic": "짧은 카테고리 (5~10자)",
  "title": "30초 쇼츠용 제목 (40~60자, 임팩트 있게)"
}}

조건:
- 정확히 60개
- 기술 트렌드, 최신 개발 기법, 프로그래밍 팁 등
- 한국 개발자가 관심 가질 만한 주제
- 중복 없이 새로운 주제만
- 타이틀은 "? 꿀팁", "방법", "원리" 등 임팩트 있게
- JSON만 반환 (설명 없음)

시작 ID: T{len(existing_topics) + 1:03d}
"""
    
    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(prompt)
        
        # JSON 추출
        response_text = response.text
        # ```json ... ``` 형태라면 제거
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0]
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0]
        
        new_topics = json.loads(response_text)
        print(f"✅ Gemini가 {len(new_topics)}개의 새로운 주제를 생성했습니다.")
        return new_topics
    
    except Exception as e:
        print(f"❌ Gemini 요청 실패: {e}")
        return []

def append_topics_to_bank(new_topics):
    """topic_bank.json에 새 주제 추가"""
    bank = read_topic_bank()
    bank.extend(new_topics)
    
    with open(TOPIC_BANK_FILE, "w", encoding="utf-8") as f:
        json.dump(bank, f, ensure_ascii=False, indent=2)
    
    print(f"📝 topic_bank.json에 {len(new_topics)}개 주제 추가. (총 {len(bank)}개)")

def select_topic():
    """다음 주제 선택"""
    available = get_available_topics()
    
    if not available:
        print("⚠️  사용 가능한 주제가 없습니다. Gemini로 새로운 주제를 생성하고 있습니다...")
        new_topics = generate_new_topics(60)
        
        if new_topics:
            append_topics_to_bank(new_topics)
            available = get_available_topics()
        else:
            print("❌ 주제를 생성할 수 없습니다. 나중에 다시 시도하세요.")
            return None
    
    # 첫 번째 미사용 주제 선택
    selected = available[0]
    print(f"✅ 주제 선택: {selected['id']} - {selected['title']}")
    return selected

def log_to_csv(topic, video_id, status="success"):
    """used_log.csv에 기록"""
    with open(USED_LOG_FILE, "a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["date", "topic_id", "topic", "title", "youtube_video_id", "status"])
        writer.writerow({
            "date": datetime.now().isoformat(),
            "topic_id": topic["id"],
            "topic": topic["topic"],
            "title": topic["title"],
            "youtube_video_id": video_id or "",
            "status": status
        })

def main():
    """메인 파이프라인"""
    print("🚀 Rush22 자동 파이프라인 시작\n")
    
    # 1. 주제 선택
    topic = select_topic()
    if not topic:
        return
    
    print(f"\n📺 주제: {topic['title']}")
    print(f"💾 topic 데이터: {json.dumps(topic, ensure_ascii=False)}")
    
    # 2. 영상 생성 (현재는 로깅만)
    # TODO: generate_video.py 호출 또는 Gemini로 스크립트 생성
    print("\n⏳ 영상 생성 중...")
    # video_id = generate_video(topic)  # 실제 구현
    video_id = "dummy_video_id"  # 임시
    
    # 3. YouTube 업로드
    print("⏳ YouTube 업로드 중...")
    # upload_video(video_id)  # 실제 구현
    
    # 4. 로그 기록
    log_to_csv(topic, video_id, "success")
    print(f"\n✅ 완료! 로그 기록됨: {topic['title']}")

if __name__ == "__main__":
    main()
