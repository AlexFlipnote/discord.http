import asyncio
import io
import unittest

from unittest import mock

from discord_http import (
    ActionRow, Button, ButtonStyles, CheckboxGroupComponent, ComponentOption,
    ContainerComponent, File, Link, Modal, Premium, RadioComponent, Select,
    TextDisplayComponent, View,
)
from discord_http.view import (
    AttachmentComponent, CheckpointComponent, FileComponent, LabelComponent,
    MediaGalleryComponent, MediaGalleryItem, OverflowMenuComponent, TextInputComponent, ThumbnailComponent,
)


class TestButtonStyleCoercion(unittest.TestCase):
    def test_enum_style_passed_through(self) -> None:
        button = Button(style=ButtonStyles.danger)
        self.assertEqual(button.style, ButtonStyles.danger)

    def test_int_style_converted_to_enum(self) -> None:
        button = Button(style=2)
        self.assertEqual(button.style, ButtonStyles.secondary)

    def test_valid_str_style_converted_to_enum(self) -> None:
        button = Button(style="danger")
        self.assertEqual(button.style, ButtonStyles.danger)

    def test_invalid_str_style_falls_back_to_primary(self) -> None:
        button = Button(style="not_a_real_style")
        self.assertEqual(button.style, ButtonStyles.primary)

    def test_unrecognized_type_falls_back_to_primary(self) -> None:
        button = Button(style=3.5)  # type: ignore[arg-type]
        self.assertEqual(button.style, ButtonStyles.primary)

    def test_link_style_forces_custom_id_none(self) -> None:
        button = Button(style=ButtonStyles.link, custom_id="x", url="https://example.com")
        self.assertIsNone(button.custom_id)

    def test_premium_style_forces_custom_id_none(self) -> None:
        button = Button(style=ButtonStyles.premium, custom_id="x", sku_id=123)
        self.assertIsNone(button.custom_id)


class TestButtonToDict(unittest.TestCase):
    def test_link_without_url_raises(self) -> None:
        button = Button(style=ButtonStyles.link)
        with self.assertRaises(ValueError):
            button.to_dict()

    def test_premium_without_sku_id_raises(self) -> None:
        button = Button(style=ButtonStyles.premium)
        with self.assertRaises(ValueError):
            button.to_dict()

    def test_sku_id_requires_premium_style(self) -> None:
        button = Button(style=ButtonStyles.primary)
        button.sku_id = 123
        with self.assertRaises(ValueError):
            button.to_dict()

    def test_sku_id_present_ignores_label_and_custom_id(self) -> None:
        button = Premium(sku_id=123)
        payload = button.to_dict()
        self.assertEqual(payload, {
            "type": int(button.type),
            "style": int(ButtonStyles.premium),
            "disabled": False,
            "sku_id": "123",
        })

    def test_custom_id_and_url_together_raises(self) -> None:
        button = Button(custom_id="x")
        button.url = "https://example.com"
        with self.assertRaises(ValueError):
            button.to_dict()

    def test_label_over_80_chars_raises(self) -> None:
        button = Button(label="x" * 81)
        with self.assertRaises(ValueError):
            button.to_dict()

    def test_url_over_512_chars_raises(self) -> None:
        button = Link(url="https://example.com/" + ("x" * 500))
        with self.assertRaises(ValueError):
            button.to_dict()

    def test_link_to_dict_contains_url_not_custom_id(self) -> None:
        button = Link(url="https://example.com", label="hi")
        payload = button.to_dict()
        self.assertEqual(payload["url"], "https://example.com")
        self.assertNotIn("custom_id", payload)


class TestSelectToDict(unittest.TestCase):
    def test_min_values_out_of_range_raises(self) -> None:
        select = Select(min_values=26)
        with self.assertRaises(ValueError):
            select.to_dict()

    def test_max_values_out_of_range_raises(self) -> None:
        select = Select(max_values=0)
        with self.assertRaises(ValueError):
            select.to_dict()

    def test_option_label_over_100_chars_raises(self) -> None:
        select = Select()
        select.add_item(label="x" * 101, value="v")
        with self.assertRaises(ValueError):
            select.to_dict()

    def test_validation_happens_at_to_dict_not_add_item(self) -> None:
        # add_item() itself has no length checks - only to_dict() validates.
        select = Select()
        select.add_item(label="x" * 101, value="v")
        self.assertEqual(len(select._options), 1)

    def test_more_than_25_options_raises(self) -> None:
        select = Select()
        for i in range(25):
            select.add_item(label=str(i), value=str(i))
        with self.assertRaises(ValueError):
            select.add_item(label="26", value="26")


class TestRadioComponentToDict(unittest.TestCase):
    def test_fewer_than_2_options_raises(self) -> None:
        radio = RadioComponent(
            ComponentOption(label="a", value="a"),
            custom_id="r",
        )
        with self.assertRaises(ValueError):
            radio.to_dict()

    def test_2_to_10_options_is_valid(self) -> None:
        radio = RadioComponent(
            ComponentOption(label="a", value="a"),
            ComponentOption(label="b", value="b"),
            custom_id="r",
        )
        payload = radio.to_dict()
        self.assertEqual(len(payload["options"]), 2)

    def test_more_than_10_options_raises_on_add(self) -> None:
        radio = RadioComponent(custom_id="r")
        for i in range(10):
            radio.add_item(value=str(i), label=str(i))
        with self.assertRaises(ValueError):
            radio.add_item(value="10", label="10")


class TestCheckboxGroupMutationRegression(unittest.TestCase):
    """ Regression test: to_dict() used to permanently cache a computed
    max_values onto self.max_values the first time it ran, so a later
    add_item() call that grew the option list was never reflected in
    subsequent to_dict() calls. """

    def test_max_values_reflects_options_added_after_a_prior_to_dict_call(self) -> None:
        group = CheckboxGroupComponent(
            ComponentOption(label="a", value="a"),
            ComponentOption(label="b", value="b"),
            ComponentOption(label="c", value="c"),
        )
        first = group.to_dict()
        self.assertEqual(first["max_values"], 3)

        group.add_item(value="d", label="d")
        second = group.to_dict()
        self.assertEqual(second["max_values"], 4)

        # self.max_values itself must never have been mutated
        self.assertIsNone(group.max_values)

    def test_explicit_max_values_is_not_overridden(self) -> None:
        group = CheckboxGroupComponent(
            ComponentOption(label="a", value="a"),
            ComponentOption(label="b", value="b"),
            max_values=1,
        )
        payload = group.to_dict()
        self.assertEqual(payload["max_values"], 1)

    def test_zero_options_raises(self) -> None:
        group = CheckboxGroupComponent()
        with self.assertRaises(ValueError):
            group.to_dict()


class TestActionRowToDict(unittest.TestCase):
    def test_rejects_unsupported_component_type(self) -> None:
        row = ActionRow(TextDisplayComponent(content="hi"))  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            row.to_dict()

    def test_empty_row_raises(self) -> None:
        row = ActionRow()
        with self.assertRaises(ValueError):
            row.to_dict()

    def test_more_than_5_components_raises(self) -> None:
        row = ActionRow(*[Button(custom_id=str(i)) for i in range(6)])
        with self.assertRaises(ValueError):
            row.to_dict()

    def test_select_cannot_share_row_with_another_component(self) -> None:
        row = ActionRow(Select(), Button(custom_id="x"))
        with self.assertRaises(ValueError):
            row.to_dict()

    def test_single_select_alone_is_valid(self) -> None:
        row = ActionRow(Select())
        payload = row.to_dict()
        self.assertEqual(len(payload["components"]), 1)

    def test_from_dict_coerces_url_component_to_link_regardless_of_type(self) -> None:
        row = ActionRow.from_dict({
            "type": 1,
            "components": [
                {"type": 2, "style": 1, "url": "https://example.com", "label": "hi"},
            ],
        })
        self.assertIsInstance(row.components[0], Link)


class TestContainerComponentToDict(unittest.TestCase):
    def test_rejects_unsupported_component_type(self) -> None:
        container = ContainerComponent(Button(custom_id="x"))  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            container.to_dict()

    def test_add_item_rejects_nested_container(self) -> None:
        container = ContainerComponent()
        with self.assertRaises(ValueError):
            container.add_item(ContainerComponent())

    def test_add_item_over_40_raises(self) -> None:
        container = ContainerComponent()
        for _ in range(40):
            container.add_item(TextDisplayComponent(content="x"))
        with self.assertRaises(ValueError):
            container.add_item(TextDisplayComponent(content="x"))

    def test_valid_items_serialize(self) -> None:
        container = ContainerComponent(TextDisplayComponent(content="hi"))
        payload = container.to_dict()
        self.assertEqual(len(payload["components"]), 1)


class TestViewToDict(unittest.IsolatedAsyncioTestCase):
    # View subclasses InteractionStorage, which requires a running event loop.

    async def test_rejects_component_not_allowed_at_root(self) -> None:
        view = View(Button(custom_id="x"))
        with self.assertRaises(ValueError):
            view.to_dict()

    async def test_action_row_at_root_is_valid(self) -> None:
        view = View(ActionRow(Button(custom_id="x")))
        payload = view.to_dict()
        self.assertEqual(len(payload), 1)

    async def test_inaccessible_component_types_skip_validation(self) -> None:
        view = View(CheckpointComponent())
        payload = view.to_dict()
        self.assertEqual(len(payload), 1)

    async def test_more_than_40_items_raises(self) -> None:
        view = View(*[ActionRow(Button(custom_id=str(i))) for i in range(41)])
        with self.assertRaises(ValueError):
            view.to_dict()


class TestViewFromDictUnfurledMedia(unittest.IsolatedAsyncioTestCase):
    def _media(self, **overrides) -> dict:
        data = {"url": "https://cdn.example/a.png", "proxy_url": "https://proxy.example/a.png"}
        data.update(overrides)
        return data

    async def test_file_keeps_attachment_id_and_spoiler(self) -> None:
        view = View.from_dict(state=None, data={"components": [  # type: ignore[arg-type]
            {"type": 13, "id": 1, "file": self._media(attachment_id="55"), "spoiler": True, "name": "a.png", "size": 3},
        ]})
        file = view.items[0]
        self.assertIsInstance(file, FileComponent)
        self.assertTrue(file.spoiler)
        self.assertEqual(file.file.attachment_id, 55)

    async def test_missing_proxy_url_and_attachment_id(self) -> None:
        view = View.from_dict(state=None, data={"components": [  # type: ignore[arg-type]
            {"type": 13, "file": {"url": "https://example.com/a.png"}},
        ]})
        self.assertIsNone(view.items[0].file.proxy_url)
        self.assertIsNone(view.items[0].file.attachment_id)

    async def test_section_thumbnail_keeps_description_and_spoiler(self) -> None:
        view = View.from_dict(state=None, data={"components": [  # type: ignore[arg-type]
            {"type": 9, "components": [{"type": 10, "content": "hi"}], "accessory": {
                "type": 11, "media": self._media(), "description": "alt", "spoiler": True,
            }},
        ]})
        accessory = view.items[0].accessory
        self.assertIsInstance(accessory, ThumbnailComponent)
        self.assertEqual(accessory.to_dict(), {
            "type": 11, "media": {"url": "https://cdn.example/a.png"},
            "description": "alt", "spoiler": True,
        })


    async def test_gallery_items_keep_their_attachment(self) -> None:
        view = View.from_dict(state=None, data={"components": [  # type: ignore[arg-type]
            {"type": 12, "items": [{"media": self._media(), "description": "alt"}]},
        ]})
        item = view.items[0].items[0]
        self.assertIsInstance(item.url, AttachmentComponent)
        self.assertEqual(item.url.proxy_url, "https://proxy.example/a.png")
        self.assertEqual(item.to_dict()["media"], {"url": "https://cdn.example/a.png"})


class TestMediaGalleryFiles(unittest.TestCase):
    def test_file_item_points_at_the_attachment(self) -> None:
        file = File(io.BytesIO(b"x"), filename="a.png")
        self.assertEqual(MediaGalleryItem(file).to_dict()["media"], {"url": "attachment://a.png"})
        self.assertEqual(
            MediaGalleryComponent(file).to_dict()["items"][0]["media"],
            {"url": "attachment://a.png"},
        )


class TestLabelComponentToDict(unittest.TestCase):
    def test_no_label_anywhere_raises_type_error(self) -> None:
        label = LabelComponent(label=None, component=TextInputComponent())
        with self.assertRaises(TypeError):
            label.to_dict()

    def test_component_label_takes_priority_over_wrapper_label(self) -> None:
        text_input = TextInputComponent(label="inner")
        label = LabelComponent(label="outer", component=text_input)
        self.assertEqual(label.label, "inner")

    def test_label_over_45_chars_raises(self) -> None:
        label = LabelComponent(label="x" * 46, component=TextInputComponent())
        with self.assertRaises(ValueError):
            label.to_dict()

    def test_description_over_100_chars_raises(self) -> None:
        label = LabelComponent(
            label="hi", description="x" * 101, component=TextInputComponent()
        )
        with self.assertRaises(ValueError):
            label.to_dict()

    def test_unsupported_component_type_raises(self) -> None:
        # LabelComponent's whitelist check only runs in to_dict(), not __init__,
        # so a duck-typed stand-in avoids the AttributeError a real Button would
        # hit in __init__ (Button has no .description attribute).
        class _FakeComponent:
            type = None
            label = "hi"
            description = None

        fake = _FakeComponent()
        fake.type = Button(custom_id="x").type
        label = LabelComponent(label="hi", component=fake)  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            label.to_dict()


class TestModalAddItem(unittest.IsolatedAsyncioTestCase):
    # Modal subclasses InteractionStorage, which requires a running event loop.

    async def test_text_display_added_directly_without_wrapping(self) -> None:
        modal = Modal(title="t")
        item = modal.add_item(TextDisplayComponent(content="hi"))
        self.assertIsInstance(item, TextDisplayComponent)
        self.assertIs(modal.items[0], item)

    async def test_other_components_are_wrapped_in_label_component(self) -> None:
        modal = Modal(title="t")
        item = modal.add_item(TextInputComponent(), label="hi")
        self.assertIsInstance(item, LabelComponent)

    async def test_more_than_5_items_raises(self) -> None:
        modal = Modal(title="t")
        for i in range(5):
            modal.add_item(TextInputComponent(), label=str(i))
        with self.assertRaises(ValueError):
            modal.add_item(TextInputComponent(), label="6")

    async def test_to_dict_round_trip(self) -> None:
        modal = Modal(title="t", custom_id="m")
        modal.add_item(TextInputComponent(custom_id="a"), label="hi")
        payload = modal.to_dict()
        self.assertEqual(payload["title"], "t")
        self.assertEqual(payload["custom_id"], "m")
        self.assertEqual(len(payload["components"]), 1)



class TestButtonCustomIdGeneration(unittest.TestCase):
    def test_link_and_premium_do_not_generate_ids(self) -> None:
        with mock.patch("discord_http.view._garbage_id", side_effect=AssertionError("generated")):
            self.assertIsNone(Button(style=ButtonStyles.link, url="https://example.com").custom_id)
            self.assertIsNone(Button(style=ButtonStyles.premium, sku_id=1).custom_id)

    def test_regular_button_still_gets_random_id(self) -> None:
        custom_id = Button(label="x").custom_id
        self.assertIsInstance(custom_id, str)
        self.assertEqual(len(custom_id), 32)

    def test_explicit_custom_id_is_kept(self) -> None:
        self.assertEqual(Button(label="x", custom_id="mine").custom_id, "mine")


class _FakeCtx:
    def __init__(self, bot, id_: int = 1):
        self.bot = bot
        self.id = id_
        self.message = None

    async def original_response(self):
        raise RuntimeError("no message")


class _FakeBot:
    def __init__(self):
        self._view_storage: dict = {}


class TestViewWaitStorage(unittest.IsolatedAsyncioTestCase):
    async def test_no_timeout_watcher_when_timeout_is_none(self) -> None:
        bot = _FakeBot()
        view = View()
        waiter = asyncio.create_task(view.wait(_FakeCtx(bot), timeout=None))
        await asyncio.sleep(0)
        self.assertIsNone(view._timeout_task)
        self.assertIs(bot._view_storage[1], view)
        view._update_event(True)
        await waiter
        self.assertNotIn(1, bot._view_storage)

    async def test_does_not_pop_another_views_entry(self) -> None:
        bot = _FakeBot()
        first, second = View(), View()
        waiter = asyncio.create_task(first.wait(_FakeCtx(bot), timeout=None))
        await asyncio.sleep(0)

        # A second view re-used the same key before the first one finished
        bot._view_storage[1] = second
        first._update_event(True)
        await waiter
        self.assertIs(bot._view_storage[1], second)

    async def test_early_return_cancels_timeout_watcher(self) -> None:
        bot = _FakeBot()
        view = View()
        with mock.patch("discord_http.view.asyncio.sleep", new=mock.AsyncMock()):
            result = await view.wait(_FakeCtx(bot), original_response=True, timeout=60)
        self.assertIsNone(result)
        self.assertIsNone(view._timeout_task)
        self.assertEqual(bot._view_storage, {})


class _User:
    def __init__(self, id_: int):
        self.id = id_

    def __int__(self) -> int:
        return self.id


class TestViewWaitUsers(unittest.IsolatedAsyncioTestCase):
    async def _allowed(self, users) -> set[int]:
        view = View()
        await view.wait(_FakeCtx(_FakeBot()), users=users, timeout=0.01)
        return view._user_ids

    async def test_objects_ids_and_any_iterable_are_enforced(self) -> None:
        for users in ([_User(5)], [5], ["5"], (_User(5),), {5}, iter([5])):
            with self.subTest(users=users):
                self.assertEqual(await self._allowed(users), {5})

    async def test_unusable_entries_raise_instead_of_opening_the_view(self) -> None:
        for users in (["bob"], [None], [object()], [True]):
            with self.subTest(users=users), self.assertRaises(TypeError):
                await self._allowed(users)

    async def test_no_users_means_no_restriction(self) -> None:
        self.assertEqual(await self._allowed(None), set())


if __name__ == "__main__":
    unittest.main()


class TestOverflowMenu(unittest.TestCase):
    def _menu(self) -> OverflowMenuComponent:
        from discord_http import MenuActionItem, MenuActionItemStyles, OverflowMenuComponent, OverflowMenuGroup
        return OverflowMenuComponent(
            OverflowMenuGroup(
                MenuActionItem(label="Edit", custom_id="edit", description="Change it"),
                MenuActionItem(label="Delete", style=MenuActionItemStyles.danger, custom_id="delete"),
                label="Manage",
            ),
            OverflowMenuGroup(
                MenuActionItem(label="Docs", style="link", url="https://example.com"),
            ),
        )

    def test_to_dict_matches_api_shape(self) -> None:
        self.assertEqual(self._menu().to_dict(), {
            "type": 25,
            "groups": [
                {
                    "label": "Manage",
                    "components": [
                        {"type": 26, "style": 1, "label": "Edit", "disabled": False,
                         "description": "Change it", "custom_id": "edit"},
                        {"type": 26, "style": 2, "label": "Delete", "disabled": False, "custom_id": "delete"},
                    ],
                },
                {
                    "components": [
                        {"type": 26, "style": 3, "label": "Docs", "disabled": False, "url": "https://example.com"},
                    ],
                },
            ],
        })

    def test_item_style_coercion_and_custom_ids(self) -> None:
        from discord_http import MenuActionItem, MenuActionItemStyles
        self.assertEqual(MenuActionItem(label="a", style=2).style, MenuActionItemStyles.danger)
        self.assertEqual(MenuActionItem(label="a", style="nope").style, MenuActionItemStyles.default)
        self.assertIsNotNone(MenuActionItem(label="a").custom_id)
        self.assertIsNone(MenuActionItem(label="a", style="link", custom_id="x", url="https://x").custom_id)

    def test_invalid_menus_raise(self) -> None:
        from discord_http import MenuActionItem, OverflowMenuComponent, OverflowMenuGroup
        with self.assertRaises(ValueError):
            OverflowMenuComponent().to_dict()
        with self.assertRaises(ValueError):
            OverflowMenuComponent(OverflowMenuGroup()).to_dict()
        with self.assertRaises(ValueError):
            MenuActionItem(label="a", style="link").to_dict()
        with self.assertRaises(ValueError):
            MenuActionItem(label="a", custom_id="x", url="https://x").to_dict()
        with self.assertRaises(TypeError):
            OverflowMenuGroup(Button(label="nope")).to_dict()  # type: ignore[arg-type]

    def test_add_group(self) -> None:
        from discord_http import MenuActionItem, OverflowMenuComponent
        menu = OverflowMenuComponent()
        group = menu.add_group(MenuActionItem(label="a", custom_id="a"), label="g")
        self.assertIs(menu.groups[0], group)
        self.assertEqual(menu.to_dict()["groups"][0]["label"], "g")

    def test_allowed_in_action_row_and_section(self) -> None:
        from discord_http.view import SectionComponent
        menu = self._menu()
        self.assertEqual(ActionRow(Button(label="b"), menu).to_dict()["components"][1]["type"], 25)
        self.assertEqual(SectionComponent("text", accessory=menu).to_dict()["accessory"]["type"], 25)

    def test_round_trips_through_view_from_dict(self) -> None:
        from discord_http.view import OverflowMenuComponent, SectionComponent
        menu = self._menu()
        data = {"components": [
            {"type": 1, "id": 1, "components": [{**menu.to_dict(), "id": 2}]},
            {"type": 9, "id": 3, "components": [{"type": 10, "id": 4, "content": "hi"}],
             "accessory": menu.to_dict()},
        ]}
        view = View.from_dict(state=None, data=data)  # type: ignore[arg-type]
        row, section = view.items
        self.assertIsInstance(row.components[0], OverflowMenuComponent)  # type: ignore[attr-defined]
        self.assertIsInstance(section, SectionComponent)
        self.assertEqual(row.components[0].to_dict(), menu.to_dict())  # type: ignore[attr-defined]
        self.assertEqual(section.accessory.to_dict(), menu.to_dict())  # type: ignore[attr-defined]

    def test_view_accepts_menu_item_custom_ids(self) -> None:
        from types import SimpleNamespace
        from discord_http.enums import InteractionType
        from discord_http.view import SectionComponent
        view = View(
            ActionRow(self._menu()),
            ContainerComponent(SectionComponent("text", accessory=self._menu())),
        )
        for custom_id, expected in (("edit", True), ("delete", True), ("other", False)):
            ctx = SimpleNamespace(type=InteractionType.message_component, custom_id=custom_id)
            self.assertEqual(view.accepts(ctx), expected)  # type: ignore[arg-type]

    def test_loose_items_become_a_single_group(self) -> None:
        from discord_http import MenuActionItem
        a, b = MenuActionItem(label="a", custom_id="a"), MenuActionItem(label="b", custom_id="b")
        menu = OverflowMenuComponent(a, b)
        self.assertEqual(len(menu.groups), 1)
        self.assertEqual(menu.groups[0].components, [a, b])
        self.assertNotIn("label", menu.to_dict()["groups"][0])

    def test_add_item_appends_to_last_group(self) -> None:
        from discord_http import MenuActionItem
        menu = OverflowMenuComponent()
        first = menu.add_item(MenuActionItem(label="a", custom_id="a"))
        group = menu.add_group(label="Second")
        menu.add_item(MenuActionItem(label="b", custom_id="b"))
        self.assertEqual(menu.groups[0].components, [first])
        self.assertEqual([i.custom_id for i in group.components], ["b"])

    def test_add_item_rejects_non_menu_items(self) -> None:
        with self.assertRaises(TypeError):
            OverflowMenuComponent(Button(label="nope"))  # type: ignore[arg-type]


class TestViewFindRemoveCustomId(unittest.TestCase):
    def _view(self) -> View:
        from discord_http import MenuActionItem
        from discord_http.view import SectionComponent
        return View(
            ActionRow(Button(label="a", custom_id="row_a"), Button(label="b", custom_id="row_b")),
            ContainerComponent(
                ActionRow(Select(custom_id="select")),
                SectionComponent("text", accessory=Button(label="c", custom_id="accessory")),
                SectionComponent("text", accessory=OverflowMenuComponent(
                    MenuActionItem(label="x", custom_id="acc_menu_x"),
                    MenuActionItem(label="y", custom_id="acc_menu_y"),
                )),
            ),
            ActionRow(OverflowMenuComponent(MenuActionItem(label="z", custom_id="only_item"))),
        )

    def test_find_reaches_every_level(self) -> None:
        view = self._view()
        for custom_id in ("row_b", "select", "accessory", "acc_menu_y", "only_item"):
            found = view.find_custom_id(custom_id)
            self.assertIsNotNone(found, custom_id)
            self.assertEqual(found.custom_id, custom_id)  # type: ignore[union-attr]
        self.assertIsNone(view.find_custom_id("missing"))

    def test_found_item_edits_in_place(self) -> None:
        view = self._view()
        view.find_custom_id("row_a").disabled = True  # type: ignore[union-attr]
        self.assertTrue(view.to_dict()[0]["components"][0]["disabled"])

    def test_remove_from_row_keeps_row_with_items_left(self) -> None:
        view = self._view()
        removed = view.remove_custom_id("row_a")
        self.assertEqual(removed.custom_id, "row_a")  # type: ignore[union-attr]
        self.assertIsNone(view.find_custom_id("row_a"))
        self.assertEqual(len(view.items), 3)

    def test_remove_last_item_prunes_empty_parents(self) -> None:
        view = self._view()
        view.remove_custom_id("only_item")  # item -> group -> menu -> row all empty now
        self.assertEqual(len(view.items), 2)
        view.remove_custom_id("select")  # row inside the container goes, container stays
        self.assertEqual(len(view.items[1].items), 2)  # type: ignore[attr-defined]
        view.to_dict()

    def test_remove_inside_accessory_menu(self) -> None:
        view = self._view()
        view.remove_custom_id("acc_menu_x")
        self.assertIsNone(view.find_custom_id("acc_menu_x"))
        self.assertIsNotNone(view.find_custom_id("acc_menu_y"))

    def test_remove_accessory_raises(self) -> None:
        with self.assertRaises(ValueError):
            self._view().remove_custom_id("accessory")

    def test_remove_missing_returns_none(self) -> None:
        self.assertIsNone(self._view().remove_custom_id("missing"))

    def test_replace_keeps_position(self) -> None:
        view = self._view()
        new = Button(label="new", custom_id="row_new")
        old = view.replace_custom_id("row_a", new)
        self.assertEqual(old.custom_id, "row_a")  # type: ignore[union-attr]
        self.assertIs(view.items[0].components[0], new)  # type: ignore[attr-defined]

    def test_replace_works_on_accessory(self) -> None:
        view = self._view()
        new = Button(label="new", custom_id="acc_new")
        view.replace_custom_id("accessory", new)
        self.assertIs(view.items[1].items[1].accessory, new)  # type: ignore[attr-defined]
        self.assertIsNone(view.replace_custom_id("missing", new))

    def test_walk_yields_components_only(self) -> None:
        from discord_http import MenuActionItem
        from discord_http.view import OverflowMenuGroup
        nodes = list(self._view().walk())
        self.assertFalse(any(isinstance(g, OverflowMenuGroup) for g in nodes))
        self.assertEqual(sum(isinstance(g, MenuActionItem) for g in nodes), 3)
        self.assertEqual(sum(isinstance(g, Select) for g in nodes), 1)

    def test_disable_all_and_back(self) -> None:
        view = self._view()
        self.assertIs(view.disable_all(), view)
        toggles = [g for g in view.walk() if hasattr(g, "disabled")]
        self.assertEqual(len(toggles), 7)
        self.assertTrue(all(g.disabled for g in toggles))  # type: ignore[attr-defined]
        view.disable_all(False)
        self.assertFalse(any(g.disabled for g in toggles))  # type: ignore[attr-defined]
