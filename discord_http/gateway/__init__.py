"""
This module is used to handle all the gateway events.
While originally, discord.http was only used for the HTTP requests,
it was later expanded to also handle the gateway events.

To get it working, you will need to use the `enable_gateway` parameter in the Client().
"""

# flake8: noqa: F401
from .activity import *
from .cache import *
from .client import *
from .enums import *
from .flags import *
from .object import *
from .parser import *
from .shard import *
