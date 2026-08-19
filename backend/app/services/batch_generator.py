import json
from typing import List, Dict
from datetime import datetime

MOOD_PRESETS = {
    "기본감성": {
        "themes": [
            "밤거리 드라이브", "도시의 외로움", "회상의 순간",
            "누군가를 그리며", "새벽 감성", "도시 불빛",
            "감정의 결들", "조용한 위로", "밤하늘 명상", "거리의 이야기"
        ],
        "vocal_styles": ["breathy male vocal", "restrained emotion"],
        "mood_descriptors": ["late night city vibe", "clear diction", "natural phrasing"]
    },
    "활력감성": {
        "themes": [
            "새로운 시작", "도시 에너지", "자신감의 순간",
            "나아가는 기분", "활기찬 밤", "도전의 순간",
            "희망의 빛", "함께하는 시간", "변화의 바람", "내일을 향해"
        ],
        "vocal_styles": ["confident male vocal", "open emotional delivery"],
        "mood_descriptors": ["energetic urban vibe", "powerful presence", "dynamic rhythm"]
    },
    "위로감성": {
        "themes": [
            "함께라는 것", "작은 위로", "이해해준다면",
            "힘내라는 마음", "괜찮을 거야", "함께 견디면",
            "따뜻한 손길", "응원의 말", "혼자가 아니야", "내가 여기 있어"
        ],
        "vocal_styles": ["warm male vocal", "comforting tone"],
        "mood_descriptors": ["warm ambient vibe", "gentle rhythm", "embracing presence"]
    },
    "반성감성": {
        "themes": [
            "지난날 후회", "돌아보는 마음", "실수와 배움",
            "시간의 흔적", "감정의 무게", "깨달음의 순간",
            "자책의 마음", "성장의 통증", "변해가는 모습", "그때 그 날들"
        ],
        "vocal_styles": ["introspective male vocal", "vulnerable delivery"],
        "mood_descriptors": ["melancholic tone", "slow tempo", "reflective space"]
    }
}

SUNO_BASE_STYLE = "Korean mood hip-hop, R&B hip-hop, singing rap, late night city vibe, breathy male vocal, restrained emotion, clear diction, natural phrasing, American English pronunciation on chorus"


class BatchGenerator:
    def generate(self, mood: str = "기본감성", count: int = 10) -> List[Dict]:
        """배치 자동 생성"""
        preset = MOOD_PRESETS.get(mood, MOOD_PRESETS["기본감성"])

        songs = []
        for i in range(count):
            theme_idx = i % len(preset["themes"])
            theme = preset["themes"][theme_idx]

            song = {
                "track_number": i + 1,
                "theme": theme,
                "title": self._generate_title(theme, i),
                "lyrics_outline": self._generate_lyrics_outline(theme),
                "lyrics": self._generate_lyrics(theme, mood),
                "suno_style": self._generate_suno_style(preset, theme),
                "suno_exclude": "instrumental, voice only, spoken word, no instruments",
                "bpm_target": 90,
                "duration_target": "2:30-3:00",
                "vocal_tone": preset["vocal_styles"][i % len(preset["vocal_styles"])]
            }
            songs.append(song)

        return songs

    def _generate_title(self, theme: str, index: int) -> str:
        """곡 제목 생성"""
        title_patterns = {
            "밤거리 드라이브": f"도시의 불빛 #{index+1}",
            "도시의 외로움": f"혼자인 밤 #{index+1}",
            "회상의 순간": f"그 시절로 #{index+1}",
            "누군가를 그리며": f"그리움 #{index+1}",
            "새벽 감성": f"새벽 #{index+1}",
            "도시 불빛": f"불빛 속에서 #{index+1}",
            "감정의 결들": f"마음의 결 #{index+1}",
            "조용한 위로": f"조용한 위로 #{index+1}",
            "밤하늘 명상": f"명상 #{index+1}",
            "거리의 이야기": f"거리 이야기 #{index+1}",
        }
        return title_patterns.get(theme, f"감성곡 #{index+1}")

    def _generate_lyrics_outline(self, theme: str) -> str:
        """가사 아웃라인 생성"""
        outlines = {
            "밤거리 드라이브": "도시 야경, 자동차 내부, 혼자만의 시간, 생각의 흐름",
            "도시의 외로움": "군중 속의 고독, 도시 소음, 연결되지 않은 감정",
            "회상의 순간": "과거의 순간들, 사람들의 얼굴, 돌아올 수 없는 시간",
            "누군가를 그리며": "그 사람, 대화, 함께했던 날들, 지금의 거리",
            "새벽 감성": "밤의 끝, 새로운 시작, 고요함, 숨겨진 감정",
            "도시 불빛": "야경, 건물들, 작은 희망, 밤의 아름다움",
            "감정의 결들": "감정의 층위, 복잡한 마음, 풀려는 노력",
            "조용한 위로": "함께함의 무언의 약속, 손잡음, 침묵의 따뜻함",
            "밤하늘 명상": "별, 깊은 생각, 자신과의 대화, 평온함",
            "거리의 이야기": "지나가는 사람들, 작은 이야기, 도시의 맥박",
        }
        return outlines.get(theme, "감정의 흐름을 따라가는 가사")

    def _generate_lyrics(self, theme: str, mood: str) -> str:
        """실제 가사 생성"""
        lyrics_map = {
            "밤거리 드라이브": "[Verse]\n불빛이 흐르는 도시 위로\n혼자만의 밤 거리를 걷고\n생각만 자꾸 맴도네\n이 도시의 소음 속에서\n\n[Chorus]\n밤거리를 헤매인다\n누군가의 손을 찾는다\n별빛 아래 멈춘 시간\n너만 생각하는 밤\n\n[Verse 2]\n가로등이 켜진 거리에서\n작은 발걸음을 멈춘다",
            "도시의 외로움": "[Verse]\n수많은 사람들 사이에서\n혼자라는 생각에 잠긴다\n누구도 내 마음을 모르네\n이 도시의 수많은 방들 중\n\n[Chorus]\n외로움이 점점 커져\n가슴이 점점 미어져\n누군가는 나를 안아줄\n사람이 있을까",
            "회상의 순간": "[Verse]\n그 시절로 돌아갈 수 있다면\n그때의 웃음이 그리워\n시간은 돌아오지 않는데\n추억만 자꾸 떠올라\n\n[Chorus]\n그때가 그리워\n그 순간으로 돌아가\n시간을 멈춰두고\n너와 함께 있고 싶어",
            "누군가를 그리며": "[Verse]\n그 사람의 목소리가 들리고\n함께했던 시간들이 떠나\n지금 이 자리에 없어도\n내 마음은 그곳에\n\n[Chorus]\n그리움이 밤을 채우고\n그리움이 하루를 채운다\n언제쯤이면 다시 만날까\n네 이름만 부른다",
            "새벽 감성": "[Verse]\n밤이 지나가고 새벽이 오면\n도시도 나도 조용해진다\n이 고요함 속에서 난\n너를 생각하고 있어\n\n[Chorus]\n새벽의 별빛 아래\n나만의 시간이 흐른다\n이 감정들을 담아\n내일을 향해 간다",
        }
        return lyrics_map.get(theme, "[Verse]\n감정의 결들을 모아\n하나의 노래로 만든다\n\n[Chorus]\n이 밤이 영원하면 좋겠어\n너와 함께 이 순간이")

    def _generate_suno_style(self, preset: Dict, theme: str) -> str:
        """Suno 스타일 프롬프트 생성"""
        base = "Korean mood hip-hop, R&B hip-hop, singing rap, late night city vibe"
        vocal = preset["vocal_styles"][0]
        mood_desc = ", ".join(preset["mood_descriptors"][:2])

        return f"{base}, {vocal}, {mood_desc}"
