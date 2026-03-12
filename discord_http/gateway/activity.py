from typing import TYPE_CHECKING
from datetime import datetime

from .. import utils
from ..asset import Asset
from ..emoji import EmojiParser

from .flags import ActivityFlags
from .enums import ActivityType

if TYPE_CHECKING:
    from ..http import DiscordAPI

__all__ = (
    "Activity",
    "ActivityAssets",
    "ActivityParty",
    "ActivitySecrets",
    "ActivityTimestamps",
)


class ActivityAssets:
    """ Represents the assets of an activity. """
    __slots__ = (
        "_state",
        "application_id",
        "large_image",
        "large_text",
        "small_image",
        "small_text",
    )

    def __init__(
        self,
        *,
        state: "DiscordAPI",
        application_id: int,
        data: dict
    ):
        self._state = state

        self.application_id: int = application_id
        """ The ID of the application this activity belongs to. """

        self.large_image: Asset | None = None
        """ The large image asset of the activity, if any. """

        self.large_text: str | None = data.get("large_text")
        """ The text for the large image, if any. """

        self.small_image: Asset | None = None
        """ The small image asset of the activity, if any. """

        self.small_text: str | None = data.get("small_text")
        """ The text for the small image, if any. """

        self._from_data(data)

    def _from_data(self, data: dict) -> None:
        if data.get("large_image"):
            self.large_image = Asset._from_activity_asset(
                state=self._state,
                activity_id=self.application_id,
                image=data["large_image"]
            )

        if data.get("small_image"):
            self.small_image = Asset._from_activity_asset(
                state=self._state,
                activity_id=self.application_id,
                image=data["small_image"]
            )


class ActivityTimestamps:
    """ Represents the timestamps of an activity. """
    __slots__ = (
        "end",
        "start",
    )

    def __init__(self, *, data: dict):
        self.start: datetime | None = None
        """ The start time of the activity, if any. """

        self.end: datetime | None = None
        """ The end time of the activity, if any. """

        self._from_data(data)

    def __repr__(self) -> str:
        return f"<ActivityTimestamps start={self.start} end={self.end}>"

    def _from_data(self, data: dict) -> None:
        if data.get("start"):
            self.start = utils.parse_time(data["start"])

        if data.get("end"):
            self.end = utils.parse_time(data["end"])


class ActivitySecrets:
    """ Represents the secrets of an activity. """

    __slots__ = (
        "join",
        "match",
        "spectate",
    )

    def __init__(self, *, data: dict):
        self.join: str | None = data.get("join")
        """ The secret for joining the activity, if any. """

        self.spectate: str | None = data.get("spectate")
        """ The secret for spectating the activity, if any. """

        self.match: str | None = data.get("match")
        """ The secret for joining a specific match, if any. """

    def __repr__(self) -> str:
        return (
            f"<ActivitySecrets join={self.join} "
            f"spectate={self.spectate} match={self.match}>"
        )


class ActivityParty:
    """ Represents the party of an activity. """

    __slots__ = (
        "current_size",
        "id",
        "max_size",
    )

    def __init__(self, *, data: dict):
        self.id: str | None = data.get("id")
        """ The ID of the party, if any. """

        self.current_size: int | None = None
        """ The current size of the party, if any. """

        self.max_size: int | None = None
        """ The maximum size of the party, if any. """

        if data.get("size"):
            self.current_size = data["size"][0]
            self.max_size = data["size"][1]


class Activity:
    """ Represents an activity. """

    __slots__ = (
        "_raw_type",
        "_state",
        "application_id",
        "assets",
        "buttons",
        "created_at",
        "details",
        "emoji",
        "flags",
        "instance",
        "name",
        "party",
        "secrets",
        "session_id",
        "state",
        "sync_id",
        "timestamps",
        "url",
    )

    def __init__(
        self,
        *,
        state: "DiscordAPI",
        data: dict
    ):
        self._state = state
        self._raw_type: int = data["type"]

        self.name: str = data["name"]
        """ The name of the activity. """

        self.url: str | None = data.get("url")
        """ The URL of the activity, if any. """

        self.created_at: datetime = utils.parse_time(data["created_at"])
        """ The time the activity was created at. """

        self.timestamps: ActivityTimestamps | None = None
        """ The timestamps of the activity, if any. """

        self.application_id: int | None = utils.get_int(data, "application_id")
        """ The ID of the application this activity belongs to, if any. """

        self.state: str | None = data.get("state")
        """ The state of the activity, if any. """

        self.details: str | None = data.get("details")
        """ The details of the activity, if any. """

        self.sync_id: str | None = data.get("sync_id")
        """ The sync ID of the activity, if any. """

        self.session_id: str | None = data.get("session_id")
        """ The session ID of the activity, if any. """

        self.emoji: EmojiParser | None = None
        """ The emoji of the activity, if any. """

        self.party: ActivityParty | None = None
        """ The party of the activity, if any. """

        self.assets: ActivityAssets | None = None
        """ The assets of the activity, if any. """

        self.secrets: ActivitySecrets | None = None
        """ The secrets of the activity, if any. """

        self.instance: bool = data.get("instance", False)
        """ Whether the activity is an instance, if any. """

        self.flags: ActivityFlags = ActivityFlags(data.get("flags", 0))
        """ The flags of the activity, if any. """

        self.buttons: list[str] = data.get("buttons", [])
        """ The buttons of the activity, if any. """

        self._from_data(data)

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f"<Activity name={self.name} type={self.type}>"

    def _from_data(self, data: dict) -> None:
        if data.get("timestamps"):
            self.timestamps = ActivityTimestamps(data=data["timestamps"])

        if data.get("secrets"):
            self.secrets = ActivitySecrets(data=data["secrets"])

        if data.get("party"):
            self.party = ActivityParty(data=data["party"])

        if data.get("emoji"):
            self.emoji = EmojiParser.from_dict(data["emoji"])

        if (
            data.get("assets") and
            self.application_id is not None
        ):
            self.assets = ActivityAssets(
                state=self._state,
                application_id=self.application_id,
                data=data["assets"]
            )

    @property
    def type(self) -> ActivityType:
        """ The type of the activity. """
        return ActivityType(self._raw_type)
