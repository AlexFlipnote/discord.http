import asyncio
import logging
import unittest
import warnings

from discord_http import Client
from discord_http.channel import BaseChannel, ForumChannel, TextChannel
from discord_http.context import Context, ResolvedValues, SelectValues, channel_types
from discord_http.enums import (
    CommandOptionType, ComponentType, IntegrationType, InteractionContextType, InteractionType,
)
from discord_http.member import Member
from discord_http.message import Message
from discord_http.user import User


def _make_client() -> Client:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        client = Client(token="a.b.c", logging_level=logging.CRITICAL)
    return client


def _user(id_: str, name: str = "bob") -> dict:
    return {"id": id_, "username": name, "discriminator": "0", "avatar": None}


def _member(id_: str) -> dict:
    return {"user": _user(id_), "roles": [], "joined_at": "2024-01-01T00:00:00+00:00", "deaf": False, "mute": False, "flags": 0}


def _channel(id_: str, type_: int) -> dict:
    return {"id": id_, "type": type_, "name": f"chan-{id_}", "guild_id": "100"}


def _message(id_: str = "500", *, interaction_id: str | None = None) -> dict:
    data = {
        "id": id_, "channel_id": "200", "type": 0, "content": "hi",
        "author": _user("3"),
        "components": [{"type": 1, "components": [{"type": 2, "style": 1, "label": "x", "custom_id": "btn"}]}],
    }
    if interaction_id is not None:
        data["interaction_metadata"] = {"id": interaction_id, "type": 2, "user": _user("3")}
    return data


def _payload(type_: int, data: dict | None = None, **extra) -> dict:
    payload = {
        "id": "1000", "type": type_, "token": "tok", "channel_id": "200", "guild_id": "100",
        "member": _member("42"), "data": data or {},
    }
    payload.update(extra)
    return payload


def close_client(client: Client) -> None:
    loop = client.loop
    pending = asyncio.all_tasks(loop)
    for task in pending:
        task.cancel()
    if pending:
        loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
    loop.close()


class _ClientTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.client = _make_client()

    def tearDown(self) -> None:
        close_client(self.client)


class TestNoneValuesAreNotShared(_ClientTestCase):
    def test_resolved_none_returns_fresh_instances(self) -> None:
        a = ResolvedValues.none(None)  # type: ignore[arg-type]
        b = ResolvedValues.none(None)  # type: ignore[arg-type]
        self.assertIsNot(a, b)
        a.members.append("leak")  # type: ignore[arg-type]
        self.assertEqual(b.members, [])

    def test_select_none_strings_not_shared_between_contexts(self) -> None:
        ctx_a = Context(self.client, _payload(int(InteractionType.application_command)))
        ctx_b = Context(self.client, _payload(int(InteractionType.application_command)))
        ctx_a.select_values.strings.append("leak")
        ctx_a.resolved.users.append("leak")  # type: ignore[arg-type]
        self.assertEqual(ctx_b.select_values.strings, [])
        self.assertEqual(ctx_b.resolved.users, [])
        self.assertTrue(ctx_b.select_values.is_empty())
        self.assertIsInstance(SelectValues.none(ctx_b), SelectValues)


class TestGuildId(_ClientTestCase):
    def test_guild_interaction_has_guild_id(self) -> None:
        ctx = Context(self.client, _payload(2, {"name": "cmd", "type": 1}))
        self.assertEqual(ctx.guild_id, 100)
        self.assertEqual(ctx.guild.id, 100)  # type: ignore[union-attr]

    def test_dm_interaction_has_no_guild_id(self) -> None:
        data = _payload(2, {"name": "cmd", "type": 1}, user=_user("42"))
        del data["guild_id"], data["member"]
        ctx = Context(self.client, data)
        self.assertIsNone(ctx.guild_id)
        self.assertIsNone(ctx.guild)


class TestChannelTypes(_ClientTestCase):
    def test_guild_media_maps_to_forum_channel(self) -> None:
        self.assertIs(channel_types[16], ForumChannel)

    def test_unknown_type_falls_back_to_base_channel(self) -> None:
        ctx = Context(
            self.client,
            _payload(int(InteractionType.application_command), channel=_channel("200", 999))
        )
        self.assertIs(type(ctx.channel), BaseChannel)

    def test_context_channel_payload_with_media_type(self) -> None:
        ctx = Context(
            self.client,
            _payload(int(InteractionType.application_command), channel=_channel("200", 16))
        )
        self.assertIsInstance(ctx.channel, ForumChannel)


class TestResolvedValues(_ClientTestCase):
    def _resolved(self) -> dict:
        return {
            "users": {"42": _user("42"), "43": _user("43")},
            "members": {"42": {"roles": [], "joined_at": "2024-01-01T00:00:00+00:00", "flags": 0}},
            "channels": {"7": _channel("7", 16), "8": _channel("8", 0)},
        }

    def test_select_values_share_objects_with_resolved(self) -> None:
        resolved = self._resolved()
        ctx = Context(
            self.client,
            _payload(
                int(InteractionType.message_component),
                {"custom_id": "sel", "component_type": 5, "values": ["42"], "resolved": resolved},
            )
        )
        self.assertEqual(ctx.select_values.strings, ["42"])
        self.assertIsInstance(ctx.select_values.members[0], Member)
        self.assertIs(ctx.select_values.members[0], ctx.resolved.members[0])
        self.assertEqual([u.id for u in ctx.resolved.users], [42, 43])
        self.assertIsInstance(ctx.resolved.channels[0], ForumChannel)

    def test_chat_input_args(self) -> None:
        ctx = Context(
            self.client,
            _payload(
                int(InteractionType.application_command),
                {
                    "name": "cmd", "type": 1, "resolved": self._resolved(),
                    "options": [
                        {"name": "sub", "type": int(CommandOptionType.sub_command), "options": [
                            {"name": "who", "type": int(CommandOptionType.user), "value": "42"},
                            {"name": "where", "type": int(CommandOptionType.channel), "value": "8"},
                            {"name": "n", "type": int(CommandOptionType.integer), "value": 3},
                            {"name": "f", "type": int(CommandOptionType.number), "value": 1},
                            {"name": "b", "type": int(CommandOptionType.boolean), "value": True},
                        ]},
                    ],
                },
            )
        )
        args, kwargs = asyncio.run(ctx._create_args())
        self.assertEqual(args, [])
        self.assertIsInstance(kwargs["who"], Member)
        self.assertEqual(kwargs["who"].id, 42)
        self.assertIsInstance(kwargs["where"], TextChannel)
        self.assertEqual((kwargs["n"], kwargs["f"], kwargs["b"]), (3, 1.0, True))
        self.assertIsInstance(kwargs["f"], float)

    def test_user_command_target(self) -> None:
        ctx = Context(
            self.client,
            _payload(int(InteractionType.application_command), {"name": "u", "type": 2, "resolved": self._resolved()})
        )
        args, _ = asyncio.run(ctx._create_args())
        self.assertIsInstance(args[0], Member)
        self.assertEqual(args[0].id, 42)

    def test_user_command_target_without_members(self) -> None:
        ctx = Context(
            self.client,
            _payload(int(InteractionType.application_command), {"name": "u", "type": 2, "resolved": {"users": {"43": _user("43")}}})
        )
        args, _ = asyncio.run(ctx._create_args())
        self.assertIsInstance(args[0], User)
        self.assertEqual(args[0].id, 43)

    def test_modal_values_resolve_selects(self) -> None:
        ctx = Context(
            self.client,
            _payload(
                int(InteractionType.modal_submit),
                {
                    "custom_id": "modal", "resolved": self._resolved(),
                    "components": [
                        {"type": 18, "component": {"type": int(ComponentType.user_select), "custom_id": "u", "values": ["42"]}},
                        {"type": 18, "component": {"type": int(ComponentType.channel_select), "custom_id": "c", "values": ["8", "7"]}},
                        {"type": 18, "component": {"type": int(ComponentType.string_select), "custom_id": "s", "values": ["a"]}},
                        {"type": 18, "component": {"type": 4, "custom_id": "t", "value": "text"}},
                    ],
                },
            )
        )
        self.assertEqual([m.id for m in ctx.modal_values["u"]], [42])  # type: ignore[union-attr]
        self.assertEqual(sorted(c.id for c in ctx.modal_values["c"]), [7, 8])  # type: ignore[union-attr]
        self.assertEqual(ctx.modal_values["s"], ["a"])
        self.assertEqual(ctx.modal_values["t"], "text")


class TestInteractionMetadata(_ClientTestCase):
    def test_context_owners_and_size_limit(self) -> None:
        ctx = Context(
            self.client,
            _payload(
                int(InteractionType.application_command),
                context=1,
                authorizing_integration_owners={"0": "0", "1": "42"},
                attachment_size_limit=10485760,
            )
        )
        self.assertEqual(ctx.context, InteractionContextType.bot_dm)
        self.assertTrue(ctx.is_bot_dm())
        self.assertEqual(
            ctx.authorizing_integration_owners,
            {IntegrationType.guild: 0, IntegrationType.user: 42}
        )
        self.assertEqual(ctx.attachment_size_limit, 10485760)

    def test_defaults_when_absent(self) -> None:
        ctx = Context(self.client, _payload(int(InteractionType.application_command)))
        self.assertIsNone(ctx.context)
        self.assertEqual(ctx.authorizing_integration_owners, {})
        self.assertEqual(ctx.attachment_size_limit, 0)


class TestCallAfterCreatesEvent(_ClientTestCase):
    def test_event_only_created_with_call_after(self) -> None:
        ran: list[bool] = []

        async def after() -> None:
            ran.append(True)

        async def scenario() -> None:
            ctx = Context(self.client, _payload(int(InteractionType.application_command)))

            ctx.response.send_message("hi")
            self.assertIsNone(ctx._response_sent_event)

            ctx.response.send_message("hi", call_after=after)
            self.assertIsNotNone(ctx._response_sent_event)
            ctx._response_sent_event.set()  # type: ignore[union-attr]
            tasks = [t for t in self.client._background_tasks if "call_after" in t.get_name()]
            await asyncio.wait_for(asyncio.gather(*tasks), timeout=5)

        self.client.loop.run_until_complete(scenario())
        self.assertEqual(ran, [True])


if __name__ == "__main__":
    unittest.main()
