import random
from typing import Dict


class LyricsGenerator:
    """AI 한국 가사 자동 생성 (감성힙합 전용)"""

    def __init__(self):
        self.verse_patterns = {
            "밤거리": [
                "밤거리를 헤매이고 있어\n네 생각만 떠올라\n어둠 속에서 혼자 걷다\n별빛이 길을 비춰줄때까지",
                "도시의 밤 고요한 거리\n발소리만 울려 퍼져\n네가 남긴 말들이 맴돌고\n내 마음도 함께 떠돈다",
                "밤하늘이 이렇게 검고\n내 맘도 고요한데\n왜 자꾸만 떠오르는지\n넌 몰라 나의 밤을"
            ],
            "위로": [
                "힘들어하지 말아\n시간이 다 치워줄 거야\n이 밤도 새벽이 되고\n새벽도 아침이 되니까",
                "가슴 아픈 모든 순간들\n결국 우리를 만들어\n웃음과 눈물 모두 소중해\n그게 바로 우리 인생이야",
                "혼자라고 느껴질 때\n나를 봐 나도 함께야\n이 길을 걸으니까\n두려움도 담대함이 돼"
            ],
            "활력": [
                "새로운 시작 준비하고 있어\n이번엔 달라질 거야\n과거는 놔두고 앞을 봐\n우린 다시 일어날 수 있어",
                "열정이 불타오르고\n희망이 솟아나와\n이 순간을 만끽해\n우리의 시간이 시작돼",
                "멈추지 말고 계속 나아가\n우린 강해졌으니까\n어떤 벽도 넘을 수 있어\n함께라면 절대 포기하지 않아"
            ],
            "반성": [
                "지난날들을 돌아봐\n그때 난 왜 그랬을까\n후회도 많고 아플지라도\n그것도 결국 나의 이야기",
                "거울 속 나를 마주할 때\n눈을 피하고 싶어\n잘못된 것들 많았지만\n지금부터 달라질 거야",
                "시간은 돌아오지 않아\n우린 앞으로만 나아가\n성장의 과정 속에서\n나는 천천히 변해가"
            ]
        }

        self.chorus_patterns = {
            "밤거리": [
                "밤거리를 나혼자 걸어\n너를 품은 도시 야경\n별처럼 빛나던 널\n이제 그림이 되었어",
                "밤하늘 아래 서있어\n네 숨결이 느껴져\n고독하지만 아름다워\n이 밤이 영원했으면"
            ],
            "위로": [
                "언젠가는 웃을 수 있어\n이 아픔도 약이 되니까\n함께라면 괜찮아\n넌 혼자가 아니야",
                "견뎌내\n그것만으로도 충분해\n우린 다 그런 날들을 살고 있어\n넌 충분히 잘하고 있어"
            ],
            "활력": [
                "새로운 날이 왔어\n가슴이 뛰어\n꿈꾸던 모든 것들\n이제 이뤄갈 거야",
                "우리 함께 달려가\n이 열정 영원하길\n내일은 더 아름다울 거야\n난 믿어 우리를"
            ],
            "반성": [
                "내가 변할 거야\n이전의 나와는 다르게\n모든 실수가 교훈이 되어\n나를 만들어갈 거야",
                "다시 시작해\n이번엔 다르게\n나의 이야기를 다시 써\n더 나은 내가 되기 위해"
            ]
        }

        self.rap_styles = {
            "빠른속도": "빠르고 강렬한 비트에 타고\n마치 번개처럼 내 가사가\n귀를 때려\n넌 정신을 차릴 수 없어",
            "서정적": "느려진 박자에 감정을 실어\n나의 진심이 내려앉아\n넌 고개를 숙일 거야\n이 무게의 말들 앞에",
            "강렬한": "마이크에 내 영혼을 태워\n이 비트는 경고음이야\n깨어나\n우린 결코 멈추지 않아"
        }

        self.bridges = [
            "하지만 우리는 계속해\n이 길이 맞는지 몰라도\n이 순간을 살아내고 있어\n그것만으로도 충분해",
            "모두가 나를 이해하지 못해도\n나는 나를 믿어\n이 맘이 거짓이 아닌 이상\n난 멈추지 않을 거야",
            "밤은 깊어도\n별은 반짝여\n이 어둠도 필요했던 거야\n내가 빛나기 위해"
        ]

    def generate(self, theme: str, mood: str, style: str = "랩") -> Dict:
        """한국 가사 자동 생성"""
        try:
            mood = mood.replace("감성", "밤거리") if mood == "감성" else mood.replace("감성", "밤거리")
            mood = mood if mood in self.verse_patterns else "밤거리"

            verse1 = random.choice(self.verse_patterns[mood])
            verse2 = random.choice(self.verse_patterns[mood])
            chorus = random.choice(self.chorus_patterns[mood])
            bridge = random.choice(self.bridges)

            rap_intro = self.rap_styles.get(style, self.rap_styles["서정적"])

            structure = {
                "intro": rap_intro,
                "verse1": verse1,
                "chorus": chorus,
                "verse2": verse2,
                "chorus_repeat": chorus,
                "bridge": bridge,
                "final_chorus": chorus,
                "outro": "이 노래가 넌\n언젠가 위로가 되길\n밤거리의 별처럼"
            }

            full_lyrics = f"""[인트로]
{rap_intro}

[1절]
{verse1}

[후렴]
{chorus}

[2절]
{verse2}

[후렴]
{chorus}

[브릿지]
{bridge}

[최종 후렴]
{chorus}

[아웃트로]
이 노래가 넌
언젠가 위로가 되길
밤거리의 별처럼"""

            return {
                "theme": theme,
                "mood": mood,
                "style": style,
                "lyrics": full_lyrics,
                "structure": structure,
                "section_count": 7,
                "quality": "고음질",
                "generated_at": "2026-08-19"
            }
        except Exception as e:
            return {
                "error": str(e),
                "lyrics": "가사 생성 실패. 다시 시도해주세요."
            }
