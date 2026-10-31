import unittest

from discord_http import Application, Team, ApplicationRoleConnectionMetadata, Client, User
from discord_http.user import DisplayNameStyles, Nameplate, PrimaryGuild
from discord_http.enums import ApplicationRoleConnectionMetadataType, TeamMembershipState

from _fake_client import FakeBot


class FakeState:
    def __init__(self):
        self.bot = FakeBot(self)


class TestTeamMember(unittest.TestCase):
    """ Regression test: TeamMember.user used to be built as a bare id-only
    PartialUser, discarding the username/avatar Discord actually sends. """

    def test_user_is_a_full_user_with_name(self) -> None:
        team = Team(state=FakeState(), data={
            "id": "1", "name": "T", "owner_user_id": "2",
            "members": [{
                "membership_state": 2, "role": "admin",
                "user": {"id": "3", "username": "bob", "discriminator": "0001", "avatar": None},
            }],
        })
        member = team.members[0]
        self.assertEqual(member.user.name, "bob")
        self.assertEqual(member.membership_state, TeamMembershipState.accepted)

    def test_owner_property(self) -> None:
        team = Team(state=FakeState(), data={
            "id": "1", "name": "T", "owner_user_id": "2", "members": [],
        })
        self.assertEqual(team.owner.id, 2)


class TestApplicationGuildField(unittest.TestCase):
    """ Regression test: Application.guild only checked `guild_id`, so it
    stayed None when the API returned the `guild` object without a sibling
    `guild_id` field (both are separately-documented, independently-optional
    fields on the Application object). """

    def test_falls_back_to_guild_object_id(self) -> None:
        app = Application(state=FakeState(), data={
            "id": "1", "name": "App", "verify_key": "x",
            "guild": {"id": "99", "name": "g"},
        })
        self.assertIsNotNone(app.guild)
        self.assertEqual(app.guild.id, 99)

    def test_prefers_guild_id_when_present(self) -> None:
        app = Application(state=FakeState(), data={
            "id": "1", "name": "App", "verify_key": "x", "guild_id": "50",
        })
        self.assertEqual(app.guild.id, 50)


class TestApplicationRoleConnectionMetadata(unittest.TestCase):
    def test_from_dict_to_dict_round_trip(self) -> None:
        metadata = ApplicationRoleConnectionMetadata.from_dict({
            "type": 7, "key": "is_verified", "name": "Verified", "description": "is verified",
        })
        self.assertEqual(metadata.type, ApplicationRoleConnectionMetadataType.boolean_equal)

        payload = metadata.to_dict()
        self.assertEqual(payload["key"], "is_verified")
        self.assertEqual(payload["type"], 7)


def _user_data(**overrides):
    data = {"id": "10", "username": "bob", "discriminator": "0", "avatar": None}
    data.update(overrides)
    return data


class TestUserParsing(unittest.TestCase):
    def test_discriminator_zero_becomes_none(self) -> None:
        self.assertIsNone(User(state=FakeState(), data=_user_data()).discriminator)
        self.assertEqual(User(state=FakeState(), data=_user_data(discriminator="1234")).discriminator, "1234")


class TestUserCopyFrom(unittest.TestCase):
    def test_copy_from(self) -> None:
        a = User(state=FakeState(), data=_user_data())
        b = User(state=FakeState(), data=_user_data(username="new", bot=True))
        a._copy_from(b)
        self.assertEqual(a.name, "new")
        self.assertTrue(a.bot)


class TestUserExtras(unittest.TestCase):
    """ The collectible/style payloads must still build the right objects. """

    def test_everything_unset_has_no_extra(self) -> None:
        user = User(state=FakeState(), data=_user_data(
            avatar_decoration_data=None, collectibles=None,
            display_name_styles=None, primary_guild=None,
        ))
        self.assertIsNone(user._extra)
        self.assertIsNone(user.avatar_decoration)
        self.assertIsNone(user.nameplate)
        self.assertIsNone(user.name_style)
        self.assertIsNone(user.primary_guild)

    def test_avatar_decoration(self) -> None:
        user = User(state=FakeState(), data=_user_data(
            avatar_decoration_data={"asset": "a_deco", "sku_id": "55", "expires_at": None},
        ))
        deco = user.avatar_decoration
        self.assertEqual(deco.sku_id, 55)
        self.assertEqual(deco.asset.key, "a_deco")
        self.assertTrue(deco.asset.animated)

    def test_nameplate(self) -> None:
        user = User(state=FakeState(), data=_user_data(collectibles={"nameplate": {
            "sku_id": "77", "label": "Lbl", "palette": "crimson",
            "asset": "nameplates/x/", "expires_at": None,
        }}))
        plate = user.nameplate
        self.assertIsInstance(plate, Nameplate)
        self.assertEqual(plate.sku_id, 77)
        self.assertEqual(plate.label, "Lbl")
        self.assertEqual(plate.palette, "crimson")
        self.assertEqual(plate.asset.url, Nameplate(FakeState(), {
            "sku_id": "77", "label": "Lbl", "palette": "crimson", "asset": "nameplates/x/",
        }).asset.url)

    def test_name_style(self) -> None:
        raw = {"colors": [1, 2], "font_id": 3, "effect_id": 2}
        user = User(state=FakeState(), data=_user_data(display_name_styles=raw))
        style = user.name_style
        self.assertEqual(style.to_dict(), DisplayNameStyles(data=raw).to_dict())

    def test_primary_guild(self) -> None:
        raw = {"identity_guild_id": "123", "identity_enabled": True, "tag": "ABCD", "badge": "a_badge"}
        user = User(state=FakeState(), data=_user_data(primary_guild=raw))
        pg = user.primary_guild
        expected = PrimaryGuild(state=FakeState(), data=raw)
        self.assertEqual(pg.guild_id, 123)
        self.assertEqual(pg.tag, "ABCD")
        self.assertEqual(pg.badge.url, expected.badge.url)

    def test_names_are_not_interned(self) -> None:
        # Unique per-user strings should not be pushed into the (immortal) intern table
        name = "".join(["uniq", "ue_name_", "xyz"])
        user = User(state=FakeState(), data=_user_data(username=name))
        self.assertIs(user.name, name)


if __name__ == "__main__":
    unittest.main()
