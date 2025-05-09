Event references
================
This serves as a reference for all events that can be used in the bot.
The events are divided into categories, and each event has a description of what it does and what parameters it takes.

An example of how one event is used:

.. code-block:: python

  import discord_http

  client = discord_http.Client(...)

  @client.listener()
  async def on_ready(user: discord_http.User):
      print(f"Logged in as {user}")

If you are trying to get listeners inside a cog, you will need to do the following:

.. code-block:: python

  from discord_http import commands, User

  @commands.listener()
  async def on_ready(self, user: User):
      print(f"Logged in as {user}")

Connection
----------

.. function:: async def on_ready(client)

  Called when the bot token has been verified and everything is loaded, ready to start receiving events from Discord.
  Using this event will disable the default INFO print given by the library, and instead let you decide what it should do.

  :param user: :class:`User` object with information about the token provided.

.. function:: async def on_ping(ping)

  Called whenever Discord sends a ping to the bot, checking if the URL provided for interactions is valid.
  Using this event will disable the default INFO print given by the library, and instead let you decide what it should do.

  :param ping: :class:`Ping` object that tells what information was sent to the bot.


Webhook
-------
.. function:: async def on_raw_interaction(data)

  Called whenever an interaction is received from Discord.
  In order to use this event, you must have `Client.debug_events` set to True, otherwise it will not be called.

  :param data: :class:`dict` raw dictionary with the interaction data sent by Discord.


Errors
------
.. function:: async def on_event_error(client, error)

  Called whenever an error occurs in an event (listener)

  Using this event will disable the default ERROR print given by the library, and instead let you decide what it should do.

  :param client: :class:`Client` The client object.
  :param error: :class:`Exception` object with the error that occurred.


.. function:: async def on_interaction_error(ctx, error):

  Called whenever an error occurs in an interaction (command, autocomplete, button, etc.)

  Using this event will disable the default ERROR print given by the library, and instead let you decide what it should do.

  :param ctx: :class:`Context` The context object.
  :param error: :class:`Exception` object with the error that occurred.


Gateway events
--------------
.. note::
  These events are only provided if discord.http/gateway is enabled.

  .. code-block:: python

    from discord_http import Client
    from discord_http.gateway import Intents

    client = Client(
        ...,
        enable_gateway=True,
        # intents=Intents
    )


Shard events
~~~~~~~~~~~~

.. note::
  These events are only provided if discord.http/gateway is enabled.
  By default if the gateway is enabled, they will do ``[  INFO ]`` logs.
  You can in theory listen to the events and simply do nothing to disable the logs.

.. function:: async def on_shard_ready(shard):

  Called whenever a shard is now ready

  :param shard: :class:`ShardEventPayload` object with information about the shard that is ready.


.. function:: async def on_shard_resumed(shard):

  Called whenever a shard is resumed

  :param shard: :class:`ShardEventPayload` object with information about the shard that was resumed.


.. function:: async def on_shard_closed(shard_close_payload):

  Called whenever a shard is closed

  :param payload: :class:`ShardEventPayload` object with information about the shard that crashed and more information.


Intents.guilds
~~~~~~~~~~~~~~

.. function:: async def on_guild_create(guild):

  Called whenever a guild is created (Bot was added)

  .. note::
    This event is not called unless the shard is ready, to prevent spam.

  :param guild: :class:`Guild` object with information about the guild.


.. function:: async def on_guild_update(guild):

  Called whenever a guild is updated.

  :param guild: :class:`Guild` object with information about the guild.


.. function:: async def on_guild_delete(guild):

  Called whenever a guild is deleted (Bot was removed)

  .. note::
    Depending on your cache rules, Guild will either return Full or Partial object.

  :param guild: :class:`PartialGuild` object with information about the guild.


.. function:: async def on_guild_available(guild):

  Called whenever a guild was initially created, but came back from unavailable state

  .. note::
    Depending on your cache rules, Guild will either return Full or Partial object.

  :param guild: :class:`Guild` object with information about that guild


.. function:: async def on_guild_unavailable(guild):

  Called whenever a guild is deleted, but came back from available state

  .. note::
    Depending on your cache rules, Guild will either return Full or Partial object.

  :param guild: :class:`Guild` object with information about that guild


.. function:: async def on_guild_role_create(role):

  Called whenever a role was created

  .. note::
    Depending on your cache rules, Role.guild will either return Full or Partial object.

  :param role: :class:`Role` object with information about the role.


.. function:: async def on_guild_role_update(role):

  Called whenever a role was updated

  .. note::
    Depending on your cache rules, Role.guild will either return Full or Partial object.

  :param role: :class:`Role` object with information about the role.


.. function:: async def on_guild_role_delete(role):

  Called whenever a role was deleted

  :param role: :class:`PartialRole` object with information about the role.


.. function:: async def on_channel_create(channel):

  Called whenever a channel is created

  .. note::
    Depending on what channel was made, it will either return TextChannel, VoiceChannel, etc.

  :param channel: :class:`BaseChannel` object with information about the channel.


.. function:: async def on_channel_update(channel):

  Called whenever a channel is updated

  :param channel: :class:`BaseChannel` object with information about the channel.


.. function:: async def on_channel_delete(channel):

  Called whenever a channel is deleted

  :param channel: :class:`BaseChannel` object with information about the channel.


.. function:: async def on_channel_pins_update(payload):

  Called whenever a channel's pins are updated

  :param payload: :class:`ChannelPinsUpdate` object with information about the pins.


.. function:: async def on_thread_create(thread):

  Called whenever a thread is created

  .. note::
    Depending on what type of thread was made, it will either return `PublicThread`, `PrivateThread`, etc.

  :param thread: :class:`BaseChannel` object with information about the thread.


.. function:: async def on_thread_update(thread):

  Called whenever a thread is updated

  .. note::
    Depending on what type of thread was updated, it will either return `PublicThread`, `PrivateThread`, etc.

  :param thread: :class:`BaseChannel` object with information about the thread.


.. function:: async def on_thread_delete(thread):

  Called whenever a thread is deleted

  :param thread: :class:`PartialChannel` object with information about the thread.


.. function:: async def on_thread_list_sync(payload):

  Called whenever a thread list is synced

  :param payload: :class:`ThreadListSyncPayload` object with information about the thread list.


.. function:: async def on_thread_member_update(payload):

  Called whenever a thread member is updated

  :param payload: :class:`ThreadMembersUpdatePayload` object with information about the thread member.


.. function:: async def on_thread_members_update(payload):

  Called whenever a thread members are updated

  :param payload: :class:`ThreadMembersUpdatePayload` object with information about the thread members.


.. function:: async def on_stage_instance_create(stage_instance):

  Called whenever a stage instance is created

  .. note::
    Depending on your cache rules, StageInstance.guild will either return Full or Partial object.

  :param stage_instance: :class:`StageInstance` object with information about the stage instance.


.. function:: async def on_stage_instance_update(stage_instance):

  Called whenever a stage instance is updated

  .. note::
    Depending on your cache rules, StageInstance.guild will either return Full or Partial object.

  :param stage_instance: :class:`StageInstance` object with information about the stage instance.


.. function:: async def on_stage_instance_delete(stage_instance):

  Called whenever a stage instance is deleted

  .. note::
    Depending on your cache rules, StageInstance.guild will either return Full or Partial object.

  :param stage_instance: :class:`PartialStageInstance` object with information about the stage instance.


Intents.guild_members
~~~~~~~~~~~~~~~~~~~~~

.. function:: async def on_guild_member_add(guild, member):

  Called whenever a member joins a guild

  .. note::
    Depending on your cache rules, Member.guild and guild will either return Full or Partial object.

  :param guild: :class:`Guild` | :class:`PartialGuild` object with information about the guild.
  :param member: :class:`Member` object with information about the member.


.. function:: async def on_guild_member_update(guild, member):

  Called whenever a member is updated

  .. note::
    Depending on your cache rules, Member.guild and guild will either return Full or Partial object.

  :param guild: :class:`Guild` | :class:`PartialGuild` object with information about the guild.
  :param member: :class:`Member` object with information about the member.


.. function:: async def on_guild_member_remove(guild, member):

  Called whenever a member leaves a guild

  .. note::
    Depending on your cache rules, guild will either return Full or Partial object.

  :param guild: :class:`Guild` | :class:`PartialGuild` object with information about the guild.
  :param member: :class:`User` object with information about the member.


.. function:: async def on_thread_members_update(payload):

  Called whenever a thread members are updated

  .. note::
    Depending on your cache rules, ThreadMember.guild will either return Full or Partial object.

  :param payload: :class:`ThreadMembersUpdatePayload` object with information about the thread members.


Intents.guild_moderation
~~~~~~~~~~~~~~~~~~~~~~~~

.. function:: async def on_guild_audit_log_entry_create(entry):

  Called whenever an audit log entry is created

  .. note::
    Depending on your cache rules, AuditLogEntry.guild will either return Full or Partial object.

  :param entry: :class:`AuditLogEntry` object with information about the audit log entry.


.. function:: async def on_guild_ban_add(guild, user):

  Called whenever a user is banned from a guild

  .. note::
    Depending on your cache rules, guild will either return Full or Partial object.

  :param guild: :class:`Guild` | :class:`PartialGuild` object with information about the guild.
  :param user: :class:`User` object with information about the user.


.. function:: async def on_guild_ban_remove(guild, user):

  Called whenever a user is unbanned from a guild

  .. note::
    Depending on your cache rules, guild will either return Full or Partial object.

  :param guild: :class:`Guild` | :class:`PartialGuild` object with information about the guild.
  :param user: :class:`User` object with information about the user.


Intents.guild_expressions
~~~~~~~~~~~~~~~~~~~~~~~~~

.. function:: async def on_guild_emojis_update(guild, before, after):

  Called whenever guild emojis have been updated

  .. warning::
    The ``before`` will remain the same as ``after`` unless you have Guild and Emoji cache flags enabled (not partial).

  :param guild: :class:`Guild` | :class:`PartialGuild` object with information about the guild.
  :param before: list[:class:`Emoji`] emojis before the update.
  :param after: list[:class:`Emoji`] emojis after the update.


.. function:: async def on_guild_stickers_update(guild, before, after):

  Called whenever guild stickers have been updated

  .. warning::
    The ``before`` will remain the same as ``after`` unless you have Guild and Sticker cache flags enabled (not partial).

  :param guild: :class:`Guild` | :class:`PartialGuild` object with information about the guild.
  :param before: list[:class:`Sticker`] stickers before the update.
  :param after: list[:class:`Sticker`] stickers after the update.


.. function:: async def on_guild_soundboard_sound_create(sound):

  Called whenever a soundboard sound is created

  .. note::
    Depending on your cache rules, SoundboardSound.guild will either return Full or Partial object.

  :param sound: :class:`SoundboardSound` object with information about the soundboard sound.


.. function:: async def on_guild_soundboard_sound_update(sound):

  Called whenever a soundboard sound is updated

  .. note::
    Depending on your cache rules, SoundboardSound.guild will either return Full or Partial object.

  :param sound: :class:`SoundboardSound` object with information about the soundboard sound.


.. function:: async def on_guild_soundboard_sound_delete(sound):

  Called whenever a soundboard sound is deleted

  .. note::
    Depending on your cache rules, SoundboardSound.guild will either return Full or Partial object.

  :param sound: :class:`SoundboardSound` object with information about the soundboard sound.


.. function:: async def on_guild_soundboard_sounds_update(sounds):

  Called whenever a soundboard sounds are updated

  .. note::
    Depending on your cache rules, sounds[].guild will either return Full or Partial object.

  :param sounds: list[:class:`SoundboardSound`] object with information about the soundboard sounds.


Intents.guild_integrations
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. function:: async def on_guild_integrations_update(guild):

  Called whenever a guild integration is updated

  .. note::
    Depending on your cache rules, guild will either return Full or Partial object.

  :param guild: :class:`Guild` | :class:`PartialGuild` object with information about the guild.


.. function:: async def on_integration_create(integration):

  Called whenever an integration is created

  .. note::
    Depending on your cache rules, Integration.guild will either return Full or Partial object.

  :param integration: :class:`Integration` object with information about the integration.


.. function:: async def on_integration_update(integration):

  Called whenever an integration is updated

  .. note::
    Depending on your cache rules, Integration.guild will either return Full or Partial object.

  :param integration: :class:`Integration` object with information about the integration.


.. function:: async def on_integration_delete(integration):

  Called whenever an integration is deleted

  :param integration: :class:`PartialIntegration` object with information about the integration.


Intents.guild_webhooks
~~~~~~~~~~~~~~~~~~~~~~

.. function:: async def on_webhooks_update(channel):

  Called whenever a webhook is updated

  .. note::
    Depending on your cache rules, channel will either return TextChannel/VoiceChannel/etc. or Partial object.

  :param channel: :class:`PartialChannel` | :class:`BaseChannel`\* object with information about the channel.


Intents.guild_invites
~~~~~~~~~~~~~~~~~~~~~

.. function:: async def on_invite_create(invite):

  Called whenever an invite is created

  :param invite: :class:`Invite` object with information about the invite.


.. function:: async def on_invite_delete(invite):

  Called whenever an invite is deleted

  :param invite: :class:`PartialInvite` object with information about the invite.


Intents.guild_voice_states
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. function:: async def on_voice_state_update(before_voice, after_voice):

  Called whenever a voice state is updated

  .. note::
    Depending on your cache rules, before_voice will either return Full, Partial object or None.

  :param before_voice: :class:`VoiceState` object with information about the new voice state.
  :param after_voice: :class:`VoiceState` object with information about the new voice state.


Intents.guild_presences
~~~~~~~~~~~~~~~~~~~~~~~

.. function:: async def on_presence_update(presence):

  Called whenever a presence is updated

  .. note::
    Depending on your cache rules, Presence.guild and Presence.user will either return Full or Partial object.

  :param presence: :class:`Presence` object with information about the presence.


Intents.guild_messages
~~~~~~~~~~~~~~~~~~~~~~

.. note::
  Message.content will only return something if you have enabled `Intents.message_content`.

.. function:: async def on_message_create(message):

  Called whenever a message is created

  :param message: :class:`Message` object with information about the message.


.. function:: async def on_message_update(message):

  Called whenever a message is updated

  :param message: :class:`Message` object with information about the message.


.. function:: async def on_message_delete(message):

  Called whenever a message is deleted

  :param message: :class:`PartialMessage` object with information about the message.


.. function:: async def on_message_delete_bulk(payload):

  Called whenever a message is deleted in bulk

  .. note::
    Depending on your cache rules, payload.guild will either return Full or Partial object.

  :param payload: :class:`BulkDeletePayload` object with information about the message.


Intents.direct_messages
~~~~~~~~~~~~~~~~~~~~~~~

Same as `Intents.guild_messages`


Intents.guild_message_reactions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. function:: async def on_message_reaction_add(reaction):

  Called whenever a message reaction is added

  :param reaction: :class:`Reaction` object with information about the reaction.


.. function:: async def on_message_reaction_remove(reaction):

  Called whenever a message reaction is removed

  :param reaction: :class:`Reaction` object with information about the reaction.


.. function:: async def on_message_reaction_remove_all(message):

  Called whenever all message reactions are removed

  :param reaction: :class:`PartialMessage` object with information about the message.


.. function:: async def on_message_reaction_remove_emoji(message, emoji):

  Called whenever a message reaction is removed by an emoji

  :param reaction: :class:`PartialMessage` object with information about the message.
  :param emoji: :class:`EmojiParser` object with information about the emoji.


Intents.direct_message_reactions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Same as `Intents.guild_message_reactions`


Intents.guild_message_typing
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. function:: async def on_typing_start(typing):

  Called whenever a user starts typing

  .. note::
    Depending on your cache rules, typing.guild, typing.channel and typing.user will either return Full or Partial object.

  :param typing: :class:`TypingStartEvent` object with information about the typing.


Intents.direct_message_typing
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Same as `Intents.guild_message_typing`


Intents.guild_scheduled_events
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. function:: async def on_guild_scheduled_event_create(event):

  Called whenever a guild scheduled event is created

  :param event: :class:`ScheduledEvent` object with information about the scheduled event.


.. function:: async def on_guild_scheduled_event_update(event):

  Called whenever a guild scheduled event is updated

  :param event: :class:`ScheduledEvent` object with information about the scheduled event.


.. function:: async def on_guild_scheduled_event_delete(event):

  Called whenever a guild scheduled event is deleted

  :param event: :class:`PartialScheduledEvent` object with information about the scheduled event.


.. function:: async def on_guild_scheduled_event_user_add(event, member):

  Called whenever a user is added to a guild scheduled event

  .. note::
    Depending on your cache rules, member will either return Full or Partial object.

  :param event: :class:`ScheduledEvent` object with information about the scheduled event.
  :param member: :class:`PartialMember` | :class:`Member` object with information about the member.


.. function:: async def on_guild_scheduled_event_user_remove(event, member):

  Called whenever a user is removed from a guild scheduled event

  .. note::
    Depending on your cache rules, member will either return Full or Partial object.

  :param event: :class:`ScheduledEvent` object with information about the scheduled event.
  :param member: :class:`PartialMember` | :class:`Member` object with information about the member.


Intents.auto_moderation_configuration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. function:: async def on_auto_moderation_rule_create(rule):

  Called whenever an automod rule is created

  :param rule: :class:`AutoModRule` object with information about the automod rule.


.. function:: async def on_auto_moderation_rule_update(rule):

  Called whenever an automod rule is updated

  :param rule: :class:`AutoModRule` object with information about the automod rule.


.. function:: async def on_auto_moderation_rule_delete(rule):

  Called whenever an automod rule is deleted

  :param rule: :class:`PartialAutoModRule` object with information about the automod rule.


Intents.auto_moderation_execution
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. function:: async def on_auto_moderation_action_execution(execution):

  Called whenever an automod action is executed

  :param execution: :class:`AutomodExecution` object with information about the automod rule.


Intents.guild_message_polls
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. function:: async def on_message_poll_vote_add(vote):

  Called whenever a message poll vote is added

  .. note::
    Depending on your cache rules, vote.guild, vote.channel and vote.user will either return Full or Partial object.

  :param vote: :class:`PollVoteEvent` object with information about the poll vote.


.. function:: async def on_message_poll_vote_remove(vote):

  Called whenever a message poll vote is removed

  .. note::
    Depending on your cache rules, vote.guild, vote.channel and vote.user will either return Full or Partial object.

  :param vote: :class:`PollVoteEvent` object with information about the poll vote.


Intents.direct_message_polls
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Same as `Intents.guild_message_polls`
