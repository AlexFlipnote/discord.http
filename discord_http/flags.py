from collections.abc import Iterator
from typing import Self, cast

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


class BaseFlag:
    """
    Base class for all flags inside discord.http library.

    This is a hand-rolled bitfield, not `enum.Flag`. Every value passed to a
    subclass is a plain combination of power-of-two members, and stdlib's
    `Flag` has to fall back to an O(members) linear scan to decompose those
    combinations on every single construction (`_missing_`/`_iter_member_by_value_`),
    which shows up hot: every interaction and every member/role touches a
    `Permissions` bitmask at least once. This class does the same masking
    with a single `&` against a precomputed "all known bits" value instead.

    Comparisons still work with values or names directly, example:

    .. code-block:: python

        Permissions.administrator == 1 << 3  # True
        Permissions.administrator > 0  # True
    """

    __slots__ = ("_name", "value")

    _name2member_: dict[str, "BaseFlag"]
    _value2member_: dict[int, "BaseFlag"]
    _members_: tuple["BaseFlag", ...]
    _all_value_: int
    __members__: dict[str, "BaseFlag"]

    def __init_subclass__(cls, **kwargs) -> None:
        super().__init_subclass__(**kwargs)

        name2member: dict[str, BaseFlag] = {}
        value2member: dict[int, BaseFlag] = {}
        members: list[BaseFlag] = []
        all_value = 0

        for name, value in list(vars(cls).items()):
            if name.startswith("_") or not isinstance(value, int) or isinstance(value, bool):
                continue

            member = object.__new__(cls)
            member.value = value
            member._name = name

            name2member[name] = member
            value2member[value] = member
            members.append(member)
            all_value |= value

            setattr(cls, name, member)

        none_member = object.__new__(cls)
        none_member.value = 0
        none_member._name = None
        value2member[0] = none_member

        cls._name2member_ = name2member
        cls._value2member_ = value2member
        cls._members_ = tuple(members)
        cls._all_value_ = all_value
        cls.__members__ = name2member

    def __new__(cls, value: int = 0) -> Self:
        """ Mask `value` to the class's known bits, reusing a cached member if one matches. """
        value = int(value) & cls._all_value_

        cached = cls._value2member_.get(value)
        if cached is not None:
            return cached  # type: ignore[return-value]

        self = object.__new__(cls)
        self.value = value
        self._name = None
        return self

    def __str__(self) -> str:
        return str(self.value)

    def __int__(self) -> int:
        return self.value

    def __bool__(self) -> bool:
        return self.value != 0

    def __repr__(self) -> str:
        name = self.name
        if name is None:
            return f"<{self.__class__.__name__}: {self.value}>"
        return f"<{self.__class__.__name__}.{name}: {self.value}>"

    def __hash__(self) -> int:
        return hash((self.__class__, self.value))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, self.__class__):
            return NotImplemented
        return self.value == other.value

    def __gt__(self, other: Self | int) -> bool:
        if isinstance(other, self.__class__):
            other = other.value
        if not isinstance(other, int):
            return NotImplemented
        return self.value > other

    def __lt__(self, other: Self | int) -> bool:
        if isinstance(other, self.__class__):
            other = other.value
        if not isinstance(other, int):
            return NotImplemented
        return self.value < other

    def __ge__(self, other: Self | int) -> bool:
        if isinstance(other, self.__class__):
            other = other.value
        if not isinstance(other, int):
            return NotImplemented
        return self.value >= other

    def __le__(self, other: Self | int) -> bool:
        if isinstance(other, self.__class__):
            other = other.value
        if not isinstance(other, int):
            return NotImplemented
        return self.value <= other

    def __iter__(self) -> Iterator[Self]:
        value = self.value
        for member in self.__class__._members_:
            if member.value & value:
                yield member  # type: ignore[misc]

    def __contains__(self, other: Self | int) -> bool:
        if isinstance(other, self.__class__):
            other_value = other.value
        elif isinstance(other, int):
            other_value = other
        else:
            raise TypeError(
                "unsupported operand type(s) for 'in': "
                f"'{other.__class__.__name__}' and '{self.__class__.__name__}'"
            )
        return (other_value & self.value) == other_value

    def __or__(self, other: Self | int) -> Self:
        if isinstance(other, self.__class__):
            other = other.value
        if not isinstance(other, int):
            return NotImplemented
        return self.__class__(self.value | other)

    def __and__(self, other: Self | int) -> Self:
        if isinstance(other, self.__class__):
            other = other.value
        if not isinstance(other, int):
            return NotImplemented
        return self.__class__(self.value & other)

    def __xor__(self, other: Self | int) -> Self:
        if isinstance(other, self.__class__):
            other = other.value
        if not isinstance(other, int):
            return NotImplemented
        return self.__class__(self.value ^ other)

    def __invert__(self) -> Self:
        return self.__class__(self.__class__._all_value_ ^ self.value)

    @property
    def name(self) -> str | None:
        """ The name of the flag, or the `|`-joined names if it's a combination. """
        if self._name is not None or self.value == 0:
            return self._name

        self._name = "|".join(
            m._name for m in self.__class__._members_
            if m.value & self.value
        )
        return self._name

    @property
    def pretty_name(self) -> str:
        """ A pretty name for the flag. """
        if not self.name:
            return "Unknown"
        return self.name.replace("_", " ").capitalize()

    @property
    def list_names(self) -> list[str]:
        """ A list of all the names of the flag. """
        return [
            g.name or "UNKNOWN"
            for g in self
        ]

    def to_names(self) -> list[str]:
        """ Returns the current names of the flag. """
        return [g.name for g in self if g.name]

    def add_flags(
        self,
        *flag_name: Self | str
    ) -> Self:
        """
        Add a flag by name.

        Parameters
        ----------
        *flag_name
            The flag to add

        Returns
        -------
            The flag with the added flag

        Raises
        ------
        ValueError
            The flag name is not a valid flag
        """
        for p in flag_name:
            if isinstance(p, BaseFlag):
                self |= p
                continue

            if (member_flag := self.__class__.__members__.get(p)) and member_flag in self:
                continue

            try:
                self |= self.__class__._name2member_[p]
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
        flag_name
            The flag to remove

        Returns
        -------
            The flag with the removed flag

        Raises
        ------
        ValueError
            The flag name is not a valid flag
        """
        for p in flag_name:
            if isinstance(p, BaseFlag):
                self &= ~p
                continue

            if (member_flag := self.__class__.__members__.get(p)) and member_flag not in self:
                continue

            try:
                self &= ~self.__class__._name2member_[p]
            except KeyError:
                raise ValueError(
                    f"{p} is not a valid "
                    f"{self.__class__.__name__} flag value"
                )

        return self

    def copy(self) -> Self:
        """ Returns a copy of the flag. """
        return self.__class__(self.value)

    @classmethod
    def all(cls) -> Self:
        """ Returns a flag with all the flags. """
        return cls(cls._all_value_)

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
        *args
            The names of the flags to create

        Returns
        -------
            The flag with the added flags

        Raises
        ------
        ValueError
            The flag name is not a valid flag
        """
        value = cls.none()
        return value.add_flags(*args)

    @classmethod
    def __class_getitem__(cls, name: str) -> Self:
        try:
            return cls._name2member_[name]  # type: ignore[return-value]
        except KeyError:
            raise KeyError(name)


class MessageFlags(BaseFlag):
    """ Represents the flags of a Discord message. """
    __slots__ = ()

    crossposted = cast("MessageFlags", 1 << 0)
    is_crosspost = cast("MessageFlags", 1 << 1)
    suppress_embeds = cast("MessageFlags", 1 << 2)
    source_message_deleted = cast("MessageFlags", 1 << 3)
    urgent = cast("MessageFlags", 1 << 4)
    has_thread = cast("MessageFlags", 1 << 5)
    ephemeral = cast("MessageFlags", 1 << 6)
    loading = cast("MessageFlags", 1 << 7)
    failed_to_mention_some_roles_in_thread = cast("MessageFlags", 1 << 8)
    suppress_notifications = cast("MessageFlags", 1 << 12)
    is_voice_message = cast("MessageFlags", 1 << 13)
    has_snapshot = cast("MessageFlags", 1 << 14)
    is_components_v2 = cast("MessageFlags", 1 << 15)


class SKUFlags(BaseFlag):
    """ Represents the flags of an application SKU. """
    __slots__ = ()

    available = cast("SKUFlags", 1 << 2)
    guild_subscription = cast("SKUFlags", 1 << 7)
    user_subscription = cast("SKUFlags", 1 << 8)


class GuildInviteFlags(BaseFlag):
    """ Represents the flags of a guild invite. """
    __slots__ = ()

    is_guest_invite = cast("GuildInviteFlags", 1 << 0)


class GuildMemberFlags(BaseFlag):
    """ Represents the flags of a guild member. """
    __slots__ = ()

    did_rejoin = cast("GuildMemberFlags", 1 << 0)
    completed_onboarding = cast("GuildMemberFlags", 1 << 1)
    bypasses_verification = cast("GuildMemberFlags", 1 << 2)
    started_onboarding = cast("GuildMemberFlags", 1 << 3)
    is_guest = cast("GuildMemberFlags", 1 << 4)
    started_home_actions = cast("GuildMemberFlags", 1 << 5)
    completed_home_actions = cast("GuildMemberFlags", 1 << 6)
    automod_quarantined_username = cast("GuildMemberFlags", 1 << 7)
    dm_settings_upsell_acknowledged = cast("GuildMemberFlags", 1 << 9)
    automod_quarantined_guild_tag = cast("GuildMemberFlags", 1 << 10)


class ChannelFlags(BaseFlag):
    """ Represents the flags of a Discord channel. """
    __slots__ = ()

    pinned = cast("ChannelFlags", 1 << 1)
    require_tag = cast("ChannelFlags", 1 << 4)
    hide_media_download_options = cast("ChannelFlags", 1 << 15)
    obfuscated = cast("ChannelFlags", 1 << 17)
    is_spoiler_channel = cast("ChannelFlags", 1 << 21)


class UserFlags(BaseFlag):
    """ Represents the public flags on a user's account. """
    __slots__ = ()

    staff = cast("UserFlags", 1 << 0)
    partner = cast("UserFlags", 1 << 1)
    hypesquad = cast("UserFlags", 1 << 2)
    bug_hunter_level_1 = cast("UserFlags", 1 << 3)
    hypesquad_online_house_1 = cast("UserFlags", 1 << 6)
    hypesquad_online_house_2 = cast("UserFlags", 1 << 7)
    hypesquad_online_house_3 = cast("UserFlags", 1 << 8)
    premium_early_supporter = cast("UserFlags", 1 << 9)
    team_pseudo_user = cast("UserFlags", 1 << 10)
    bug_hunter_level_2 = cast("UserFlags", 1 << 14)
    verified_bot = cast("UserFlags", 1 << 16)
    verified_developer = cast("UserFlags", 1 << 17)
    certified_moderator = cast("UserFlags", 1 << 18)
    bot_http_interactions = cast("UserFlags", 1 << 19)
    spammer = cast("UserFlags", 1 << 20)
    active_developer = cast("UserFlags", 1 << 22)
    provisional_account = cast("UserFlags", 1 << 23)


class AttachmentFlags(BaseFlag):
    """ Represents the flags of a message attachment. """
    __slots__ = ()

    is_clip = cast("AttachmentFlags", 1 << 0)
    is_thumbnail = cast("AttachmentFlags", 1 << 1)
    is_remix = cast("AttachmentFlags", 1 << 2)
    is_spoiler = cast("AttachmentFlags", 1 << 3)
    is_animated = cast("AttachmentFlags", 1 << 5)


class ApplicationFlags(BaseFlag):
    """ Represents the flags of a Discord application. """
    __slots__ = ()

    application_auto_moderation_rule_create_badge = cast("ApplicationFlags", 1 << 6)
    gateway_presence = cast("ApplicationFlags", 1 << 12)
    gateway_presence_limited = cast("ApplicationFlags", 1 << 13)
    gateway_guild_members = cast("ApplicationFlags", 1 << 14)
    gateway_guild_members_limited = cast("ApplicationFlags", 1 << 15)
    verification_pending_guild_limit = cast("ApplicationFlags", 1 << 16)
    embedded = cast("ApplicationFlags", 1 << 17)
    gateway_message_content = cast("ApplicationFlags", 1 << 18)
    gateway_message_content_limited = cast("ApplicationFlags", 1 << 19)
    application_command_badge = cast("ApplicationFlags", 1 << 23)


class SystemChannelFlags(BaseFlag):
    """ Represents the system channel flags for a guild. """
    __slots__ = ()

    suppress_join_notifications = cast("SystemChannelFlags", 1 << 0)
    suppress_premium_subscriptions = cast("SystemChannelFlags", 1 << 1)
    suppress_guild_reminder_notifications = cast("SystemChannelFlags", 1 << 2)
    suppress_join_notification_replies = cast("SystemChannelFlags", 1 << 3)
    suppress_role_subscription_purchase_notifications = cast("SystemChannelFlags", 1 << 4)
    suppress_role_subscription_purchase_notifications_replies = cast("SystemChannelFlags", 1 << 5)


class Permissions(BaseFlag):
    """ Represents the permission flags for a guild member or role. """
    __slots__ = ()

    create_instant_invite = cast("Permissions", 1 << 0)
    kick_members = cast("Permissions", 1 << 1)
    ban_members = cast("Permissions", 1 << 2)
    administrator = cast("Permissions", 1 << 3)
    manage_channels = cast("Permissions", 1 << 4)
    manage_guild = cast("Permissions", 1 << 5)
    add_reactions = cast("Permissions", 1 << 6)
    view_audit_log = cast("Permissions", 1 << 7)
    priority_speaker = cast("Permissions", 1 << 8)
    stream = cast("Permissions", 1 << 9)
    view_channel = cast("Permissions", 1 << 10)
    send_messages = cast("Permissions", 1 << 11)
    send_tts_messages = cast("Permissions", 1 << 12)
    manage_messages = cast("Permissions", 1 << 13)
    embed_links = cast("Permissions", 1 << 14)
    attach_files = cast("Permissions", 1 << 15)
    read_message_history = cast("Permissions", 1 << 16)
    mention_everyone = cast("Permissions", 1 << 17)
    use_external_emojis = cast("Permissions", 1 << 18)
    view_guild_insights = cast("Permissions", 1 << 19)
    connect = cast("Permissions", 1 << 20)
    speak = cast("Permissions", 1 << 21)
    mute_members = cast("Permissions", 1 << 22)
    deafen_members = cast("Permissions", 1 << 23)
    move_members = cast("Permissions", 1 << 24)
    use_vad = cast("Permissions", 1 << 25)
    change_nickname = cast("Permissions", 1 << 26)
    manage_nicknames = cast("Permissions", 1 << 27)
    manage_roles = cast("Permissions", 1 << 28)
    manage_webhooks = cast("Permissions", 1 << 29)
    manage_guild_expressions = cast("Permissions", 1 << 30)
    use_application_commands = cast("Permissions", 1 << 31)
    request_to_speak = cast("Permissions", 1 << 32)
    manage_events = cast("Permissions", 1 << 33)
    manage_threads = cast("Permissions", 1 << 34)
    create_public_threads = cast("Permissions", 1 << 35)
    create_private_threads = cast("Permissions", 1 << 36)
    use_external_stickers = cast("Permissions", 1 << 37)
    send_messages_in_threads = cast("Permissions", 1 << 38)
    use_embedded_activities = cast("Permissions", 1 << 39)
    moderate_members = cast("Permissions", 1 << 40)
    view_creator_monetization_analytics = cast("Permissions", 1 << 41)
    use_soundboard = cast("Permissions", 1 << 42)
    create_guild_expressions = cast("Permissions", 1 << 43)
    create_events = cast("Permissions", 1 << 44)
    use_external_sounds = cast("Permissions", 1 << 45)
    send_voice_messages = cast("Permissions", 1 << 46)
    set_voice_channel_status = cast("Permissions", 1 << 48)
    send_polls = cast("Permissions", 1 << 49)
    use_external_apps = cast("Permissions", 1 << 50)
    pin_messages = cast("Permissions", 1 << 51)
    bypass_slowmode = cast("Permissions", 1 << 52)

    def handle_overwrite(self, allow: int, deny: int) -> "Permissions":
        """
        Handles the overwrite of permissions.

        Parameters
        ----------
        allow
            The permission flag integer to allow
        deny
            The permission flag integer to deny

        Returns
        -------
            The permissions with the overwrite applied
        """
        new_value: int = (self.value & ~deny) | allow
        return Permissions(new_value)


class PermissionOverwrite:
    """ Represents a permission overwrite for a channel target (member or role). """

    __slots__ = (
        "allow",
        "deny",
        "target",
        "target_type",
    )

    def __init__(
        self,
        target: Snowflake | int,
        *,
        allow: Permissions | None = None,
        deny: Permissions | None = None,
        target_type: PermissionType | None = None
    ):
        self.allow: Permissions = allow or Permissions.none()
        """ The permissions that are explicitly allowed for the target. """

        self.deny: Permissions = deny or Permissions.none()
        """ The permissions that are explicitly denied for the target. """

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

        self.target: Snowflake = target
        """ The target of the permission overwrite (member or role). """

        self.target_type: PermissionType = (
            target_type or
            PermissionType.member
        )
        """ The type of the overwrite target, either member or role. """

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
        data
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
