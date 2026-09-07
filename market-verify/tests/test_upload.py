import pytest

from src import upload


def _env(**kwargs):
    base = {
        upload.CLIENT_ID_ENV: "id",
        upload.CLIENT_SECRET_ENV: "secret",
        upload.REFRESH_TOKEN_ENV: "refresh",
    }
    base.update(kwargs)
    return base


def test_missing_credentials_are_named():
    problem = upload.check_credentials({})
    assert upload.CLIENT_ID_ENV in problem
    assert upload.REFRESH_TOKEN_ENV in problem


def test_complete_credentials_pass():
    assert upload.check_credentials(_env()) is None


def test_sibling_channel_env_names_work_as_fallback():
    env = {"YT_CLIENT_ID": "id", "YT_CLIENT_SECRET": "s", "YT_REFRESH_TOKEN": "r"}
    assert upload.check_credentials(env) is None


def test_blank_values_count_as_missing():
    assert upload.check_credentials(_env(**{upload.REFRESH_TOKEN_ENV: "   "})) is not None


def test_body_defaults_to_private():
    body = upload.build_body("제목", "설명", ["태그"], "private")
    assert body["status"]["privacyStatus"] == "private"
    assert body["status"]["selfDeclaredMadeForKids"] is False


def test_body_rejects_an_unknown_privacy_value():
    with pytest.raises(ValueError):
        upload.build_body("제목", "설명", [], "secret-mode")


def test_body_trims_overlong_fields():
    body = upload.build_body("가" * 300, "나" * 9000, ["t"] * 50, "private")
    assert len(body["snippet"]["title"]) == 100
    assert len(body["snippet"]["description"]) == 5000
    assert len(body["snippet"]["tags"]) == 20


class FakeChannels:
    def __init__(self, ids):
        self.ids = ids

    def list(self, **kwargs):
        class R:
            def execute(_):
                return {"items": [{"id": i} for i in self.ids]}
        return R()


class FakeYouTube:
    def __init__(self, ids):
        self._channels = FakeChannels(ids)

    def channels(self):
        return self._channels


def test_channel_guard_blocks_the_wrong_account():
    """채널을 여러 개 운영한다. 토큰을 잘못 넣으면 남의 채널에 올라간다."""
    with pytest.raises(upload.UploadConfigError) as excinfo:
        upload.assert_target_channel(FakeYouTube(["UC_other"]), "UC_mine")
    assert "업로드하지 않는다" in str(excinfo.value)


def test_channel_guard_passes_the_right_account():
    assert upload.assert_target_channel(FakeYouTube(["UC_mine"]), "UC_mine") == "UC_mine"


def test_channel_guard_is_skipped_when_unset():
    assert upload.assert_target_channel(None, "") is None
