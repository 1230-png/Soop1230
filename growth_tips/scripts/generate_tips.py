#!/usr/bin/env python3
"""
Groq API를 사용한 자기계발 팁 자동 생성

특징:
- 매일 10-15개 팁 생성
- 1분 이내 분량 (50~100 글자)
- 영어 + 한국어 이중 언어
- Shorts 최적화
"""

import json
import os
import sys
from datetime import datetime
import requests

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "your_key_here")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

TIP_CATEGORIES = [
    "생산성 (Productivity)",
    "습관 형성 (Habit Building)",
    "심리학 (Psychology)",
    "금융 (Finance)",
    "커리어 (Career)",
    "시간 관리 (Time Management)",
    "자신감 (Confidence)",
    "동기부여 (Motivation)",
    "의사소통 (Communication)",
    "학습 (Learning)",
]


def generate_daily_tips(num_tips: int = 10) -> list:
    """
    하루분 팁 10-15개 생성

    Returns:
        [{
            "tip": "팁 내용 (50~100글자)",
            "category": "카테고리",
            "hashtags": ["#생산성", "#팁"],
            "duration": 30,  # 초 (읽기 시간)
            "lang": "ko"
        }, ...]
    """

    system_message = """당신은 세계적인 자기계발 코치입니다.

다음 요구사항을 만족하는 짧은 팁을 작성하세요:

1. 한국어 + 영어 이중 언어
2. 한 줄 (50~100글자)
3. 행동 가능한 실용적인 팁
4. 즉시 적용 가능
5. 긍정적이고 자극적인 톤

형식:
{
    "tip_ko": "한국어 팁",
    "tip_en": "English tip",
    "category": "카테고리",
    "hashtags": ["#tag1", "#tag2"],
    "duration": 30
}"""

    prompt = f"""다음 {len(TIP_CATEGORIES)}개 카테고리에서 각각 1개씩, 총 {num_tips}개의 자기계발 팁을 생성하세요:

카테고리: {", ".join(TIP_CATEGORIES[:num_tips])}

JSON 배열 형식으로 반환하세요. 예:
[
  {{"tip_ko": "...", "tip_en": "...", ...}},
  ...
]"""

    try:
        response = requests.post(
            GROQ_API_URL,
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "mixtral-8x7b-32768",
                "messages": [
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.8,
                "max_tokens": 2000,
            },
            timeout=60,
        )

        response.raise_for_status()
        result = response.json()

        content = result["choices"][0]["message"]["content"]

        # JSON 파싱
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        tips = json.loads(content.strip())

        # 각 팁에 메타데이터 추가
        for i, tip in enumerate(tips):
            tip["id"] = f"{datetime.now().strftime('%Y%m%d')}_{i:02d}"
            tip["generated_at"] = datetime.now().isoformat()

        return tips

    except Exception as e:
        print(f"❌ Groq API 에러: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    # 명령행 인자: 팁 개수 (기본 10)
    num_tips = int(sys.argv[1]) if len(sys.argv) > 1 else 10

    tips = generate_daily_tips(num_tips)

    # JSON 출력
    result = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "total_tips": len(tips),
        "tips": tips,
    }

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
