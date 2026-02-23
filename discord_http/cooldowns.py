import time

from typing import TYPE_CHECKING

from .enums import BaseEnum

if TYPE_CHECKING:
    from .context import Context

__all__ = (
    "BucketType",
    "Cooldown",
    "CooldownCache",
)


class BucketType(BaseEnum):
    default = 0
    user = 1
    member = 2
    guild = 3
    category = 4
    channel = 5

    def get_key(self, ctx: "Context") -> int | tuple[int, int]:
        """
        Returns the key for the bucket.

        Parameters
        ----------
        ctx:
            The bot context

        Returns
        -------
            The key for the bucket
        """
        match self:
            case BucketType.user:
                return ctx.user.id

            case BucketType.member:
                return (ctx.guild.id, ctx.user.id)

            case BucketType.guild:
                return ctx.guild.id

            case BucketType.category:
                return (
                    ctx.channel.parent_id or
                    ctx.channel.id
                )

            case BucketType.channel:
                return ctx.channel.id

            case _:
                return 0

    def __call__(self, ctx: "Context") -> int | tuple[int, int]:
        """
        Returns the key for the bucket.

        Parameters
        ----------
        ctx:
            The bot context

        Returns
        -------
            The key for the bucket
        """
        return self.get_key(ctx)


class CooldownCache:
    __slots__ = (
        "_cache",
        "_cooldown",
        "_type",
    )

    def __init__(
        self,
        original: "Cooldown",
        type: BucketType  # noqa: A002
    ):
        self._cache: dict[int | tuple[int, int], Cooldown] = {}
        self._cooldown: Cooldown = original
        self._type: BucketType = type

    def __repr__(self) -> str:
        return (
            f"<CooldownCache type={self._type!r} rate={self._cooldown.rate} "
            f"per={self._cooldown.per} "
            f"cache={len(self._cache) if self._cache else None}>"
        )

    def _bucket_key(self, ctx: "Context") -> int | tuple[int, int]:
        """
        Creates a key for the bucket based on the type.

        Parameters
        ----------
        ctx:
            Context to create the key for.

        Returns
        -------
            Key for the bucket.
        """
        return self._type(ctx)

    def _cleanup_cache(
        self,
        current: float | None = None
    ) -> None:
        """
        Cleans up the cache by removing expired buckets.

        Parameters
        ----------
        current:
            Current time to check the cache for.
        """
        current = current or time.time()
        any(
            self._cache.pop(k)
            for k, v in self._cache.items()
            if current > v._last + v.per
        )

    def create_bucket(self) -> "Cooldown":
        """ Creates a new cooldown bucket. """
        return self._cooldown.copy()

    def get_bucket(
        self,
        ctx: "Context",
        current: float | None = None
    ) -> "Cooldown":
        """
        Gets the cooldown bucket for the given context.

        Parameters
        ----------
        ctx:
            Context to get the bucket for.
        current:
            Current time to check the bucket for.

        Returns
        -------
            Cooldown bucket for the context.
        """
        if self._type is BucketType.default:
            return self._cooldown

        self._cleanup_cache(current)
        key = self._bucket_key(ctx)

        if key not in self._cache:
            bucket = self.create_bucket()
            self._cache[key] = bucket
        else:
            bucket = self._cache[key]

        return bucket

    def update_rate_limit(
        self,
        ctx: "Context",
        current: float | None = None,
        *,
        tokens: int = 1
    ) -> float | None:
        """
        Updates the rate limit for the given context.

        Parameters
        ----------
        ctx:
            Context to update the rate limit for.
        current:
            Current time to update the rate limit for.
        tokens:
            Amount of tokens to remove from the rate limit.

        Returns
        -------
            Time left before the cooldown resets.
            Returns `None` if the rate limit was not exceeded.
        """
        bucket = self.get_bucket(ctx, current)
        return bucket.update_rate_limit(current, tokens=tokens)


class Cooldown:
    """
    Represents a cooldown for a rate limit.

    Attributes
    ----------
    rate: int
        The amount of tokens per `per` time
    per: float
        The time in seconds for the rate limit
    """

    __slots__ = (
        "_last",
        "_tokens",
        "_window",
        "per",
        "rate",
    )

    def __init__(self, rate: int, per: float):
        self.rate: int = int(rate)
        self.per: float = float(per)

        self._window: float = 0.0
        self._tokens: int = self.rate
        self._last: float = 0.0

    def __repr__(self) -> str:
        return f"<Cooldown rate={self.rate} per={self.per} tokens={self._tokens}>"

    def get_tokens(
        self,
        current: float | None = None
    ) -> int:
        """
        Gets the amount of tokens available for the current time.

        Parameters
        ----------
        current:
            The current time to check the tokens for.

        Returns
        -------
            Amount of tokens available.
        """
        current = current or time.time()
        tokens = max(self._tokens, 0)

        if current > self._window + self.per:
            tokens = self.rate

        return tokens

    def get_retry_after(
        self,
        current: float | None = None
    ) -> float:
        """
        Gets the time left before the cooldown resets.

        Parameters
        ----------
        current:
            The current time to check the retry after for.

        Returns
        -------
            Time left before the cooldown resets.
        """
        current = current or time.time()
        tokens = self.get_tokens(current)

        return (
            self.per - (current - self._window)
            if tokens == 0 else 0.0
        )

    def update_rate_limit(
        self,
        current: float | None = None,
        *,
        tokens: int = 1
    ) -> float | None:
        """
        Updates the rate limit for the current time.

        Parameters
        ----------
        current:
            The current time to update the rate limit for.
        tokens:
            Amount of tokens to remove from the rate limit.

        Returns
        -------
            Time left before the cooldown resets.
            Returns `None` if the rate limit was not exceeded.
        """
        current = current or time.time()

        self._last = current
        self._tokens = self.get_tokens(current)

        if self._tokens == self.rate:
            self._window = current

        self._tokens -= tokens

        if self._tokens < 0:
            return self.per - (current - self._window)
        return None

    def reset(self) -> None:
        """ Resets the rate limit. """
        self._tokens = self.rate
        self._last = 0.0

    def copy(self) -> "Cooldown":
        """ Copies the cooldown. """
        return Cooldown(self.rate, self.per)
