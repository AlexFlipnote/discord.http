import unittest

from discord_http import (
    ActionRow, Button, ButtonStyles, CheckboxGroupComponent, ComponentOption,
    ContainerComponent, Link, Modal, Premium, RadioComponent, Select,
    TextDisplayComponent, View,
)
from discord_http.view import CheckpointComponent, LabelComponent, TextInputComponent


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


if __name__ == "__main__":
    unittest.main()
