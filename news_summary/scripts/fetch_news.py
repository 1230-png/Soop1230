#!/usr/bin/env python3
"""
NewsAPI에서 실시간 뉴스 수집

특징:
- 특정 키워드로 최신 뉴스 검색
- 영문 기사를 한국어로 요약
- 각 뉴스의 이미지/소스 수집
"""

import json
import os
import sys
from datetime import datetime, timedelta
import requests

NEWSAPI_KEY = os.getenv("NEWSAPI_KEY", "your_key")
NEWSAPI_URL = "https://newsapi.org/v2/everything"

# 니치별 검색 키워드
NEWS_CATEGORIES = {
    "ai": {
        "keywords": "artificial intelligence OR AI OR machine learning OR GPT OR Claude OR LLaMA",
        "sources": "techcrunch,theverge,arstechnica",
        "language": "en",
        "description": "AI & Machine Learning News",
    },
    "crypto": {
        "keywords": "cryptocurrency OR bitcoin OR ethereum OR web3 OR blockchain",
        "sources": "coindesk,cointelegraph",
        "language": "en",
        "description": "Cryptocurrency & Blockchain News",
    },
    "startup": {
        "keywords": "startup OR venture capital OR IPO OR funding OR tech company",
        "sources": "techcrunch,theinformation",
        "language": "en",
        "description": "Startup & VC News",
    },
    "tech": {
        "keywords": "technology OR software OR hardware OR tech",
        "sources": "techcrunch,theverge,wired",
        "language": "en",
        "description": "Technology News",
    },
}


def fetch_news(category: str = "ai", num_articles: int = 5) -> list:
    """
    뉴스 수집

    Args:
        category: 'ai', 'crypto', 'startup', 'tech'
        num_articles: 수집할 기사 수

    Returns:
        [{
            "title": "제목",
            "description": "설명",
            "content": "전체 내용",
            "source": "소스",
            "url": "링크",
            "image": "이미지 URL",
            "published_at": "ISO 8601",
            "category": "카테고리"
        }, ...]
    """

    if category not in NEWS_CATEGORIES:
        print(f"❌ 알 수 없는 카테고리: {category}", file=sys.stderr)
        sys.exit(1)

    cat_config = NEWS_CATEGORIES[category]

    params = {
        "q": cat_config["keywords"],
        "apiKey": NEWSAPI_KEY,
        "language": cat_config["language"],
        "sortBy": "publishedAt",
        "pageSize": num_articles,
        # 최근 7일만
        "from": (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d"),
    }

    try:
        response = requests.get(NEWSAPI_URL, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        if data["status"] != "ok":
            print(f"❌ NewsAPI 에러: {data.get('message', 'Unknown error')}", file=sys.stderr)
            sys.exit(1)

        articles = []
        for article in data["articles"][:num_articles]:
            articles.append(
                {
                    "title": article.get("title", "No title"),
                    "description": article.get("description", ""),
                    "content": article.get("content", "")[:500],  # 처음 500글자만
                    "source": article.get("source", {}).get("name", "Unknown"),
                    "url": article.get("url", ""),
                    "image": article.get("urlToImage", ""),
                    "published_at": article.get("publishedAt", ""),
                    "category": category,
                }
            )

        print(f"✅ {len(articles)}개 뉴스 수집: {category}")
        return articles

    except Exception as e:
        print(f"❌ NewsAPI 에러: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    """메인 프로세스"""
    category = sys.argv[1] if len(sys.argv) > 1 else "ai"
    num_articles = int(sys.argv[2]) if len(sys.argv) > 2 else 5

    articles = fetch_news(category, num_articles)

    result = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "category": category,
        "total_articles": len(articles),
        "articles": articles,
    }

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
