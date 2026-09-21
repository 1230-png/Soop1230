"""채널 설명·키워드를 어떻게 바꿀지 정하는 부분. 네트워크를 타지 않는다.

유튜브를 부르는 쪽은 한 줄이고 틀리면 눈에 보인다. 조용히 틀리는 쪽은
"무엇을 덮어쓸지 정하는" 이 판단이다. 이 채널은 새로 만든 것이 아니라
@Rush22 의 방향을 바꾼 것이라, **설명란에 예전 문구가 이미 들어 있다.**
그걸 실수로 덮어쓰거나, 반대로 영영 못 바꾸거나 하는 두 가지를 다 막아야 한다.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import channel_settings as settings  # noqa: E402

WANTED = {
    "name": "지구의 오늘",
    "description": "지구가 오늘 어떻게 움직였는지를 관측 자료 그대로 봅니다.",
    "keywords": ["지진", "데이터 시각화", "USGS"],
}
OLD = {"channel": {"title": "머니러시",
                   "description": "예전 채널 설명",
                   "keywords": "쇼츠 개발"}}


def test_빈_채널은_전부_채운다():
    branding, changes = settings.plan_changes({}, WANTED, force=False)
    channel = branding["channel"]
    assert channel["title"] == "지구의 오늘"
    assert channel["description"] == WANTED["description"]
    assert channel["defaultLanguage"] == "ko"
    assert not any(c.startswith("[건너뜀]") for c in changes)


def test_예전_문구는_force_없이_안_덮는다():
    """실수로 돌렸을 때 남의 글을 지우지 않는다."""
    branding, changes = settings.plan_changes(OLD, WANTED, force=False)
    assert branding["channel"]["title"] == "머니러시"
    assert branding["channel"]["description"] == "예전 채널 설명"
    assert sum(1 for c in changes if c.startswith("[건너뜀]")) == 3


def test_force_면_예전_문구를_갈아_끼운다():
    """방향을 바꾸는 경우다. 이 채널에서는 이쪽이 정상 경로다."""
    branding, changes = settings.plan_changes(OLD, WANTED, force=True)
    channel = branding["channel"]
    assert channel["title"] == "지구의 오늘"
    assert channel["description"] == WANTED["description"]
    assert "지진" in channel["keywords"]
    assert not any(c.startswith("[건너뜀]") for c in changes)


def test_이미_맞으면_아무것도_안_한다():
    ready = {"channel": {"title": WANTED["name"],
                         "description": WANTED["description"],
                         "keywords": settings.format_keywords(WANTED["keywords"]),
                         "defaultLanguage": "ko"}}
    _, changes = settings.plan_changes(ready, WANTED, force=True)
    assert changes == []


def test_공백_있는_키워드만_따옴표로():
    """전부 묶으면 500자 한도에서 말마다 두 글자씩 그냥 버린다."""
    out = settings.format_keywords(["지진", "데이터 시각화"])
    assert out == '지진 "데이터 시각화"'


def test_한도를_넘으면_보내기_전에_멈춘다():
    """넘긴 채로 보내면 유튜브가 요청 전체를 거절해 멀쩡한 칸까지 안 들어간다."""
    with pytest.raises(settings.SettingsError):
        settings.plan_changes({}, {**WANTED, "description": "가" * 1001}, force=True)
    with pytest.raises(settings.SettingsError):
        settings.plan_changes({}, {**WANTED, "keywords": ["가" * 501]}, force=True)


def test_실제_channel_yaml_이_한도_안에_든다():
    """저장소에 적어 둔 값이 그대로 들어가는지. 문구를 늘리다 넘기기 쉽다."""
    wanted = settings.load_channel()
    _, changes = settings.plan_changes({}, wanted, force=True)
    assert changes


def test_채널_ID_가_다르면_멈춘다():
    """남의 채널 설명을 갈아 끼우지 않는다."""
    channel = {"id": "UC_real", "snippet": {"title": "지구의 오늘"}}
    with pytest.raises(settings.SettingsError):
        settings.assert_right_channel(channel, {"RUSH_CHANNEL_ID": "UC_other"})
    with pytest.raises(settings.SettingsError):
        settings.assert_right_channel(channel, {})
    settings.assert_right_channel(channel, {"RUSH_CHANNEL_ID": "UC_real"})
