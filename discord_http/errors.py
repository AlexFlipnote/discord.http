from typing import TYPE_CHECKING

from .flag import Permissions
from .cooldowns import Cooldown

if TYPE_CHECKING:
    from .http import HTTPResponse

__all__ = (
    "BotMissingPermissions",
    "CheckFailed",
    "DiscordException",
    "DiscordServerError",
    "Forbidden",
    "HTTPException",
    "InvalidMember",
    "CommandOnCooldown",
    "NotFound",
    "Ratelimited",
    "UserMissingPermissions",
    "AutomodBlock",
)


class DiscordException(Exception):
    """ Base exception for discord_http """
    pass


class CheckFailed(DiscordException):
    """ Raised whenever a check fails """
    pass


class InvalidMember(CheckFailed):
    """ Raised whenever a user was found, but not a member of a guild """
    pass


class CommandOnCooldown(CheckFailed):
    def __init__(self, cooldown: Cooldown, retry_after: float):
        self.cooldown: Cooldown = cooldown
        self.retry_after: float = retry_after
        super().__init__(f"Command is on cooldown for {retry_after:.2f}s")


class UserMissingPermissions(CheckFailed):
    """ Raised whenever a user is missing permissions """
    def __init__(self, perms: Permissions):
        self.permissions = perms
        super().__init__(f"Missing permissions: {', '.join(perms.list_names)}")


class BotMissingPermissions(CheckFailed):
    """ Raised whenever a bot is missing permissions """
    def __init__(self, perms: Permissions):
        self.permissions = perms
        super().__init__(f"Bot is missing permissions: {', '.join(perms.list_names)}")


class HTTPException(DiscordException):
    """ Base exception for HTTP requests """
    def __init__(self, r: "HTTPResponse"):
        self.request = r
        self.status: int = r.status

        self.code: int
        self.text: str

        if isinstance(r.response, dict):
            self.code = r.response.get("code", 0)
            self.text = r.response.get("message", "Unknown")
            if r.response.get("errors", None):
                self.text += f"\n{r.response['errors']}"
        else:
            self.text: str = str(r.response)
            self.code = 0

        error_text = f"HTTP {self.request.status} > {self.request.reason} (code: {self.code})"
        if len(self.text):
            error_text += f": {self.text}"

        super().__init__(error_text)


class NotFound(HTTPException):
    """ Raised whenever a HTTP request returns 404 """
    pass


class Forbidden(HTTPException):
    """ Raised whenever a HTTP request returns 403 """
    pass


class AutomodBlock(HTTPException):
    """ Raised whenever a HTTP request was blocked by Discord """
    pass


class Ratelimited(HTTPException):
    """ Raised whenever a HTTP request returns 429, but without a Retry-After header """
    pass


class DiscordServerError(HTTPException):
    """ Raised whenever an unexpected HTTP error occurs """
    pass
