"""표현 뱅크로 인쇄용 문장집을 만든다.

**임계값이 없는 유일한 수익 경로다.** 파트너 프로그램은 구독자와 시청 시간을
채워야 열리지만 이것은 오늘 팔 수 있다. 표현 뱅크가 이미 있으므로 새로
만들 내용도 없다.

PDF 를 직접 쓰지 않고 **인쇄용 HTML** 을 낸다. reportlab 을 붙이면 한글 폰트를
또 한 벌 관리해야 하고(CLAUDE.md 가 matplotlib 을 막은 것과 같은 이유), 브라우저
인쇄는 시스템에 깔린 한글 폰트를 그대로 쓴다. 브라우저에서 Ctrl+P → PDF 로
저장하면 끝이고 의존성이 늘지 않는다.

**무엇을 담을지는 장사의 문제다.** 영상으로 이미 공짜로 푼 1,000개를 그대로
묶으면 살 이유가 없다. 그래서 고르는 축(`--topic`, `--limit`, `--exclude-used`)만
만들어 두고 기본값으로 전부를 내지 않는다. 무엇을 팔지는 사람이 정한다.
"""

import argparse
import csv
import html
import json
from collections import OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BANK_PATH = ROOT / "phrase_bank.json"
USED_LOG = ROOT.parent / "used_log.csv"

DEFAULT_TITLE = "매일 영어 한마디 — 문장집"
CHANNEL = "@200-y3b"

# 한 주제에서 이보다 적게 남으면 묶음으로 세우지 않는다. 표지에 주제가
# 늘어서 있는데 열어 보니 두 문장뿐이면 산 사람이 속았다고 느낀다.
MIN_PER_TOPIC = 3

STYLE = """
@page { size: A4; margin: 16mm 14mm; }
* { box-sizing: border-box; }
body { font-family: 'Noto Sans KR', 'Malgun Gothic', 'Apple SD Gothic Neo', sans-serif;
       color: #1a1a1a; line-height: 1.5; margin: 0; }
.cover { height: 260mm; display: flex; flex-direction: column;
         justify-content: center; page-break-after: always; }
.cover .kicker { color: #0e6c8c; font-size: 13pt; font-weight: 700;
                 letter-spacing: .08em; }
.cover h1 { font-size: 34pt; line-height: 1.25; margin: 10pt 0 14pt; }
.cover .sub { color: #555; font-size: 13pt; margin: 0 0 28pt; }
.cover .how { border-left: 4px solid #0e6c8c; padding: 4pt 0 4pt 12pt;
              color: #333; font-size: 11pt; }
.cover .brand { margin-top: auto; color: #888; font-size: 10pt; }
.toc { page-break-after: always; }
.toc h2 { border: 0; }
.toc ol { columns: 2; column-gap: 12mm; padding-left: 16pt; font-size: 11pt; }
.toc li { margin: 3pt 0; }
h2 { font-size: 15pt; margin: 0 0 8pt; padding-bottom: 4pt;
     border-bottom: 2px solid #1a1a1a; }
section { page-break-before: always; }
.items { columns: 2; column-gap: 9mm; column-rule: 1px solid #eee; }
.item { padding: 5pt 0 6pt; border-bottom: 1px solid #eee;
        break-inside: avoid; page-break-inside: avoid; }
.en { font-size: 11pt; font-weight: 700; }
.en::before { content: "☐ "; color: #0e6c8c; font-weight: 400; }
.ko { font-size: 9.5pt; color: #333; }
.ex { font-size: 8.5pt; color: #777; margin-top: 2pt; }
.id { font-size: 7pt; color: #bbb; float: right; }
footer { margin-top: 20pt; padding-top: 8pt; border-top: 1px solid #ddd;
         font-size: 8.5pt; color: #888; }
@media print { a { text-decoration: none; color: inherit; } }
"""


def load_bank(path=BANK_PATH):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def used_ids(path=USED_LOG):
    """영상으로 이미 나간 표현 id.

    **열 이름으로 읽는다.** 처음에 0번 열을 집었다가 phrase_id 가 아니라
    date 를 모으고 있었다 — 21개를 뺐다고 찍으면서 한 개도 빠지지 않았다.
    제목에 쉼표가 들어 있어 split(",") 로는 열 위치도 믿을 수 없다.

    파일이 없으면 빈 집합이다 — 없다고 멈추지 않는다. 이 도구는 발행
    경로가 아니라서 여기서 멈추면 얻는 것 없이 못 쓰게만 된다.
    """
    path = Path(path)
    if not path.exists():
        return set()
    with path.open(encoding="utf-8", newline="") as handle:
        rows = csv.DictReader(handle)
        if "phrase_id" not in (rows.fieldnames or []):
            raise ValueError(
                f"{path} 에 phrase_id 열이 없다: {rows.fieldnames}. "
                "열 이름이 바뀌었다면 여기도 같이 고칠 것 — 조용히 빈 집합을 "
                "돌려주면 이미 나간 표현이 그대로 상품에 들어간다.")
        return {(row.get("phrase_id") or "").strip()
                for row in rows if (row.get("phrase_id") or "").strip()}


def select(bank, topic=None, limit=None, exclude=()):
    """담을 표현을 고른다. 뱅크의 순서를 유지한다."""
    exclude = set(exclude)
    chosen = [item for item in bank
              if item.get("id") not in exclude
              and (topic is None or item.get("topic") == topic)]
    return chosen[:limit] if limit else chosen


def group_by_topic(items, min_per_topic=MIN_PER_TOPIC):
    """주제별로 묶는다. 너무 적은 주제는 '그 밖의 표현'으로 합친다."""
    buckets = OrderedDict()
    for item in items:
        buckets.setdefault(item.get("topic") or "그 밖의 표현", []).append(item)

    kept, spare = OrderedDict(), []
    for name, group in buckets.items():
        if len(group) >= min_per_topic:
            kept[name] = group
        else:
            spare.extend(group)
    if spare:
        kept.setdefault("그 밖의 표현", []).extend(spare)
    return kept


def _item_html(item):
    out = [f'<div class="item"><span class="id">{html.escape(item.get("id", ""))}</span>',
           f'<div class="en">{html.escape(item.get("phrase_en", ""))}</div>',
           f'<div class="ko">{html.escape(item.get("meaning_ko", ""))}</div>']
    example_en = item.get("example_en")
    if example_en:
        example_ko = item.get("example_ko", "")
        out.append(f'<div class="ex">{html.escape(example_en)}<br>'
                   f'{html.escape(example_ko)}</div>')
    out.append("</div>")
    return "\n".join(out)


def render(items, title=DEFAULT_TITLE, min_per_topic=MIN_PER_TOPIC):
    """인쇄용 HTML 한 장. 표지 → 목차 → 주제마다 새 쪽, 2단.

    돈을 받는 물건이라 영상 설명란처럼 보이면 안 된다. 표지와 목차가 있어야
    "책"으로 읽히고, 2단으로 앉혀야 쪽수가 절반이 되어 인쇄해 쓸 수 있다.
    ☐ 는 외운 표현을 지워 나가라는 칸이다 — 영상에는 없는, 이것만의 쓸모다.
    """
    groups = group_by_topic(items, min_per_topic)
    toc = "".join(f"<li>{html.escape(name)} <small>({len(group)})</small></li>"
                  for name, group in groups.items())
    body = []
    for name, group in groups.items():
        body.append(f"<section><h2>{html.escape(name)} "
                    f"<small>({len(group)})</small></h2><div class=\"items\">")
        body.extend(_item_html(item) for item in group)
        body.append("</div></section>")
    days = max(1, -(-len(items) // 10))
    return f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>{STYLE}</style></head><body>
<div class="cover">
  <div class="kicker">매일 영어 한마디</div>
  <h1>{html.escape(title)}</h1>
  <div class="sub">{html.escape(CHANNEL)} · 표현 {len(items)}개 · 주제 {len(groups)}갈래</div>
  <div class="how">하루 10문장씩 {days}일이면 끝납니다.<br>
  소리 내어 읽고, 외운 표현은 ☐ 에 표시하세요.<br>
  예문까지 읽어야 언제 쓰는 말인지 감이 잡힙니다.</div>
  <div class="brand">youtube.com/{html.escape(CHANNEL)} — 표현마다 원어민 발음 쇼츠가 있습니다.</div>
</div>
<div class="toc"><h2>목차</h2><ol>{toc}</ol></div>
{"".join(body)}
<footer>© {html.escape(CHANNEL)} 매일 영어 한마디. 개인 학습용으로만 사용할 수 있으며 재배포를 금합니다.</footer>
</body></html>
"""


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--out", default="phrasebook.html")
    parser.add_argument("--title", default=DEFAULT_TITLE)
    parser.add_argument("--topic", help="이 주제만")
    parser.add_argument("--limit", type=int, help="앞에서 이만큼만")
    parser.add_argument("--exclude-used", action="store_true",
                        help="영상으로 이미 나간 표현을 뺀다")
    parser.add_argument("--bank-path", default=str(BANK_PATH))
    args = parser.parse_args(argv)

    bank = load_bank(args.bank_path)
    exclude = used_ids() if args.exclude_used else set()
    items = select(bank, args.topic, args.limit, exclude)
    if not items:
        print("담을 표현이 없다. --topic 이름이나 --limit 을 볼 것.")
        return 1

    Path(args.out).write_text(render(items, args.title), encoding="utf-8")
    print(f"문장집: {args.out} — 표현 {len(items)}개")
    if exclude:
        print(f"  영상으로 나간 {len(exclude)}개를 뺐다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
