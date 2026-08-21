"""채널 브랜드 상수 — 이 파일 한 곳만 고치면 설명문·배너·메타데이터에 일괄 반영된다.

채널 이름과 핸들은 YouTube Data API로 변경할 수 없다(핸들 변경 엔드포인트 자체가 없고,
brandingSettings.channel.title도 channels.update로 쓰이지 않는다).
YouTube Studio → 맞춤설정에서 수동으로 바꾼 뒤, 아래 값을 그에 맞춰 고칠 것.
"""

CHANNEL_NAME = "기묘한 현실"
CHANNEL_HANDLE = "@gimyo-real"
CHANNEL_URL = f"https://youtube.com/{CHANNEL_HANDLE}"

CHANNEL_TAGLINE = "현실 속 기괴한 현상을 기록합니다"

# 영상 설명문 하단에 붙는 공통 블록
CHANNEL_FOOTER = f"""━━━━━━━━━━━━━━━━━━━━
📺 {CHANNEL_NAME} ({CHANNEL_HANDLE})
{CHANNEL_TAGLINE}
구독 👉 {CHANNEL_URL}
━━━━━━━━━━━━━━━━━━━━"""

# 모든 영상에 공통으로 붙는 해시태그
BASE_HASHTAGS = ["#기묘한현실", "#미스터리", "#기괴한현상", "#shorts"]

# update_channel_branding.py가 채널 자체에 기록하는 값
CHANNEL_KEYWORDS = [
    "기묘한 현실", "미스터리", "기괴한 현상", "만델라 효과",
    "도시전설", "미스터리 쇼츠", "설명할 수 없는", "데자뷰",
]

CHANNEL_DESCRIPTION = f"""{CHANNEL_TAGLINE}

만델라 효과, 데자뷰, 도시전설, 아직 설명되지 않은 현상들.
매일 1편, 짧게 기록합니다.

{CHANNEL_HANDLE}"""
