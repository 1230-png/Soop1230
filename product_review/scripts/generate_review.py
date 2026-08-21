#!/usr/bin/env python3
"""
Groq API를 사용한 제품 리뷰 자동 생성

특징:
- 제품 사양 기반 리뷰 생성
- 장단점 분석
- 가격대 평가
- 추천 대상 명확화
"""

import json
import os
import sys
from datetime import datetime
import requests

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "your_key")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"


def generate_review(product: dict) -> dict:
    """
    제품 리뷰 생성

    Args:
        product: 제품 정보 dict

    Returns:
        {
            "title": "리뷰 제목",
            "summary_short": "한 문장 요약",
            "pros": ["장점1", "장점2"],
            "cons": ["단점1", "단점2"],
            "rating": 4.5,
            "verdict": "최종 평가",
            "recommended_for": ["추천 대상1", "추천 대상2"],
            "price_verdict": "가성비 평가",
            "affiliate_tip": "제휴 팁"
        }
    """

    system_message = """당신은 전문 제품 리뷰어입니다.

다음 요구사항을 만족하는 리뷰를 작성하세요:

1. 객관적이고 균형잡힌 평가
2. 장단점 명확히
3. 가격대 고려
4. 추천 대상 명시
5. 실용적인 조언

반환 형식:
{
    "title": "매력적인 제목",
    "summary_short": "한 문장 요약",
    "pros": ["장점1", "장점2", "장점3"],
    "cons": ["단점1", "단점2"],
    "rating": 4.5,
    "verdict": "최종 평가 (2-3문장)",
    "recommended_for": ["사용자그룹1", "사용자그룹2"],
    "price_verdict": "가성비 평가",
    "affiliate_tip": "구매 팁"
}"""

    specs = product.get('specs', [])
    if isinstance(specs, str):
        try:
            specs = json.loads(specs)
        except:
            specs = [specs] if specs else []
    specs_text = ", ".join(specs) if isinstance(specs, list) else str(specs)
    prompt = f"""다음 제품에 대한 상세 리뷰를 작성하세요:

제품명: {product['name']}
카테고리: {product['category']}
가격: {int(product.get('price', 0)):,}원
주요 기능: {specs_text}
기본 설명: {product['description']}
현재 별점: {product.get('rating', 4.0)}/5

이 리뷰는 유튜브 영상용입니다.
객관적이고 신뢰할 수 있는 리뷰를 작성하세요.

JSON으로 반환하세요."""

    # Groq API 사용 (API 키가 없으면 fallback 사용)
    if GROQ_API_KEY and GROQ_API_KEY != "your_key":
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
                    "temperature": 0.7,
                    "max_tokens": 800,
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

            review = json.loads(content.strip())

            # 메타데이터 추가
            review["product_name"] = product["name"]
            review["product_price"] = product["price"]
            review["generated_at"] = datetime.now().isoformat()

            return review

        except Exception as e:
            print(f"⚠️ Groq API 에러: {e}, fallback 사용", file=sys.stderr)
    else:
        print(f"⚠️ Groq API 키 없음, fallback 리뷰 사용", file=sys.stderr)

    # Fallback
        return {
            "title": f"{product['name']} 리뷰",
            "summary_short": product["description"],
            "pros": product.get("specs", ["좋은 기능"])[:3],
            "cons": ["더 알아봐야 함"],
            "rating": 4.0,
            "verdict": "좋은 제품입니다.",
            "recommended_for": ["일반 사용자"],
            "price_verdict": "합리적인 가격",
            "affiliate_tip": "링크를 통해 구매하세요",
            "product_name": product["name"],
            "product_price": product["price"],
            "generated_at": datetime.now().isoformat(),
        }


def main():
    """메인 프로세스"""
    # 표준입력에서 제품 JSON 받기
    products_json = sys.stdin.read()
    products_data = json.loads(products_json)

    products = products_data["products"]
    reviews = []

    for product in products:
        print(f"✍️ 리뷰 생성: {product['name'][:40]}...", file=sys.stderr)

        review = generate_review(product)

        # 제품 정보와 리뷰 결합
        review["product_id"] = product.get("id", "")
        review["amazon_affiliate_link"] = product.get("amazon_affiliate_link", "")
        review["coupang_affiliate_link"] = product.get("coupang_affiliate_link", "")
        review["image_url"] = product.get("image_url", "")

        reviews.append(review)

    result = {
        "date": products_data["date"],
        "category": products_data["category"],
        "total_reviews": len(reviews),
        "reviews": reviews,
    }

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
