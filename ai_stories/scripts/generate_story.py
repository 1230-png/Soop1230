#!/usr/bin/env python3
"""
Groq API를 사용한 감성 짧은 이야기 자동 생성
- 무료: Groq API (제한 있음)
- 출력: JSON (제목, 본문, 감정 태그)
"""

import json
import os
import sys
from datetime import datetime
import requests

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "your_key_here")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

STORY_PROMPTS = [
    "감성적인 일상 이야기 (3분 분량)",
    "따뜻한 인간관계 에피소드",
    "혼자라고 느껴지는 날의 위로",
    "작은 성공의 기쁨",
    "우연한 만남의 의미",
    "떠나보낸 것에 대한 그리움",
    "변화 속에서 찾은 희망",
    "혼자만의 시간의 소중함",
]

def generate_story(prompt_idx: int = 0) -> dict:
    """
    Groq API로 감성 이야기 생성

    Returns:
        {
            "title": "제목",
            "content": "본문 (약 600~800글자)",
            "tags": ["감성", "일상", ...],
            "duration": 180,  # 초 (대략)
            "generated_at": "ISO 8601"
        }
    """

    if prompt_idx >= len(STORY_PROMPTS):
        prompt_idx = 0

    prompt = STORY_PROMPTS[prompt_idx]

    system_message = """당신은 감성적인 한국어 이야기 작가입니다.
다음 요구사항을 만족하는 짧은 이야기를 작성하세요:

1. 3~5분 분량 (약 600~800글자)
2. 따뜻하고 공감 가능한 감정
3. 일상에서의 소소한 순간들
4. 시작-중간-끝이 명확함
5. 청자가 힐링할 수 있도록

출력 형식:
{
    "title": "제목 (10글자 내외)",
    "content": "본문",
    "tags": ["감정1", "감정2", ...],
    "moral": "짧은 메시지 (1문장)"
}"""

    try:
        response = requests.post(
            GROQ_API_URL,
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "mixtral-8x7b-32768",  # 무료 모델
                "messages": [
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": f"주제: {prompt}"},
                ],
                "temperature": 0.7,
                "max_tokens": 1000,
            },
            timeout=30,
        )

        response.raise_for_status()
        result = response.json()

        # AI 응답에서 JSON 추출
        content = result["choices"][0]["message"]["content"]

        # JSON 파싱 (마크다운 코드 블록 처리)
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        story_data = json.loads(content.strip())
        story_data["generated_at"] = datetime.now().isoformat()
        story_data["duration"] = int(len(story_data["content"]) / 3)  # 추정치

        return story_data

    except Exception as e:
        print(f"❌ Groq API 에러: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    # 명령행 인자 처리
    prompt_idx = int(sys.argv[1]) if len(sys.argv) > 1 else 0

    story = generate_story(prompt_idx)

    # JSON 출력
    print(json.dumps(story, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
