import unittest

from discord_http import Embed, MessageFlags
from discord_http.enums import ResponseType
from discord_http.response import (
    AutocompleteResponse, DeferResponse, EmptyResponse,
    MessageResponse, ModalResponse,
)
from discord_http.view import Modal


class TestMessageResponseMutualExclusion(unittest.TestCase):
    def test_file_and_files_together_raises(self) -> None:
        with self.assertRaises(TypeError):
            MessageResponse(file=object(), files=[object()])  # type: ignore[arg-type]

    def test_embed_and_embeds_together_raises(self) -> None:
        with self.assertRaises(TypeError):
            MessageResponse(embed=Embed(), embeds=[Embed()])

    def test_attachment_and_attachments_together_raises(self) -> None:
        with self.assertRaises(TypeError):
            MessageResponse(attachment=object(), attachments=[object()])  # type: ignore[arg-type]


class TestMessageResponseEphemeralFlag(unittest.TestCase):
    def test_ephemeral_true_sets_the_flag(self) -> None:
        response = MessageResponse(ephemeral=True)
        self.assertIn(MessageFlags.ephemeral, response.flags)

    def test_ephemeral_false_leaves_flags_untouched(self) -> None:
        response = MessageResponse(ephemeral=False, flags=MessageFlags(0))
        self.assertNotIn(MessageFlags.ephemeral, response.flags)

    def test_ephemeral_true_combines_with_explicit_flags(self) -> None:
        response = MessageResponse(ephemeral=True, flags=MessageFlags.suppress_embeds)
        self.assertIn(MessageFlags.ephemeral, response.flags)
        self.assertIn(MessageFlags.suppress_embeds, response.flags)


class TestMessageResponseViewDefaulting(unittest.IsolatedAsyncioTestCase):
    # View() subclasses InteractionStorage, which requires a running event loop.

    async def test_view_none_becomes_an_empty_view(self) -> None:
        response = MessageResponse(view=None)
        self.assertEqual(response.view.items, [])

    async def test_view_missing_is_left_as_missing(self) -> None:
        from discord_http.utils import MISSING
        response = MessageResponse()
        self.assertIs(response.view, MISSING)


class TestMessageResponseToDictBranching(unittest.TestCase):
    def test_is_request_true_returns_unwrapped_output(self) -> None:
        response = MessageResponse(content="hi")
        payload = response.to_dict(is_request=True)
        self.assertNotIn("type", payload)
        self.assertNotIn("data", payload)
        self.assertEqual(payload["content"], "hi")

    def test_is_request_false_wraps_in_type_and_data(self) -> None:
        response = MessageResponse(content="hi")
        payload = response.to_dict(is_request=False)
        self.assertEqual(payload["type"], int(response.type))
        self.assertEqual(payload["data"]["content"], "hi")

    def test_none_content_is_preserved_as_none_not_stringified(self) -> None:
        response = MessageResponse(content=None)
        payload = response.to_dict(is_request=True)
        self.assertIsNone(payload["content"])

    def test_missing_content_is_omitted(self) -> None:
        response = MessageResponse()
        payload = response.to_dict(is_request=True)
        self.assertNotIn("content", payload)

    def test_embeds_filters_out_non_embed_entries(self) -> None:
        response = MessageResponse(embeds=[Embed(title="a"), None])  # type: ignore[list-item]
        payload = response.to_dict(is_request=True)
        self.assertEqual(len(payload["embeds"]), 1)

    def test_attachments_none_results_in_empty_list(self) -> None:
        response = MessageResponse(attachments=None)
        payload = response.to_dict(is_request=True)
        self.assertEqual(payload["attachments"], [])


class TestAutocompleteResponseTruncation(unittest.TestCase):
    def test_truncates_to_25_choices(self) -> None:
        choices = {str(i): str(i) for i in range(30)}
        response = AutocompleteResponse(choices)
        payload = response.to_dict()
        self.assertEqual(len(payload["data"]["choices"]), 25)

    def test_choice_key_value_mapping(self) -> None:
        response = AutocompleteResponse({"internal": "Shown To User"})
        payload = response.to_dict()
        self.assertEqual(payload["data"]["choices"][0], {
            "name": "Shown To User", "value": "internal",
        })

    def test_type_is_autocomplete_result(self) -> None:
        response = AutocompleteResponse({})
        payload = response.to_dict()
        self.assertEqual(payload["type"], int(ResponseType.application_command_autocomplete_result))


class TestDeferResponse(unittest.TestCase):
    def test_thinking_true_uses_deferred_channel_message_with_source(self) -> None:
        response = DeferResponse(thinking=True)
        payload = response.to_dict()
        self.assertEqual(payload["type"], int(ResponseType.deferred_channel_message_with_source))

    def test_thinking_false_uses_deferred_update_message(self) -> None:
        response = DeferResponse(thinking=False)
        payload = response.to_dict()
        self.assertEqual(payload["type"], int(ResponseType.deferred_update_message))

    def test_ephemeral_sets_the_flag(self) -> None:
        response = DeferResponse(ephemeral=True)
        self.assertIn(MessageFlags.ephemeral, response.flags)
        payload = response.to_dict()
        self.assertEqual(payload["data"]["flags"], int(MessageFlags.ephemeral))


class TestEmptyResponse(unittest.TestCase):
    def test_to_dict_is_empty(self) -> None:
        self.assertEqual(EmptyResponse().to_dict(), {})

    def test_to_multipart_is_empty_bytes(self) -> None:
        self.assertEqual(EmptyResponse().to_multipart(), b"")


class TestModalResponse(unittest.IsolatedAsyncioTestCase):
    # Modal subclasses InteractionStorage, which requires a running event loop.

    async def test_to_dict_wraps_modal_data(self) -> None:
        modal = Modal(title="t", custom_id="m")
        response = ModalResponse(modal)
        payload = response.to_dict()
        self.assertEqual(payload["type"], int(ResponseType.modal))
        self.assertEqual(payload["data"]["title"], "t")


if __name__ == "__main__":
    unittest.main()
