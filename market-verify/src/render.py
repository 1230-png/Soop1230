"""장면을 화면으로 그리고 ffmpeg 로 영상을 조립한다.

수치를 다루는 채널이라 화면은 건조하게 간다. 자극적인 연출을 넣지 않는 것이
채널 원칙이고, 그건 그대로다.

다만 **어두운 그라데이션 위에 정중앙 큰 글씨**는 자동 생성 영상의 전형이라,
사람이 만든 것으로 보이지 않는다. 그래서 인쇄물 쪽으로 옮겼다 — 미색 종이,
결이 약간 있는 바탕, 왼쪽 정렬, 가는 괘선. 연출을 더한 것이 아니라
'기계가 찍어낸 티'를 뺀 것이다.
"""

import subprocess
import textwrap
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont

WIDTH, HEIGHT = 1920, 1080
THUMB_WIDTH, THUMB_HEIGHT = 1280, 720
# 숏폼(세로) 컷용. 롱폼과 같은 그리기 함수를 재사용하려고 크기만 인자로 뺐다.
SHORT_WIDTH, SHORT_HEIGHT = 1080, 1920

# 종이. 순백은 화면에서 눈을 때려서 미색으로 낮춘다.
PAPER = (250, 247, 241)
INK = (26, 25, 22)
MUTED = (140, 134, 121)
RULE = (203, 197, 183)
GRAIN = 6  # 종이 결. 0 이면 완전 평면이라 다시 인쇄물 느낌이 사라진다.
GRAIN_MIX = 0.07  # 더 올리면 종이가 탁해진다.
# 본문 크기는 가로폭에 비례시키되, 세로(숏폼)는 폰에서 보므로 훨씬 키운다.
BODY_RATIO_LANDSCAPE = 0.040
BODY_RATIO_PORTRAIT = 0.092

FONT_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    "C:/Windows/Fonts/malgunbd.ttf",
    "C:/Windows/Fonts/malgun.ttf",
]


def find_korean_font():
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            return path
    raise SystemExit(
        "한글 폰트를 찾지 못했다. 설치할 것:\n"
        "  Ubuntu: sudo apt-get install -y fonts-noto-cjk\n"
        "  Windows: 맑은 고딕이 기본 설치돼 있다. 경로를 확인할 것."
    )


def _font(size):
    return ImageFont.truetype(find_korean_font(), size)


def _paper(width, height):
    """미색 바탕에 결을 약간 얹는다. 완전한 평면은 화면에서 인쇄물로 안 읽힌다."""
    image = Image.new("RGB", (width, height), PAPER)
    if GRAIN:
        noise = Image.effect_noise((width, height), GRAIN).convert("RGB")
        # 결을 더하되 밝기는 유지한다. multiply 로 섞으면 종이가 회색으로 죽는다.
        image = ImageChops.blend(image, ImageChops.overlay(image, noise), GRAIN_MIX)
    return image


def _draw_block(draw, text, font, top, left, color, wrap, gap):
    """왼쪽 정렬로 여러 줄을 그리고 마지막 y 를 돌려준다.

    가운데 정렬은 자동 생성 영상의 전형이라 왼쪽으로 옮겼다.
    """
    y = top
    for line in textwrap.fill(text, width=wrap).split("\n"):
        draw.text((left, y), line, font=font, fill=color)
        box = draw.textbbox((0, 0), line, font=font)
        y += (box[3] - box[1]) + gap
    return y


def slide(screen_text, section, out_path, source_note=None, width=WIDTH, height=HEIGHT):
    """장면 한 컷. 화면 문구가 주인공이고 섹션 이름은 작게 남긴다.

    width/height 를 바꾸면 그대로 세로(숏폼) 캔버스가 된다 — 그리기 로직은
    가로·세로가 같아서 따로 만들지 않았다.
    """
    portrait = height > width
    image = _paper(width, height)
    draw = ImageDraw.Draw(image)

    margin = int(width * 0.085)
    body_size = int(width * (BODY_RATIO_PORTRAIT if portrait else BODY_RATIO_LANDSCAPE))
    small = max(18, int(body_size * 0.40))
    hairline = max(1, round(width / 960))

    # 머리말: 섹션 이름과 그 아래 가는 괘선. 인쇄물의 난외주 자리다.
    head_y = int(height * (0.07 if portrait else 0.11))
    draw.text((margin, head_y), section, font=_font(small), fill=MUTED)
    rule_y = head_y + int(small * 1.9)
    draw.line([(margin, rule_y), (width - margin, rule_y)], fill=RULE, width=hairline)

    # 본문: 왼쪽 정렬. 한가운데보다 조금 위가 눈에 편하다(시각 중심).
    wrap = 11 if portrait else 17
    body = _font(body_size)
    line_gap = int(body_size * 0.42)
    lines = len(textwrap.fill(screen_text, width=wrap).split("\n"))
    block_height = lines * (body_size + line_gap)
    top = max(rule_y + body_size, (height - block_height) / 2 - height * 0.04)
    _draw_block(draw, screen_text, body, top, margin, INK, wrap, line_gap)

    # 꼬리말: 아래 괘선 하나로 판을 닫는다. 없으면 글자가 허공에 뜬다.
    foot_y = height - int(height * (0.06 if portrait else 0.11))
    draw.line([(margin, foot_y), (width - margin, foot_y)], fill=RULE, width=hairline)
    if source_note:
        draw.text((margin, foot_y + int(small * 0.7)), source_note,
                  font=_font(small), fill=MUTED)
    image.save(out_path)
    return out_path


def thumbnail(title, out_path, subtitle=None):
    image = _paper(THUMB_WIDTH, THUMB_HEIGHT)
    draw = ImageDraw.Draw(image)

    margin = int(THUMB_WIDTH * 0.085)
    body = _font(78)
    line_gap = 26
    lines = len(textwrap.fill(title, width=13).split("\n"))
    top = (THUMB_HEIGHT - lines * (body.size + line_gap)) / 2 - 20
    end = _draw_block(draw, title, body, top, margin, INK, 13, line_gap)

    if subtitle:
        rule_y = end + 26
        draw.line([(margin, rule_y), (margin + 150, rule_y)], fill=INK, width=4)
        _draw_block(draw, subtitle, _font(34), rule_y + 24, margin, MUTED, 30, 10)
    image.save(out_path)
    return out_path


def audio_duration(path):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(path)],
        check=True, capture_output=True, text=True,
    )
    return float(result.stdout.strip())


def mux(image_path, audio_path, out_path):
    """정지 화면 + 음성 → 영상 한 토막."""
    subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
         "-loop", "1", "-i", str(image_path),
         "-i", str(audio_path),
         "-c:v", "libx264", "-tune", "stillimage", "-pix_fmt", "yuv420p",
         "-r", "30", "-c:a", "aac", "-b:a", "192k",
         "-shortest", str(out_path)],
        check=True, capture_output=True,
    )
    return out_path


def concat(parts, out_path, workdir):
    """토막들을 하나로 잇는다."""
    listing = Path(workdir) / "parts.txt"
    listing.write_text(
        "".join(f"file '{Path(p).resolve().as_posix()}'\n" for p in parts), encoding="utf-8"
    )
    subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
         "-f", "concat", "-safe", "0", "-i", str(listing),
         "-c", "copy", str(out_path)],
        check=True, capture_output=True,
    )
    listing.unlink(missing_ok=True)
    return out_path
