from typing import Self

from .object import Snowflake

__all__ = (
    "AllowedMentions",
)


class AllowedMentions:
    def __init__(
        self,
        *,
        everyone: bool = True,
        users: bool | list[Snowflake | int] | None = True,
        roles: bool | list[Snowflake | int] | None = True,
        replied_user: bool = True,
    ):
        self.everyone: bool = everyone
        self.users: bool | list[Snowflake | int] | None = users
        self.roles: bool | list[Snowflake | int] | None = roles
        self.reply_user: bool = replied_user

    @classmethod
    def all(cls) -> Self:
        """ Preset to allow all mentions. """
        return cls(everyone=True, roles=True, users=True, replied_user=True)

    @classmethod
    def none(cls) -> Self:
        """ Preset to deny any mentions. """
        return cls(everyone=False, roles=False, users=False, replied_user=False)

    def to_dict(self) -> dict:
        """ Representation of the `AllowedMentions` that is Discord API friendly. """
        parse = []
        data = {}

        if self.everyone:
            parse.append("everyone")

        if isinstance(self.users, list):
            data["users"] = [int(x) for x in self.users]
        elif self.users is True:
            parse.append("users")

        if isinstance(self.roles, list):
            data["roles"] = [int(x) for x in self.roles]
        elif self.roles is True:
            parse.append("roles")

        if self.reply_user:
            data["replied_user"] = True

        data["parse"] = parse
        return data
