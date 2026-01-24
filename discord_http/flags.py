from enum import Flag, CONFORM
from typing import Self

from .enums import PermissionType
from .object import Snowflake

__all__ = (
    "ApplicationFlags",
    "AttachmentFlags",
    "BaseFlag",
    "ChannelFlags",
    "GuildInviteFlags",
    "GuildMemberFlags",
    "MessageFlags",
    "PermissionOverwrite",
    "Permissions",
    "SKUFlags",
    "SystemChannelFlags",
    "UserFlags",
)


class _FlagPyMeta(Flag, boundary=CONFORM):
    pass


class BaseFlag(_FlagPyMeta):
    def __str__(self) -> str:
        return str(self.value)

    def __int__(self) -> int:
        return self.value

    @classmethod
    def all(cls) -> Self:
        """ Returns a flag with all the flags. """
        return cls(sum([int(g) for g in cls.__members__.values()]))

    @classmethod
    def none(cls) -> Self:
        """ Returns a flag with no flags. """
        return cls(0)

    @classmethod
    def from_names(cls, *args: str) -> Self:
        """
        Create a flag from names.

        Parameters
        ----------
        *args:
            The names of the flags to create

        Returns
        -------
            The flag with the added flags

        Raises
        ------
        `ValueError`
            The flag name is not a valid flag
        """
        value = cls.none()
        return value.add_flags(*args)

    @property
    def list_names(self) -> list[str]:
        """ Returns a list of all the names of the flag. """
        return [
            g.name or "UNKNOWN"
            for g in self
        ]

    def to_names(self) -> list[str]:
        """ Returns the current names of the flag. """
        return [
            name for name, member in self.__class__.__members__.items()
            if member in self
        ]

    def add_flags(
        self,
        *flag_name: Self | str
    ) -> Self:
        """
        Add a flag by name.

        Parameters
        ----------
        *flag_name:
            The flag to add

        Returns
        -------
            The flag with the added flag

        Raises
        ------
        `ValueError`
            The flag name is not a valid flag
        """
        for p in flag_name:
            if isinstance(p, BaseFlag):
                self |= p
                continue

            if p in self.list_names:
                continue

            try:
                self |= self.__class__[p]
            except KeyError:
                raise ValueError(
                    f"{p} is not a valid "
                    f"{self.__class__.__name__} flag value"
                )

        return self

    def remove_flags(
        self,
        *flag_name: Self | str
    ) -> Self:
        """
        Remove a flag by name.

        Parameters
        ----------
        flag_name:
            The flag to remove

        Returns
        -------
            The flag with the removed flag

        Raises
        ------
        `ValueError`
            The flag name is not a valid flag
        """
        for p in flag_name:
            if isinstance(p, BaseFlag):
                self &= ~p
                continue

            if p not in self.list_names:
                continue

            try:
                self &= ~self.__class__[p]
            except KeyError:
                raise ValueError(
                    f"{p} is not a valid "
                    f"{self.__class__.__name__} flag value"
                )

        return self

    def copy(self) -> Self:
        """ Returns a copy of the flag. """
        return self.__class__(self.value)


class MessageFlags(BaseFlag):
    crossposted = 1 << 0
    is_crosspost = 1 << 1
    suppress_embeds = 1 << 2
    source_message_deleted = 1 << 3
    urgent = 1 << 4
    has_thread = 1 << 5
    ephemeral = 1 << 6
    loading = 1 << 7
    failed_to_mention_some_roles_in_thread = 1 << 8
    suppress_notifications = 1 << 12
    is_voice_message = 1 << 13
    is_components_v2 = 1 << 15


class SKUFlags(BaseFlag):
    available = 1 << 2
    guild_subscription = 1 << 7
    user_subscription = 1 << 8


class GuildInviteFlags(BaseFlag):
    is_guest_invite = 1 << 0


class GuildMemberFlags(BaseFlag):
    did_rejoin = 1 << 0
    completed_onboarding = 1 << 1
    bypasses_verification = 1 << 2
    started_onboarding = 1 << 3
    is_guest = 1 << 4
    started_home_actions = 1 << 5
    completed_home_actions = 1 << 6
    automod_quarantined_username = 1 << 7
    dm_settings_upsell_acknowledged = 1 << 9


class ChannelFlags(BaseFlag):
    pinned = 1 << 1
    require_tag = 1 << 4
    hide_media_download_options = 1 << 15


class UserFlags(BaseFlag):
    staff = 1 << 0
    partner = 1 << 1
    hypesquad = 1 << 2
    bug_hunter_level_1 = 1 << 3
    hypesquad_online_house_1 = 1 << 6
    hypesquad_online_house_2 = 1 << 7
    hypesquad_online_house_3 = 1 << 8
    premium_early_supporter = 1 << 9
    team_pseudo_user = 1 << 10
    bug_hunter_level_2 = 1 << 14
    verified_bot = 1 << 16
    verified_developer = 1 << 17
    certified_moderator = 1 << 18
    bot_http_interactions = 1 << 19
    spammer = 1 << 20
    active_developer = 1 << 22
    provisional_account = 1 << 23


class AttachmentFlags(BaseFlag):
    clip = 1 << 0
    thumbnail = 1 << 1
    remix = 1 << 2


class ApplicationFlags(BaseFlag):
    application_auto_moderation_rule_create_badge = 1 << 6
    gateway_presence = 1 << 12
    gateway_presence_limited = 1 << 13
    gateway_guild_members = 1 << 14
    gateway_guild_members_limited = 1 << 15
    verification_pending_guild_limit = 1 << 16
    embedded = 1 << 17
    gateway_message_content = 1 << 18
    gateway_message_content_limited = 1 << 19
    application_command_badge = 1 << 23


class SystemChannelFlags(BaseFlag):
    suppress_join_notifications = 1 << 0
    suppress_premium_subscriptions = 1 << 1
    suppress_guild_reminder_notifications = 1 << 2
    suppress_join_notification_replies = 1 << 3
    suppress_role_subscription_purchase_notifications = 1 << 4
    suppress_role_subscription_purchase_notifications_replies = 1 << 5


class Permissions(BaseFlag):
    create_instant_invite = 1 << 0
    kick_members = 1 << 1
    ban_members = 1 << 2
    administrator = 1 << 3
    manage_channels = 1 << 4
    manage_guild = 1 << 5
    add_reactions = 1 << 6
    view_audit_log = 1 << 7
    priority_speaker = 1 << 8
    stream = 1 << 9
    view_channel = 1 << 10
    send_messages = 1 << 11
    send_tts_messages = 1 << 12
    manage_messages = 1 << 13
    embed_links = 1 << 14
    attach_files = 1 << 15
    read_message_history = 1 << 16
    mention_everyone = 1 << 17
    use_external_emojis = 1 << 18
    view_guild_insights = 1 << 19
    connect = 1 << 20
    speak = 1 << 21
    mute_members = 1 << 22
    deafen_members = 1 << 23
    move_members = 1 << 24
    use_vad = 1 << 25
    change_nickname = 1 << 26
    manage_nicknames = 1 << 27
    manage_roles = 1 << 28
    manage_webhooks = 1 << 29
    manage_guild_expressions = 1 << 30
    use_application_commands = 1 << 31
    request_to_speak = 1 << 32
    manage_events = 1 << 33
    manage_threads = 1 << 34
    create_public_threads = 1 << 35
    create_private_threads = 1 << 36
    use_external_stickers = 1 << 37
    send_messages_in_threads = 1 << 38
    use_embedded_activities = 1 << 39
    moderate_members = 1 << 40
    view_creator_monetization_analytics = 1 << 41
    use_soundboard = 1 << 42
    create_guild_expressions = 1 << 43
    create_events = 1 << 44
    use_external_sounds = 1 << 45
    send_voice_messages = 1 << 46
    set_voice_channel_status = 1 << 48
    send_polls = 1 << 49
    use_external_apps = 1 << 50

    def handle_overwrite(self, allow: int, deny: int) -> "Permissions":
        """
        Handles the overwrite of permissions.

        Parameters
        ----------
        allow:
            The permission flag integer to allow
        deny:
            The permission flag integer to deny

        Returns
        -------
            The permissions with the overwrite applied
        """
        new_value: int = (self.value & ~deny) | allow
        return Permissions(new_value)


class PermissionOverwrite:
    def __init__(
        self,
        target: Snowflake | int,
        *,
        allow: Permissions | None = None,
        deny: Permissions | None = None,
        target_type: PermissionType | None = None
    ):
        self.allow = allow or Permissions.none()
        self.deny = deny or Permissions.none()

        if not isinstance(self.allow, Permissions):
            raise TypeError(
                "Expected Permissions for allow, "
                f"received {type(self.allow)} instead"
            )
        if not isinstance(self.deny, Permissions):
            raise TypeError(
                "Expected Permissions for deny, "
                f"received {type(self.deny)} instead"
            )

        if isinstance(target, int):
            target = Snowflake(id=target)

        self.target = target
        self.target_type = (
            target_type or
            PermissionType.member
        )

        if getattr(self.target, "_target_type", None) == PermissionType.role:
            self.target_type = PermissionType.role

        if not isinstance(self.target_type, PermissionType):
            raise TypeError(
                "Expected PermissionType, "
                f"received {type(self.target_type)} instead"
            )

    def __repr__(self) -> str:
        return (
            f"<PermissionOverwrite target={self.target} "
            f"allow={int(self.allow)} deny={int(self.deny)}>"
        )

    def is_role(self) -> bool:
        """ Returns whether the overwrite is a role overwrite. """
        return self.target_type == PermissionType.role

    def is_member(self) -> bool:
        """ Returns whether the overwrite is a member overwrite. """
        return self.target_type == PermissionType.member

    @classmethod
    def from_dict(cls, data: dict) -> Self:
        """
        Create a permission overwrite from a dictionary.

        Parameters
        ----------
        data:
            The dictionary to create the permission overwrite from

        Returns
        -------
            The permission overwrite
        """
        return cls(
            target=int(data["id"]),
            allow=Permissions(int(data["allow"])),
            deny=Permissions(int(data["deny"])),
            target_type=PermissionType(int(data["type"]))
        )

    def to_dict(self) -> dict:
        """ Returns the permission overwrite as a dictionary. """
        return {
            "id": str(int(self.target)),
            "allow": int(self.allow),
            "deny": int(self.deny),
            "type": int(self.target_type)
        }

    def copy(self) -> Self:
        """ Returns a copy of the flag. """
        return self.__class__(
            target=self.target,
            allow=self.allow,
            deny=self.deny,
            target_type=self.target_type
        )
