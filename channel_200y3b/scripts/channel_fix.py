"""@200-y3b 채널 뒷정리 — 감사, 재생목록 보정, 중복 영상 정리.

    python3 channel_200y3b/scripts/channel_fix.py audit
    python3 channel_200y3b/scripts/channel_fix.py backfill [--apply]
    python3 channel_200y3b/scripts/channel_fix.py playlist-add --video ID --playlist "제목"
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
import os
import re
import sys
from collections import defaultdict

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
    (re.compile(r"^이번 주 영어 표현 \d+개 몰아듣기"), "주간 복습 몰아듣기"),
    (re.compile(r"^영어 쉐도잉 훈련 \d+문장"), "쉐도잉 트레이닝"),
    (re.compile(r"^자면서 듣는 영어 표현 \d+개"), "자면서 듣는 영어"),
    (re.compile(r"^이번 달 영어 표현 \d+개 총정리"), "월간 총정리"),
    (re.compile(r"^영어 표현 총정리 Vol\."), "매일 영어 한마디 · 주간 표현 모음"),
    (re.compile(r"^실생활 영어 표현 \d+개 모음 Vol\."), "매일 영어 한마디 · 주간 표현 모음"),
    (re.compile(r"^.+ 영어 표현 \d+개 총정리"), "상황별 영어 표현"),
]


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
    print(f"\n[중복] 같은 표현으로 두 번 이상 올라간 묶음: {len(dupes)}건")
    for key, vids in dupes.items():
        rows = sorted(
            ((v, details[v]["snippet"]["publishedAt"],
              details[v]["snippet"]["title"]) for v in vids),
            key=lambda r: r[1],
        )
        print(f"  {key!r}")
        for i, (vid, pub, title) in enumerate(rows):
            mark = "지킴" if i == 0 else "삭제 후보"
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
            victims.append((key, vid, details[vid]["snippet"]["publishedAt"]))

    if not victims:
        print("중복 없음.")
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

    p = sub.add_parser("playlist-add", help="영상을 재생목록에 넣는다")
    p.add_argument("--video", required=True)
    p.add_argument("--playlist", required=True)

    p = sub.add_parser("backfill", help="재생목록 누락분을 제목 규칙대로 채운다")
    p.add_argument("--apply", action="store_true", help="실제로 넣는다")

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
        "dedupe": cmd_dedupe,
        "delete": cmd_delete,
    }[args.cmd]
    try:
        return handler(youtube, channel, args)
    except HttpError as e:
        print(f"YouTube API 오류: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
