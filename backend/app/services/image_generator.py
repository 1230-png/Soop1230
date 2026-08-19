from PIL import Image, ImageDraw, ImageFilter, ImageFont
import numpy as np
from datetime import datetime
import os


class ImageGenerator:
    """감성힙합 커버 이미지 생성"""

    def __init__(self):
        self.width = 1080
        self.height = 1080
        self.mood_colors = {
            "감성": {
                "bg_primary": (20, 30, 50),  # 진한 네이비
                "bg_secondary": (35, 60, 100),  # 라이트 네이비
                "accent": (200, 150, 220),  # 보라 톤
                "text": (240, 240, 250)  # 밝은 흰색
            },
            "활력": {
                "bg_primary": (30, 40, 60),  # 짙은 그레이-블루
                "bg_secondary": (80, 120, 180),  # 밝은 블루
                "accent": (255, 180, 100),  # 따뜻한 오렌지
                "text": (255, 255, 255)
            },
            "위로": {
                "bg_primary": (50, 40, 60),  # 다크 보라
                "bg_secondary": (100, 80, 120),  # 라이트 보라
                "accent": (200, 180, 200),  # 부드러운 핑크-보라
                "text": (240, 240, 250)
            },
            "반성": {
                "bg_primary": (25, 25, 35),  # 거의 검정
                "bg_secondary": (45, 45, 65),  # 다크 그레이
                "accent": (150, 150, 180),  # 차가운 라벤더
                "text": (200, 200, 220)
            }
        }

    def generate(self, output_path: str, title: str, artist: str = "새벽공기", mood: str = "감성") -> str:
        """커버 이미지 생성"""
        # 컬러 팔레트 선택
        colors = self.mood_colors.get(mood, self.mood_colors["감성"])

        # 캔버스 생성
        img = Image.new('RGB', (self.width, self.height), colors["bg_primary"])

        # 배경 그래디언트 생성
        self._apply_gradient_background(img, colors)

        # 기하학적 패턴 추가
        self._add_geometric_pattern(img, colors)

        # 텍스트 그리기
        self._draw_text(img, title, artist, colors)

        # 노이즈 추가 (감성 표현)
        self._add_noise(img)

        # 저장
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        img.save(output_path, quality=95)

        return output_path

    def _apply_gradient_background(self, img: Image.Image, colors: dict) -> None:
        """그래디언트 배경 적용"""
        pixels = img.load()

        for y in range(self.height):
            # 위에서 아래로 그래디언트
            progress = y / self.height
            r = int(colors["bg_primary"][0] * (1 - progress) + colors["bg_secondary"][0] * progress)
            g = int(colors["bg_primary"][1] * (1 - progress) + colors["bg_secondary"][1] * progress)
            b = int(colors["bg_primary"][2] * (1 - progress) + colors["bg_secondary"][2] * progress)

            for x in range(self.width):
                pixels[x, y] = (r, g, b)

    def _add_geometric_pattern(self, img: Image.Image, colors: dict) -> None:
        """기하학적 패턴 추가 (원형 그라디언트)"""
        draw = ImageDraw.Draw(img, 'RGBA')

        # 중심에서 방사형 그래디언트
        center_x, center_y = self.width // 2, self.height // 2
        max_radius = int(np.sqrt(self.width ** 2 + self.height ** 2))

        for radius in range(max_radius, 0, -20):
            alpha = int(255 * (1 - radius / max_radius) * 0.3)
            color = (*colors["accent"], alpha)
            draw.ellipse(
                [center_x - radius, center_y - radius, center_x + radius, center_y + radius],
                outline=color,
                width=5
            )

    def _draw_text(self, img: Image.Image, title: str, artist: str, colors: dict) -> None:
        """텍스트 그리기"""
        draw = ImageDraw.Draw(img)

        # 폰트 크기 계산
        title_size = 70
        artist_size = 40
        date_size = 25

        # 제목 그리기 (중앙 상단)
        title_y = self.height // 3
        self._draw_centered_text(
            draw, title, title_size, title_y, colors["text"], colors
        )

        # 아티스트명 그리기 (중앙)
        artist_y = self.height // 2 + 80
        self._draw_centered_text(
            draw, artist, artist_size, artist_y, colors["accent"], colors
        )

        # 날짜 그리기 (하단)
        date_str = datetime.now().strftime("%Y.%m.%d")
        date_y = self.height - 150
        self._draw_centered_text(
            draw, date_str, date_size, date_y, colors["text"], colors, alpha=0.6
        )

    def _draw_centered_text(self, draw: ImageDraw.ImageDraw, text: str, size: int, y: int, color: tuple, colors: dict, alpha: float = 1.0) -> None:
        """중앙 정렬된 텍스트 그리기"""
        # 기본 폰트 사용 (시스템 폰트 없을 시)
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
        except:
            font = ImageFont.load_default()

        # 텍스트 크기 계산
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_x = (self.width - text_width) // 2

        # 그림자 효과
        shadow_offset = 3
        shadow_color = (0, 0, 0, int(100 * alpha))
        draw.text(
            (text_x + shadow_offset, y + shadow_offset),
            text,
            font=font,
            fill=shadow_color
        )

        # 메인 텍스트
        draw.text((text_x, y), text, font=font, fill=color)

    def _add_noise(self, img: Image.Image) -> None:
        """노이즈 추가 (감성 표현)"""
        pixels = img.load()

        for _ in range(self.width * self.height // 100):
            x = np.random.randint(0, self.width)
            y = np.random.randint(0, self.height)

            r, g, b = pixels[x, y]
            noise = np.random.randint(-10, 10)

            r = max(0, min(255, r + noise))
            g = max(0, min(255, g + noise))
            b = max(0, min(255, b + noise))

            pixels[x, y] = (r, g, b)

        # 빈티지 필터 (약한 비네팅)
        self._apply_vignette(img)

    def _apply_vignette(self, img: Image.Image) -> None:
        """비네팅 효과 (가장자리 어둡게)"""
        pixels = img.load()

        center_x, center_y = self.width // 2, self.height // 2
        max_dist = np.sqrt(center_x ** 2 + center_y ** 2)

        for x in range(self.width):
            for y in range(self.height):
                dist = np.sqrt((x - center_x) ** 2 + (y - center_y) ** 2)
                vignette_factor = 1 - (dist / max_dist) ** 1.5 * 0.4

                r, g, b = pixels[x, y]
                r = int(r * vignette_factor)
                g = int(g * vignette_factor)
                b = int(b * vignette_factor)

                pixels[x, y] = (r, g, b)
