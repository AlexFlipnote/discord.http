from typing import TYPE_CHECKING
from datetime import datetime

from .flags import ActivityFlags
from .enums import ActivityType

from .. import utils
from ..asset import Asset
from ..emoji import EmojiParser

if TYPE_CHECKING:
    from ..http import DiscordAPI

__all__ = (
    "ActivityTimestamps",
    "ActivityParty",
    "ActivityAssets",
    "ActivitySecrets",
    "Activity",
)


class ActivityAssets:
    def __init__(
        self,
        *,
        state: "DiscordAPI",
        application_id: int,
        data: dict
    ):
        self._state = state
        self.application_id: int = application_id

        self.large_image: Asset | None = None
        self.large_text: str | None = data.get("large_text")
        self.small_image: Asset | None = None
        self.small_text: str | None = data.get("small_text")

        self._from_data(data)

    def _from_data(self, data: dict) -> None:
        if data.get("large_image", None):
            self.large_image = Asset._from_activity_asset(
                state=self._state,
                activity_id=self.application_id,
                image=data["large_image"]
            )

        if data.get("small_image", None):
            self.small_image = Asset._from_activity_asset(
                state=self._state,
                activity_id=self.application_id,
                image=data["small_image"]
            )


class ActivityTimestamps:
    def __init__(self, *, data: dict):
        self.start: datetime | None = None
        self.end: datetime | None = None

        self._from_data(data)

    def __repr__(self) -> str:
        return f"<ActivityTimestamps start={self.start} end={self.end}>"

    def _from_data(self, data: dict) -> None:
        if data.get("start", None):
            self.start = utils.parse_time(data["start"])

        if data.get("end", None):
            self.end = utils.parse_time(data["end"])


class ActivitySecrets:
    def __init__(self, *, data: dict):
        self.join: str | None = data.get("join", None)
        self.spectate: str | None = data.get("spectate", None)
        self.match: str | None = data.get("match", None)

    def __repr__(self) -> str:
        return (
            f"<ActivitySecrets join={self.join} "
            f"spectate={self.spectate} match={self.match}>"
        )


class ActivityParty:
    def __init__(self, *, data: dict):
        self.id: str | None = data.get("id", None)
        self.current_size: int | None = None
        self.max_size: int | None = None

        if data.get("size", None):
            self.current_size = data["size"][0]
            self.max_size = data["size"][1]


class Activity:
    def __init__(
        self,
        *,
        state: "DiscordAPI",
        data: dict
    ):
        self._state = state

        self.name: str = data["name"]
        self.type: ActivityType = ActivityType(data["type"])
        self.url: str | None = data.get("url", None)
        self.created_at: datetime = utils.parse_time(data["created_at"])
        self.timestamps: ActivityTimestamps | None = None
        self.application_id: int | None = utils.get_int(data, "application_id")
        self.state: str | None = data.get("state", None)
        self.details: str | None = data.get("details", None)
        self.sync_id: str | None = data.get("sync_id", None)
        self.session_id: str | None = data.get("session_id", None)
        self.emoji: EmojiParser | None = None
        self.party: ActivityParty | None = None
        self.assets: ActivityAssets | None = None
        self.secrets: ActivitySecrets | None = None
        self.instance: bool = data.get("instance", False)
        self.flags: ActivityFlags = ActivityFlags(data.get("flags", 0))
        self.buttons: list[str] = data.get("buttons", [])

        self._from_data(data)

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f"<Activity name={self.name} type={self.type}>"

    def _from_data(self, data: dict) -> None:
        if data.get("timestamps", None):
            self.timestamps = ActivityTimestamps(data=data["timestamps"])

        if data.get("secrets", None):
            self.secrets = ActivitySecrets(data=data["secrets"])

        if data.get("party", None):
            self.party = ActivityParty(data=data["party"])

        if data.get("emoji", None):
            self.emoji = EmojiParser.from_dict(data["emoji"])

        if (
            data.get("assets", None) and
            self.application_id is not None
        ):
            self.assets = ActivityAssets(
                state=self._state,
                application_id=self.application_id,
                data=data["assets"]
            )
