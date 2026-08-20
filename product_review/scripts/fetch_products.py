#!/usr/bin/env python3
"""
제품 리뷰용 신상품 수집

특징:
- 여러 소스에서 상품 정보 수집
- 아마존/쿠팡 제휴 링크 자동 생성
- 카테고리별 상품 분류
"""

import json
import os
import sys
from datetime import datetime
import csv
from pathlib import Path

# API 키 (필요시)
AMAZON_AFFILIATE_ID = os.getenv("AMAZON_AFFILIATE_ID", "")
COUPANG_AFFILIATE_ID = os.getenv("COUPANG_AFFILIATE_ID", "")

DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)

# 샘플 상품 데이터 (초기 구동용)
SAMPLE_PRODUCTS = [
    {
        "id": "PROD_001",
        "name": "AI 기반 스마트 스피커 Pro",
        "category": "electronics",
        "price": 150000,
        "amazon_link": "https://amazon.com/dp/B0XXXXX",
        "coupang_link": "https://coupang.com/vp/products/XXXXX",
        "description": "음성 인식 기능과 AI 비서 기능을 갖춘 최신형 스마트 스피커",
        "image_url": "https://via.placeholder.com/400x300?text=Smart+Speaker",
        "specs": ["음성 제어", "AI 비서", "고급 음질", "스마트홈 연동"],
    },
    {
        "id": "PROD_002",
        "name": "초고속 USB-C 충전기 65W",
        "category": "electronics",
        "price": 45000,
        "amazon_link": "https://amazon.com/dp/B0YYYYY",
        "coupang_link": "https://coupang.com/vp/products/YYYYY",
        "description": "최대 65W 고속 충전 지원, 최신 전자기기 호환",
        "image_url": "https://via.placeholder.com/400x300?text=USB-C+Charger",
        "specs": ["65W 고속 충전", "4개 포트", "안전 인증", "보증 2년"],
    },
    {
        "id": "PROD_003",
        "name": "무선 노이즈 캔슬링 헤드폰",
        "category": "electronics",
        "price": 250000,
        "amazon_link": "https://amazon.com/dp/B0ZZZZZ",
        "coupang_link": "https://coupang.com/vp/products/ZZZZZ",
        "description": "ANC 기술로 완벽한 소음 차단, 30시간 배터리",
        "image_url": "https://via.placeholder.com/400x300?text=Headphones",
        "specs": ["노이즈 캔슬링", "30시간 배터리", "Bluetooth 5.3", "편안한 착용감"],
    },
]


def load_products_from_csv(category: str = "electronics") -> list:
    """
    CSV 파일에서 제품 정보 로드
    초기에는 샘플 데이터 사용
    """
    csv_path = DATA_DIR / f"products_{category}.csv"

    # CSV 파일이 없으면 샘플 데이터 사용
    if not csv_path.exists():
        print(f"📝 CSV 파일 없음, 샘플 데이터 사용: {category}", file=sys.stderr)
        return [p for p in SAMPLE_PRODUCTS if p["category"] == category]

    products = []
    try:
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                products.append(row)
        print(f"✅ {len(products)}개 제품 로드: {csv_path}", file=sys.stderr)
        return products
    except Exception as e:
        print(f"⚠️ CSV 로드 실패: {e}, 샘플 사용", file=sys.stderr)
        return [p for p in SAMPLE_PRODUCTS if p["category"] == category]


def create_affiliate_link(product: dict, platform: str = "amazon") -> str:
    """
    제휴 링크 생성 (자동 수익 추적)
    """
    if platform == "amazon":
        base_url = product.get("amazon_link", "")
        if AMAZON_AFFILIATE_ID and "?" not in base_url:
            return f"{base_url}?tag={AMAZON_AFFILIATE_ID}"
        return base_url
    elif platform == "coupang":
        base_url = product.get("coupang_link", "")
        if COUPANG_AFFILIATE_ID and "?" not in base_url:
            return f"{base_url}?sourceType=srp&partnerType=affiliate&affiliateId={COUPANG_AFFILIATE_ID}"
        return base_url
    return ""


def fetch_products(category: str = "electronics", num_products: int = 3) -> list:
    """
    카테고리별 제품 수집

    Args:
        category: 'electronics', 'home', 'fashion', 'health'
        num_products: 수집할 제품 수

    Returns:
        [{
            "id": "상품ID",
            "name": "상품명",
            "price": 가격,
            "description": "설명",
            "amazon_affiliate_link": "아마존 제휴 링크",
            "coupang_affiliate_link": "쿠팡 제휴 링크",
            "image_url": "이미지 URL",
            "specs": ["기능1", "기능2"],
            "rating": 4.5,  # 별점
            "fetch_date": "ISO 8601"
        }, ...]
    """

    products = load_products_from_csv(category)

    selected = products[:num_products]

    for product in selected:
        # 제휴 링크 추가
        product["amazon_affiliate_link"] = create_affiliate_link(product, "amazon")
        product["coupang_affiliate_link"] = create_affiliate_link(product, "coupang")
        product["fetch_date"] = datetime.now().isoformat()
        product["rating"] = product.get("rating", 4.5)  # 기본 별점

    return selected


def main():
    """메인 프로세스"""
    category = sys.argv[1] if len(sys.argv) > 1 else "electronics"
    num_products = int(sys.argv[2]) if len(sys.argv) > 2 else 3

    products = fetch_products(category, num_products)

    result = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "category": category,
        "total_products": len(products),
        "products": products,
    }

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
