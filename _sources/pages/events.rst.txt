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

  Called whenever an error occurs in an event (aka. listener)

  Using this event will disable the default ERROR print given by the library, and instead let you decide what it should do.

  :param client: :class:`Client` The client object.
  :param error: :class:`Exception` object with the error that occurred.


.. function:: async def on_interaction_error(ctx, error):

  Called whenever an error occurs in an interaction (command, autocomplete, button, etc.)

  Using this event will disable the default ERROR print given by the library, and instead let you decide what it should do.

  :param ctx: :class:`Context` The context object.
  :param error: :class:`Exception` object with the error that occurred.
