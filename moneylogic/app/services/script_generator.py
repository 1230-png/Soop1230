"""yfinance + OpenAI를 이용한 영상 스크립트 생성.

금융 데이터를 크롤링하고 LLM으로 분석 스크립트를 생성한다.
"""

import json
import os
from datetime import datetime, timedelta

import yfinance as yf
from openai import OpenAI

from app.config import get_settings


async def fetch_financial_data(ticker: str) -> dict:
    """yfinance로 금융 데이터를 가져온다."""
    try:
        stock = yf.Ticker(ticker)

        # 최근 1년 히스토리
        hist = stock.history(period="1y")

        # 최신 정보
        info = stock.info

        # 최근 가격 변동
        current_price = info.get("currentPrice", 0)
        prev_close = info.get("previousClose", 0)
        change_percent = ((current_price - prev_close) / prev_close * 100) if prev_close else 0

        return {
            "ticker": ticker,
            "company_name": info.get("longName", ticker),
            "current_price": round(current_price, 2),
            "change_percent": round(change_percent, 2),
            "market_cap": info.get("marketCap", "N/A"),
            "pe_ratio": round(info.get("trailingPE", 0), 2),
            "dividend_yield": round(info.get("dividendYield", 0) * 100, 2),
            "52week_high": round(info.get("fiftyTwoWeekHigh", 0), 2),
            "52week_low": round(info.get("fiftyTwoWeekLow", 0), 2),
            "avg_volume": info.get("averageVolume", 0),
            "recent_prices": hist["Close"].tail(7).to_dict(),  # 최근 7일
        }
    except Exception as e:
        raise ValueError(f"yfinance 데이터 수집 실패 ({ticker}): {str(e)}")


async def generate_script_with_openai(ticker: str, financial_data: dict) -> dict:
    """OpenAI gpt-4o-mini로 분석 스크립트를 생성한다.

    Returns:
        {
            "topic": "영상 주제",
            "segments": [
                {"keyword": "키워드", "text": "5-10초 나레이션"},
                ...
            ]
        }
    """
    settings = get_settings()

    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY 환경 변수가 설정되지 않았습니다.")

    client = OpenAI(api_key=settings.openai_api_key)

    # 프롬프트 작성
    prompt = f"""당신은 경제 유튜브 채널 '머니로직'의 스크립트 작가입니다.

[종목 정보]
- 종목코드: {ticker}
- 회사명: {financial_data['company_name']}
- 현재가: ${financial_data['current_price']}
- 변동률: {financial_data['change_percent']}%
- PER: {financial_data['pe_ratio']}
- 배당수익률: {financial_data['dividend_yield']}%
- 52주 최고가: ${financial_data['52week_high']}
- 52주 최저가: ${financial_data['52week_low']}

[작성 규칙]
1. 2-3분 분량의 쇼츠 스크립트 (각 세그먼트 5-10초)
2. **절대 금지**: 매수/매도 추천, 투자 조언
3. **필수 포함**: 객관적 재무 지표 분석, [KEY: 핵심 용어] 태그
4. 한국어, 자연스러운 톤
5. JSON 형식 반환

응답 형식:
{{
  "topic": "영상 제목 (예: 애플, 2024년 실적으로 보는 배당금 전략)",
  "segments": [
    {{"keyword": "배당수익률", "text": "애플의 배당수익률은 {financial_data['dividend_yield']}%입니다. [KEY: 배당수익률]"}},
    {{"keyword": "PER", "text": "현재 PER은 {financial_data['pe_ratio']}입니다. [KEY: PER]"}},
    ...
  ]
}}"""

    try:
        response = client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": "You are a financial education content creator. Return valid JSON only."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=settings.openai_max_tokens,  # 비용 폭탄 방지
            temperature=0.7,
        )

        content = response.choices[0].message.content

        # JSON 파싱
        result = json.loads(content)
        return result

    except json.JSONDecodeError as e:
        # Fallback 스크립트 (JSON 파싱 실패 시)
        return {
            "topic": f"{ticker} 재무 분석",
            "segments": [
                {
                    "keyword": "현재가",
                    "text": f"{ticker}의 현재 주가는 ${financial_data['current_price']}입니다. [KEY: 현재가]"
                },
                {
                    "keyword": "PER",
                    "text": f"PER은 {financial_data['pe_ratio']}로 업계 평균 대비 어떻게 평가되는지 봅시다. [KEY: PER]"
                }
            ]
        }
    except Exception as e:
        raise ValueError(f"OpenAI API 호출 실패: {str(e)}")


async def generate_complete_script(ticker: str) -> dict:
    """금융 데이터 수집 → OpenAI 스크립트 생성을 한 번에 처리한다."""
    # 1. 금융 데이터 수집
    financial_data = await fetch_financial_data(ticker)

    # 2. OpenAI 스크립트 생성
    script = await generate_script_with_openai(ticker, financial_data)

    # 3. 스크립트에 타이밍 정보 추가
    timeline = []
    current_start = 0.0

    for segment in script.get("segments", []):
        # 텍스트 길이로 대략적인 음성 길이 계산 (한글 5-6글자 ≈ 1초)
        text = segment.get("text", "")
        duration = max(len(text) / 5.5, 2.0)  # 최소 2초

        timeline.append({
            "keyword": segment.get("keyword", ""),
            "text": text,
            "start": current_start,
            "duration": duration,
        })
        current_start += duration

    return {
        "topic": script.get("topic", f"{ticker} 분석"),
        "timeline": timeline,
        "raw_script": script,
        "total_duration": current_start,
    }
