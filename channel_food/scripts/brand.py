"""채널 브랜드 상수 — 이 파일 한 곳만 고치면 설명문·배너·메타데이터에 일괄 반영된다.

채널 이름과 핸들은 YouTube Data API로 변경할 수 없다(핸들 변경 엔드포인트 자체가 없고,
brandingSettings.channel.title도 channels.update로 쓰이지 않는다).
YouTube Studio → 맞춤설정에서 수동으로 바꾼 뒤, 아래 값을 그에 맞춰 고칠 것.
"""

CHANNEL_NAME = "현실 속 기괴한 현상"
CHANNEL_HANDLE = "@reality_bizarre"
CHANNEL_URL = f"https://youtube.com/{CHANNEL_HANDLE}"

CHANNEL_TAGLINE = "설명되지 않는 것들을 매일 하나씩 기록합니다"

# 영상 설명문 하단에 붙는 공통 블록
CHANNEL_FOOTER = f"""━━━━━━━━━━━━━━━━━━━━
📺 {CHANNEL_NAME} ({CHANNEL_HANDLE})
{CHANNEL_TAGLINE}
구독 👉 {CHANNEL_URL}
━━━━━━━━━━━━━━━━━━━━"""

# 모든 영상에 공통으로 붙는 해시태그
BASE_HASHTAGS = ["#현실속기괴한현상", "#미스터리", "#기괴한현상", "#shorts"]

# update_channel_branding.py가 채널 자체에 기록하는 값
CHANNEL_KEYWORDS = [
    "현실 속 기괴한 현상", "기묘한 현실", "미스터리", "기괴한 현상", "만델라 효과",
    "도시전설", "미스터리 쇼츠", "설명할 수 없는", "데자뷰",
]

CHANNEL_DESCRIPTION = f"""{CHANNEL_TAGLINE}

만델라 효과, 데자뷰, 시간이 멈춘 듯한 1초, 아무도 설명하지 못한 소리.
현실에서 실제로 일어나지만 좀처럼 이름 붙지 않는 것들을 다룹니다.

{CHANNEL_HANDLE}"""
