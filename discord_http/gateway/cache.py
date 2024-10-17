from typing import TYPE_CHECKING

from ..channel import BaseChannel
from ..voice import VoiceState, PartialVoiceState

from .flags import GatewayCacheFlags

if TYPE_CHECKING:
    from .object import Presence
    from ..channel import PartialChannel, PublicThread, PrivateThread
    from ..client import Client
    from ..guild import PartialGuild, Guild
    from ..emoji import Emoji
    from ..sticker import Sticker
    from ..member import PartialMember, Member
    from ..role import PartialRole, Role

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
        return list(self.__guilds.values())

    def get_guild(self, guild_id: int | None) -> "PartialGuild | Guild | None":
        if guild_id is None:
            return None
        return self.__guilds.get(guild_id, None)

    def add_guild(
        self,
        guild_id: int,
        guild: "PartialGuild | Guild",
        data: dict
    ) -> None:
        if self.cache_flags is None:
            return None

        if GatewayCacheFlags.guilds in self.cache_flags:
            self.__guilds[guild_id] = guild
        elif GatewayCacheFlags.partial_guilds in self.cache_flags:
            self.__guilds[guild_id] = self.bot.get_partial_guild(guild_id)
        else:
            # (Partial)Guild is not cached, nowhere to store it
            return None

        _guild = self.__guilds[guild_id]

        # When GUILD_CREATE is received, the cache is already created
        # Make sure we respect what the cache flags are
        if GatewayCacheFlags.channels in self.cache_flags:
            _guild._cache_channels = {  # type: ignore
                int(g["id"]): BaseChannel.from_dict(
                    state=self.bot.state,
                    data=g,
                    guild_id=guild_id
                )
                for g in data["channels"]
            }
        elif GatewayCacheFlags.partial_channels in self.cache_flags:
            _guild._cache_channels = {
                int(g["id"]): self.bot.get_partial_channel(
                    int(g["id"]),
                    guild_id=guild_id
                )
                for g in data["channels"]
            }
        else:
            _guild._cache_channels = {}

        if GatewayCacheFlags.members in self.cache_flags:
            from ..member import Member
            _guild._cache_members = {  # type: ignore
                int(g["user"]["id"]): Member(
                    state=self.bot.state,
                    guild=_guild,
                    data=g
                )
                for g in data["members"]
            }
        elif GatewayCacheFlags.partial_members in self.cache_flags:
            _guild._cache_members = {
                int(g["user"]["id"]): self.bot.get_partial_member(
                    g["user"]["id"], guild_id=guild_id
                )
                for g in data["members"]
            }
        else:
            # Still cache the only member which is the bot
            from ..member import Member
            _guild._cache_members = {  # type: ignore
                int(g["user"]["id"]): Member(
                    state=self.bot.state,
                    guild=_guild,
                    data=g
                )
                for g in data["members"]
                if int(g["user"]["id"]) == self.bot.user.id
            }

        if GatewayCacheFlags.roles in self.cache_flags:
            pass
        elif GatewayCacheFlags.partial_roles in self.cache_flags:
            _guild._cache_roles = {
                k: self.bot.get_partial_role(
                    v.id, guild_id
                )
                for k, v in dict(_guild._cache_roles).items()
            }
        else:
            _guild._cache_roles = {}

        if GatewayCacheFlags.emojis in self.cache_flags:
            pass
        elif GatewayCacheFlags.partial_emojis in self.cache_flags:
            _guild._cache_emojis = {
                k: self.bot.get_partial_emoji(
                    v.id, guild_id=guild_id
                )
                for k, v in dict(_guild._cache_emojis).items()
            }
        else:
            _guild._cache_emojis = {}

        if GatewayCacheFlags.stickers in self.cache_flags:
            pass
        elif GatewayCacheFlags.partial_stickers in self.cache_flags:
            _guild._cache_stickers = {
                k: self.bot.get_partial_sticker(
                    v.id, guild_id=guild_id
                )
                for k, v in dict(_guild._cache_stickers).items()
            }
        else:
            _guild._cache_stickers = {}

        # Do voice states in the end
        if GatewayCacheFlags.voice_states in self.cache_flags:
            _guild._cache_voice_states = {  # type: ignore
                int(g["user_id"]): VoiceState(
                    state=self.bot.state,
                    data=g,
                    guild=_guild,
                    channel=(
                        _guild.get_channel(int(g["channel_id"])) or
                        self.bot.get_partial_channel(
                            int(g["channel_id"]),
                            guild_id=guild_id
                        )
                    )
                )
                for g in data["voice_states"]
            }
        elif GatewayCacheFlags.partial_voice_states in self.cache_flags:
            _guild._cache_voice_states = {
                int(g["user_id"]): self.bot.get_partial_voice_state(
                    int(g["user_id"]),
                    guild_id=guild_id,
                    channel_id=int(g["channel_id"])
                )
                for g in data["voice_states"]
            }
        else:
            _guild._cache_voice_states = {}

    def update_guild(self, guild_id: int, data: dict) -> None:
        if self.cache_flags is None:
            return None

        guild = self.get_guild(guild_id)
        if not guild:
            return None

        if GatewayCacheFlags.guilds not in self.cache_flags:
            # Guild is not cached, nothing to update
            return None

        guild._update(data)  # type: ignore

    def update_voice_state(self, voice_state: "VoiceState") -> None:
        if self.cache_flags is None:
            return None
        if not voice_state.guild_id:
            return None

        guild = self.get_guild(voice_state.guild_id)
        if not guild:
            return None

        _vs_update: "VoiceState | PartialVoiceState | None" = None
        if GatewayCacheFlags.voice_states in self.cache_flags:
            _vs_update = voice_state

        elif GatewayCacheFlags.partial_voice_states in self.cache_flags:
            _vs_update = self.bot.get_partial_voice_state(
                voice_state.id,
                guild_id=voice_state.guild_id,
                channel_id=voice_state.channel_id
            )

        if _vs_update is not None:
            if _vs_update.channel_id is None:
                # Voice state is not in a channel, remove it
                guild._cache_voice_states.pop(voice_state.id, None)
            else:
                guild._cache_voice_states[voice_state.id] = _vs_update

    def remove_guild(self, guild_id: int) -> "PartialGuild | Guild | None":
        if self.cache_flags is None:
            return None

        return self.__guilds.pop(guild_id, None)

    def add_member(self, member: "Member | PartialMember") -> None:
        if self.cache_flags is None:
            return None

        guild = self.get_guild(member.guild_id)
        if not guild:
            return None

        if guild.member_count is not None:
            guild.member_count += 1

        if GatewayCacheFlags.members in self.cache_flags:
            guild._cache_members[member.id] = member
        elif GatewayCacheFlags.partial_members in self.cache_flags:
            guild._cache_members[member.id] = self.bot.get_partial_member(
                member.id, member.guild_id
            )

    def remove_member(self, member: "Member | PartialMember") -> None:
        if self.cache_flags is None:
            return None

        guild = self.get_guild(member.guild_id)
        if not guild:
            return None

        if guild.member_count is not None:
            guild.member_count -= 1

        guild._cache_members.pop(member.id, None)

    def update_presence(self, presence: "Presence | None") -> None:
        if self.cache_flags is None:
            return None

        if GatewayCacheFlags.presences not in self.cache_flags:
            return None

        guild = self.get_guild(presence.guild.id)
        if not guild:
            return None

        member = guild.get_member(presence.user.id)
        if not member:
            return None

        member._update_presence(presence)

    def get_channel(
        self,
        guild_id: int | None,
        channel_id: int
    ) -> "BaseChannel | PartialChannel | None":
        guild = self.get_guild(guild_id)
        if not guild:
            return None

        return guild.get_channel(channel_id)

    def add_channel(self, channel: "BaseChannel | PartialChannel") -> None:
        if self.cache_flags is None:
            return None
        if not channel.guild_id:
            return None

        guild = self.get_guild(channel.guild_id)
        if not guild:
            return None

        if GatewayCacheFlags.channels in self.cache_flags:
            guild._cache_channels[channel.id] = channel
        elif GatewayCacheFlags.partial_channels in self.cache_flags:
            guild._cache_channels[channel.id] = self.bot.get_partial_channel(
                channel.id, guild_id=channel.guild_id
            )

    def remove_channel(self, channel: "BaseChannel | PartialChannel") -> None:
        if self.cache_flags is None:
            return None
        if not channel.guild_id:
            return None

        guild = self.get_guild(channel.guild_id)
        if not guild:
            return None

        guild._cache_channels.pop(channel.id, None)

    def add_thread(self, thread: "PublicThread | PrivateThread") -> None:
        if self.cache_flags is None:
            return None
        if not thread.guild_id:
            return None

        guild = self.get_guild(thread.guild_id)
        if not guild:
            return None

        if GatewayCacheFlags.threads in self.cache_flags:
            guild._cache_threads[thread.id] = thread
        elif GatewayCacheFlags.partial_threads in self.cache_flags:
            guild._cache_threads[thread.id] = self.bot.get_partial_channel(
                thread.id, guild_id=thread.guild_id
            )

    def remove_thread(self, thread: "PublicThread | PrivateThread") -> None:
        if self.cache_flags is None:
            return None
        if not thread.guild_id:
            return None

        guild = self.get_guild(thread.guild_id)
        if not guild:
            return None

        guild._cache_threads.pop(thread.id, None)

    def add_role(self, role: "Role | PartialRole") -> None:
        if self.cache_flags is None:
            return None

        guild = self.get_guild(role.guild_id)
        if not guild:
            return None

        if GatewayCacheFlags.roles in self.cache_flags:
            guild._cache_roles[role.id] = role
        elif GatewayCacheFlags.partial_roles in self.cache_flags:
            guild._cache_roles[role.id] = self.bot.get_partial_role(
                role.id, role.guild_id
            )

    def remove_role(self, role: "Role | PartialRole") -> None:
        if self.cache_flags is None:
            return None

        guild = self.get_guild(role.guild_id)
        if not guild:
            return None

        guild._cache_roles.pop(role.id, None)

    def update_emojis(self, guild_id: int, emojis: list["Emoji"]):
        if self.cache_flags is None:
            return None

        guild = self.get_guild(guild_id)
        if not guild:
            return None

        if GatewayCacheFlags.emojis in self.cache_flags:
            guild._cache_emojis = {  # type: ignore
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

    def update_stickers(self, guild_id: int, stickers: list["Sticker"]):
        if self.cache_flags is None:
            return None

        guild = self.get_guild(guild_id)
        if not guild:
            return None

        if GatewayCacheFlags.stickers in self.cache_flags:
            guild._cache_stickers = {  # type: ignore
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
