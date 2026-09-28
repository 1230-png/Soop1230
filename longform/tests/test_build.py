"""python -m pytest longform/tests — no network, no TTS, no ffmpeg."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import build  # noqa: E402


def test_description_fits_youtube_limit_with_many_chapters():
    # 수면 팩(150문장)과 3시간 팩(640문장)이 챕터 때문에 5,000바이트를 넘겨
    # 업로드에서 죽었다(이슈 #28, #29).
    pack = build.load_packs()["packs"]["weekly_100"]
    chapters = [(0.0, "인트로")] + [(10.0 + i * 20, f"I'd like to weigh in on that {i}.")
                                   for i in range(640)]
    chapters += [(20000.0, "반복 훈련 · 듣고 영어로 말하기"), (30000.0, "마무리")]
    text = build.build_description(pack, chapters, 100, "생활영어", 60)
    assert len(text.encode("utf-8")) <= build.DESCRIPTION_BUDGET
    for pinned in ("0:00 인트로", "반복 훈련", "마무리"):
        assert pinned in text


def test_weekly_titles_never_repeat_and_fit():
    pack = build.load_packs()["packs"]["weekly_100"]
    state = {"theme_cursor": {}}
    titles = []
    for week in range(len(pack["themes"]) * 3):
        state["theme_cursor"]["weekly_100"] = week
        theme = build.pick_theme("weekly_100", pack, state)
        titles.append(build.make_title(pack, 100, 62, theme["name"], theme))
    assert len(set(titles)) == len(titles)
    assert all(len(t) <= 100 for t in titles)


def test_every_phrase_has_hangul_pronunciation():
    # 제목에 「한글 발음 포함」이라고 적는다. 문장을 새로 들이면 pron.tsv 도 채울 것.
    missing = [p["id"] for p in build.load_phrases() if not p.get("pron")]
    assert not missing, missing[:10]
