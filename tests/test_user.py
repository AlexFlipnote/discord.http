import unittest

from discord_http import Application, Team, ApplicationRoleConnectionMetadata
from discord_http.enums import ApplicationRoleConnectionMetadataType, TeamMembershipState


class FakeState:
    pass


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


if __name__ == "__main__":
    unittest.main()
