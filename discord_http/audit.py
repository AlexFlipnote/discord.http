import logging

from typing import TYPE_CHECKING, Any, TypeVar, ClassVar
from collections.abc import Callable
from datetime import datetime

from . import utils, enums, flags
from .asset import Asset
from .automod import AutoModRuleTriggers, AutoModRuleAction
from .object import Snowflake
from .guild import PartialGuild
from .channel import PartialChannel, ForumTag
from .colour import Colour
from .role import PartialRole
from .user import User, PartialUser
from .emoji import EmojiParser

if TYPE_CHECKING:
    from .http import DiscordAPI

_log = logging.getLogger(__name__)

__all__ = (
    "AuditChange",
    "AuditLogEntry",
)


def _handle_snowflake(entry: "AuditLogEntry", data: int) -> Snowflake:  # noqa: ARG001
    return Snowflake(id=int(data))


def _handle_type(entry: "AuditLogEntry", data: int | str) -> (
    enums.ChannelType | enums.StickerType |
    enums.WebhookType | enums.PermissionType | str
):
    if entry.action_type.name.startswith("sticker_"):
        return enums.StickerType(data)
    if entry.action_type.name.startswith("webhook_"):
        return enums.WebhookType(data)
    if entry.action_type.name.startswith("integration_"):
        # Might use enums.IntegrationType in the future, not sure yet
        return data  # type: ignore
    if entry.action_type.name.startswith("channel_overwrite_"):
        return enums.PermissionType(data)
    return enums.ChannelType(data)


def _handle_overloaded_flags(entry: "AuditLogEntry", data: int) -> flags.BaseFlag | int:
    valid_types = (
        enums.AuditLogType.channel_create,
        enums.AuditLogType.channel_update,
        enums.AuditLogType.channel_delete,
        enums.AuditLogType.thread_create,
        enums.AuditLogType.thread_update,
        enums.AuditLogType.thread_delete,
    )

    if entry.action_type in valid_types:
        return flags.ChannelFlags(data)
    return data


def _handle_default_reaction(
    entry: "AuditLogEntry",  # noqa: ARG001
    data: dict | None
) -> EmojiParser | None:
    if not data:
        return None

    return EmojiParser.from_dict({
        "name": data.get("emoji_name", None),
        "id": data.get("emoji_id", None) or None
    })


def _handle_cover_image(entry: "AuditLogEntry", data: str | None) -> Asset | None:
    if not data:
        return None
    if not entry.target_id:
        return None

    return Asset._from_scheduled_event_cover_image(
        state=entry._state,
        scheduled_event_id=entry.target_id,
        cover_image=data
    )


def _handle_guild_hash(path: str) -> Callable[["AuditLogEntry", str], Asset | None]:
    def _handler(entry: "AuditLogEntry", data: str | None) -> Asset | None:
        if not data:
            return None

        return Asset._from_guild_image(
            state=entry._state,
            guild_id=entry.guild.id,
            image=data,
            path=path
        )

    return _handler


def _handle_guild_id(entry: "AuditLogEntry", data: str | None) -> PartialGuild | None:
    if not data:
        return None

    return entry._convert_target_guild(int(data))


def _handle_timestamp(
    entry: "AuditLogEntry",  # noqa: ARG001
    data: str | None
) -> datetime | None:
    if not data:
        return None
    return utils.parse_time(data)


def _handle_applied_tags(
    entry: "AuditLogEntry",  # noqa: ARG001
    data: list[str]
) -> list[Snowflake]:
    return [
        Snowflake(id=int(g))
        for g in data
    ]


def _handle_forum_tags(
    entry: "AuditLogEntry",  # noqa: ARG001
    data: list[dict]
) -> list[ForumTag]:
    return [
        ForumTag.from_data(data=g)
        for g in data
    ]


def _hanndle_icon(entry: "AuditLogEntry", data: str | None) -> Asset | None:
    if data is None:
        return None

    if entry.action_type is enums.AuditLogType.guild_update:
        return Asset._from_guild_image(
            state=entry._state,
            guild_id=entry.guild.id,
            image=data,
            path="icons"
        )

    return Asset._from_icon(
        state=entry._state,
        object_id=entry.guild.id,
        icon_hash=data,
        path="role"
    )


def _handle_avatar(entry: "AuditLogEntry", data: str | None) -> Asset | None:
    if data is None:
        return None
    if not entry.target_id:
        return None

    return Asset._from_avatar(
        state=entry._state,
        user_id=entry.target_id,
        avatar=data
    )


def _handle_overwrites(entry: "AuditLogEntry", data: dict) -> list[tuple[
    PartialUser | PartialRole, flags.PermissionOverwrite
]]:
    overwrites = []
    for g in data:
        allow = flags.Permissions(int(g["allow"]))
        deny = flags.Permissions(int(g["deny"]))

        target = None
        ow_type = g["type"]
        ow_id = int(g["id"])

        if ow_type == "0":
            target = entry.guild.get_partial_role(ow_id)
        elif ow_type == "1":
            target = entry.guild.get_partial_member(ow_id)

        if target is None:
            target = Snowflake(id=ow_id)

        ow = flags.PermissionOverwrite(
            target=target,
            allow=allow,
            deny=deny,
            target_type=enums.PermissionType(int(ow_type))
        )

        overwrites.append((target, ow))

    return overwrites


def _handle_colour(
    entry: "AuditLogEntry",  # noqa: ARG001
    data: int
) -> Colour:
    return Colour(int(data))


def _handle_automod_triggers(
    entry: "AuditLogEntry",  # noqa: ARG001
    data: dict
) -> AutoModRuleTriggers:
    return AutoModRuleTriggers.from_dict(data)


def _handle_automod_actions(
    entry: "AuditLogEntry",  # noqa: ARG001
    data: list[dict]
) -> list[AutoModRuleAction]:
    return [
        AutoModRuleAction.from_dict(g)
        for g in data
    ]


def _handle_automod_roles(entry: "AuditLogEntry", data: list[int]) -> list[PartialRole]:
    return [
        entry._convert_target_role(g)
        for g in data
    ]


def _handle_automod_channels(entry: "AuditLogEntry", data: list[int]) -> list[PartialChannel]:
    return [
        entry._convert_target_channel(g)
        for g in data
    ]


def _handle_member(entry: "AuditLogEntry", data: int) -> User | PartialUser:
    return entry._convert_target_user(int(data))


def _handle_channel(entry: "AuditLogEntry", data: str) -> PartialChannel:
    return entry._convert_target_channel(int(data))


def _handle_role(entry: "AuditLogEntry", data: str) -> PartialRole:
    return entry._convert_target_role(int(data))


E = TypeVar("E", bound=enums.BaseEnum)


def _handle_enum(cls: type[E]) -> Callable[["AuditLogEntry", str | int], E]:
    def _handler(
        entry: "AuditLogEntry",  # noqa: ARG001
        data: str | int
    ) -> E:
        return cls(int(data))

    return _handler


F = TypeVar("F", bound=flags.BaseFlag)


def _handle_flags(cls: type[F]) -> Callable[["AuditLogEntry", str | int], F]:
    def _handler(
        entry: "AuditLogEntry",  # noqa: ARG001
        data: str | int
    ) -> F:
        return cls(int(data))

    return _handler


class AuditChange:
    """
    Represents a change in an audit log entry.

    Attributes
    ----------
    entry: `AuditLogEntry`
        The audit log entry this change belongs to.
    key: `str`
        The key of the change.
    old_value: `Any | None`
        The old value of the change, if applicable.
    new_value: `Any | None`
        The new value of the change, if applicable.
    """
    _translaters: ClassVar[dict[str, Callable[["AuditLogEntry", Any], Any] | None]] = {
        "verification_level": _handle_enum(enums.VerificationLevel),
        "explicit_content_filter": _handle_enum(enums.ContentFilterLevel),
        "allow": _handle_flags(flags.Permissions),
        "deny": _handle_flags(flags.Permissions),
        "permissions": _handle_flags(flags.Permissions),
        "id": _handle_snowflake,
        "color": _handle_colour,
        "owner_id": _handle_member,
        "inviter_id": _handle_member,
        "channel_id": _handle_channel,
        "afk_channel_id": _handle_channel,
        "system_channel_id": _handle_channel,
        "system_channel_flags": _handle_flags(flags.SystemChannelFlags),
        "widget_channel_id": _handle_channel,
        "rules_channel_id": _handle_channel,
        "public_updates_channel_id": _handle_channel,
        "permission_overwrites": _handle_overwrites,
        "splash_hash": _handle_guild_hash("splashes"),
        "banner_hash": _handle_guild_hash("banners"),
        "discovery_splash_hash": _handle_guild_hash("discovery-splashes"),
        "icon_hash": _hanndle_icon,
        "avatar_hash": _handle_avatar,
        "rate_limit_per_user": None,
        "default_thread_rate_limit_per_user": None,
        "guild_id": _handle_guild_id,
        "tags": None,
        "default_message_notifications": _handle_enum(enums.DefaultNotificationLevel),
        "video_quality_mode": _handle_enum(enums.VideoQualityType),
        "privacy_level": _handle_enum(enums.PrivacyLevelType),
        "format_type": _handle_enum(enums.StickerFormatType),
        "type": _handle_type,
        "communication_disabled_until": _handle_timestamp,
        "expire_behavior": _handle_enum(enums.ExpireBehaviour),
        "mfa_level": _handle_enum(enums.MFALevel),
        "status": _handle_enum(enums.ScheduledEventStatusType),
        "entity_type": _handle_enum(enums.ScheduledEventEntityType),
        "preferred_locale": _handle_enum(enums.Locale),
        "image_hash": _handle_cover_image,
        "trigger_type": _handle_enum(enums.AutoModRuleTriggerType),
        "trigger_metadata": _handle_automod_triggers,
        "event_type": _handle_enum(enums.AutoModRuleEventType),
        "actions": _handle_automod_actions,
        "exempt_channels": _handle_automod_channels,
        "exempt_roles": _handle_automod_roles,
        "applied_tags": _handle_applied_tags,
        "available_tags": _handle_forum_tags,
        "flags": _handle_overloaded_flags,
        "default_reaction_emoji": _handle_default_reaction,
    }

    def __init__(
        self,
        *,
        entry: "AuditLogEntry",
        data: dict
    ):
        self.entry = entry

        self.key: str = data["key"]

        self.old_value: Any | None = data.get("old_value")
        self.new_value: Any | None = data.get("new_value")

        if self.key in ("$add", "$remove"):
            self.new_value = self._handle_partial_role(data)
            return

        translator: Callable[["AuditLogEntry", Any], Any] | None = self._translaters.get(self.key, None)

        if translator:
            if self.new_value is not None:
                self.new_value = translator(self.entry, self.new_value)

            if self.old_value is not None:
                self.old_value = translator(self.entry, self.old_value)

    def _handle_partial_role(self, data: dict) -> list[PartialRole]:
        return [
            PartialRole(
                state=self.entry._state,
                id=int(g["id"]),
                guild_id=self.entry.guild.id
            )
            for g in data["new_value"]
        ]


class AuditLogEntry(Snowflake):
    """
    Represents an entry in an audit log.

    Attributes
    ----------
    guild: `PartialGuild`
        The guild this audit log entry belongs to.
    action_type: `enums.AuditLogType`
        The type of action that was performed.
    reason: `str | None`
        The reason for the action, if provided.
    user_id: `int | None`
        The ID of the user who performed the action, if available.
    target_id: `int | None`
        The ID of the target of the action, if available.
    options: `dict`
        Additional options related to the action, if any.
    changes: `list[AuditChange]`
        A list of changes made in this audit log entry.
    """
    def __init__(
        self,
        *,
        state: "DiscordAPI",
        data: dict,
        guild: PartialGuild | None = None,
        users: dict[int, User] | None = None,
    ):
        super().__init__(id=int(data["id"]))
        self._state = state

        self.guild: PartialGuild = guild or PartialGuild(
            state=self._state,
            id=int(data["guild_id"])
        )

        try:
            self.action_type: enums.AuditLogType = enums.AuditLogType(int(data["action_type"]))
        except ValueError:
            # There might be a new audit log type added
            _log.debug(f"Unknown audit log type detected from guild {self.guild.id}: {data['action_type']}")
            self.action_type = enums.AuditLogType.unknown

        self.reason: str | None = data.get("reason")

        self.user_id: int | None = utils.get_int(data, "user_id")
        self.target_id: int | None = utils.get_int(data, "target_id")

        # Add parsing methods for options
        self.options: dict = data.get("options", {})
        self.changes: list[AuditChange] = []

        self._users: dict[int, User] = users or {}

        self._from_data(data)

    def __repr__(self) -> str:
        return (
            f"<AuditLogEntry action_type={self.action_type} user_id={self.user_id}>"
        )

    def _from_data(self, data: dict) -> None:
        self.changes: list[AuditChange] = [
            AuditChange(entry=self, data=g)
            for g in data.get("changes", [])
        ]

    @property
    def user(self) -> User | PartialUser | None:
        """ Returns the user object of the audit log if available. """
        if not self.user_id:
            return None
        return self._convert_target_user(self.user_id)

    @property
    def target(self) -> Snowflake | None:
        """
        Returns the target object of the audit log.

        The Snowflake can be a PartialChannel, User, PartialRole, etc
        """
        if not self.target_id:
            return None

        try:
            converter = getattr(self, f"_convert_target_{self.action_type.target_type}")
        except AttributeError:
            return Snowflake(id=self.target_id)
        else:
            return converter(self.target_id)

    def _convert_target_guild(self, guild_id: int) -> PartialGuild:
        return PartialGuild(
            state=self._state,
            id=guild_id
        )

    def _convert_target_channel(self, channel_id: int) -> PartialChannel:
        return PartialChannel(
            state=self._state,
            id=channel_id,
            guild_id=self.guild.id
        )

    def _convert_target_user(self, user_id: int) -> User | PartialUser:
        return self._users.get(user_id, PartialUser(
            state=self._state,
            id=user_id
        ))

    def _convert_target_role(self, role_id: int) -> PartialRole:
        return PartialRole(
            state=self._state,
            id=role_id,
            guild_id=self.guild.id
        )

    def _convert_target_message(self, user_id: int) -> User | PartialUser:
        return self._convert_target_user(user_id)
