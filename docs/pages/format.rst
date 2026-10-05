Style Guide
===========

This document outlines the coding standards for the ``discord_http`` library. All contributions should adhere to these guidelines to maintain consistency and readability.

General Guidelines
------------------
- **Indentation:** Use 4 spaces per level.
- **Line Length:** Maximum 128 characters.
- **Python Version:** 3.11 or higher.
- **Quotes:** Use double quotes (``"``) by default. Use single quotes (``'``) only to avoid escaping internal double quotes.
- **Files:** Must always end with a single newline.
- **Logging:** Never use ``print()``, instead use the logging provided by the library.
- **Formatting:** Use f-strings over ``.format()`` or ``%`` wherever possible.

Import Conventions
------------------
Imports should be grouped by type, separated by a blank line, and sorted alphabetically within each group.
The reason for this is to improve readability and maintain a consistent structure across the codebase, making it easier for developers to quickly identify dependencies and navigate the code.

Implementation Order
~~~~~~~~~~~~~~~~~~~~
1. **Standard/External Imports:** ``import module``
2. **From-style Imports:** ``from module import object``
3. **Local/Relative Imports:** ``from .module import object``
4. **Type-Checking Imports:** Wrapped in an ``if TYPE_CHECKING:`` block to avoid circular imports and reduce runtime overhead.

.. code-block:: python

    import random

    from datetime import datetime
    from typing import TYPE_CHECKING

    from .utils import MISSING

    if TYPE_CHECKING:
        from .client import Client
        from .models import User

Anything imported under ``TYPE_CHECKING`` only exists for the type checker, so it must be quoted when used in a type hint (e.g. ``-> "User"``).
If an object is needed at runtime and importing it at the top would cause a circular import, import it locally inside the function instead and mark it as such:

.. code-block:: python

    def _get_cached_member(self, user_id: int) -> "Member | None":
        from .member import Member  # Circular import

        member = self.guild.get_member(user_id)
        return member if isinstance(member, Member) else None

Type Hints
----------
All functions, methods, and variables must be fully type-hinted using modern Python syntax (e.g., ``|`` for unions).
We do not use the older ``Union``, ``Optional`` or similar syntax from the ``typing`` module, as it is more verbose and less readable.
There are exceptions to this rule, but only when there are no native Python types that can be used, such as ``Literal`` or ``TypedDict``.

.. code-block:: python

    def fetch_user(user_id: int, cache: bool | None = None) -> User:
        ...

Docstrings
----------
Use the NumPy/Google-style hybrid for detailed documentation. Skip type hints inside the docstring to avoid redundancy with the code signature.
These days, most IDEs and documentation generators can extract type information directly from the code.
Including it in the docstring is unnecessary and can lead to maintenance issues if the code signature changes but the docstring does not.
For this same reason, do not add a trailing colon after a parameter or exception name.
It used to separate the name from its type (e.g. ``arg1 : int``), but is redundant due to types being omitted entirely from docstring.

.. code-block:: python

    def function(arg1: int, arg2: str) -> str:
        """
        Summary of the function.

        Extended description providing more context.

        Parameters
        ----------
        arg1
            Description of the first argument.
        arg2
            Description of the second argument.

        Returns
        -------
            Description of the return value.

        Raises
        ------
        ValueError
            Description of why this error is raised.
        """
        ...

When the same exception can be raised for several reasons, list each reason as a bullet:

.. code-block:: python

    async def edit(self, *, request_to_speak_timestamp: datetime | None = MISSING) -> None:
        """
        Updates the voice state of the member.

        Parameters
        ----------
        request_to_speak_timestamp
            When the user requested to speak, or `None` to clear it.

        Raises
        ------
        ValueError
            - If the voice state has no guild_id
            - If `request_to_speak_timestamp` is used on another user's voice state
        """
        ...

For generator and async generator functions, use ``Yields`` instead of ``Returns`` to describe each item produced.
Like ``Returns``, it is typeless and has no name, just the description:

.. code-block:: python

    async def fetch_items(self, *, limit: int | None = 100) -> AsyncIterator[Item]:
        """
        Fetch the items.

        Parameters
        ----------
        limit
            The maximum amount of items to fetch.
            `None` will fetch all items.

        Yields
        ------
            Each item as it is fetched.
        """
        ...

Methods and properties that take no parameters (besides ``self``) use a one-line docstring, with a space on each side of the text (``""" Text. """``).
Since there are no parameters to document, a ``Returns`` or ``Yields`` section would only repeat the summary, so leave it out:

.. code-block:: python

    def is_expired(self) -> bool:
        """ Returns whether the object has expired. """
        ...

    async def fetch_all_items(self) -> AsyncIterator[Item]:
        """ Fetch all items, yielding each one as it is fetched. """
        ...

If it needs more explaining, such as required permissions or edge cases, use a multi-line docstring instead.
It still has no ``Returns`` or ``Yields`` section, but ``Raises`` can be used if it raises anything worth knowing about:

.. code-block:: python

    async def fetch_webhooks(self) -> list[Webhook]:
        """
        Fetches all the webhooks in the guild.

        Requires the ``MANAGE_WEBHOOKS`` permission.
        """
        ...

Attributes and Slots
--------------------
To ensure clean documentation, ``discord_http`` utilizes ``__slots__`` and **Inline Attribute Docstrings**.
Of course, there are exceptions to this rule, such as when using ``dataclasses`` or when defining a class which can be changed by the user, such as a ``Client`` or ``Bot`` subclass.
Classes that only ever exist a handful of times (the client, shards, the HTTP client, registered commands) may also skip ``__slots__``,
as the memory saved is negligible and it would only make them harder to extend.
However, for all other classes, the following rules apply.

This rule is in place to make both Sphinx (this page you are looking at now) and IDEs display attributes in a more user-friendly way, as well as to reduce redundancy in documentation.

Implementation Rules
~~~~~~~~~~~~~~~~~~~~
1. **No Attribute Blocks:** Do not list attributes in the class docstring.
2. **Inline Documentation:** Place docstrings directly beneath the variable assignment in ``__init__``.
3. **Slots:** All public attributes must be defined in ``__slots__``.
4. **Inheritance:** Do not re-define inherited slots in subclasses; only define new attributes unique to that class.
5. **Type Hints:** All attributes must be fully type-hinted.
6. **No Redundancy:** Avoid type hints in docstrings for attributes, as they are already present in the code.
7. **Private Attributes:** Private attributes (``_raw_*``, ``_state``, etc.) are still slotted and type-hinted, but get no docstring, as they are not part of the public documentation.
   If one needs explaining, use a ``#`` comment above it instead.

Class docstrings follow the same one-line convention shown in `Docstrings`_ above, a summary only.
Since attributes are documented inline rather than in the class body.

.. note::
    A subclass that defines new attributes must still declare ``__slots__``, even if only listing them.
    If ``__slots__`` is omitted entirely, Python silently gives the subclass a ``__dict__``, which negates the memory savings ``__slots__`` was meant to provide for every instance of that class.

.. code-block:: python

    class BaseObject:
        """ Represents a base object. """
        __slots__ = ("id", "name")

        def __init__(self, data: dict):
            self.id: int = int(data["id"])
            """ The unique ID of this object. """

            self.name: str | None = data.get("name")
            """ The name of this object. """

    class CustomObject(BaseObject):
        """ Represents a more specific object. """
        __slots__ = ("extra",)

        def __init__(self, data: dict):
            super().__init__(data)

            self.extra: bool = data.get("extra", False)
            """ An extra attribute unique to this subclass. """

Library Conventions
-------------------
Beyond formatting, these are the patterns the library is built around.
New code should follow them, so it feels like it belongs and keeps memory usage low.

Partial and Full Objects
~~~~~~~~~~~~~~~~~~~~~~~~
Most Discord objects come in two classes: ``PartialX`` which only knows its ID (and maybe a parent ID), and ``X(PartialX)`` which holds the full data.
Any method that only needs the ID to make its request belongs on the partial class, so it works on both partial and full objects without fetching first.
Only put a method on the full class when it actually needs the full data.

.. code-block:: python

    class PartialGuild(PartialBase):
        """ Represents a partial guild object. """

        async def fetch_webhooks(self) -> list[Webhook]:
            """ Fetches all the webhooks in the guild. """
            # Only needs self.id, so it lives here and works for Guild too
            ...

    class Guild(PartialGuild):
        """ Represents a guild object. """
        ...

Naming
~~~~~~
- ``fetch_*``: makes an HTTP request, and is always ``async``.
- ``get_*``: reads from the cache, synchronous, returns ``None`` if not found.
- ``get_partial_*``: builds a partial object from an ID, without any request.
- ``create_*_from_data``: builds an object from raw API data, used through ``self._state.bot`` so the cache can be involved.

How a parameter is named decides what it accepts:

- Named after the ID (``user_id``, ``guild_id``): typed as ``int``, for lookups like ``fetch_user(user_id)``.
- Named after the object (``user``, ``member``, ``role``): typed as ``Snowflake | int``, so users can pass either the object or the raw ID.
  Use ``utils.normalize_entity_id()`` (or ``int()``) to turn it into an ID.

MISSING vs None
~~~~~~~~~~~~~~~
For optional parameters that are sent to Discord, such as in ``edit()`` methods, the default is ``MISSING`` and not ``None``.
They mean different things: ``MISSING`` means *"not provided, do not send it"*, while ``None`` means *"clear this value"*.

.. code-block:: python

    async def edit(self, *, name: str | None = MISSING, reason: str | None = None) -> "Role":
        """ ... """
        payload = {}

        if name is not MISSING:
            payload["name"] = name  # None will clear it on Discord's side
        ...

HTTP Requests
~~~~~~~~~~~~~
- Requests go through ``self._state.query()``, with one argument per line.
- Endpoints that return ``204 No Content`` must use ``res_method="text"``.
- Endpoints that support the ``X-Audit-Log-Reason`` header take a ``reason: str | None = None`` keyword and pass it along.

.. code-block:: python

    await self._state.query(
        "PUT",
        f"/channels/{self.channel.id}/messages/pins/{self.id}",
        res_method="text",
        reason=reason
    )

Paginated endpoints are exposed as async iterators with ``before``, ``after`` and ``limit`` keywords where Discord supports them.
``limit=None`` fetches everything, requesting pages until Discord has no more to give.
See ``PartialGuild.fetch_bans()`` or ``PartialChannel.fetch_history()`` for the reference implementation.

Memory Efficiency
~~~~~~~~~~~~~~~~~
Objects in the gateway cache can exist hundreds of thousands of times, so every byte per instance adds up.
``__slots__`` is the baseline, these patterns go further:

- **Raw values, lazy properties:** Store the cheap raw value (``_raw_*``) and convert it in a property when accessed, instead of building enums, flags or objects up front.
- **Rarely-set fields:** Group fields that most instances do not have into a single ``NamedTuple`` slot (``_extra``) that is ``None`` when all of them are empty, see ``Member`` and ``Message``.
  Check for emptiness by comparing against a shared all-``None`` tuple, ``any()`` with a generator is several times slower on hot paths.
- **Bit-packing:** Pack booleans and small flags into a single int, see ``Role._flags``.
- **Timestamps:** Store timestamps with ``utils.pack_timestamps()`` and read them back with ``utils.unpack_timestamp()`` in a property, instead of keeping ``datetime`` objects around.
- **Tuples over lists:** Use tuples for data that does not change, an empty tuple is shared by Python while every empty list is a new object.
- **Interning:** Values repeated across many objects (feature lists, role IDs, permission overwrites) are deduplicated through the cache's ``intern_*`` helpers.

.. code-block:: python

    _EMPTY_THING_EXTRA = (None,) * len(_ThingExtra._fields)

    class Thing(PartialThing):
        """ Represents a thing. """
        __slots__ = ("_extra", "_raw_flags")

        def __init__(self, *, state: "DiscordAPI", data: dict):
            ...
            self._raw_flags: int = data.get("flags", 0)

            # Checked as a plain tuple first, most things have none of these
            extra = (
                data.get("position"),
                data.get("thread"),
            )
            self._extra: _ThingExtra | None = (
                _ThingExtra._make(extra) if extra != _EMPTY_THING_EXTRA else None
            )

        @property
        def flags(self) -> ThingFlags:
            """ The flags of the thing. """
            return ThingFlags(self._raw_flags)

        @property
        def position(self) -> int | None:
            """ The position of the thing, if any. """
            return self._extra.position if self._extra else None

Flags
~~~~~
Flags are checked with ``in``, not by accessing the flag as an attribute.
Accessing it as an attribute returns the class constant, which is always truthy:

.. code-block:: python

    RoleFlags.in_prompt in role.flags  # Correct
    role.flags.in_prompt  # Wrong, always truthy

Module Exports
~~~~~~~~~~~~~~
Every module defines ``__all__`` as a tuple, sorted alphabetically (``ruff`` enforces the order).
It lists everything users are meant to import, which is every type they receive from or pass to the library, as most modules are re-exported from the package root.
Internal plumbing (HTTP sessions, ratelimiters, base storage classes) and helpers used through their module namespace,
such as the ``commands.command`` decorators, are left out, as are private names (prefixed with ``_``).
The exceptions are ``utils`` and ``tasks``, which intentionally have no ``__all__``, so they are always used through their module (``utils.X``, ``tasks.loop``) instead of being imported from the package root.

Comments
~~~~~~~~
Keep comments sparse. Code should explain *what* it does by itself, comments are for *why*,
such as a Discord quirk, a performance reason or a non-obvious edge case.

Before Submitting
-----------------
- ``ruff check`` must pass, the configuration is in ``pyproject.toml``.
- ``python -m pytest`` must pass.
- New parsing or endpoints should come with a test under ``tests/``, using the fake client from ``tests/_fake_client.py`` instead of real requests.
