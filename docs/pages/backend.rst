HTTP backend
============
The HTTP backend is a simple HTTP server that listens for incoming requests and
manages all the communication received by Discord HTTP POST requests.
However since this is essentially based on Quart, you are free to intervean and
add your own componenets to the server.

.. code-block:: python

  from discord_http import Context, Client

  client = Client(
      token="Your bot token here",
      application_id="Bot application ID",
      public_key="Bot public key",
      sync=True
  )

With this simple code, you have the ability to interact with Quart API using ``client.backend``.
If you need help with Quart, please refer to the `Quart documentation <https://pgjones.gitlab.io/quart/>`_.
Essentially you are able to add your very own paths to the server.

By default, the library adds a GET and POST listener to ``/`` of the domain` (aka. the root of the domain).
The ``POST`` is responsible for handling all the incoming requests from Discord
(We **STRONGLY** recommend you do not change the default behaviour of this, unless you know what you are doing).
``GET`` is used for you to verify that the bot is online and working, which shows a simple
debug information about your bot and nothing more.

GET Path
--------
By default, the library provides you with a debug GET path that you can use to verify that the bot is online.
It shows something like this when accessing it through your browser or any other tools:

.. image:: ../_static/images/backend/get_path.png

If you want to as well, you could theoretically make this a way to show your bot being online,
by having your main website ping this source and then be able to see if the bot is online or not.

Don't like the default behaviour, you can simply change it by doing the following:

.. code-block:: python

  client = Client(
      ...
      disable_default_get_path=True
  )

Instead of then showing the default JSON value in there, it will then instead return ``HTTP 405: Method not allowed``.


Adding paths
------------
A very simplified example of how you can add your own paths to the server.
Keep in mind that there are many more methods, but this is just a simple example.
Code example will be taking the code above as an expantion of the code.

.. code-block:: python

  async def simple_test():
      return {"hello": "world"}

  client.backend.add_url_rule(
      "/test", "test",
      simple_test, methods=["GET"]
  )

This code would essentially add a new path to the server called ``/test`` that
returns a JSON response with the key ``hello`` and the value ``world``.
Of course you can do much more than this, but this is more of an idea of what you could do.
