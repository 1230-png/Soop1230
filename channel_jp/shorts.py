"""쇼츠 한 편을 만든다: 문장 하나 → 세로 카드 → 일본어·뜻·느리게·다시.

    python3 channel_jp/shorts.py [--offline]

결과는 `channel_jp/build/<날짜>-shorts-<문장ID>/` 에 video.mp4 · metadata.json
으로 떨어지고, 올리는 것은 롱폼과 같은 `upload.py --dir` 이다.

**쇼츠는 시청 시간을 벌지 않는다.** 파트너 프로그램 3,000시간에 안 들어간다
(README 「왜 롱폼이고」). 여기서 쇼츠가 하는 일은 **구독자를 데려오는 것**
하나다 — 구독자 1,000명도 같은 문턱이고, 들어온 사람은 롱폼을 본다. 그래서
설명란이 롱폼 재생목록을 가리킨다. 쇼츠 조회수가 늘었다고 수익화가 가까워진
것으로 읽지 말 것.

문장 고르기·검사·합성·인코딩은 전부 `build.py` 것을 그대로 쓴다. 다른 것은
화면(세로 카드)과 한 편에 문장이 하나라는 것뿐이다. 문장 사용 기록은
used.json 의 `packs.shorts` 에 따로 센다 — 롱폼에 나온 문장도 쇼츠에서는 새
것이고, 쇼츠에서 본 문장을 롱폼에서 다시 듣는 것이 이 구성의 요점이다.
"""

import argparse
import datetime
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build  # noqa: E402
from lib import cards, tts  # noqa: E402

PACK_ID = build.SHORTS_PACK
WIDTH, HEIGHT = 1080, 1920
FPS = 30

# 일본어 → 뜻 → 느리게 → 다시. 두 번째 일본어가 느린 이유는 한글 읽기를
# 눈으로 따라갈 시간을 주려는 것이고, 마지막 보통 속도는 귀에 남기려는 것이다.
# 느린 읽기는 atempo 로 만들고 반복은 캐시에서 나오므로 글자 값은 ja + ko 뿐이다.
RECIPE = [
    ("ja", "voice_ja", None),
    ("gap", 0.4, None),
    ("ko", "voice_ko", None),
    ("gap", 0.6, None),
    ("ja", "voice_ja_alt", "rate_slow"),
    ("gap", 0.6, None),
    ("ja", "voice_ja", None),
    ("gap", 1.2, None),
]

PLAYLIST_HINT = "자면서 듣는 일본어"


def render_vertical(out_path: Path, phrase: dict) -> Path:
    """세로 카드 한 장.

    쇼츠 화면은 아래 ~400px 와 오른쪽 ~140px 를 제목·버튼이 덮는다. 글은
    그 바깥, 세로 가운데보다 조금 위에 모은다.
    """
    img = Image.new("RGB", (WIDTH, HEIGHT), cards.BG)
    draw = ImageDraw.Draw(img)
    max_w = WIDTH - 240

    def block(text, size, top, fill, line_gap=16):
        font = cards._font(size)
        for line in cards._wrap(draw, text, font, max_w):
            width = draw.textlength(line, font=font)
            draw.text(((WIDTH - width) / 2, top), line, font=font, fill=fill)
            bbox = font.getbbox(line)
            top += (bbox[3] - bbox[1]) + line_gap
        return top

    y = block("귀트는 일본어", 40, 250, cards.MUTED)
    draw.line([(WIDTH / 2 - 160, y + 20), (WIDTH / 2 + 160, y + 20)],
              fill=cards.RULE, width=3)
    y = block(phrase["ja"], 80, 560, cards.BODY, line_gap=24)
    y = block(f"[{phrase['yomi']}]", 58, y + 40, cards.ACCENT)
    y = block(phrase["ko"], 64, y + 70, cards.BODY)
    block("매일 한 문장, 귀가 트입니다", 38, y + 120, cards.MUTED)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path)
    return out_path


def build_metadata(phrase: dict, duration: float, video: Path) -> dict:
    title = f"'{phrase['ko']}' 일본어로? {phrase['ja']} #shorts"
    description = "\n".join([
        f"{phrase['ja']}",
        f"[{phrase['yomi']}] {phrase['ko']}",
        "",
        "일본어 문장 → 한글 읽기 → 한국어 뜻 순서로 들려드립니다.",
        f"길게 흘려듣고 싶으시면 채널의 「{PLAYLIST_HINT}」 재생목록을 틀어 두세요.",
        "",
        "#일본어 #일본어공부 #일본어회화 #기초일본어 #귀트는일본어 #shorts",
    ])
    return {
        "pack": PACK_ID,
        "topic": phrase.get("topic", ""),
        "target_minutes": None,
        "title": title[:100],
        "description": description,
        "tags": ["일본어", "일본어공부", "일본어회화", "기초일본어", "생활일본어",
                 "일본어한마디", "귀트는일본어", "learn japanese", "shorts"],
        "categoryId": "27",
        "privacyStatus": "private",     # 워크플로가 --privacy 로 덮어쓴다
        "playlist": "",
        "duration_seconds": round(duration, 2),
        "phrase_ids": [phrase["id"]],
        "file": str(video.relative_to(build.ROOT)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="쇼츠 한 편을 만든다")
    parser.add_argument("--offline", action="store_true",
                        help="TTS 대신 무음 — 네트워크 없이 파이프라인만 검증")
    args = parser.parse_args()

    defaults = build.load_packs()["defaults"]
    engine = defaults.get("engine", "elevenlabs")
    state = build.load_used()
    phrase = build.pick_phrases(build.load_phrases(), PACK_ID, 1, state)[0]
    build.verify_phrases([phrase])      # 합성을 시작하기 전에 막는다

    date_str = datetime.date.today().isoformat()
    out_dir = build.BUILD_ROOT / f"{date_str}-shorts-{phrase['id']}"
    work = out_dir / "work"
    work.mkdir(parents=True, exist_ok=True)

    card = render_vertical(work / "card.png", phrase)
    segments = []
    for i, (kind, value, rate_key) in enumerate(RECIPE):
        if kind == "gap":
            audio = tts.make_silence(value, work / f"gap_{i}.mp3")
        else:
            rate = defaults[rate_key] if rate_key else "+0%"
            audio = tts.synthesize(phrase[kind], defaults[value], rate,
                                   offline=args.offline, engine=engine)
        segments.append({"audio": audio, "seconds": tts.duration_of(audio),
                         "card": card})

    video = build.encode(segments, out_dir, work, FPS)
    metadata = build_metadata(phrase, tts.duration_of(video), video)
    (out_dir / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")

    if args.offline:
        print("[shorts] offline 실행 — used.json 을 건드리지 않았다", file=sys.stderr)
    else:
        state.setdefault("packs", {}).setdefault(PACK_ID, {})[phrase["id"]] = date_str
        build.save_used(state)

    build.verify_publishable(metadata, 1, None)
    print(f"[shorts] {phrase['id']} {metadata['duration_seconds']}초", file=sys.stderr)
    print(out_dir)      # 표준 출력의 유일한 줄 — 워크플로가 이것을 읽는다
    return 0


if __name__ == "__main__":
    sys.exit(main())
