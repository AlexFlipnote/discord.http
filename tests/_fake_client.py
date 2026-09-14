"""
Shared lightweight test double for `Client`.

Mirrors every `get_partial_x` / `create_x_from_data` factory method on the
real `Client` class, bound to whatever `state` object is handed to it (almost
always a test file's own minimal `FakeState`). Individual test files should
give their `FakeState` a `self.bot = FakeBot(self)` in `__init__` so any code
path that does `self._state.bot.get_partial_x(...)` / `create_x_from_data(...)`
keeps working under test, exactly like it does against a real `Client`.
"""

from discord_http.audit import AuditLogEntry
from discord_http.automod import PartialAutoModRule
from discord_http.channel import PartialChannel, PublicThread, PrivateThread, Thread, ForumThread
from discord_http.emoji import PartialEmoji, Emoji
from discord_http.entitlements import PartialSKU, SKU, PartialEntitlements, Entitlements
from discord_http.guild import PartialGuild, Guild, PartialScheduledEvent
from discord_http.integrations import Integration
from discord_http.invite import PartialInvite, Invite
from discord_http.member import PartialMember, Member, ThreadMember, PartialThreadMember
from discord_http.message import PartialMessage, Message, WebhookMessage
from discord_http.role import PartialRole, Role
from discord_http.soundboard import PartialSoundboardSound, SoundboardSound
from discord_http.sticker import PartialSticker, Sticker
from discord_http.user import User, PartialUser, Application
from discord_http.webhook import PartialWebhook


class FakeBot:
    def __init__(self, state):
        self.state = state

    def get_partial_channel(self, channel_id, *, guild_id=None):
        return PartialChannel(state=self.state, id=channel_id, guild_id=guild_id)

    def get_partial_automod_rule(self, rule_id, guild_id):
        return PartialAutoModRule(state=self.state, id=rule_id, guild_id=guild_id)

    def get_partial_invite(self, invite_code, *, channel_id=None, guild_id=None):
        return PartialInvite(state=self.state, code=invite_code, channel_id=channel_id, guild_id=guild_id)

    def get_partial_emoji(self, emoji_id, *, guild_id=None):
        return PartialEmoji(state=self.state, id=emoji_id, guild_id=guild_id)

    def get_partial_sticker(self, sticker_id, *, guild_id=None):
        return PartialSticker(state=self.state, id=sticker_id, guild_id=guild_id)

    def get_partial_soundboard_sound(self, sound_id, *, guild_id=None):
        return PartialSoundboardSound(state=self.state, id=sound_id, guild_id=guild_id)

    def get_partial_message(self, message_id, channel_id, guild_id=None):
        return PartialMessage(state=self.state, id=message_id, channel_id=channel_id, guild_id=guild_id)

    def get_partial_webhook(self, webhook_id, *, webhook_token=None):
        return PartialWebhook(state=self.state, id=webhook_id, token=webhook_token)

    def get_partial_user(self, user_id):
        return PartialUser(state=self.state, id=user_id)

    def get_partial_member(self, user_id, guild_id):
        return PartialMember(state=self.state, id=user_id, guild_id=guild_id)

    def get_partial_sku(self, sku_id):
        return PartialSKU(state=self.state, id=sku_id)

    def get_partial_entitlement(self, entitlement_id):
        return PartialEntitlements(state=self.state, id=entitlement_id)

    def get_partial_scheduled_event(self, event_id, guild_id):
        return PartialScheduledEvent(state=self.state, id=event_id, guild_id=guild_id)

    def get_partial_guild(self, guild_id):
        return PartialGuild(state=self.state, id=guild_id)

    def get_partial_role(self, role_id, guild_id):
        return PartialRole(state=self.state, id=role_id, guild_id=guild_id)

    def create_public_thread_from_data(self, data):
        return PublicThread(state=self.state, data=data)

    def create_application_from_data(self, data):
        return Application(state=self.state, data=data)

    def create_emoji_from_data(self, data, guild=None):
        return Emoji(state=self.state, data=data, guild=guild)

    def create_sticker_from_data(self, data, guild=None):
        return Sticker(state=self.state, data=data, guild=guild)

    def create_soundboard_sound_from_data(self, data, guild=None):
        return SoundboardSound(state=self.state, data=data, guild=guild)

    def create_invite_from_data(self, data):
        return Invite(state=self.state, data=data)

    def create_message_from_data(self, data, guild=None):
        return Message(state=self.state, data=data, guild=guild)

    def create_webhook_message_from_data(self, data, *, application_id, token):
        return WebhookMessage(state=self.state, data=data, application_id=application_id, token=token)

    def create_user_from_data(self, data):
        return User(state=self.state, data=data)

    def create_member_from_data(self, data, guild):
        return Member(state=self.state, guild=guild, data=data)

    def create_thread_member_from_data(self, data, guild):
        return ThreadMember(state=self.state, guild=guild, data=data)

    def create_entitlements_from_data(self, data):
        return Entitlements(state=self.state, data=data)

    def create_guild_from_data(self, data, *, populate_cache=True):
        return Guild(state=self.state, data=data, populate_cache=populate_cache)

    def create_role_from_data(self, data, guild):
        return Role(state=self.state, guild=guild, data=data)

    def create_private_thread_from_data(self, data):
        return PrivateThread(state=self.state, data=data)

    def create_thread_from_data(self, data):
        return Thread(state=self.state, data=data)

    def create_forum_thread_from_data(self, data):
        return ForumThread(state=self.state, data=data)

    def create_partial_thread_member_from_data(self, data, guild_id):
        return PartialThreadMember(state=self.state, data=data, guild_id=guild_id)

    def create_sku_from_data(self, data):
        return SKU(state=self.state, data=data)

    def create_integration_from_data(self, data, guild):
        return Integration(state=self.state, data=data, guild=guild)

    def create_audit_log_entry_from_data(self, data, *, guild=None, users=None):
        return AuditLogEntry(state=self.state, data=data, guild=guild, users=users)
