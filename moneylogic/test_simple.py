"""간단한 테스트 - 스크립트 생성 검증"""

import asyncio
import sys
from pathlib import Path
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

sys.path.insert(0, str(Path(__file__).parent))

from app.config import get_settings
from app.services.script_generator import (
    fetch_financial_data,
    generate_script_with_openai,
    generate_complete_script,
)


async def test_financial_data():
    """금융 데이터 수집 테스트"""
    print("\n" + "="*60)
    print("📊 [테스트 1] 금융 데이터 수집 (yfinance)")
    print("="*60)

    try:
        ticker = "AAPL"
        data = await fetch_financial_data(ticker)

        print(f"\n✅ 데이터 수집 성공!")
        print(f"   종목: {ticker}")
        print(f"   회사명: {data['company_name']}")
        print(f"   현재가: ${data['current_price']}")
        print(f"   변동률: {data['change_percent']}%")
        print(f"   PER: {data['pe_ratio']}")
        print(f"   배당수익률: {data['dividend_yield']}%")

        return data

    except Exception as e:
        print(f"❌ 실패: {str(e)}")
        return None


async def test_script_generation():
    """LLM 스크립트 생성 테스트"""
    print("\n" + "="*60)
    print("📝 [테스트 2] LLM 스크립트 생성 (OpenAI)")
    print("="*60)

    try:
        ticker = "AAPL"
        financial_data = await fetch_financial_data(ticker)

        if not financial_data:
            print("❌ 금융 데이터가 없습니다")
            return None

        script = await generate_script_with_openai(ticker, financial_data)

        print(f"\n✅ 스크립트 생성 성공!")
        print(f"   주제: {script.get('topic', 'N/A')}")
        print(f"   세그먼트 수: {len(script.get('segments', []))}")

        if script.get('segments'):
            for i, seg in enumerate(script['segments'][:3], 1):
                print(f"   {i}. {seg.get('keyword', 'N/A')}: {seg.get('text', 'N/A')[:50]}...")

        return script

    except Exception as e:
        print(f"❌ 실패: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


async def test_complete_pipeline():
    """전체 파이프라인 (타이밍 포함)"""
    print("\n" + "="*60)
    print("🚀 [테스트 3] 전체 파이프라인")
    print("="*60)

    try:
        ticker = "AAPL"
        result = await generate_complete_script(ticker)

        print(f"\n✅ 완료!")
        print(f"   주제: {result['topic']}")
        print(f"   총 길이: {result['total_duration']:.1f}초")
        print(f"   세그먼트: {len(result['timeline'])}")

        print(f"\n📋 타임라인:")
        for seg in result['timeline']:
            print(f"   [{seg['start']:.1f}s ~ {seg['start'] + seg['duration']:.1f}s] "
                  f"{seg['keyword']}: {seg['text'][:40]}...")

        return result

    except Exception as e:
        print(f"❌ 실패: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


async def main():
    print("\n" + "█"*60)
    print("█  머니로직 테스트 (Step 2)")
    print("█"*60)

    settings = get_settings()
    print(f"\n⚙️  환경: {settings.environment}")
    print(f"   OpenAI Model: {settings.openai_model}")
    print(f"   Max Tokens: {settings.openai_max_tokens}")

    # Test 1: 금융 데이터
    financial_data = await test_financial_data()

    if financial_data:
        # Test 2: 스크립트 생성
        script = await test_script_generation()

        if script:
            # Test 3: 전체 파이프라인
            result = await test_complete_pipeline()

            if result:
                print("\n" + "█"*60)
                print("█  ✅ 모든 테스트 통과!")
                print("█"*60)
                return 0

    return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
