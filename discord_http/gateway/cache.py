from typing import TYPE_CHECKING

from ..channel import BaseChannel
from ..voice import VoiceState, PartialVoiceState

from .flags import GatewayCacheFlags


if TYPE_CHECKING:
    from ..channel import PartialChannel, PartialThread
    from ..client import Client
    from ..emoji import Emoji
    from ..guild import PartialGuild, Guild
    from ..member import PartialMember, Member
    from ..role import PartialRole, Role
    from ..sticker import Sticker

    from .object import Presence

__all__ = (
    "Cache",
)


class Cache:
    def __init__(
        self,
        *,
        client: "Client"
    ):
        self.bot = client
        self.cache_flags = client._gateway_cache

        self.__guilds: dict[int, "PartialGuild | Guild"] = {}

    @property
    def guilds(self) -> list["PartialGuild | Guild"]:
        """ Returns a list of all the guilds in the cache. """
        return list(self.__guilds.values())

    def get_guild(self, guild_id: int | None) -> "PartialGuild | Guild | None":
        """ Returns the guild from the cache if it exists. """
        if guild_id is None:
            return None
        return self.__guilds.get(guild_id, None)

    def add_guild(
        self,
        guild_id: int,
        guild: "PartialGuild | Guild",
        data: dict
    ) -> "Guild | PartialGuild | None":
        """
        Add a guild to the cache.

        Parameters
        ----------
        guild_id:
            Guild ID to add
        guild:
            The object of the guild
        data:
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

        guild_ = self.__guilds[guild_id]

        # When GUILD_CREATE is received, the cache is already created
        # Make sure we respect what the cache flags are
        if GatewayCacheFlags.channels in self.cache_flags:
            guild_._cache_channels = {
                int(g["id"]): BaseChannel.from_dict(
                    state=self.bot.state,
                    data=g,
                    guild_id=guild_id
                )
                for g in data["channels"]
            }
        elif GatewayCacheFlags.partial_channels in self.cache_flags:
            guild_._cache_channels = {
                int(g["id"]): self.bot.get_partial_channel(
                    int(g["id"]),
                    guild_id=guild_id
                )
                for g in data["channels"]
            }
        else:
            guild_._cache_channels = {}

        if GatewayCacheFlags.members in self.cache_flags:
            from ..member import Member
            guild_._cache_members = {
                int(g["user"]["id"]): Member(
                    state=self.bot.state,
                    guild=guild_,
                    data=g
                )
                for g in data["members"]
            }
        elif GatewayCacheFlags.partial_members in self.cache_flags:
            guild_._cache_members = {
                int(g["user"]["id"]): self.bot.get_partial_member(
                    g["user"]["id"], guild_id=guild_id
                )
                for g in data["members"]
            }
        else:
            # Still cache the only member which is the bot
            from ..member import Member
            guild_._cache_members = {
                int(g["user"]["id"]): Member(
                    state=self.bot.state,
                    guild=guild_,
                    data=g
                )
                for g in data["members"]
                if int(g["user"]["id"]) == self.bot.user.id
            }

        if GatewayCacheFlags.roles in self.cache_flags:
            pass
        elif GatewayCacheFlags.partial_roles in self.cache_flags:
            guild_._cache_roles = {
                k: self.bot.get_partial_role(
                    v.id, guild_id
                )
                for k, v in dict(guild_._cache_roles).items()
            }
        else:
            guild_._cache_roles = {}

        if GatewayCacheFlags.emojis in self.cache_flags:
            pass
        elif GatewayCacheFlags.partial_emojis in self.cache_flags:
            guild_._cache_emojis = {
                k: self.bot.get_partial_emoji(
                    v.id, guild_id=guild_id
                )
                for k, v in dict(guild_._cache_emojis).items()
            }
        else:
            guild_._cache_emojis = {}

        if GatewayCacheFlags.stickers in self.cache_flags:
            pass
        elif GatewayCacheFlags.partial_stickers in self.cache_flags:
            guild_._cache_stickers = {
                k: self.bot.get_partial_sticker(
                    v.id, guild_id=guild_id
                )
                for k, v in dict(guild_._cache_stickers).items()
            }
        else:
            guild_._cache_stickers = {}

        if GatewayCacheFlags.threads in self.cache_flags:
            guild_._cache_threads = {
                int(g["id"]): BaseChannel.from_dict(
                    state=self.bot.state,
                    data=g,
                    guild_id=guild_id
                )
                for g in data["threads"]
            }
        elif GatewayCacheFlags.partial_threads in self.cache_flags:
            guild_._cache_threads = {
                int(g["id"]): self.bot.get_partial_channel(
                    int(g["id"]),
                    guild_id=guild_id
                )
                for g in data["threads"]
            }
        else:
            guild_._cache_threads = {}

        # Do voice states in the end
        if GatewayCacheFlags.voice_states in self.cache_flags:
            guild_._cache_voice_states = {
                int(g["user_id"]): VoiceState(
                    state=self.bot.state,
                    data=g,
                    guild=guild_,
                    channel=(
                        guild_.get_channel(int(g["channel_id"])) or
                        self.bot.get_partial_channel(
                            int(g["channel_id"]),
                            guild_id=guild_id
                        )
                    )
                )
                for g in data["voice_states"]
            }
        elif GatewayCacheFlags.partial_voice_states in self.cache_flags:
            guild_._cache_voice_states = {
                int(g["user_id"]): self.bot.get_partial_voice_state(
                    int(g["user_id"]),
                    guild_id=guild_id,
                    channel_id=int(g["channel_id"])
                )
                for g in data["voice_states"]
            }
        else:
            guild_._cache_voice_states = {}

        return guild_

    def update_guild(self, guild_id: int, data: dict) -> None:
        """
        Update a guild in the cache.

        Parameters
        ----------
        guild_id:
            Guild ID to update
        data:
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
        voice_state:
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
        guild_id:
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
        member:
            The member to add
        count_member:
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
            guild._cache_members[member.id] = member
        elif GatewayCacheFlags.partial_members in self.cache_flags:
            guild._cache_members[member.id] = self.bot.get_partial_member(
                member.id, member.guild_id
            )
        else:
            # Cache bot regardless of cache flags
            if member.id == self.bot.user.id:
                guild._cache_members[member.id] = member

    def update_member(self, member: "Member | PartialMember") -> None:
        """
        Update a member in the cache.

        Parameters
        ----------
        member:
            The member to update
        """
        self.add_member(member, count_member=False)

    def remove_member(self, guild_id: int, member_id: int) -> "Member | PartialMember | None":
        """
        Remove a member from the cache.

        Parameters
        ----------
        guild_id:
            Guild ID to remove the member from
        member_id:
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
        presence:
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
        guild_id:
            Guild ID to get the channel from
        channel_id:
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
        guild_id:
            The Guild ID to get the channel thread from
        channel_id:
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
        channel:
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
        channel:
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
        thread:
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
        thread:
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
        role:
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
        role:
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
        guild_id:
            Guild ID to update the emojis from
        emojis:
            The emojis to update
        """
        if self.cache_flags is None:
            return

        guild = self.get_guild(guild_id)
        if not guild:
            return

        if GatewayCacheFlags.emojis in self.cache_flags:
            guild._cache_emojis = {
                int(g.id): g
                for g in emojis
            }
        elif GatewayCacheFlags.partial_emojis in self.cache_flags:
            guild._cache_emojis = {
                int(g.id): self.bot.get_partial_emoji(
                    g.id, guild_id=guild_id
                )
                for g in emojis
            }

    def update_stickers(self, guild_id: int, stickers: list["Sticker"]) -> None:
        """
        Update stickers in the cache.

        Parameters
        ----------
        guild_id:
            Guild ID to update the stickers from
        stickers:
            The stickers to update
        """
        if self.cache_flags is None:
            return

        guild = self.get_guild(guild_id)
        if not guild:
            return

        if GatewayCacheFlags.stickers in self.cache_flags:
            guild._cache_stickers = {
                int(g.id): g
                for g in stickers
            }
        elif GatewayCacheFlags.partial_stickers in self.cache_flags:
            guild._cache_stickers = {
                int(g.id): self.bot.get_partial_sticker(
                    g.id, guild_id=guild_id
                )
                for g in stickers
            }
