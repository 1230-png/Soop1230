from typing import Dict, List


class MetadataGenerator:
    """메타데이터 자동 생성"""

    def __init__(self):
        self.mood_descriptions = {
            "감성": "늦은 밤 도시, 혼자만의 생각, 감정의 결들",
            "활력": "도시 에너지, 새로운 시작, 함께하는 기분",
            "위로": "따뜻한 손길, 응원의 말, 함께라는 것",
            "반성": "돌아보는 마음, 깨달음, 성장의 통증"
        }

        self.tags = {
            "감성": ["감성힙합", "밤감성", "도시", "혼자", "생각", "마음"],
            "활력": ["활력", "도시에너지", "시작", "함께", "희망", "도전"],
            "위로": ["위로", "응원", "함께", "따뜻함", "공감", "치유"],
            "반성": ["반성", "성장", "돌아봄", "깨달음", "변화", "배움"]
        }

    def generate(self, title: str, mood: str = "감성", bpm: int = 90) -> Dict:
        """메타데이터 생성"""
        return {
            "title": title,
            "artist": "새벽공기",
            "mood": mood,
            "bpm": bpm,
            "description": self._generate_description(title, mood, bpm),
            "tags": self._generate_tags(mood),
            "keywords": self._generate_keywords(title, mood),
            "youtube_title": self._generate_youtube_title(title, mood),
            "youtube_description": self._generate_youtube_description(title, mood)
        }

    def _generate_description(self, title: str, mood: str, bpm: int) -> str:
        """설명 생성"""
        base_desc = self.mood_descriptions.get(mood, "감성힙합")

        return f"{title} | {base_desc}\n\n" \
               f"BPM: {bpm} | 새벽공기 채널\n" \
               f"감성 힙합 & R&B 플레이리스트\n\n" \
               f"늦은 밤의 감정을 담은 곡입니다.\n" \
               f"Your mood, your night, your story."

    def _generate_tags(self, mood: str) -> List[str]:
        """태그 생성"""
        base_tags = ["감성힙합", "hiphop", "감성", "새벽공기", "한국힙합", "r&b"]
        mood_tags = self.tags.get(mood, [])

        return base_tags + mood_tags

    def _generate_keywords(self, title: str, mood: str) -> str:
        """검색 키워드 생성"""
        keywords = [
            "감성힙합",
            "한국힙합",
            f"{mood}감성",
            title,
            "밤감성",
            "도시",
            "혼자"
        ]

        return ", ".join(keywords)

    def _generate_youtube_title(self, title: str, mood: str) -> str:
        """YouTube 제목 생성"""
        emoji_map = {
            "감성": "🌙",
            "활력": "⚡",
            "위로": "💙",
            "반성": "🌑"
        }
        emoji = emoji_map.get(mood, "🎵")

        return f"{emoji} {title} | 감성힙합 | 새벽공기"

    def _generate_youtube_description(self, title: str, mood: str) -> str:
        """YouTube 설명 생성"""
        desc = f"{title}\n" \
               f"감성 힙합 & R&B 플레이리스트 '새벽공기'\n\n"

        mood_desc_map = {
            "감성": "늦은 밤, 도시 거리를 혼자 거닐 때 듣기 좋은 곡입니다.\n혼자만의 시간, 감정의 결들을 함께하세요.",
            "활력": "도시의 에너지, 새로운 시작을 응원하는 곡입니다.\n활기찬 밤, 함께하는 기분으로 나아가세요.",
            "위로": "누군가의 손길이 필요한 밤, 따뜻한 위로를 드립니다.\n혼자가 아니라는 것을 느껴보세요.",
            "반성": "지난 날을 돌아보며 성장하는 마음을 담았습니다.\n깨달음의 순간, 변화의 바람을 함께하세요."
        }

        desc += mood_desc_map.get(mood, "감성 있는 음악으로 당신의 밤을 함께합니다.\n")

        desc += "\n---\n\n" \
                "📱 Follow & Subscribe\n" \
                "- Spotify: [URL]\n" \
                "- SoundCloud: [URL]\n" \
                "- Instagram: [URL]\n\n" \
                "#감성힙합 #hiphop #밤감성 #새벽공기 #한국힙합"

        return desc
