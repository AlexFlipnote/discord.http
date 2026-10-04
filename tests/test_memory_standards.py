""" Guards the memory conventions of the library, so new code can't quietly regress them. """

import enum
import importlib
import inspect
import pkgutil
import re
import unittest

from pathlib import Path

import discord_http


# Long-lived or one-per-process objects, a __dict__ costs nothing meaningful here
DICT_ALLOWED = {
    "discord_http.backend.DiscordHTTP",
    "discord_http.client.Client",
    "discord_http.commands.Choice",
    "discord_http.commands.ChoiceMeta",
    "discord_http.commands.Cog",
    "discord_http.commands.Command",
    "discord_http.commands.Interaction",
    "discord_http.commands.Listener",
    "discord_http.commands.PartialCommand",
    "discord_http.commands.Range",
    "discord_http.commands.RangeMeta",
    "discord_http.commands.SubCommand",
    "discord_http.commands.SubGroup",
    "discord_http.commands._CommandMeta",
    "discord_http.gateway.client.GatewayClient",
    "discord_http.gateway.shard.Shard",
    "discord_http.guild._GuildLimits",
    "discord_http.http.DiscordAPI",
    "discord_http.http.HTTPSession",
    "discord_http.tasks.Loop",
    "discord_http.utils.CustomFormatter",
    "discord_http.utils.MultipartData",
}

# Slots that intentionally replace a lazy property from the partial base class
SHADOW_ALLOWED = {
    "discord_http.member.Member._user",
}


def _slots_of(cls: type) -> tuple[str, ...]:
    slots = cls.__dict__.get("__slots__", ())
    return (slots,) if isinstance(slots, str) else tuple(slots)


def _library_classes() -> list[type]:
    classes: dict[str, type] = {}

    for info in pkgutil.walk_packages(discord_http.__path__, "discord_http."):
        module = importlib.import_module(info.name)
        for _, cls in inspect.getmembers(module, inspect.isclass):
            if cls.__module__ != module.__name__:
                continue
            if issubclass(cls, (BaseException, enum.Enum)):
                continue
            if any(b.__name__ in ("TypedDict", "Protocol", "NamedTuple") for b in cls.__mro__):
                continue
            classes[f"{cls.__module__}.{cls.__qualname__}"] = cls

    return list(classes.values())


def _name(cls: type) -> str:
    return f"{cls.__module__}.{cls.__qualname__}"


class TestMemoryStandards(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.classes = _library_classes()

        root = Path(discord_http.__file__).parent
        source = "\n".join(p.read_text(encoding="utf-8") for p in root.rglob("*.py"))
        # Slot declarations themselves don't count as a use
        cls.source = re.sub(r"__slots__\s*=\s*\(.*?\)\n", "", source, flags=re.DOTALL)

    def test_no_instance_dict(self) -> None:
        offenders = sorted(
            _name(cls) for cls in self.classes
            if cls.__dictoffset__ != 0 and _name(cls) not in DICT_ALLOWED
        )
        self.assertEqual(
            offenders, [],
            "These classes get a __dict__, add __slots__ to them (and every base class) "
            "or add them to DICT_ALLOWED if they are long-lived singletons"
        )

    def test_dict_allowlist_is_not_stale(self) -> None:
        names = {_name(cls) for cls in self.classes if cls.__dictoffset__ != 0}
        self.assertEqual(sorted(DICT_ALLOWED - names), [], "Remove these from DICT_ALLOWED, they have slots now")

    def test_no_duplicate_slots(self) -> None:
        offenders = []
        for cls in self.classes:
            own = _slots_of(cls)
            if len(own) != len(set(own)):
                offenders.append(f"{_name(cls)} repeats a slot")
            for slot in own:
                for base in cls.__mro__[1:]:
                    if slot in _slots_of(base):
                        offenders.append(f"{_name(cls)}.{slot} is already a slot on {base.__qualname__}")

        self.assertEqual(offenders, [])

    def test_no_unused_slots(self) -> None:
        offenders = [
            f"{_name(cls)}.{slot}"
            for cls in self.classes
            for slot in _slots_of(cls)
            if not re.search(rf"\.{re.escape(slot)}\b|[\"']{re.escape(slot)}[\"']", self.source)
        ]
        self.assertEqual(offenders, [], "These slots are declared but never read or written")

    def test_slots_do_not_shadow_properties(self) -> None:
        offenders = [
            f"{_name(cls)}.{slot} shadows a property on {base.__qualname__}"
            for cls in self.classes
            for slot in _slots_of(cls)
            for base in cls.__mro__[1:]
            if isinstance(base.__dict__.get(slot), property)
            and f"{_name(cls)}.{slot}" not in SHADOW_ALLOWED
        ]
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
