"""@200-y3b 채널 뒷정리 — 감사, 재생목록 보정, 중복 영상 정리.

    python3 channel_200y3b/scripts/channel_fix.py audit
    python3 channel_200y3b/scripts/channel_fix.py stats
    python3 channel_200y3b/scripts/channel_fix.py backfill [--apply]
    python3 channel_200y3b/scripts/channel_fix.py playlist-add --video ID --playlist "제목"
    python3 channel_200y3b/scripts/channel_fix.py retitle [--apply]
    python3 channel_200y3b/scripts/channel_fix.py comment [--apply]
    python3 channel_200y3b/scripts/channel_fix.py dedupe [--apply] [--private]
    python3 channel_200y3b/scripts/channel_fix.py delete --video ID --confirm ID

무인 발행이라 사람이 Studio를 보지 않는다. 업로드가 실패해도 다음 크론이
새 영상을 올려 버리기 때문에, 실패한 흔적(재생목록에 안 들어간 영상, 같은
표현으로 두 번 올라간 영상)은 쌓이기만 하고 아무도 치우지 않는다.
그 뒷정리를 워크플로에서 손으로 돌릴 수 있게 모아 둔 도구다.

상태를 바꾸는 명령은 전부 기본이 미리보기(dry run)이고 --apply 를 붙여야
실행된다. dedupe 는 --private 로 비공개 전환만 할 수 있다 — 조회수와 댓글이
남고 다시 공개할 수 있으므로, 삭제보다 이쪽을 먼저 고려할 것.
`delete`는 --confirm 에 같은 ID를 한 번 더 적어야 실제로 지운다.

할당량: channels.list 1, playlistItems.list 1/페이지(50개), videos.list 1/50개,
playlists.insert 50, playlistItems.insert 50, videos.update 50, videos.delete 50.
audit 전체가 30단위 안쪽이다.
"""

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ["https://www.googleapis.com/auth/youtube"]
CHANNEL_ID = "UCeXsmdfyW4hoxgWV2K8EwFw"  # @200-y3b

# 자동 업로드가 매번 지정하는 값. Studio 의 '업로드 기본 설정'은 수동
# 업로드에만 걸리므로, 실제로 확인해야 하는 것은 올라간 영상이 이 값인지다.
EXPECTED = {"categoryId": "27", "privacyStatus": "public", "madeForKids": False}


def credential(name: str) -> str:
    return os.environ.get(f"Y3B_{name}") or os.environ.get(f"YT_{name}") or ""


def youtube_client():
    client_id = credential("CLIENT_ID")
    client_secret = credential("CLIENT_SECRET")
    refresh_token = credential("REFRESH_TOKEN")
    if not all([client_id, client_secret, refresh_token]):
        raise SystemExit(
            "OAuth 자격 증명이 없다. Y3B_CLIENT_ID / Y3B_CLIENT_SECRET / "
            "Y3B_REFRESH_TOKEN (또는 YT_* 대체)를 환경변수로 넣을 것."
        )

    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=SCOPES,
    )
    creds.refresh(Request())
    youtube = build("youtube", "v3", credentials=creds)

    resp = youtube.channels().list(part="id,snippet,contentDetails", mine=True).execute()
    items = resp.get("items", [])
    if not items:
        raise SystemExit("이 자격 증명이 어느 채널 것인지 확인할 수 없다.")
    if items[0]["id"] != CHANNEL_ID:
        title = items[0]["snippet"].get("title", "?")
        raise SystemExit(
            f"엉뚱한 채널이다: {items[0]['id']} ({title}). "
            f"@200-y3b 는 {CHANNEL_ID}."
        )
    return youtube, items[0]


def paged(request_fn, youtube):
    """nextPageToken 을 따라가며 items 를 모두 모은다."""
    token, out = None, []
    while True:
        resp = request_fn(token).execute()
        out.extend(resp.get("items", []))
        token = resp.get("nextPageToken")
        if not token:
            return out


def all_uploads(youtube, channel) -> list:
    uploads = channel["contentDetails"]["relatedPlaylists"]["uploads"]
    return paged(
        lambda t: youtube.playlistItems().list(
            part="snippet,contentDetails", playlistId=uploads,
            maxResults=50, pageToken=t),
        youtube,
    )


def video_details(youtube, video_ids: list) -> dict:
    """videos.list 는 한 번에 50개까지. id → {snippet, status} 로 돌려준다."""
    out = {}
    for i in range(0, len(video_ids), 50):
        chunk = video_ids[i:i + 50]
        resp = youtube.videos().list(
            part="snippet,status,contentDetails", id=",".join(chunk)
        ).execute()
        for item in resp.get("items", []):
            out[item["id"]] = item
    return out


def all_playlists(youtube) -> list:
    return paged(
        lambda t: youtube.playlists().list(
            part="snippet,contentDetails", mine=True, maxResults=50, pageToken=t),
        youtube,
    )


def playlist_video_ids(youtube, playlist_id: str) -> set:
    items = paged(
        lambda t: youtube.playlistItems().list(
            part="contentDetails", playlistId=playlist_id,
            maxResults=50, pageToken=t),
        youtube,
    )
    return {i["contentDetails"]["videoId"] for i in items}


# 쇼츠 제목은 '"표현" 무슨 뜻일까? | 매일 영어 한마디' 꼴이다. 초기에 올라간
# 몇 편은 따옴표가 없어서, 따옴표를 선택으로 두지 않으면 그것들만 판정에서
# 빠져 같은 표현이 두 번 올라간 것을 못 잡는다.
SHORTS_TITLE = re.compile(r'^"?(?P<phrase>.+?)"?\s*무슨 뜻일까\?')


def dupe_key(title: str) -> str:
    """쇼츠 제목에서 영어 표현만 남긴 비교용 키. 쇼츠가 아니면 빈 문자열.

    롱폼 제목은 통째로 한국어라 여기서 걸러 내지 않으면 전부 같은 키(빈
    문자열)로 묶여 서로 중복으로 잡힌다. 지우면 안 되는 것을 지우는 쪽이
    못 지우는 쪽보다 훨씬 비싸므로, 아는 형식만 판정한다.
    """
    m = SHORTS_TITLE.match(title.strip())
    if not m:
        return ""
    return re.sub(r"[^a-z0-9]+", " ", m.group("phrase").lower()).strip()


# 제목 → 재생목록. 각 생성기가 쓰는 제목 서식에서 그대로 따왔고, 위에서부터
# 처음 맞는 것을 쓴다. '총정리'가 월간·상황별 양쪽에 들어가므로 좁은 쪽이 먼저다.
PLAYLIST_RULES = [
    (SHORTS_TITLE, "매일 영어 한마디 · 쇼츠 모음"),
    # 검색어를 앞세운 현재 서식.
    (re.compile(r"^영어 회화 표현 \d+개 몰아듣기"), "주간 복습 몰아듣기"),
    (re.compile(r"^영어 쉐도잉 연습 \d+문장"), "쉐도잉 트레이닝"),
    (re.compile(r"^잠들기 전 영어 듣기"), "자면서 듣는 영어"),
    (re.compile(r"^영어 회화 표현 \d+개 총정리"), "월간 총정리"),
    (re.compile(r"^.+ 영어 회화 표현 \d+개 \| 상황별"), "상황별 영어 표현"),
    # 검색어 개편 전 서식. 이미 올라간 영상이 남아 있는 한 지우면 안 된다.
    (re.compile(r"^이번 주 영어 표현 \d+개 몰아듣기"), "주간 복습 몰아듣기"),
    (re.compile(r"^영어 쉐도잉 훈련 \d+문장"), "쉐도잉 트레이닝"),
    (re.compile(r"^자면서 듣는 영어 표현 \d+개"), "자면서 듣는 영어"),
    (re.compile(r"^이번 달 영어 표현 \d+개 총정리"), "월간 총정리"),
    (re.compile(r"^영어 표현 총정리 Vol\."), "매일 영어 한마디 · 주간 표현 모음"),
    (re.compile(r"^실생활 영어 표현 \d+개 모음 Vol\."), "매일 영어 한마디 · 주간 표현 모음"),
    (re.compile(r"^.+ 영어 표현 \d+개 총정리"), "상황별 영어 표현"),
]

# 검색어 개편 전에 올라간 롱폼의 제목을 새 서식으로 바꾼다. 현재 제목으로
# 찾으므로 한 번 바꾸고 나면 저절로 아무것도 하지 않는다.
RETITLE = {
    "실생활 영어 표현 30개 모음 Vol.1 | 매일 영어 한마디": (
        "영어 회화 표현 30개 몰아듣기 | 생활 영어 흘려듣기 5분",
        ["영어몰아듣기", "생활영어회화", "영어회화표현", "영어반복듣기", "영어복습"],
    ),
    "실생활 영어 표현 35개 모음 Vol.2 | 매일 영어 한마디": (
        "영어 회화 표현 35개 몰아듣기 | 생활 영어 흘려듣기 8분",
        ["영어몰아듣기", "생활영어회화", "영어회화표현", "영어반복듣기", "영어복습"],
    ),
    "여행·공항·호텔 영어 표현 30개 총정리 | 매일 영어 한마디": (
        "여행·공항·호텔 영어 회화 표현 30개 | 상황별 영어 한마디 14분",
        ["상황별영어", "여행영어", "공항영어", "호텔영어", "여행영어회화"],
    ),
    "이번 주 영어 표현 30개 몰아듣기 | 매일 영어 한마디": (
        "영어 회화 표현 30개 몰아듣기 | 출퇴근 영어 흘려듣기 14분",
        ["영어몰아듣기", "출퇴근영어", "영어회화표현", "영어반복듣기", "영어복습"],
    ),
}

BASE_TAGS = ["영어공부", "영어회화", "매일영어한마디", "영어듣기", "영어표현",
             "english listening", "learn english", "shadowing"]

# 쇼츠 댓글로 붙이는 롱폼 안내. 설명란보다 눈에 띄고, 쇼츠 시청자를 시청
# 시간이 실제로 쌓이는 롱폼으로 넘기는 것이 목적이다.
SHORTS_COMMENT = (
    "🎧 이 표현들 몰아듣기 — 롱폼 재생목록\n"
    "https://www.youtube.com/@200-y3b/playlists\n"
    "\n"
    "일요일 주간 복습 · 월요일 쉐도잉 · 수요일 상황별 · 금요일 자면서 듣는 영어\n"
    "출퇴근길에 틀어 두기 좋게 만들었습니다."
)


def playlist_for(title: str) -> str:
    """이 제목이 들어가야 할 재생목록. 모르는 서식이면 빈 문자열."""
    title = title.strip()
    for pattern, name in PLAYLIST_RULES:
        if pattern.match(title):
            return name
    return ""


def get_or_create_playlist(youtube, title: str, cache: dict) -> str:
    if title in cache:
        return cache[title]
    resp = youtube.playlists().insert(
        part="snippet,status",
        body={"snippet": {"title": title},
              "status": {"privacyStatus": "public"}},
    ).execute()
    cache[title] = resp["id"]
    print(f"  재생목록을 새로 만들었다: {title!r} ({resp['id']})")
    return resp["id"]


def cmd_backfill(youtube, channel, args) -> int:
    """재생목록에 못 들어간 영상을 제목 규칙대로 넣는다."""
    uploads = all_uploads(youtube, channel)
    ids = [i["contentDetails"]["videoId"] for i in uploads]
    details = video_details(youtube, ids)

    playlists = {p["snippet"]["title"]: p["id"] for p in all_playlists(youtube)}
    members = {name: playlist_video_ids(youtube, pid)
               for name, pid in playlists.items()}
    in_any = set().union(*members.values()) if members else set()

    todo, unknown = [], []
    for vid in ids:
        if vid in in_any:
            continue
        title = details[vid]["snippet"]["title"]
        target = playlist_for(title)
        (todo if target else unknown).append((vid, target, title))

    for vid, target, title in todo:
        print(f"{'넣는다' if args.apply else '넣을 것'}: {vid} → {target!r}  {title[:50]}")
    for vid, _, title in unknown:
        print(f"규칙 없음(그대로 둠): {vid}  {title[:50]}")

    if not todo:
        print("\n넣을 것이 없다.")
        return 0
    if not args.apply:
        cost = len(todo) * 50
        print(f"\n미리보기다. 실제로 넣으려면 --apply ({len(todo)}편, "
              f"할당량 약 {cost}단위).")
        return 0

    for vid, target, _ in todo:
        pid = get_or_create_playlist(youtube, target, playlists)
        youtube.playlistItems().insert(
            part="snippet",
            body={"snippet": {"playlistId": pid,
                              "resourceId": {"kind": "youtube#video",
                                             "videoId": vid}}},
        ).execute()
        print(f"  넣었다: {vid} → {target!r}")
    return 0


def cmd_audit(youtube, channel, args) -> int:
    uploads = all_uploads(youtube, channel)
    ids = [i["contentDetails"]["videoId"] for i in uploads]
    print(f"업로드된 영상: {len(ids)}편")

    details = video_details(youtube, ids)

    # 1) 업로드 기본값이 실제로 걸렸는지
    #
    # 비공개는 따로 센다. 중복 정리로 내린 것과 예전에 손으로 내린 것이 섞여
    # 있어 매번 '어긋남'으로 뜨면, 정작 진짜 어긋난 건이 묻힌다.
    wrong, private = [], []
    for vid, item in details.items():
        got = {
            "categoryId": item["snippet"].get("categoryId"),
            "privacyStatus": item["status"].get("privacyStatus"),
            "madeForKids": item["status"].get("madeForKids"),
        }
        if got["privacyStatus"] != "public":
            private.append((vid, item["snippet"]["title"][:50],
                            got["privacyStatus"]))
        diff = {k: got[k] for k in EXPECTED
                if k != "privacyStatus" and got[k] != EXPECTED[k]}
        if diff:
            wrong.append((vid, item["snippet"]["title"][:40], diff))

    print(f"\n[업로드 설정] 기대값 {EXPECTED}")
    if wrong:
        print(f"  어긋난 영상 {len(wrong)}편:")
        for vid, title, diff in wrong:
            print(f"    {vid} {title!r} → {diff}")
    else:
        print("  카테고리·아동용 전부 일치 — Studio 기본 설정은 수동 업로드에만"
              " 걸리므로 만질 이유가 없다.")
    print(f"  공개가 아닌 영상 {len(private)}편 (의도적일 수 있음):")
    for vid, title, status in private:
        print(f"    {vid} [{status}] {title}")

    # 2) 같은 표현이 두 번 올라갔는지
    groups = defaultdict(list)
    for vid, item in details.items():
        key = dupe_key(item["snippet"]["title"])
        if key:
            groups[key].append(vid)
    dupes = {k: v for k, v in groups.items() if len(v) > 1}
    open_dupes = sum(
        1 for vids in dupes.values()
        for v in sorted(vids, key=lambda v: details[v]["snippet"]["publishedAt"])[1:]
        if details[v]["status"].get("privacyStatus") == "public"
    )
    print(f"\n[중복] 같은 표현으로 두 번 이상 올라간 묶음: {len(dupes)}건, "
          f"아직 공개로 남아 있는 중복분 {open_dupes}편")
    for key, vids in dupes.items():
        rows = sorted(
            ((v, details[v]["snippet"]["publishedAt"],
              details[v]["snippet"]["title"]) for v in vids),
            key=lambda r: r[1],
        )
        print(f"  {key!r}")
        for i, (vid, pub, title) in enumerate(rows):
            if i == 0:
                mark = "지킴"
            elif details[vid]["status"].get("privacyStatus") != "public":
                mark = "처리됨"
            else:
                mark = "정리 대상"
            print(f"    [{mark}] {vid}  {pub}  {title[:50]}")

    # 3) 재생목록에 못 들어간 영상
    playlists = all_playlists(youtube)
    in_any = set()
    print(f"\n[재생목록] {len(playlists)}개")
    for pl in playlists:
        members = playlist_video_ids(youtube, pl["id"])
        in_any |= members
        print(f"  {pl['snippet']['title']!r}: {len(members)}편  ({pl['id']})")
    orphans = [v for v in ids if v not in in_any]
    print(f"\n  어느 재생목록에도 없는 영상: {len(orphans)}편")
    for vid in orphans:
        title = details[vid]["snippet"]["title"]
        target = playlist_for(title) or "(규칙 없음 — 손대지 않는다)"
        print(f"    {vid}  {target:22}  {title[:60]}")
    return 0


def cmd_playlist_add(youtube, channel, args) -> int:
    playlists = {p["snippet"]["title"]: p["id"] for p in all_playlists(youtube)}
    if args.playlist not in playlists:
        print(f"그런 재생목록이 없다: {args.playlist!r}", file=sys.stderr)
        print(f"있는 것: {sorted(playlists)}", file=sys.stderr)
        return 1
    pid = playlists[args.playlist]
    if args.video in playlist_video_ids(youtube, pid):
        print(f"이미 들어 있다: {args.video} → {args.playlist!r}")
        return 0
    youtube.playlistItems().insert(
        part="snippet",
        body={"snippet": {"playlistId": pid,
                          "resourceId": {"kind": "youtube#video",
                                         "videoId": args.video}}},
    ).execute()
    print(f"넣었다: {args.video} → {args.playlist!r}")
    return 0


def cmd_dedupe(youtube, channel, args) -> int:
    """중복 묶음마다 가장 먼저 올라간 것만 남기고 나머지를 지운다."""
    uploads = all_uploads(youtube, channel)
    ids = [i["contentDetails"]["videoId"] for i in uploads]
    details = video_details(youtube, ids)

    groups = defaultdict(list)
    for vid, item in details.items():
        key = dupe_key(item["snippet"]["title"])
        if key:
            groups[key].append(vid)

    victims = []
    for key, vids in groups.items():
        if len(vids) < 2:
            continue
        rows = sorted(vids, key=lambda v: details[v]["snippet"]["publishedAt"])
        for vid in rows[1:]:
            # 이미 비공개로 내린 것은 다시 건드리지 않는다. 그러지 않으면
            # 비공개로 처리한 뒤에도 매번 정리 대상으로 다시 올라온다.
            if details[vid]["status"].get("privacyStatus") != "public":
                continue
            victims.append((key, vid, details[vid]["snippet"]["publishedAt"]))

    if not victims:
        print("정리할 중복 없음 (이미 처리된 것은 세지 않는다).")
        return 0

    how = "비공개 전환" if args.private else "삭제"
    for key, vid, pub in victims:
        print(f"{how}{'' if args.apply else ' 예정'}: {vid}  {pub}  {key!r}")
    if not args.apply:
        print(f"\n미리보기다. 실제로 실행하려면 --apply ({len(victims)}편, {how}).")
        return 0

    for _, vid, _ in victims:
        if args.private:
            # 삭제와 달리 되돌릴 수 있다. 조회수·댓글이 남고 다시 공개할 수 있다.
            #
            # videos.update 는 지정한 part 를 통째로 갈아 끼운다. privacyStatus
            # 하나만 보내면 같은 status 안의 다른 값들이 기본값으로 초기화되므로,
            # 읽어 둔 status 에 덮어써서 보낸다.
            status = dict(details[vid]["status"])
            status.pop("madeForKids", None)  # 읽기 전용
            status.pop("publishAt", None)
            status["privacyStatus"] = "private"
            youtube.videos().update(
                part="status", body={"id": vid, "status": status},
            ).execute()
            print(f"비공개 전환: {vid}")
        else:
            youtube.videos().delete(id=vid).execute()
            print(f"삭제 완료: {vid}")
    return 0


ISO_DURATION = re.compile(
    r"^P(?:(?P<d>\d+)D)?T(?:(?P<h>\d+)H)?(?:(?P<m>\d+)M)?(?:(?P<s>\d+)S)?$"
)


def duration_seconds(iso: str) -> int:
    m = ISO_DURATION.match(iso or "")
    if not m:
        return 0
    d, h, mi, s = (int(m.group(k) or 0) for k in ("d", "h", "m", "s"))
    return ((d * 24 + h) * 60 + mi) * 60 + s


def cmd_stats(youtube, channel, args) -> int:
    """수익 창출 자격까지 얼마나 남았는지.

    시청 시간은 추정이다. 정확한 값은 YouTube Analytics API 에 있는데 그쪽은
    yt-analytics.readonly 스코프가 따로 필요하고 지금 토큰에는 없다. 그래서
    조회수 × 길이 × 평균 시청률로 위아래 범위를 낸다. 범위 폭이 크므로 결론을
    한 숫자로 읽지 말 것.
    """
    import datetime

    stats = youtube.channels().list(
        part="statistics", mine=True).execute()["items"][0]["statistics"]
    subs = int(stats.get("subscriberCount", 0))

    uploads = all_uploads(youtube, channel)
    ids = [i["contentDetails"]["videoId"] for i in uploads]
    details = {}
    for i in range(0, len(ids), 50):
        resp = youtube.videos().list(
            part="snippet,status,contentDetails,statistics",
            id=",".join(ids[i:i + 50]),
        ).execute()
        for item in resp.get("items", []):
            details[item["id"]] = item

    now = datetime.datetime.now(datetime.timezone.utc)
    cut_90 = now - datetime.timedelta(days=90)
    cut_365 = now - datetime.timedelta(days=365)

    long_rows, short_rows = [], []
    public_90 = 0
    for vid, item in details.items():
        if item["status"].get("privacyStatus") != "public":
            continue
        pub = datetime.datetime.fromisoformat(
            item["snippet"]["publishedAt"].replace("Z", "+00:00"))
        secs = duration_seconds(item["contentDetails"].get("duration", ""))
        views = int(item["statistics"].get("viewCount", 0))
        if pub >= cut_90:
            public_90 += 1
        # 쇼츠(3분 이하)는 유효 공개 시청 시간에 들어가지 않는다.
        row = (vid, pub, secs, views)
        (short_rows if secs <= 180 else long_rows).append(row)

    def hours(rows, retention):
        return sum(v * s for _, _, s, v in rows) * retention / 3600

    long_12mo = [r for r in long_rows if r[1] >= cut_365]
    short_90 = [r for r in short_rows if r[1] >= cut_90]

    print(f"기준 시각: {now.date()} (UTC)\n")
    print("[현재]")
    print(f"  구독자                     {subs:>8,} 명")
    print(f"  최근 90일 공개 업로드      {public_90:>8,} 편")
    print(f"  롱폼(3분 초과) 공개        {len(long_rows):>8,} 편"
          f"  (최근 12개월 {len(long_12mo)}편)")
    print(f"  쇼츠 공개                  {len(short_rows):>8,} 편")
    print(f"  최근 90일 쇼츠 조회수      "
          f"{sum(v for _, _, _, v in short_90):>8,} 회")

    # 롱폼 편별 조회수가 결론을 좌우한다. 합계만 보면 '편수가 적어서'인지
    # '편당 안 보여서'인지 구분이 안 된다.
    print("\n[롱폼 편별]")
    for vid, pub, secs, views in sorted(long_rows, key=lambda r: r[1]):
        title = details[vid]["snippet"]["title"][:44]
        print(f"  {pub.date()}  {secs // 60:>3}분  {views:>6,}회  {title}")
    if short_rows:
        sv = sorted(v for _, _, _, v in short_rows)
        mid = sv[len(sv) // 2]
        print(f"\n[쇼츠 편별] 중앙값 {mid:,}회, 최고 {sv[-1]:,}회, "
              f"최저 {sv[0]:,}회 ({len(sv)}편)")

    print("\n[유효 공개 시청 시간 추정 — 최근 12개월 롱폼만]")
    raw = sum(v * s for _, _, s, v in long_12mo) / 3600
    print(f"  조회수 × 길이 (시청률 100% 가정, 상한)  {raw:>10.1f} 시간")
    for r in (0.5, 0.35, 0.2):
        print(f"  평균 시청률 {int(r * 100):>3}% 라면              "
              f"{hours(long_12mo, r):>10.1f} 시간")

    print("\n[남은 거리]")
    for label, need_subs, need_hours in (
        ("초기 수익 창출 (팬 후원·쇼핑)", 500, 3000),
        ("정식 파트너 (광고 수익)", 1000, 4000),
    ):
        print(f"  {label}")
        print(f"    구독자   {subs:,} / {need_subs:,}"
              f"  → {max(0, need_subs - subs):,}명 부족")
        for r in (0.5, 0.35):
            got = hours(long_12mo, r)
            print(f"    시청시간 {got:,.0f} / {need_hours:,}"
                  f"  → {max(0, need_hours - got):,.0f}시간 부족"
                  f"  (시청률 {int(r * 100)}% 가정)")
    print("\n  최근 90일 공개 업로드 3편 요건: "
          f"{'충족' if public_90 >= 3 else '미충족'} ({public_90}편)")
    return 0


def cmd_retitle(youtube, channel, args) -> int:
    """RETITLE 표대로 기존 롱폼 제목과 태그를 새 서식으로 바꾼다.

    videos.update 는 지정한 part 를 통째로 갈아 끼우므로, 읽어 둔 snippet 에
    덮어써서 보낸다. 설명은 건드리지 않는다 — 타임스탬프가 들어 있고 그건
    다시 만들려면 영상을 다시 빌드해야 한다.
    """
    uploads = all_uploads(youtube, channel)
    ids = [i["contentDetails"]["videoId"] for i in uploads]
    details = video_details(youtube, ids)

    todo = []
    for vid, item in details.items():
        entry = RETITLE.get(item["snippet"]["title"].strip())
        if entry:
            todo.append((vid, item, entry))

    if not todo:
        print("바꿀 제목 없음 (이미 새 서식이거나 해당 영상이 없다).")
        return 0

    for vid, item, (new_title, tags) in todo:
        print(f"{'바꾼다' if args.apply else '바꿀 것'}: {vid}")
        print(f"    이전: {item['snippet']['title']}")
        print(f"    이후: {new_title}")
    if not args.apply:
        print(f"\n미리보기다. 실제로 바꾸려면 --apply ({len(todo)}편, "
              f"할당량 약 {len(todo) * 50}단위).")
        return 0

    for vid, item, (new_title, tags) in todo:
        snippet = dict(item["snippet"])
        for key in ("thumbnails", "publishedAt", "channelId", "channelTitle",
                    "liveBroadcastContent", "localized", "tagSuggestions"):
            snippet.pop(key, None)
        snippet["title"] = new_title
        snippet["tags"] = tags + BASE_TAGS
        youtube.videos().update(
            part="snippet", body={"id": vid, "snippet": snippet}).execute()
        print(f"바꿨다: {vid}  {new_title}")
    return 0


def error_reason(e: HttpError) -> str:
    """HttpError 에서 사유 문자열을 꺼낸다.

    403 하나로는 댓글이 꺼진 것인지 할당량이 떨어진 것인지 권한이 없는
    것인지 구분이 안 되고, 셋은 대응이 전부 다르다.
    """
    try:
        errors = json.loads(e.content.decode("utf-8"))["error"]["errors"]
        return errors[0].get("reason", "?")
    except Exception:
        return "?"


def my_comment_exists(youtube, video_id: str) -> bool:
    """이 채널이 이미 이 영상에 댓글을 달았는지."""
    resp = youtube.commentThreads().list(
        part="snippet", videoId=video_id, maxResults=100,
        textFormat="plainText").execute()
    for thread in resp.get("items", []):
        top = thread["snippet"]["topLevelComment"]["snippet"]
        if top.get("authorChannelId", {}).get("value") == CHANNEL_ID:
            return True
    return False


def cmd_comment(youtube, channel, args) -> int:
    """쇼츠에 롱폼으로 가는 채널 댓글을 단다.

    고정(pin)은 Data API 에 없다 — 스튜디오에서만 된다. 그래서 여기서 다는
    댓글은 고정되지 않은 채널 댓글이다. 고정만큼은 아니어도 설명란보다는
    눈에 띈다.
    """
    uploads = all_uploads(youtube, channel)
    ids = [i["contentDetails"]["videoId"] for i in uploads]
    details = video_details(youtube, ids)

    todo, skipped = [], []
    for vid, item in details.items():
        if item["status"].get("privacyStatus") != "public":
            continue
        if not dupe_key(item["snippet"]["title"]):
            continue  # 쇼츠만
        try:
            if my_comment_exists(youtube, vid):
                skipped.append((vid, "이미 댓글 있음"))
                continue
        except HttpError as e:
            skipped.append((vid, f"{e.resp.status} {error_reason(e)}"))
            continue
        todo.append((vid, item["snippet"]["title"]))

    # 댓글 하나가 50단위다. 43편이면 2,200단위로, 하루 10,000단위 안에서
    # 쇼츠 3편(각 1,700)과 롱폼 1편이 쓰고 남는 자리를 넘길 수 있다.
    # 나눠 돌릴 수 있게 열어 둔다 — 이미 단 곳은 건너뛰므로 다시 돌려도 된다.
    if args.limit:
        todo = todo[:args.limit]

    tally = Counter(reason for _, reason in skipped)
    for reason, n in tally.most_common():
        print(f"건너뜀 {n:>3}편: {reason}")
    for vid, title in todo:
        print(f"{'단다' if args.apply else '달 것'}: {vid}  {title[:50]}")

    if not todo:
        print("\n달 곳이 없다.")
        return 0
    if not args.apply:
        print(f"\n미리보기다. 실제로 달려면 --apply ({len(todo)}편, "
              f"할당량 약 {len(todo) * 50}단위).")
        print("\n달릴 내용:\n" + SHORTS_COMMENT)
        return 0

    done = 0
    for vid, _ in todo:
        try:
            youtube.commentThreads().insert(
                part="snippet",
                body={"snippet": {
                    "videoId": vid,
                    "topLevelComment": {
                        "snippet": {"textOriginal": SHORTS_COMMENT}},
                }},
            ).execute()
            done += 1
            print(f"달았다: {vid}")
        except HttpError as e:
            # 한 편이 막혀도 나머지는 계속 단다.
            print(f"실패(무시): {vid} — {e.resp.status} {error_reason(e)}",
                  file=sys.stderr)
    print(f"\n{done}/{len(todo)}편에 달았다. 고정은 스튜디오에서만 된다.")
    return 0


def cmd_delete(youtube, channel, args) -> int:
    if args.confirm != args.video:
        print("--confirm 에 같은 영상 ID 를 한 번 더 적어야 지운다.", file=sys.stderr)
        return 1
    info = video_details(youtube, [args.video]).get(args.video)
    if not info:
        print(f"이 채널에 없는 영상이다: {args.video}", file=sys.stderr)
        return 1
    print(f"삭제: {args.video}  {info['snippet']['title']!r}  "
          f"{info['snippet']['publishedAt']}")
    youtube.videos().delete(id=args.video).execute()
    print("삭제 완료.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("audit", help="설정·중복·재생목록 누락을 한 번에 본다")
    sub.add_parser("stats", help="수익 창출 자격까지 남은 거리")

    p = sub.add_parser("playlist-add", help="영상을 재생목록에 넣는다")
    p.add_argument("--video", required=True)
    p.add_argument("--playlist", required=True)

    p = sub.add_parser("backfill", help="재생목록 누락분을 제목 규칙대로 채운다")
    p.add_argument("--apply", action="store_true", help="실제로 넣는다")

    p = sub.add_parser("retitle", help="기존 롱폼 제목을 새 검색 서식으로")
    p.add_argument("--apply", action="store_true", help="실제로 바꾼다")

    p = sub.add_parser("comment", help="쇼츠에 롱폼 안내 댓글을 단다")
    p.add_argument("--apply", action="store_true", help="실제로 단다")
    p.add_argument("--limit", type=int, default=0,
                   help="한 번에 이 편수까지만 (할당량 분할용)")

    p = sub.add_parser("dedupe", help="같은 표현 중복분을 정리한다")
    p.add_argument("--apply", action="store_true", help="실제로 실행")
    p.add_argument("--private", action="store_true",
                   help="지우지 않고 비공개로 돌린다 (되돌릴 수 있다)")

    p = sub.add_parser("delete", help="영상 하나를 지운다")
    p.add_argument("--video", required=True)
    p.add_argument("--confirm", required=True, help="같은 영상 ID 를 다시 적을 것")

    args = ap.parse_args()
    youtube, channel = youtube_client()
    handler = {
        "audit": cmd_audit,
        "playlist-add": cmd_playlist_add,
        "backfill": cmd_backfill,
        "retitle": cmd_retitle,
        "comment": cmd_comment,
        "dedupe": cmd_dedupe,
        "delete": cmd_delete,
        "stats": cmd_stats,
    }[args.cmd]
    try:
        return handler(youtube, channel, args)
    except HttpError as e:
        print(f"YouTube API 오류: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
