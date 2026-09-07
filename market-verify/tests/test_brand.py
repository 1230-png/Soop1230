from src import brand


def test_channel_name_is_set():
    assert brand.NAME == "머니로직"
    assert brand.NAME_EN == "MoneyLogic"


def test_three_content_pillars_are_recorded():
    """채널은 세 갈래다. market-verify 는 그중 일부만 다룬다는 사실을 남겨 둔다."""
    assert len(brand.PILLARS) == 3
    assert any("토크노믹스" in p for p in brand.PILLARS)
    assert any("매크로" in p for p in brand.PILLARS)
    assert any("리밸런싱" in p for p in brand.PILLARS)


def test_disclaimer_covers_what_the_regulation_needs():
    assert "추천하거나 권유하지 않습니다" in brand.DISCLAIMER
    assert "판단과 책임은 투자자 본인에게 있습니다" in brand.DISCLAIMER


def test_video_description_appends_the_channel_disclaimer():
    text = brand.video_description("이번 영상 설명입니다.")
    assert text.startswith("이번 영상 설명입니다.")
    assert text.endswith(brand.DISCLAIMER)


def test_video_description_survives_an_empty_script_section():
    assert brand.video_description("") == brand.DISCLAIMER
    assert brand.video_description("   \n ") == brand.DISCLAIMER


def test_tags_lead_with_the_channel_name():
    assert brand.TAGS[0] == brand.NAME
    assert len(brand.TAGS) <= 20
