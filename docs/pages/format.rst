Style guide
===========
This is a style guide for the discord.http library. It's a work in progress, and will be updated as the library evolves.

General guidelines
------------------
- Use 4 spaces for indentation.
- Line length are limited to 256 characters.
- Version of python used should be 3.11 or higher.
- Quotes should always be double quotes. Except for strings that require double quote inside.
- Files always end with a newline.
- Never use any ``print()`` statements, use ``logging`` instead.
- Use ``f-strings`` instead of ``.format()`` whenever possible.

Import conventions
------------------
The following conventions should be followed when importing modules from the library:

.. code-block:: python

    import discord.http
    import random

    from datetime import datetime
    from typing import TYPE_CHECKING

    from .<module> import <function>

1. Any imports that do not use the ``from`` keyword should be placed at the top of the file.
2. Imports that do in fact use the ``from`` keyword are then placed underneath the first imports.
3. Imports that are only used locally should be at the bottom of the import tree.
4. All imports should be sorted alphabetically.

Type hints
----------
All functions and methods should have type hints. The type hints should be formatted as follows:

For example:

.. code-block:: python

    def function(arg1: int, arg2: str | None = None) -> str:
        ...


Docstrings
----------
Docstrings should be formatted as follows:

.. code-block:: python

    def function(arg1: int, arg2: str) -> str:
        """
        This is a function.

        Here is more information about the function.
        It is separated from the short summary by a blank line.

        Parameters
        ----------
        arg1:
            This is the first argument.
            We skip the type hint inside the docstring.
        arg2:
            This is the second argument.
            We skip the type hint inside the docstring.

        Returns/Yields
        --------------
            This is the return value.
            We skip the return inside the docstring.

        Raises
        ------
        ValueError:
            This is raised if the function fails.
            Raises do use type inside the docstring.
        """
        ...

For short summaries, make it a one-liner like for example:

.. code-block:: python

    def function(arg1: int, arg2: str) -> str:
        """ This is a function. """
        ...
