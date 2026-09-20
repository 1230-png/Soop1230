"""주제별 조각을 모아 data/phrases.json 을 만든다. 어긋나면 멈춘다.

머니로직은 제목에 `nan%` 가 박힌 영상을 여드레 동안 공개로 올렸다. 원인은
`float('nan') >= 0` 이 False 라 항상 "하락"으로 갈라진 것이었는데, 진짜 문제는
**아무도 값을 보지 않았다는 것**이다. 깨진 값이 파이프라인 끝까지 흘러가
발행됐다.

그래서 이 파일은 문장 은행이 영상 파이프라인에 들어가기 전에 선다. 여기서
막는 것이 나중에 영상에서 □□□ 를 보는 것보다 싸다.

    python3 channel_jp/build_bank.py            # 검사하고 쓴다
    python3 channel_jp/build_bank.py --check    # 검사만 한다 (CI용)
"""

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARTS_DIR = HERE / "data" / "_parts"
OUT_PATH = HERE / "data" / "phrases.json"

FIELDS = ("ja", "yomi", "ko", "ex_ja", "ex_yomi", "ex_ko", "topic")

# 일본어 글자: 히라가나·가타카나·한자. 한글과 겹치는 구간이 없다.
JAPANESE = re.compile(r"[぀-ゟ゠-ヿ一-鿿]")
# 한글: 완성형 음절 + 자모. 읽기·뜻 칸은 이것만 있어야 한다.
HANGUL = re.compile(r"[가-힣ᄀ-ᇿ㄰-㆏]")

# 일본어 칸에 들어와도 되는 로마자. Wi-Fi·M 사이즈처럼 실제로 그렇게 쓰는
# 표기가 있어서 로마자 자체를 막지는 않는다. 막는 것은 한글이다.


class BankError(Exception):
    """문장 은행이 쓸 수 없는 상태. 메시지에 어느 문장인지 담는다."""


def _describe(part: str, index: int, entry: dict) -> str:
    """사람이 파일에서 찾아갈 수 있게. id 는 아직 없으므로 원문을 쓴다."""
    return f"{part} [{index}] {entry.get('ja', '(ja 없음)')!r}"


def check_entry(part: str, index: int, entry: dict) -> list:
    """한 문장의 문제 목록. 빈 목록이면 통과."""
    problems = []
    where = _describe(part, index, entry)

    for field in FIELDS:
        value = entry.get(field)
        if not isinstance(value, str) or not value.strip():
            problems.append(f"{where}: {field} 가 비었다")

    if problems:                    # 칸이 비었으면 내용 검사는 의미가 없다
        return problems

    for field in ("ja", "ex_ja"):
        text = entry[field]
        if not JAPANESE.search(text):
            problems.append(f"{where}: {field} 에 일본어 글자가 없다 — {text!r}")
        if HANGUL.search(text):
            # 07-관광 초안에서 실제로 났다. ja 칸에 한국어 문장을 적어 두면
            # TTS 가 일본어 음성으로 한글을 읽으려다 무음이 된다.
            problems.append(f"{where}: {field} 에 한글이 섞였다 — {text!r}")

    for field in ("yomi", "ex_yomi", "ko", "ex_ko"):
        text = entry[field]
        if not HANGUL.search(text):
            problems.append(f"{where}: {field} 에 한글이 없다 — {text!r}")
        if JAPANESE.search(text):
            # 05-교통 초안에서 'ん' 하나가 읽기 칸에 남아 있었다. 카드에는
            # 그대로 찍히고, 학습자는 그게 한글인 줄 안다.
            problems.append(f"{where}: {field} 에 일본어 글자가 섞였다 — {text!r}")

    return problems


def load_parts() -> list:
    """조각 파일을 이름순으로 읽는다. 순서가 곧 영상에서의 순서다."""
    paths = sorted(PARTS_DIR.glob("*.json"))
    if not paths:
        raise BankError(f"{PARTS_DIR} 에 조각 파일이 없다")

    entries, problems = [], []
    for path in paths:
        try:
            part = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise BankError(f"{path.name}: JSON 을 읽을 수 없다 — {error}") from error
        if not isinstance(part, list):
            raise BankError(f"{path.name}: 목록이어야 한다")
        for index, entry in enumerate(part):
            problems += check_entry(path.name, index, entry)
            entries.append(entry)

    if problems:
        raise BankError("\n".join(problems))
    return entries


def drop_duplicates(entries: list) -> tuple:
    """같은 일본어 문장은 한 번만 남긴다.

    중복을 지우는 것이지 오류로 세우지 않는다 — 조각을 주제별로 나눠 쓰면
    같은 표현이 두 주제에 걸치는 일이 자연스럽게 생긴다(「お世話になりました」가
    자기소개와 호텔 양쪽에 있었다). 다만 **몇 개가 사라졌는지는 말한다.**
    조용히 줄면 150문장을 넣었는데 영상이 짧아진 이유를 못 찾는다.
    """
    seen, kept, dropped = set(), [], []
    for entry in entries:
        if entry["ja"] in seen:
            dropped.append(entry["ja"])
            continue
        seen.add(entry["ja"])
        kept.append(entry)
    return kept, dropped


def assign_ids(entries: list) -> list:
    """J001 부터 매긴다. used.json 이 이 값으로 '쓴 문장'을 기억한다."""
    return [{"id": f"J{number:03d}", **entry}
            for number, entry in enumerate(entries, start=1)]


def moved_ids(before: list, after: list) -> list:
    """뜻이 바뀐 번호 목록.

    번호는 위치로 매겨진다(assign_ids). 그래서 앞쪽 조각에 문장을 하나
    끼워 넣으면 그 뒤가 전부 한 칸씩 밀리고, used.json 에 적힌 J001 이
    **다른 문장**을 가리키게 된다. 이미 두 편이 나간 뒤라 그 순간 "쓴 문장"과
    "안 쓴 문장"이 통째로 뒤바뀐다 — 영상은 멀쩡해 보이고 아무도 모른다.

    그래서 은행을 늘릴 때는 **뒤에 붙인다.** 조각 파일 이름이 정렬 순서이므로
    기존 것보다 뒤에 오는 이름(13-, 14-, ...)을 쓰면 기존 번호는 그대로 있고
    새 문장이 다음 번호를 받는다.
    """
    old_by_id = {entry["id"]: entry["ja"] for entry in before}
    return [entry["id"] for entry in after
            if entry["id"] in old_by_id and old_by_id[entry["id"]] != entry["ja"]]


def previous_entries() -> list:
    """직전에 쓴 은행. 없으면 빈 목록 — 첫 빌드를 막지 않는다."""
    if not OUT_PATH.exists():
        return []
    try:
        return json.loads(OUT_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true",
                        help="검사만 하고 파일을 쓰지 않는다")
    args = parser.parse_args()

    try:
        entries = load_parts()
    except BankError as error:
        print("문장 은행을 쓸 수 없다:\n" + str(error), file=sys.stderr)
        return 1

    entries, dropped = drop_duplicates(entries)
    entries = assign_ids(entries)

    moved = moved_ids(previous_entries(), entries)
    if moved:
        print(
            "이미 나간 번호의 뜻이 바뀐다:\n  "
            + ", ".join(moved[:10])
            + (f" 외 {len(moved) - 10}개" if len(moved) > 10 else "")
            + "\n  used.json 이 이 번호로 '쓴 문장'을 기억한다. 지금 쓰면"
              " 발행한 편의 기록이 다른 문장을 가리킨다.\n"
              "  은행을 늘릴 때는 뒤에 붙일 것 — 기존 것보다 뒤에 오는 이름"
              "(13-, 14-, ...)의 조각 파일을 만들면 기존 번호는 그대로다.\n"
              "  정말로 다시 매겨야 한다면 data/phrases.json 을 지우고 돌릴 것"
              " (그 전에 used.json 을 어떻게 할지 정할 것).",
            file=sys.stderr)
        return 1

    for text in dropped:
        print(f"  · 중복이라 뺐다: {text}")

    topics = {}
    for entry in entries:
        topics[entry["topic"]] = topics.get(entry["topic"], 0) + 1
    for topic, count in topics.items():
        print(f"  {topic}: {count}개")
    print(f"합계 {len(entries)}개")

    if args.check:
        print("검사만 했다. 파일은 그대로다.")
        return 0

    OUT_PATH.write_text(
        json.dumps(entries, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8")
    print(f"{OUT_PATH.relative_to(HERE.parent)} 에 썼다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
