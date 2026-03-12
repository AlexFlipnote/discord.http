Style Guide
===========

This document outlines the coding standards for the ``discord_http`` library. All contributions should adhere to these guidelines to maintain consistency and readability.

General Guidelines
------------------
- **Indentation:** Use 4 spaces per level.
- **Line Length:** Maximum 256 characters.
- **Python Version:** 3.11 or higher.
- **Quotes:** Use double quotes (``"``) by default. Use single quotes (``'``) only to avoid escaping internal double quotes.
- **Files:** Must always end with a single newline.
- **Logging:** Never use ``print()``. Use the standard ``logging`` module.
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

.. code-block:: python

    def function(arg1: int, arg2: str) -> str:
        """
        Summary of the function.

        Extended description providing more context.

        Parameters
        ----------
        arg1:
            Description of the first argument.
        arg2:
            Description of the second argument.

        Returns
        -------
            Description of the return value.

        Raises
        ------
        ValueError:
            Description of why this error is raised.
        """
        ...

For simple logic, use a concise one-line docstring:

.. code-block:: python

    def is_expired(self) -> bool:
        """ Returns whether the object has expired. """
        ...

Attributes and Slots
--------------------
To ensure clean documentation, ``discord_http`` utilizes ``__slots__`` and **Inline Attribute Docstrings**.
Of course, there are exceptions to this rule, such as when using ``dataclasses`` or when defining a class which can be changed by the user, such as a ``Client`` or ``Bot`` subclass.
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
