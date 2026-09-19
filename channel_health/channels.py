"""어느 채널을 어떤 자격 증명으로 읽는지.

**여기 있는 것은 전부 읽기 전용이다.** 이 폴더의 코드는 유튜브에 아무것도
올리지 않고 아무것도 고치지 않는다. 업로드하는 코드와 같은 자격 증명을 쓰기
때문에, 쓰기 호출을 하나라도 들이면 그 순간 이 폴더가 발행 경로가 된다.
그러면 "읽기만 하니까 안전하다"는 전제로 둔 cron 이 위험해진다.

다른 프로젝트의 모듈을 import 하지 않는다. 이 저장소는 디렉터리마다 독립이고
(CLAUDE.md), 여기가 남의 코드를 끌어 쓰면 그쪽을 고칠 때 이 폴더가 같이
깨진다. 채널 ID 처럼 겹치는 값은 아래에 사본을 두고 원본 위치를 적어 둔다.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Channel:
    name: str            # metrics.csv 에 남는 이름
    label: str           # 사람이 읽는 이름
    client_id_env: str
    client_secret_env: str
    refresh_token_env: str
    expected_channel_id: str = ""   # 빈 값이면 아래 env 를 본다
    channel_id_env: str = ""

    def credentials_missing(self, env):
        """없는 환경변수 이름 목록. 자격 증명은 값을 절대 돌려주지 않는다."""
        names = (self.client_id_env, self.client_secret_env,
                 self.refresh_token_env)
        return [name for name in names if not (env.get(name) or "").strip()]

    def target_channel_id(self, env):
        """어느 채널이어야 하는지. 모르면 빈 문자열."""
        if self.channel_id_env:
            from_env = (env.get(self.channel_id_env) or "").strip()
            if from_env:
                return from_env
        return self.expected_channel_id


CHANNELS = (
    Channel(
        name="200y3b",
        label="@200-y3b — 매일 영어 한마디",
        client_id_env="Y3B_CLIENT_ID",
        client_secret_env="Y3B_CLIENT_SECRET",
        refresh_token_env="Y3B_REFRESH_TOKEN",
        # 원본은 channel_200y3b/scripts/upload_video.py 의 CHANNEL_ID 다.
        # import 하지 않으려고 사본을 둔다. 채널을 옮기면 두 곳을 고칠 것.
        expected_channel_id="UCeXsmdfyW4hoxgWV2K8EwFw",
        channel_id_env="Y3B_CHANNEL_ID",
    ),
    Channel(
        name="moneylogic",
        label="머니로직 MoneyLogic",
        client_id_env="MV_CLIENT_ID",
        client_secret_env="MV_CLIENT_SECRET",
        refresh_token_env="MV_REFRESH_TOKEN",
        channel_id_env="MV_CHANNEL_ID",
    ),
)

BY_NAME = {channel.name: channel for channel in CHANNELS}
