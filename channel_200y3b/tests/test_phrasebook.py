"""문장집 — 무엇을 담고 무엇을 빼는가."""

import json

import pytest

import phrasebook


def phrase(pid, topic="일상 표현", **kwargs):
    base = {"id": pid, "phrase_en": "Break a leg.", "meaning_ko": "행운을 빈다",
            "example_en": "Break a leg!", "example_ko": "행운을 빌어!",
            "topic": topic}
    base.update(kwargs)
    return base


# --- 이미 나간 표현 빼기 -----------------------------------------------

def test_used_ids_reads_the_phrase_id_column_not_the_first_one(tmp_path):
    """처음에 0번 열(date)을 집어서, 뺐다고 찍으면서 한 개도 빠지지 않았다."""
    log = tmp_path / "used_log.csv"
    log.write_text(
        "date,phrase_id,phrase_en,video_title\n"
        "2026-08-19,E001,How's it going?,\"제목, 쉼표 있음\"\n"
        "2026-08-19,E002,I'm on it.,제목\n",
        encoding="utf-8")
    assert phrasebook.used_ids(log) == {"E001", "E002"}


def test_a_missing_log_is_not_an_error(tmp_path):
    assert phrasebook.used_ids(tmp_path / "없음.csv") == set()


def test_a_renamed_column_is_loud_instead_of_silently_empty(tmp_path):
    """조용히 빈 집합을 주면 이미 나간 표현이 그대로 상품에 들어간다."""
    log = tmp_path / "used_log.csv"
    log.write_text("date,expression_id\n2026-08-19,E001\n", encoding="utf-8")
    with pytest.raises(ValueError):
        phrasebook.used_ids(log)


def test_excluded_ids_are_actually_removed():
    bank = [phrase("E001"), phrase("E002"), phrase("E003")]
    kept = phrasebook.select(bank, exclude={"E002"})
    assert [item["id"] for item in kept] == ["E001", "E003"]


# --- 고르기 ------------------------------------------------------------

def test_a_topic_filter_keeps_only_that_topic():
    bank = [phrase("E001", "호텔"), phrase("E002", "식당·카페")]
    assert [x["id"] for x in phrasebook.select(bank, topic="호텔")] == ["E001"]


def test_a_limit_takes_from_the_front_and_keeps_bank_order():
    bank = [phrase(f"E{n:03d}") for n in range(1, 6)]
    assert [x["id"] for x in phrasebook.select(bank, limit=2)] == ["E001", "E002"]


# --- 묶기 --------------------------------------------------------------

def test_a_thin_topic_is_folded_into_the_leftovers():
    """주제가 표지에 늘어서 있는데 열어 보니 두 문장이면 속았다고 느낀다."""
    bank = ([phrase(f"A{n}", "호텔") for n in range(5)]
            + [phrase("B1", "은행·관공서")])
    groups = phrasebook.group_by_topic(bank, min_per_topic=3)
    assert "은행·관공서" not in groups
    assert len(groups["그 밖의 표현"]) == 1
    assert len(groups["호텔"]) == 5


def test_no_leftover_section_when_every_topic_is_thick_enough():
    bank = [phrase(f"A{n}", "호텔") for n in range(5)]
    assert list(phrasebook.group_by_topic(bank, min_per_topic=3)) == ["호텔"]


# --- 내보내기 ----------------------------------------------------------

def test_the_html_escapes_what_comes_from_the_bank():
    bank = [phrase("E001", phrase_en="<script>alert(1)</script>")]
    out = phrasebook.render(bank)
    assert "<script>alert(1)</script>" not in out
    assert "&lt;script&gt;" in out


def test_the_page_carries_the_channel_and_a_count():
    out = phrasebook.render([phrase("E001")], title="제목")
    assert phrasebook.CHANNEL in out
    assert "표현 1개" in out


def test_an_entry_without_an_example_still_renders():
    bank = [phrase("E001", example_en=None, example_ko=None)]
    assert "행운을 빈다" in phrasebook.render(bank)


def test_the_real_bank_loads_and_renders(tmp_path):
    """뱅크 형식이 바뀌면 여기서 걸린다."""
    bank = phrasebook.load_bank()
    assert len(bank) > 100
    out = phrasebook.render(phrasebook.select(bank, limit=20))
    assert out.startswith("<!DOCTYPE html>")


def test_main_refuses_an_empty_selection(tmp_path, capsys):
    bank = tmp_path / "bank.json"
    bank.write_text(json.dumps([phrase("E001", "호텔")]), encoding="utf-8")
    code = phrasebook.main(["--bank-path", str(bank), "--topic", "없는주제",
                            "--out", str(tmp_path / "x.html")])
    assert code == 1
    assert "담을 표현이 없다" in capsys.readouterr().out
