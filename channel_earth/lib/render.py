"""화면. `channel_sim` 과 같은 이유로 PIL 이 아니라 numpy 로 그린다.

MoviePy 를 쓰지 않은 이유도 같다. MoviePy 는 결국 ffmpeg 래퍼인데, 프레임을
직접 만들어 내는 이 작업에서는 중간 계층이 느리기만 하고 얻는 것이 없다.
여기서는 numpy 배열을 ffmpeg 표준 입력으로 흘려보낸다.

세 겹으로 나눠 그린다. 이게 이 파일의 유일한 요령이다.

1. **바탕** — 지구 사진과 눈금. 한 번 만들고 프레임마다 복사만 한다.
2. **쌓이는 층** — 이미 일어난 지진의 점. 한 번 찍으면 안 지우므로,
   새로 생긴 것만 더한다. 프레임마다 300개를 다시 그리지 않는다.
3. **퍼지는 층** — 방금 일어난 지진의 고리. 짧게 살다 사라지므로 매 프레임
   다시 그리지만, 동시에 살아 있는 것은 보통 한두 개다.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ASSETS = Path(__file__).resolve().parent.parent / "assets"
EARTH = ASSETS / "earth_equirect_1920.jpg"

BG = (7, 9, 14)
FG = (232, 238, 246)
DIM = (128, 140, 158)
GRID = (58, 70, 92)
ACCENT = (120, 190, 255)

KR_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
]
KR_BOLD_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
]
MONO_CANDIDATES = [
    "/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
]

# 깊이를 색으로. USGS 가 쓰는 관례를 따른다 — 얕을수록 붉다.
#
# 관례를 따르는 것이 취향 문제가 아닌 이유: 얕은 지진이 같은 규모라도 지표에
# 훨씬 큰 피해를 준다. 색이 깊이를 말해 주면 "규모는 작은데 왜 크게 느껴졌나"가
# 화면에서 바로 읽힌다.
DEPTH_STOPS = [
    (0.0, (255, 86, 72)),
    (35.0, (255, 158, 66)),
    (70.0, (250, 226, 90)),
    (150.0, (120, 220, 150)),
    (300.0, (96, 170, 255)),
    (700.0, (150, 130, 255)),
]


def _pick(candidates: list[str]) -> str:
    for path in candidates:
        if Path(path).exists():
            return path
    raise RuntimeError(f"글꼴을 찾지 못했다: {candidates}")


def kr_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(_pick(KR_BOLD_CANDIDATES if bold else KR_CANDIDATES), size)


def mono_font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(_pick(MONO_CANDIDATES), size)


def depth_color(depth_km: float) -> tuple[int, int, int]:
    """깊이를 색으로. 구간 사이는 선형으로 섞는다."""
    if depth_km <= DEPTH_STOPS[0][0]:
        return DEPTH_STOPS[0][1]
    for (d0, c0), (d1, c1) in zip(DEPTH_STOPS, DEPTH_STOPS[1:]):
        if depth_km <= d1:
            t = (depth_km - d0) / (d1 - d0)
            return tuple(int(a + (b - a) * t) for a, b in zip(c0, c1))
    return DEPTH_STOPS[-1][1]


@dataclass(frozen=True)
class Layout:
    """화면 크기에서 자리를 계산한다.

    세로(숏폼)와 가로(롱폼) 둘 다 만든다. 같은 자료로 두 벌을 뽑는 이유는
    **숏폼 시청 시간이 파트너 프로그램의 3,000시간에 집계되지 않기** 때문이다.
    숏폼은 도달에, 롱폼은 시청 시간에 쓴다. 렌더러가 같아 추가 비용이 없다.

    위도를 -65~80 으로 잘라 쓴다. 남극 대륙이 새하얘서 그대로 두면 화면에서
    제일 밝은 덩어리가 되는데, 정작 지진은 거의 없다. 잘라 내면 지도가 덜
    납작해져 세로 화면에서 더 크게 들어가기도 한다.
    """

    width: int
    height: int
    map_x: int
    map_y: int
    map_w: int
    map_h: int
    vertical: bool
    lat_min: float = -65.0
    lat_max: float = 80.0

    @classmethod
    def for_size(cls, width: int, height: int,
                 lat_min: float = -65.0, lat_max: float = 80.0) -> "Layout":
        vertical = height > width
        aspect = 360.0 / (lat_max - lat_min)
        if vertical:
            map_w = width
            map_h = int(round(map_w / aspect))
            # 위쪽에 제목·시계, 아래쪽에 범례·숫자·시간대 막대가 들어간다.
            return cls(width, height, 0, int(height * 0.255), map_w, map_h,
                       True, lat_min, lat_max)
        map_w = int(width * 0.72)
        map_h = int(round(map_w / aspect))
        return cls(width, height, 48, (height - map_h) // 2 + 20,
                   map_w, map_h, False, lat_min, lat_max)

    def project(self, lon: float, lat: float) -> tuple[float, float]:
        """정거원통도법. 지구 사진이 그 도법이라 계산이 이것뿐이다."""
        x = (lon + 180.0) / 360.0 * self.map_w + self.map_x
        y = ((self.lat_max - lat) / (self.lat_max - self.lat_min)
             * self.map_h + self.map_y)
        return x, y

    def on_map(self, lat: float) -> bool:
        """잘라 낸 위도 밖인가. 남극 근처 지진은 그릴 자리가 없다."""
        return self.lat_min <= lat <= self.lat_max


def base_frame(layout: Layout, *, dim: float = 0.62) -> np.ndarray:
    """지구 사진 + 눈금. 꼭지 내내 변하지 않는다.

    사진을 어둡게 까는 이유: 원본 그대로 두면 사막과 구름이 밝아서 그 위의
    붉은 점이 안 보인다. 지도는 배경이고 점이 주인공이다.
    """
    frame = np.zeros((layout.height, layout.width, 3), dtype=np.uint8)
    frame[:] = BG

    earth = Image.open(EARTH).convert("RGB")
    # 원본은 위도 -90~90 이다. 쓰는 구간만 잘라 낸 뒤 자리에 맞춘다.
    full_h = earth.height
    top = int(round((90.0 - layout.lat_max) / 180.0 * full_h))
    bottom = int(round((90.0 - layout.lat_min) / 180.0 * full_h))
    earth = earth.crop((0, top, earth.width, bottom)).resize(
        (layout.map_w, layout.map_h), Image.LANCZOS)

    band = (np.asarray(earth, dtype=np.float32) * dim).astype(np.uint8)
    frame[layout.map_y:layout.map_y + layout.map_h,
          layout.map_x:layout.map_x + layout.map_w] = band

    image = Image.fromarray(frame)
    draw = ImageDraw.Draw(image)
    for lat in (-60, -30, 0, 30, 60):
        if not layout.on_map(lat):
            continue
        _, y = layout.project(0, lat)
        draw.line([layout.map_x, y, layout.map_x + layout.map_w, y],
                  fill=GRID, width=2 if lat == 0 else 1)
    for lon in (-120, -60, 0, 60, 120):
        x, _ = layout.project(lon, 0)
        draw.line([x, layout.map_y, x, layout.map_y + layout.map_h],
                  fill=GRID, width=1)
    draw.rectangle([layout.map_x, layout.map_y,
                    layout.map_x + layout.map_w - 1,
                    layout.map_y + layout.map_h - 1], outline=GRID, width=2)
    return np.asarray(image, dtype=np.uint8).copy()


def draw_depth_legend(draw, layout: Layout, x: int, y: int, width: int,
                      height: int) -> None:
    """깊이 색 띠. 이게 없으면 색이 무슨 뜻인지 알 길이 없다.

    눈금을 0-35-70-150-300-700 에 찍는 이유는 그게 색이 꺾이는 지점이고,
    지구물리에서도 얕은지진/중발지진/심발지진을 가르는 대략의 경계이기
    때문이다.
    """
    stops = [d for d, _ in DEPTH_STOPS]
    span = stops[-1] ** 0.5
    for i in range(width):
        # 제곱근 눈금. 선형으로 깔면 얕은 구간이 한 픽셀로 뭉개진다.
        depth = (i / max(1, width - 1) * span) ** 2
        draw.line([x + i, y, x + i, y + height], fill=depth_color(depth))
    font = kr_font(max(16, height))
    for depth in stops:
        pos = x + int((depth ** 0.5) / span * (width - 1))
        label = f"{int(depth)}"
        box = draw.textbbox((0, 0), label, font=font)
        draw.text((pos - (box[2] - box[0]) / 2, y + height + 8), label,
                  font=font, fill=DIM)
    tag = kr_font(max(16, height))
    draw.text((x + width + 16, y - 2), "km", font=tag, fill=DIM)


def draw_hour_bars(draw, layout: Layout, counts: list[int], hours_done: float,
                   x: int, y: int, width: int, height: int) -> None:
    """시간대별 건수 막대. 하루의 리듬이 여기서 보인다.

    지도만 있으면 "몇 시에 몰렸나"를 알 수 없다. 막대가 차오르는 것이
    타임랩스의 진행 바 노릇도 한다 — 롱폼에서 끝이 보이면 끝까지 본다.
    """
    slots = len(counts)
    if slots == 0:
        return
    gap = max(1, width // (slots * 8))
    bar_w = max(2, (width - gap * (slots - 1)) // slots)
    top = max(1, max(counts) if counts else 1)
    for index, value in enumerate(counts):
        bx = x + index * (bar_w + gap)
        filled = index <= hours_done
        colour = ACCENT if filled else GRID
        bar_h = int(height * (value / top)) if top else 0
        draw.rectangle([bx, y + height - 2, bx + bar_w, y + height],
                       fill=GRID)
        if bar_h > 0 and filled:
            draw.rectangle([bx, y + height - bar_h, bx + bar_w, y + height],
                           fill=colour)


def _disc(shape: tuple[int, int], cx: float, cy: float, radius: float
          ) -> tuple[slice, slice, np.ndarray]:
    """원 하나의 경계 상자와 그 안의 알파 마스크.

    화면 전체에 거리 배열을 만들면 프레임당 수백 번이라 못 쓴다. 경계
    상자만 계산하면 반지름이 10픽셀일 때 21×21 이다.

    가장자리를 0/1 로 자르지 않고 한 픽셀 안에서 부드럽게 넘긴다. 점이
    작아서 계단이 그대로 보이고, 유튜브 재인코딩에서 그 계단이 더 뭉갠다.
    """
    height, width = shape
    pad = int(np.ceil(radius)) + 1
    x0, x1 = max(0, int(cx) - pad), min(width, int(cx) + pad + 1)
    y0, y1 = max(0, int(cy) - pad), min(height, int(cy) + pad + 1)
    if x0 >= x1 or y0 >= y1:
        return slice(0, 0), slice(0, 0), np.zeros((0, 0), dtype=np.float32)

    ys = np.arange(y0, y1, dtype=np.float32)[:, None] - cy
    xs = np.arange(x0, x1, dtype=np.float32)[None, :] - cx
    dist = np.sqrt(ys * ys + xs * xs)
    alpha = np.clip(radius - dist + 0.5, 0.0, 1.0)
    return slice(y0, y1), slice(x0, x1), alpha


def add_dot(layer: np.ndarray, cx: float, cy: float, radius: float,
            color: tuple, strength: float = 1.0) -> None:
    """쌓이는 층에 점 하나. 있는 값 위에 겹쳐 올린다."""
    rows, cols, alpha = _disc(layer.shape[:2], cx, cy, radius)
    if alpha.size == 0:
        return
    patch = layer[rows, cols]
    a = (alpha * strength)[:, :, None]
    layer[rows, cols] = patch * (1 - a) + np.array(color, dtype=np.float32) * a


def add_ring(layer: np.ndarray, cx: float, cy: float, radius: float,
             thickness: float, color: tuple, strength: float) -> None:
    """퍼지는 층에 고리 하나. 안쪽 원을 빼서 테두리만 남긴다."""
    rows, cols, outer = _disc(layer.shape[:2], cx, cy, radius)
    if outer.size == 0:
        return
    inner_r = max(0.0, radius - thickness)
    _, _, inner = _disc(layer.shape[:2], cx, cy, inner_r)
    if inner.shape == outer.shape:
        band = np.clip(outer - inner, 0.0, 1.0)
    else:
        band = outer
    a = (band * strength)[:, :, None]
    patch = layer[rows, cols]
    layer[rows, cols] = patch * (1 - a) + np.array(color, dtype=np.float32) * a


def composite(base: np.ndarray, *layers: np.ndarray) -> np.ndarray:
    """바탕 위에 층들을 더한다. 넘치는 값은 자른다.

    알파로 섞지 않고 **더하는** 이유: 같은 자리에서 지진이 여러 번 나면
    그 자리가 밝아져야 한다. 덮어쓰면 열 번 난 곳과 한 번 난 곳이 똑같이
    보인다 — 지도에서 제일 말하고 싶은 것이 그 차이다.
    """
    out = base.astype(np.float32)
    for layer in layers:
        out += layer
    return np.clip(out, 0, 255).astype(np.uint8)


def text_layer(layout: Layout, draw_fn) -> tuple[np.ndarray, np.ndarray]:
    """PIL 로 글자를 그리고, 글자가 있는 자리를 알려 주는 마스크를 함께 낸다.

    마스크가 필요한 이유: 글자는 배경을 **덮어야** 한다. 더하기로 얹으면
    밝은 지도 위에서 흰 글자가 하얗게 뭉개진다.
    """
    image = Image.new("RGB", (layout.width, layout.height), (0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw_fn(draw)
    array = np.asarray(image, dtype=np.uint8)
    mask = (array.max(axis=2) > 0)
    return array, mask


def blit_text(frame: np.ndarray, text: np.ndarray, mask: np.ndarray) -> None:
    frame[mask] = text[mask]
