from typing import TYPE_CHECKING, Self, Any

from . import utils
from .channel import PartialChannel
from .enums import (
    AutoModRulePresetType, AutoModRuleTriggerType,
    AutoModRuleActionType, AutoModRuleEventType
)
from .object import PartialBase, Snowflake
from .role import PartialRole
from .user import PartialUser

if TYPE_CHECKING:
    from .guild import PartialGuild, Guild
    from .http import DiscordAPI

MISSING = utils.MISSING

__all__ = (
    "AutoModRule",
    "AutoModRuleAction",
    "AutoModRuleTriggers",
    "PartialAutoModRule",
)


class AutoModRuleTriggers:
    def __init__(
        self,
        *,
        keyword_filter: list[str] | None = None,
        regex_patterns: list[str] | None = None,
        presets: list[AutoModRulePresetType] | None = None,
        allow_list: list[str] | None = None,
        mention_total_limit: int | None = None,
        mention_raid_protection_enabled: bool = False
    ):
        self.keyword_filter: list[str] | None = keyword_filter
        self.regex_patterns: list[str] | None = regex_patterns
        self.presets: list[AutoModRulePresetType] | None = presets
        self.allow_list: list[str] | None = allow_list
        self.mention_total_limit: int | None = mention_total_limit
        self.mention_raid_protection_enabled: bool = mention_raid_protection_enabled

    def __repr__(self) -> str:
        output = "<AutoModTriggers "

        if self.keyword_filter:
            output += f"keyword_filter={self.keyword_filter}"
        if self.regex_patterns:
            output += f"regex_patterns={self.regex_patterns}"
        if self.presets:
            output += f"presets={self.presets}"
        if self.allow_list:
            output += f"allow_list={self.allow_list}"
        if self.mention_total_limit:
            output += f"mention_total_limit={self.mention_total_limit}"
        if self.mention_raid_protection_enabled:
            output += "mention_raid_protection_enabled=True"

        return f"{output}>"

    def to_dict(self) -> dict:
        """ The auto moderation rule as a dictionary. """
        payload = {}

        if self.keyword_filter is not None:
            payload["keyword_filter"] = [str(g) for g in self.keyword_filter]
        if self.regex_patterns is not None:
            payload["regex_patterns"] = [str(g) for g in self.regex_patterns]
        if self.presets is not None:
            payload["presets"] = [int(g) for g in self.presets]
        if self.allow_list is not None:
            payload["allow_list"] = [str(g) for g in self.allow_list]
        if self.mention_total_limit is not None:
            payload["mention_total_limit"] = int(self.mention_total_limit)
        if self.mention_raid_protection_enabled is True:
            payload["mention_raid_protection_enabled"] = True

        return payload

    @classmethod
    def from_dict(cls, data: dict) -> Self:
        """
        Create an auto moderation rule from a dictionary.

        Parameters
        ----------
        data:
            The dictionary to create the auto moderation rule from

        Returns
        -------
            The auto moderation rule
        """
        return cls(
            keyword_filter=data.get("keyword_filter"),
            regex_patterns=data.get("regex_patterns"),
            presets=data.get("presets"),
            allow_list=data.get("allow_list"),
            mention_total_limit=data.get("mention_total_limit"),
            mention_raid_protection_enabled=data.get("mention_raid_protection_enabled", False)
        )


class AutoModRuleAction:
    def __init__(
        self,
        *,
        type: AutoModRuleActionType,  # noqa: A002
        channel_id: Snowflake | int | None = None,
        duration_seconds: int | None = None,
        custom_message: str | None = None,
    ):
        self.type: AutoModRuleActionType = type
        self.channel_id = channel_id
        self.duration_seconds: int | None = duration_seconds
        self.custom_message: str | None = custom_message

        if self.duration_seconds is not None:
            # 4 Week limit, let's just handle it
            self.duration_seconds = min(self.duration_seconds, 2419200)

    def __repr__(self) -> str:
        output = f"<AutoModAction type={self.type}"
        if self.channel_id:
            output += f" channel_id={self.channel_id}"
        if self.duration_seconds:
            output += f" duration_seconds={self.duration_seconds}"
        if self.custom_message:
            output += f" custom_message={self.custom_message}"

        return f"{output}>"

    def to_dict(self) -> dict:
        """ The auto moderation rule action as a dictionary. """
        payload = {
            "type": int(self.type),
            "metadata": {}
        }

        if self.channel_id is not None:
            payload["metadata"]["channel_id"] = str(self.channel_id)

        if self.duration_seconds is not None:
            payload["metadata"]["duration_seconds"] = int(self.duration_seconds)

        if self.custom_message is not None:
            payload["metadata"]["custom_message"] = self.custom_message

        return payload

    @classmethod
    def from_dict(cls, data: dict) -> Self:
        """
        Create an auto moderation rule action from a dictionary.

        Parameters
        ----------
        data:
            The dictionary to create the auto moderation rule action from

        Returns
        -------
            The auto moderation rule action
        """
        metadata = data.get("metadata", {})
        return cls(
            type=AutoModRuleActionType(data["type"]),
            channel_id=utils.get_int(metadata, "channel_id"),
            duration_seconds=metadata.get("duration_seconds", None),
            custom_message=metadata.get("custom_message", None)
        )

    @classmethod
    def create_message(cls, message: str) -> Self:
        """
        Create an auto moderation rule action to block a message.

        Parameters
        ----------
        message:
            The message to block

        Returns
        -------
            The auto moderation rule action
        """
        return cls(
            type=AutoModRuleActionType.block_message,
            custom_message=str(message)
        )

    @classmethod
    def create_alert_location(cls, channel: Snowflake | int) -> Self:
        """
        Create an auto moderation rule action to send an alert message.

        Parameters
        ----------
        channel:
            The channel to send the alert message to

        Returns
        -------
            The auto moderation rule action
        """
        return cls(
            type=AutoModRuleActionType.send_alert_message,
            channel_id=int(channel)
        )

    @classmethod
    def create_timeout(cls, seconds: int) -> Self:
        """
        Create an auto moderation rule action to timeout a user.

        Parameters
        ----------
        seconds:
            The number of seconds to timeout the user for

        Returns
        -------
            The auto moderation rule action
        """
        return cls(
            type=AutoModRuleActionType.timeout,
            duration_seconds=int(seconds)
        )


class PartialAutoModRule(PartialBase):
    def __init__(
        self,
        *,
        state: "DiscordAPI",
        id: int,  # noqa: A002
        guild_id: int
    ):
        super().__init__(id=int(id))
        self._state = state

        self.guild_id: int = guild_id

    def __repr__(self) -> str:
        return f"<PartialAutoModRule id={self.id}>"

    @property
    def guild(self) -> "Guild | PartialGuild | None":
        """ The guild object this event is in. """
        if not self.guild_id:
            return None

        cache = self._state.cache.get_guild(self.guild_id)
        if cache:
            return cache

        from .guild import PartialGuild
        return PartialGuild(state=self._state, id=self.guild_id)

    async def fetch(self) -> "AutoModRule":
        """ Fetches more information about the automod rule. """
        r = await self._state.query(
            "GET",
            f"/guilds/{self.guild_id}/auto-moderation/rules/{self.id}"
        )

        return AutoModRule(
            state=self._state,
            data=r.response
        )

    async def delete(self, *, reason: str | None = None) -> None:
        """
        Delete the automod rule.

        Parameters
        ----------
        reason:
            Reason for deleting the automod
        """
        await self._state.query(
            "DELETE",
            f"/guilds/{self.guild_id}/auto-moderation/rules/{self.id}",
            reason=reason,
            res_method="text"
        )

    async def edit(
        self,
        *,
        name: str | None = MISSING,
        event_type: AutoModRuleEventType | int | None = MISSING,
        keyword_filter: list[str] | None = MISSING,
        regex_patterns: list[str] | None = MISSING,
        presets: list[AutoModRulePresetType] | None = MISSING,
        allow_list: list[str] | None = MISSING,
        mention_total_limit: int | None = MISSING,
        mention_raid_protection_enabled: bool = MISSING,
        alert_channel: Snowflake | int | None = MISSING,
        timeout_seconds: int | None = MISSING,
        message: str | None = MISSING,
        enabled: bool = MISSING,
        exempt_roles: list[Snowflake | int] | None = MISSING,
        exempt_channels: list[Snowflake | int] | None = MISSING,
        reason: str | None = None
    ) -> "AutoModRule":
        """
        Create an automod rule.

        Parameters
        ----------
        name:
            Name of the automod
        event_type:
            What type of event
        keyword_filter:
            Keywords to filter
        regex_patterns:
            Keywords in regex pattern to filter
        presets:
            Automod presets to include
        allow_list:
            List of keywords that are allowed
        mention_total_limit:
            How many unique mentions allowed before trigger
        mention_raid_protection_enabled:
            If this should apply for raids
        alert_channel:
            Where the action should be logged
        timeout_seconds:
            How many seconds the user in question should be timed out
        message:
            What message the user gets when action is taken
        enabled:
            If the automod should be enabled or not
        exempt_roles:
            Which roles are allowed to bypass
        exempt_channels:
            Which channels are allowed to bypass
        reason:
            Reason for editing the automod

        Returns
        -------
            The automod that was just edited
        """
        payload = {}

        if name is not MISSING:
            payload["name"] = str(name)
        if event_type is not MISSING:
            payload["event_type"] = int(event_type or -1)

        if any([
            g is not MISSING
            for g in [alert_channel, timeout_seconds, message]
        ]):
            payload["actions"] = []

        if alert_channel is not MISSING:
            payload["actions"].append(
                AutoModRuleAction.create_alert_location(
                    int(alert_channel or -1)
                ).to_dict()
            )

        if timeout_seconds is not MISSING:
            payload["actions"].append(
                AutoModRuleAction.create_timeout(
                    int(timeout_seconds or -1)
                ).to_dict()
            )

        if message is not MISSING:
            payload["actions"].append(
                AutoModRuleAction.create_message(
                    str(message)
                ).to_dict()
            )

        if enabled is not MISSING:
            payload["enabled"] = bool(enabled)

        if isinstance(exempt_roles, list):
            payload["exempt_roles"] = [str(int(g)) for g in exempt_roles]

        if isinstance(exempt_channels, list):
            payload["exempt_channels"] = [str(int(g)) for g in exempt_channels]

        trigger_payload: dict[str, Any] = {
            k: v for k, v in {
                "keyword_filter": keyword_filter,
                "regex_patterns": regex_patterns,
                "presets": presets,
                "allow_list": allow_list,
                "mention_total_limit": mention_total_limit,
                "mention_raid_protection_enabled": mention_raid_protection_enabled
            }.items()
            if v is not MISSING
        }

        if trigger_payload:
            payload["trigger_metadata"] = AutoModRuleTriggers(
                **trigger_payload
            ).to_dict()

        r = await self._state.query(
            "PATCH",
            f"/guilds/{self.guild_id}/auto-moderation/rules/{self.id}",
            json=payload,
            reason=reason
        )

        return AutoModRule(
            state=self._state,
            data=r.response
        )


class AutoModRule(PartialAutoModRule):
    """
    Represents an auto moderation rule in a guild.

    Attributes
    ----------
    name: str
        The name of the automod rule
    creator_id: int
        The ID of the user that created the automod rule
    event_type: AutoModRuleEventType
        The type of event that triggers the automod rule
    trigger_type: AutoModRuleTriggerType
        The type of trigger for the automod rule
    actions: list[AutoModRuleAction]
        The actions that the automod rule takes when triggered
    trigger_metadata: AutoModRuleTriggers | None
        The metadata for the trigger of the automod rule
    enabled: bool
        Whether the automod rule is enabled or not
    exempt_roles: list[PartialRole]
        The roles that are exempt from the automod rule
    exempt_channels: list[PartialChannel]
        The channels that are exempt from the automod rule
    """
    def __init__(
        self,
        *,
        state: "DiscordAPI",
        data: dict
    ):
        super().__init__(
            state=state,
            id=int(data["id"]),
            guild_id=int(data["guild_id"])
        )

        self.name: str = data["name"]
        self.creator_id: int = int(data["creator_id"])
        self.event_type: AutoModRuleEventType = AutoModRuleEventType(data["event_type"])
        self.trigger_type: AutoModRuleTriggerType = AutoModRuleTriggerType(data["trigger_type"])

        self.actions: list[AutoModRuleAction] = [
            AutoModRuleAction.from_dict(g)
            for g in data["actions"]
        ]

        self.trigger_metadata: AutoModRuleTriggers | None = None

        self.enabled: bool = data.get("enabled", False)

        self.exempt_roles: list[PartialRole] = [
            PartialRole(state=state, id=int(g), guild_id=self.guild_id)
            for g in data.get("exempt_roles", [])
        ]

        self.exempt_channels: list[PartialChannel] = [
            PartialChannel(state=state, id=int(g), guild_id=self.guild_id)
            for g in data.get("exempt_channels", [])
        ]

        self._from_data(data)

    def __repr__(self) -> str:
        return f"<AutoModRule id={self.id} name={self.name}>"

    def __str__(self) -> str:
        return self.name

    def _from_data(self, data: dict) -> None:
        if data.get("trigger_metadata"):
            self.trigger_metadata = AutoModRuleTriggers.from_dict(
                data["trigger_metadata"]
            )

    @property
    def creator(self) -> PartialUser:
        """ The user that created the automod rule in User object form. """
        return PartialUser(
            state=self._state,
            id=self.creator_id
        )
