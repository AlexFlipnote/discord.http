import asyncio
import sys
import weakref

from typing import TYPE_CHECKING

from ..channel import BaseChannel
from ..member import Member
from ..user import User
from ..voice import VoiceState, PartialVoiceState

from .flags import GatewayCacheFlags

if TYPE_CHECKING:
    from collections.abc import Generator

    from ..channel import PartialChannel, PartialThread
    from ..client import Client
    from ..emoji import Emoji
    from ..guild import PartialGuild, Guild
    from ..member import PartialMember
    from ..role import PartialRole, Role
    from ..sticker import Sticker

    from .object import Presence

__all__ = (
    "Cache",
)

_SHARED_STATE_ATTR = "_state"
_YIELD_EVERY = 2000
_IMMUTABLE_LEAF_TYPES = (str, bytes, int, float, bool, complex, type(None))
_GUILD_CACHE_ATTRS = (
    "_cache_members",
    "_cache_channels",
    "_cache_threads",
    "_cache_roles",
    "_cache_emojis",
    "_cache_soundboard_sounds",
    "_cache_stickers",
    "_cache_voice_states",
)


def _iter_slots(cls: type) -> "Generator[str, None, None]":
    """ Yield every `__slots__` name declared anywhere in a class' MRO, without duplicates. """
    yielded: set[str] = set()
    for klass in cls.__mro__:
        slots = getattr(klass, "__slots__", ())
        if isinstance(slots, str):
            slots = (slots,)
        for name in slots:
            if name not in yielded:
                yielded.add(name)
                yield name


async def _deep_sizeof(
    root: object,
    seen: set[int],
    skip: frozenset[str] = frozenset({_SHARED_STATE_ATTR})
) -> int:
    """ Roughly estimate the total memory footprint of `root`, in bytes. """
    total = 0
    stack: list[object] = [root]
    since_yield = 0

    while stack:
        obj = stack.pop()

        since_yield += 1
        if since_yield >= _YIELD_EVERY:
            since_yield = 0
            await asyncio.sleep(0)

        if obj is None or isinstance(obj, _IMMUTABLE_LEAF_TYPES):
            total += sys.getsizeof(obj)
            continue

        oid = id(obj)
        if oid in seen:
            continue
        seen.add(oid)

        total += sys.getsizeof(obj)

        if isinstance(obj, (dict, weakref.WeakValueDictionary)):
            for key, value in list(obj.items()):
                stack.extend((key, value))
            continue

        if isinstance(obj, (list, tuple, set, frozenset)):
            stack.extend(list(obj))
            continue

        if getattr(type(obj), "__slots__", None) is not None:
            for name in _iter_slots(type(obj)):
                if name in skip or name in ("__dict__", "__weakref__"):
                    continue
                value = getattr(obj, name, None)
                if value is not None:
                    stack.append(value)
        elif hasattr(obj, "__dict__"):
            stack.append(dict(obj.__dict__))

    return total


class Cache:
    """ Represents the discord.http/gateway cache. """

    __slots__ = ("__guilds", "__users", "_state", "bot", "cache_flags")

    def __init__(
        self,
        *,
        client: "Client"
    ):
        self.bot = client
        """ The client that the cache belongs to. """

        self.cache_flags = client._gateway_cache
        """ The cache flags that determine what is cached. """

        self.__guilds: dict[int, "PartialGuild | Guild"] = {}
        self.__users: "weakref.WeakValueDictionary[int, User]" = weakref.WeakValueDictionary()

    async def calculate_memory_usage(self) -> dict[str, int]:
        """
        Roughly estimate how much memory the cache is currently using in bytes.

        This is a debugging aid, not an exact measurement!
        """
        seen: set[int] = set()
        usage: dict[str, int] = {
            "guilds": 0,
            "members": 0,
            "channels": 0,
            "threads": 0,
            "roles": 0,
            "emojis": 0,
            "soundboard_sounds": 0,
            "stickers": 0,
            "voice_states": 0,
            "users": 0,
        }

        usage["users"] = await _deep_sizeof(dict(self.__users), seen)

        guild_skip = frozenset({_SHARED_STATE_ATTR, *_GUILD_CACHE_ATTRS})
        for guild in list(self.__guilds.values()):
            usage["guilds"] += await _deep_sizeof(guild, seen, guild_skip)
            usage["members"] += await _deep_sizeof(guild._cache_members, seen)
            usage["channels"] += await _deep_sizeof(guild._cache_channels, seen)
            usage["threads"] += await _deep_sizeof(guild._cache_threads, seen)
            usage["roles"] += await _deep_sizeof(guild._cache_roles, seen)
            usage["emojis"] += await _deep_sizeof(guild._cache_emojis, seen)
            usage["soundboard_sounds"] += await _deep_sizeof(guild._cache_soundboard_sounds, seen)
            usage["stickers"] += await _deep_sizeof(guild._cache_stickers, seen)
            usage["voice_states"] += await _deep_sizeof(guild._cache_voice_states, seen)

        usage["total"] = sum(usage.values())
        return usage

    def get_user(self, user_id: int | None) -> "User | None":
        """ Returns the shared, deduplicated user from the cache if it exists. """
        if user_id is None:
            return None
        return self.__users.get(user_id)

    @property
    def _user_dedup_enabled(self) -> bool:
        """ Whether it's worth touching the shared user table at all right now. """
        if self.cache_flags is None:
            return False

        return (
            GatewayCacheFlags.members in self.cache_flags or
            GatewayCacheFlags.partial_members in self.cache_flags
        )

    def _dedupe_plain_user(self, user: "User") -> "User":
        """ Reuse or register the shared canonical `User` for this ID. """
        canonical = self.__users.get(user.id)
        if canonical is not None and canonical is not user:
            canonical._copy_from(user)
            return canonical

        self.__users[user.id] = user
        return user

    def _dedupe_user(self, member: "Member") -> None:
        """ Point a member's embedded user at the shared canonical `User` instance for that ID. """
        user = getattr(member, "_user", None)
        if not isinstance(user, User):
            return

        member._user = self._dedupe_plain_user(user)

    @property
    def guilds(self) -> list["PartialGuild | Guild"]:
        """ A list of all the guilds in the cache. """
        return list(self.__guilds.values())

    def get_guild(self, guild_id: int | None) -> "PartialGuild | Guild | None":
        """ Returns the guild from the cache if it exists. """
        if guild_id is None:
            return None
        return self.__guilds.get(guild_id)

    def add_guild(
        self,
        guild_id: int,
        guild: "PartialGuild | Guild"
    ) -> "Guild | PartialGuild | None":
        """
        Add a guild to the cache.

        Parameters
        ----------
        guild_id
            Guild ID to add
        guild
            The object of the guild
        data
            Data of the guild

        Returns
        -------
            The guild object
        """
        if self.cache_flags is None:
            return None

        if GatewayCacheFlags.guilds in self.cache_flags:
            self.__guilds[guild_id] = guild
        elif GatewayCacheFlags.partial_guilds in self.cache_flags:
            self.__guilds[guild_id] = self.bot.get_partial_guild(guild_id)
        else:
            # (Partial)Guild is not cached, nowhere to store it
            return None

        return self.__guilds.get(guild_id)

    def update_guild(self, guild_id: int, data: dict) -> None:
        """
        Update a guild in the cache.

        Parameters
        ----------
        guild_id
            Guild ID to update
        data
            Data of the guild
        """
        if self.cache_flags is None:
            return

        guild = self.get_guild(guild_id)
        if not guild:
            return

        if GatewayCacheFlags.guilds not in self.cache_flags:
            # Guild is not cached, nothing to update
            return

        guild._update(data)  # type: ignore

    def update_voice_state(self, voice_state: "VoiceState") -> None:
        """
        Update a voice state in the cache.

        Parameters
        ----------
        voice_state
            The voice state to update
        """
        if self.cache_flags is None:
            return
        if not voice_state.guild_id:
            return

        guild = self.get_guild(voice_state.guild_id)
        if not guild:
            return

        vs_update: "VoiceState | PartialVoiceState | None" = None
        if GatewayCacheFlags.voice_states in self.cache_flags:
            vs_update = voice_state

        elif GatewayCacheFlags.partial_voice_states in self.cache_flags:
            vs_update = self.bot.get_partial_voice_state(
                voice_state.id,
                guild_id=voice_state.guild_id,
                channel_id=voice_state.channel_id
            )

        if vs_update is not None:
            if vs_update.channel_id is None:
                # Voice state is not in a channel, remove it
                guild._cache_voice_states.pop(voice_state.id, None)
            else:
                guild._cache_voice_states[voice_state.id] = vs_update

    def remove_guild(self, guild_id: int) -> "PartialGuild | Guild | None":
        """
        Remove a guild from the cache.

        Parameters
        ----------
        guild_id
            Guild ID to remove

        Returns
        -------
            The guild object
        """
        if self.cache_flags is None:
            return None

        return self.__guilds.pop(guild_id, None)

    def add_member(
        self,
        member: "Member | PartialMember",
        *,
        count_member: bool = True
    ) -> None:
        """
        Add a member to the cache.

        Parameters
        ----------
        member
            The member to add
        count_member
            If the members should be counted or not, by default True
        """
        if self.cache_flags is None:
            return

        guild = self.get_guild(member.guild_id)
        if not guild:
            return

        if count_member and guild.member_count is not None:
            guild.member_count += 1

        if GatewayCacheFlags.members in self.cache_flags:
            if isinstance(member, Member):
                self._dedupe_user(member)
            guild._cache_members[member.id] = member
        elif GatewayCacheFlags.partial_members in self.cache_flags:
            guild._cache_members[member.id] = self.bot.get_partial_member(
                member.id, member.guild_id
            )
        else:
            # Cache bot regardless of cache flags
            if member.id == self.bot.user.id:
                if isinstance(member, Member):
                    self._dedupe_user(member)
                guild._cache_members[member.id] = member

    def update_member(self, member: "Member | PartialMember") -> None:
        """
        Update a member in the cache.

        Parameters
        ----------
        member
            The member to update
        """
        self.add_member(member, count_member=False)

    def remove_member(self, guild_id: int, member_id: int) -> "Member | PartialMember | None":
        """
        Remove a member from the cache.

        Parameters
        ----------
        guild_id
            Guild ID to remove the member from
        member_id
            Member ID to remove

        Returns
        -------
            The member object
        """
        if self.cache_flags is None:
            return None

        guild = self.get_guild(guild_id)
        if not guild:
            return None

        if guild.member_count is not None:
            guild.member_count -= 1

        return guild._cache_members.pop(member_id, None)

    def update_presence(self, presence: "Presence | None") -> None:
        """
        Update a presence in the cache.

        Parameters
        ----------
        presence
            The presence to update
        """
        if self.cache_flags is None:
            return

        if GatewayCacheFlags.presences not in self.cache_flags:
            return

        guild = self.get_guild(presence.guild.id)
        if not guild:
            return

        member = guild.get_member(presence.user.id)
        if not member:
            return

        member._update_presence(presence)

    def get_channel(
        self,
        guild_id: int | None,
        channel_id: int
    ) -> "BaseChannel | PartialChannel | None":
        """
        Get a channel from the cache.

        Parameters
        ----------
        guild_id
            Guild ID to get the channel from
        channel_id
            Channel ID to get

        Returns
        -------
            The channel object
        """
        guild = self.get_guild(guild_id)
        if not guild:
            return None

        return guild.get_channel(channel_id)

    def get_channel_thread(
        self,
        guild_id: int,
        channel_id: int
    ) -> "BaseChannel | PartialChannel | None":
        """
        Get a channel thread from the cache.

        Parameters
        ----------
        guild_id
            The Guild ID to get the channel thread from
        channel_id
            The Channel ID to get the channel thread from

        Returns
        -------
            The channel thread object
        """
        guild = self.get_guild(guild_id)
        if not guild:
            return None

        find1 = guild.get_channel(channel_id)
        find2 = guild.get_thread(channel_id)

        return find2 or find1 or None

    def add_channel(self, channel: "BaseChannel | PartialChannel") -> None:
        """
        Add a channel to the cache.

        Parameters
        ----------
        channel
            The channel to add
        """
        if self.cache_flags is None:
            return
        if not channel.guild_id:
            return

        guild = self.get_guild(channel.guild_id)
        if not guild:
            return

        if GatewayCacheFlags.channels in self.cache_flags:
            guild._cache_channels[channel.id] = channel
        elif GatewayCacheFlags.partial_channels in self.cache_flags:
            guild._cache_channels[channel.id] = self.bot.get_partial_channel(
                channel.id, guild_id=channel.guild_id
            )

    def remove_channel(self, channel: "BaseChannel | PartialChannel") -> None:
        """
        Remove a channel from the cache.

        Parameters
        ----------
        channel
            The channel to remove
        """
        if self.cache_flags is None:
            return
        if not channel.guild_id:
            return

        guild = self.get_guild(channel.guild_id)
        if not guild:
            return

        guild._cache_channels.pop(channel.id, None)

    def add_thread(self, thread: "BaseChannel") -> None:
        """
        Add a thread to the cache.

        Parameters
        ----------
        thread
            The thread to add
        """
        if self.cache_flags is None:
            return
        if not thread.guild_id:
            return

        guild = self.get_guild(thread.guild_id)
        if not guild:
            return

        if GatewayCacheFlags.threads in self.cache_flags:
            guild._cache_threads[thread.id] = thread
        elif GatewayCacheFlags.partial_threads in self.cache_flags:
            guild._cache_threads[thread.id] = self.bot.get_partial_channel(
                thread.id, guild_id=thread.guild_id
            )

    def remove_thread(self, thread: "PartialThread") -> None:
        """
        Remove a thread from the cache.

        Parameters
        ----------
        thread
            The thread to remove
        """
        if self.cache_flags is None:
            return
        if not thread.guild_id:
            return

        guild = self.get_guild(thread.guild_id)
        if not guild:
            return

        guild._cache_threads.pop(thread.id, None)

    def add_role(self, role: "Role | PartialRole") -> None:
        """
        Add a role to the cache.

        Parameters
        ----------
        role
            The role to add
        """
        if self.cache_flags is None:
            return

        guild = self.get_guild(role.guild_id)
        if not guild:
            return

        if GatewayCacheFlags.roles in self.cache_flags:
            guild._cache_roles[role.id] = role
        elif GatewayCacheFlags.partial_roles in self.cache_flags:
            guild._cache_roles[role.id] = self.bot.get_partial_role(
                role.id, role.guild_id
            )

    def remove_role(self, role: "Role | PartialRole") -> None:
        """
        Remove a role from the cache.

        Parameters
        ----------
        role
            The role to remove
        """
        if self.cache_flags is None:
            return

        guild = self.get_guild(role.guild_id)
        if not guild:
            return

        guild._cache_roles.pop(role.id, None)

    def update_emojis(self, guild_id: int, emojis: list["Emoji"]) -> None:
        """
        Update emojis in the cache.

        Parameters
        ----------
        guild_id
            Guild ID to update the emojis from
        emojis
            The emojis to update
        """
        if self.cache_flags is None:
            return

        guild = self.get_guild(guild_id)
        if not guild:
            return

        if GatewayCacheFlags.emojis in self.cache_flags:
            guild._cache_emojis = {
                g.id: g for g in emojis
            }
        elif GatewayCacheFlags.partial_emojis in self.cache_flags:
            guild._cache_emojis = {
                g.id: self.bot.get_partial_emoji(
                    g.id, guild_id=guild_id
                )
                for g in emojis
            }

    def update_stickers(self, guild_id: int, stickers: list["Sticker"]) -> None:
        """
        Update stickers in the cache.

        Parameters
        ----------
        guild_id
            Guild ID to update the stickers from
        stickers
            The stickers to update
        """
        if self.cache_flags is None:
            return

        guild = self.get_guild(guild_id)
        if not guild:
            return

        if GatewayCacheFlags.stickers in self.cache_flags:
            guild._cache_stickers = {
                g.id: g
                for g in stickers
            }
        elif GatewayCacheFlags.partial_stickers in self.cache_flags:
            guild._cache_stickers = {
                g.id: self.bot.get_partial_sticker(
                    g.id, guild_id=guild_id
                )
                for g in stickers
            }
