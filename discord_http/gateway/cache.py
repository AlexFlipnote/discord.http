from typing import Optional, Union, TYPE_CHECKING

from .flags import GatewayCacheFlags

if TYPE_CHECKING:
    from ..channel import PartialChannel, BaseChannel
    from ..client import Client
    from ..guild import PartialGuild, Guild
    from ..member import PartialMember, Member
    from ..role import PartialRole, Role
    from ..voice import VoiceState, PartialVoiceState

__all__ = (
    "Cache",
)


class Cache:
    def __init__(
        self,
        *,
        client: "Client"
    ):
        self.client = client
        self.cache_flags = client._gateway_cache

        self.__guilds: dict[int, Union["PartialGuild", "Guild"]] = {}

    @property
    def guilds(self) -> list[Union["PartialGuild", "Guild"]]:
        return list(self.__guilds.values())

    def get_guild(self, guild_id: int) -> Optional[Union["PartialGuild", "Guild"]]:
        return self.__guilds.get(guild_id, None)

    def add_guild(self, guild_id: int, guild: Union["PartialGuild", "Guild"]) -> None:
        if self.cache_flags is None:
            return None

        if GatewayCacheFlags.guilds in self.cache_flags:
            self.__guilds[guild_id] = guild
        elif GatewayCacheFlags.partial_guilds in self.cache_flags:
            self.__guilds[guild_id] = self.client.get_partial_guild(guild_id)
        else:
            # (Partial)Guild is not cached, nowhere to store it
            return None

        g = self.__guilds[guild_id]

        # When GUILD_CREATE is received, the cache is already created
        # Make sure we respect what the cache flags are
        if GatewayCacheFlags.channels in self.cache_flags:
            pass
        elif GatewayCacheFlags.partial_channels in self.cache_flags:
            g._cache_channels = {
                k: self.client.get_partial_channel(
                    v.id, guild_id=guild_id
                )
                for k, v in dict(g._cache_channels).items()
            }
        else:
            g._cache_channels = {}

        if GatewayCacheFlags.roles in self.cache_flags:
            pass
        elif GatewayCacheFlags.partial_roles in self.cache_flags:
            g._cache_roles = {
                k: self.client.get_partial_role(
                    v.id, guild_id
                )
                for k, v in dict(g._cache_roles).items()
            }
        else:
            g._cache_roles = {}

        if GatewayCacheFlags.emojis in self.cache_flags:
            pass
        elif GatewayCacheFlags.partial_emojis in self.cache_flags:
            g._cache_emojis = {
                k: self.client.get_partial_emoji(
                    v.id, guild_id=guild_id
                )
                for k, v in dict(g._cache_emojis).items()
            }
        else:
            g._cache_emojis = {}

        if GatewayCacheFlags.stickers in self.cache_flags:
            pass
        elif GatewayCacheFlags.partial_stickers in self.cache_flags:
            g._cache_stickers = {
                k: self.client.get_partial_sticker(
                    v.id, guild_id=guild_id
                )
                for k, v in dict(g._cache_stickers).items()
            }
        else:
            g._cache_stickers = {}

        if GatewayCacheFlags.voice_states in self.cache_flags:
            pass
        elif GatewayCacheFlags.partial_voice_states in self.cache_flags:
            g._cache_voice_states = {
                k: self.client.get_partial_voice_state(
                    v.id,
                    guild_id=guild_id,
                    channel_id=v.channel_id
                )
                for k, v in dict(g._cache_voice_states).items()
            }
        else:
            g._cache_voice_states = {}

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

        _vs_update: Optional[Union["VoiceState", "PartialVoiceState"]] = None
        if GatewayCacheFlags.voice_states in self.cache_flags:
            _vs_update = voice_state

        elif GatewayCacheFlags.partial_voice_states in self.cache_flags:
            _vs_update = self.client.get_partial_voice_state(
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

    def remove_guild(self, guild_id: int) -> Optional[Union["PartialGuild", "Guild"]]:
        if self.cache_flags is None:
            return None

        return self.__guilds.pop(guild_id, None)

    def add_member(self, member: Union["Member", "PartialMember"]) -> None:
        if self.cache_flags is None:
            return None

        guild = self.get_guild(member.guild_id)
        if not guild:
            return None

        if GatewayCacheFlags.members in self.cache_flags:
            guild._cache_members[member.id] = member
        elif GatewayCacheFlags.partial_members in self.cache_flags:
            guild._cache_members[member.id] = self.client.get_partial_member(
                member.id, member.guild_id
            )

    def remove_member(self, member: Union["Member", "PartialMember"]) -> None:
        if self.cache_flags is None:
            return None

        guild = self.get_guild(member.guild_id)
        if not guild:
            return None

        guild._cache_members.pop(member.id, None)

    def add_channel(self, channel: Union["BaseChannel", "PartialChannel"]) -> None:
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
            guild._cache_channels[channel.id] = self.client.get_partial_channel(
                channel.id, guild_id=channel.guild_id
            )

    def remove_channel(self, channel: Union["BaseChannel", "PartialChannel"]) -> None:
        if self.cache_flags is None:
            return None
        if not channel.guild_id:
            return None

        guild = self.get_guild(channel.guild_id)
        if not guild:
            return None

        guild._cache_channels.pop(channel.id, None)

    def add_role(self, role: Union["Role", "PartialRole"]) -> None:
        if self.cache_flags is None:
            return None

        guild = self.get_guild(role.guild_id)
        if not guild:
            return None

        if GatewayCacheFlags.roles in self.cache_flags:
            guild._cache_roles[role.id] = role
        elif GatewayCacheFlags.partial_roles in self.cache_flags:
            guild._cache_roles[role.id] = self.client.get_partial_role(
                role.id, role.guild_id
            )

    def remove_role(self, role: Union["Role", "PartialRole"]) -> None:
        if self.cache_flags is None:
            return None

        guild = self.get_guild(role.guild_id)
        if not guild:
            return None

        guild._cache_roles.pop(role.id, None)
