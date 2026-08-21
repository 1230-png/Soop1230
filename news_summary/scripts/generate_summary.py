#!/usr/bin/env python3
"""
뉴스 기사를 한국어로 요약

특징:
- 영문 뉴스를 한국어로 번역 + 요약
- 간단한 요약 (1문장, 30초 음성)
- 상세 요약 (3-5문장, 3분 음성)
- 해시태그 자동 생성
"""

import json
import os
import sys
from datetime import datetime
import requests

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "your_key")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"


def generate_summary(article: dict, summary_type: str = "short") -> dict:
    """
    뉴스 기사를 한국어로 요약

    Args:
        article: {"title", "description", "content", ...}
        summary_type: "short" (1문장) or "long" (3-5문장)

    Returns:
        {
            "title_ko": "한글 제목",
            "summary_short": "짧은 요약 (1문장)",
            "summary_long": "긴 요약 (3-5문장)",
            "hashtags": ["#해시태그1", ...],
            "importance": 1-5,  # 중요도
            "duration_short": 30,  # 초
            "duration_long": 180  # 초
        }
    """

    system_message = """당신은 전문 뉴스 에디터입니다.

영문 뉴스를 다음과 같이 처리하세요:

1. 한국어로 번역 + 요약
2. 정확하고 객관적인 톤
3. 중요한 정보만 포함
4. 이해하기 쉬운 표현

반환 형식:
{
    "title_ko": "한국어 제목 (10-20글자)",
    "summary_short": "한 문장 요약 (30-50글자)",
    "summary_long": "3-5문장 요약",
    "key_points": ["핵심1", "핵심2", "핵심3"],
    "hashtags": ["#태그1", "#태그2", "#태그3"],
    "importance": 1-5,
    "sentiment": "positive" or "negative" or "neutral"
}"""

    prompt = f"""다음 뉴스 기사를 한국어로 요약하세요:

제목: {article['title']}
설명: {article['description']}
내용: {article['content']}

요약 형식: {"짧음 (1문장)" if summary_type == "short" else "길음 (3-5문장)"}

JSON으로 반환하세요."""

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
                "temperature": 0.5,  # 뉴스는 낮은 temperature (더 객관적)
                "max_tokens": 500,
            },
            timeout=30,
        )

        response.raise_for_status()
        result = response.json()

        content = result["choices"][0]["message"]["content"]

        # JSON 파싱
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        summary = json.loads(content.strip())

        # 메타데이터 추가
        summary["generated_at"] = datetime.now().isoformat()
        summary["duration_short"] = 30  # 30초
        summary["duration_long"] = 180  # 3분
        summary["original_url"] = article["url"]
        summary["original_source"] = article["source"]

        return summary

    except Exception as e:
        print(f"❌ Groq API 에러: {e}", file=sys.stderr)
        # Fallback: 간단한 요약 생성
        return {
            "title_ko": article["title"],
            "summary_short": article["description"][:50],
            "summary_long": article["description"],
            "key_points": [],
            "hashtags": ["#뉴스"],
            "importance": 3,
            "sentiment": "neutral",
            "generated_at": datetime.now().isoformat(),
            "duration_short": 30,
            "duration_long": 180,
            "original_url": article["url"],
            "original_source": article["source"],
        }


def main():
    """메인 프로세스"""
    # 표준입력에서 뉴스 JSON 받기
    news_json = sys.stdin.read()
    news_data = json.loads(news_json)

    articles = news_data["articles"]
    summaries = []

    for article in articles:
        print(f"📝 요약 생성: {article['title'][:50]}...")

        # 긴 요약 생성 (비디오용)
        summary = generate_summary(article, summary_type="long")
        summaries.append(summary)

    result = {
        "date": news_data["date"],
        "category": news_data["category"],
        "total_summaries": len(summaries),
        "summaries": summaries,
    }

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
