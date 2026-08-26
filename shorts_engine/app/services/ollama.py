"""Ollama(로컬 Llama 3) 호출과 프롬프트 조립.

두 가지가 핵심이다.

1. **동적 제외 주입** — 실적이 나쁜 주제를 프롬프트에 명시적으로 배제한다.
2. **출력을 믿지 않는다** — format:"json" 을 줘도 로컬 모델은 깨진 JSON,
   누락 필드, 코드펜스로 감싼 응답을 흔히 낸다. Pydantic으로 검증하고
   실패하면 재시도한다. 검증 없이 DB에 넣으면 렌더링 단계에서 터진다.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re

import httpx
from pydantic import BaseModel, Field, ValidationError, field_validator

from app.config import get_settings
from app.services.feedback import FailingTopic

logger = logging.getLogger(__name__)

# 모델이 ```json ... ``` 으로 감싸는 경우가 잦다.
_FENCE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.MULTILINE)


class GeneratedScript(BaseModel):
    """Ollama 출력의 계약. 여기를 통과하지 못하면 DB에 들어가지 않는다."""

    title: str = Field(min_length=2, max_length=100)
    hook: str = Field(min_length=2, max_length=200)
    body: list[str] = Field(min_length=2, max_length=6)
    cta_question: str = Field(min_length=2, max_length=200)
    image_query: str = Field(min_length=2, max_length=100)

    @field_validator("body")
    @classmethod
    def _sentences_are_renderable(cls, v: list[str]) -> list[str]:
        # 한 화면에 안 들어가는 문장이 오면 자막이 넘친다.
        for s in v:
            if not s.strip():
                raise ValueError("빈 문장이 포함돼 있습니다")
            if len(s) > 120:
                raise ValueError(f"문장이 너무 깁니다({len(s)}자). 120자 이하로 쓰세요.")
        return [s.strip() for s in v]

    @field_validator("image_query")
    @classmethod
    def _query_is_ascii(cls, v: str) -> str:
        # Pexels는 영어 검색어에서 결과가 훨씬 낫다.
        if not v.isascii():
            raise ValueError("image_query는 영어로 작성해야 합니다")
        return v.strip()

    def content_hash(self) -> str:
        """같은 대본이 반복 생성되는 것을 막기 위한 지문."""
        payload = json.dumps(
            {"title": self.title, "hook": self.hook, "body": self.body},
            ensure_ascii=False,
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


_SYSTEM = """당신은 한국어 유튜브 쇼츠 대본 작가다.
'현실 속 기괴한 현상'을 다루는 채널이며, 시청자가 끝까지 보고 댓글을 남기게 만드는 것이 목표다."""

_SCHEMA_BLOCK = """반드시 아래 JSON 스키마로만 답하라. 설명이나 인사말을 덧붙이지 마라.
{
  "title": "영상 제목 (30자 이내)",
  "hook": "첫 3초에 화면에 뜰 한 문장. 질문이나 의외의 사실로 시선을 잡을 것",
  "body": ["본문 문장", "..."],
  "cta_question": "시청자가 댓글로 답하고 싶어지는 마무리 질문",
  "image_query": "배경 사진을 찾을 영어 검색어"
}"""

_RULES = """[작성 규칙]
- body는 3~4문장. 각 문장은 120자 이내로, 한 화면에 들어가야 한다.
- 확정되지 않은 사실을 단정하지 마라. 가설이면 "~라는 설명이 있습니다"처럼 남겨라.
- cta_question은 반드시 시청자 경험을 묻는 질문으로 끝내라.
  ("여러분도 겪어본 적 있나요?" 같은 형태)
- image_query는 영어로, 저작권 캐릭터나 인물명을 넣지 마라."""


def build_prompt(
    topic_label: str, failing_topics: list[FailingTopic]
) -> tuple[str, list[str]]:
    """프롬프트와 실제로 제외한 주제 목록을 함께 돌려준다.

    제외 목록을 반환하는 이유: DB에 남겨 두면 나중에 "이 대본은 무엇을
    피하려고 만들어졌나"를 추적할 수 있다.
    """
    parts = [_SYSTEM, "", _SCHEMA_BLOCK, ""]

    excluded = [t.label_ko for t in failing_topics]
    if excluded:
        # 요구사항의 핵심 문장. 실패한 주제가 있을 때만 주입한다.
        joined = ", ".join(excluded)
        detail = ", ".join(
            f"{t.label_ko}(좋아요 {t.avg_like_ratio * 100:.2f}%, {t.sample_size}편)"
            for t in failing_topics
        )
        parts += [
            f"[제외 조건]\n다음 주제는 시청자 반응이 안 좋았으므로 절대 제외할 것: {joined}",
            f"(근거: {detail})",
            "",
        ]

    parts += [f"[이번 주제]\n{topic_label} 범주에서 새로운 소재를 하나 고른다.", "", _RULES]
    return "\n".join(parts), excluded


def _extract_json(raw: str) -> dict:
    """모델 응답에서 JSON 객체를 꺼낸다.

    코드펜스로 감싸거나 앞뒤에 말을 붙이는 경우를 모두 처리한다.
    """
    cleaned = _FENCE.sub("", raw).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # 앞뒤에 설명이 붙은 경우: 가장 바깥 중괄호 쌍을 찾는다.
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("응답에서 JSON 객체를 찾지 못했습니다")
    return json.loads(cleaned[start : end + 1])


async def generate_script(
    topic_label: str,
    failing_topics: list[FailingTopic],
    client: httpx.AsyncClient | None = None,
) -> tuple[GeneratedScript, str, list[str]]:
    """Ollama를 호출해 검증된 대본을 얻는다.

    Returns:
        (검증된 대본, 사용한 프롬프트, 제외한 주제 목록)

    Raises:
        RuntimeError: 재시도를 모두 소진하도록 유효한 JSON을 얻지 못한 경우.
    """
    s = get_settings()
    prompt, excluded = build_prompt(topic_label, failing_topics)

    owns_client = client is None
    client = client or httpx.AsyncClient(timeout=s.ollama_timeout_sec)

    errors: list[str] = []
    try:
        for attempt in range(1, s.ollama_max_attempts + 1):
            try:
                resp = await client.post(
                    f"{s.ollama_host}/api/generate",
                    json={
                        "model": s.ollama_model,
                        "prompt": prompt,
                        "stream": False,
                        "format": "json",
                        # 재시도마다 다른 결과가 나와야 의미가 있다.
                        "options": {"temperature": 0.8 if attempt == 1 else 1.0},
                    },
                )
                resp.raise_for_status()
                raw = resp.json().get("response", "")
                return GeneratedScript.model_validate(_extract_json(raw)), prompt, excluded

            except (ValidationError, ValueError, json.JSONDecodeError) as exc:
                # 모델 출력 문제 — 재시도할 가치가 있다.
                errors.append(f"{attempt}회차: {exc}")
                logger.warning("Ollama 응답 검증 실패 (%d/%d): %s",
                               attempt, s.ollama_max_attempts, exc)
            except httpx.HTTPError as exc:
                # 네트워크/서버 문제 — Ollama가 안 떠 있으면 재시도해도 소용없다.
                raise RuntimeError(
                    f"Ollama에 연결하지 못했습니다 ({s.ollama_host}). "
                    "`ollama serve`가 실행 중인지 확인하세요."
                ) from exc
    finally:
        if owns_client:
            await client.aclose()

    raise RuntimeError(
        f"{s.ollama_max_attempts}회 시도했지만 유효한 대본을 얻지 못했습니다:\n"
        + "\n".join(errors)
    )
