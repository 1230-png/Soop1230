"""프롬프트 조립과 Ollama 응답 검증 테스트.

Ollama 서버 없이 돈다. 로컬 LLM이 실제로 내놓는 지저분한 출력을 재현해,
검증층이 그걸 걸러내는지 확인한다.
"""

import pytest
from pydantic import ValidationError

from app.services.feedback import FailingTopic
from app.services.ollama import GeneratedScript, _extract_json, build_prompt

VALID = {
    "title": "시계 초침이 멈춰 보이는 이유",
    "hook": "시계를 봤는데 초침이 멈춰 있었던 적 있나요?",
    "body": ["고개를 돌려 시계를 본 순간, 초침이 오래 멈춰 있는 것처럼 느껴집니다.",
             "크로노스타시스라는 이름이 붙은 실제 현상입니다.",
             "눈이 움직이는 동안의 빈 시간을 뇌가 메웁니다."],
    "cta_question": "여러분도 이런 순간을 겪어본 적 있나요?",
    "image_query": "clock face macro dark",
}


class TestPromptInjection:
    def test_실패_주제가_없으면_제외_조건을_넣지_않는다(self):
        prompt, excluded = build_prompt("지각 현상", [])
        assert "제외 조건" not in prompt
        assert excluded == []

    def test_실패_주제를_프롬프트에_명시한다(self):
        failing = [
            FailingTopic("mandela", "만델라 효과", 4, 0.004, 31.2),
            FailingTopic("legend", "도시전설", 3, 0.007, None),
        ]
        prompt, excluded = build_prompt("지각 현상", failing)

        assert "다음 주제는 시청자 반응이 안 좋았으므로 절대 제외할 것" in prompt
        assert "만델라 효과" in prompt
        assert "도시전설" in prompt
        assert excluded == ["만델라 효과", "도시전설"]

    def test_판정_근거를_함께_넣는다(self):
        prompt, _ = build_prompt("지각 현상", [FailingTopic("m", "만델라 효과", 4, 0.004, None)])
        assert "0.40%" in prompt, "왜 제외됐는지 수치가 있어야 모델이 강하게 따른다"
        assert "4편" in prompt

    def test_댓글_유도_지시가_항상_들어간다(self):
        prompt, _ = build_prompt("지각 현상", [])
        assert "cta_question" in prompt
        assert "댓글" in prompt

    def test_이번_주제가_프롬프트에_들어간다(self):
        prompt, _ = build_prompt("미해결 현상", [])
        assert "미해결 현상" in prompt


class TestResponseParsing:
    def test_순수_JSON(self):
        assert _extract_json('{"a": 1}') == {"a": 1}

    def test_코드펜스로_감싼_응답(self):
        # 로컬 모델이 가장 흔하게 내는 형태
        assert _extract_json('```json\n{"a": 1}\n```') == {"a": 1}
        assert _extract_json('```\n{"a": 1}\n```') == {"a": 1}

    def test_앞뒤에_설명이_붙은_응답(self):
        raw = '물론이죠! 아래는 요청하신 대본입니다:\n{"a": 1}\n도움이 되었길 바랍니다.'
        assert _extract_json(raw) == {"a": 1}

    def test_중첩_객체를_잘라먹지_않는다(self):
        raw = 'here:\n{"a": {"b": [1, 2]}}\nend'
        assert _extract_json(raw) == {"a": {"b": [1, 2]}}

    @pytest.mark.parametrize("raw", ["", "JSON 없음", "{{{", "```json\n```"])
    def test_JSON이_없으면_거부한다(self, raw):
        with pytest.raises((ValueError, Exception)):
            _extract_json(raw)


class TestScriptValidation:
    def test_정상_응답은_통과(self):
        s = GeneratedScript.model_validate(VALID)
        assert len(s.body) == 3

    def test_필드가_빠지면_거부(self):
        for missing in VALID:
            payload = {k: v for k, v in VALID.items() if k != missing}
            with pytest.raises(ValidationError):
                GeneratedScript.model_validate(payload)

    def test_자막에_안_들어가는_긴_문장은_거부(self):
        payload = {**VALID, "body": ["가" * 121, "정상 문장입니다."]}
        with pytest.raises(ValidationError, match="너무 깁니다"):
            GeneratedScript.model_validate(payload)

    def test_빈_문장은_거부(self):
        payload = {**VALID, "body": ["정상 문장입니다.", "   "]}
        with pytest.raises(ValidationError, match="빈 문장"):
            GeneratedScript.model_validate(payload)

    def test_한글_검색어는_거부(self):
        # Pexels는 한글 검색에서 결과가 거의 없다
        payload = {**VALID, "image_query": "어두운 시계"}
        with pytest.raises(ValidationError, match="영어"):
            GeneratedScript.model_validate(payload)

    def test_본문이_한_문장뿐이면_거부(self):
        payload = {**VALID, "body": ["한 문장뿐입니다."]}
        with pytest.raises(ValidationError):
            GeneratedScript.model_validate(payload)

    def test_문장_앞뒤_공백은_정리한다(self):
        payload = {**VALID, "body": ["  앞뒤 공백  ", "두 번째 문장."]}
        assert GeneratedScript.model_validate(payload).body[0] == "앞뒤 공백"


class TestContentHash:
    def test_같은_내용은_같은_지문(self):
        assert (
            GeneratedScript.model_validate(VALID).content_hash()
            == GeneratedScript.model_validate(dict(VALID)).content_hash()
        )

    def test_본문이_다르면_다른_지문(self):
        other = {**VALID, "body": [*VALID["body"][:2], "다른 마지막 문장입니다."]}
        assert (
            GeneratedScript.model_validate(VALID).content_hash()
            != GeneratedScript.model_validate(other).content_hash()
        )

    def test_검색어만_달라도_같은_대본으로_본다(self):
        # 배경 사진이 다르다고 다른 영상은 아니다
        other = {**VALID, "image_query": "different query here"}
        assert (
            GeneratedScript.model_validate(VALID).content_hash()
            == GeneratedScript.model_validate(other).content_hash()
        )
