from typing import Literal, NotRequired, TypedDict

from .snowflake import Snowflake

# fmt: off
Oauth2Scope = Literal[
    "activities.read",
    "activities.write",
    "applications.builds.read",
    "applications.builds.upload",
    "applications.commands",
    "applications.commands.update",
    "applications.commands.permissions.update",
    "applications.entitlements",
    "applications.store.update",
    "bot",
    "connections",
    "dm_channels.read",
    "email",
    "gdm.join",
    "guilds",
    "guilds.join",
    "guulds.members.read",
    "identity",
    "messages.read",
    "relationships.read",
    "role_connections.write",
    "rpc",
    "rpc.activities.read",
    "rpc.notifications.read",
    "rpc.voice.read",
    "rpc.voice.write",
    "voice",
    "webhook.incoming",

]
IntegrationTypes = Literal[
    "0", # GUILD_INSTALL
    "1", # USER_INSTALL
]

# fmt: on


class InstallParams(TypedDict):
    scopes: list[Oauth2Scope]
    permissions: str


class IntegrationTypeConfig(TypedDict):
    oauth2_install_params: NotRequired[InstallParams]


class Application(TypedDict):
    id: Snowflake
    name: str
    icon: str | None
    description: str
    rpc_origins: list[str]
    bot_public: bool
    bot_require_code_grant: bool
    bot: NotRequired[dict] # partial user object
    terms_of_service_url: NotRequired[str]
    privacy_policy_url: NotRequired[str]
    owner: NotRequired[dict] # partial user object
    verify_key: str
    team: dict | None # team object
    guild_id: NotRequired[Snowflake]
    guild: NotRequired[dict] # partial guild object
    primary_sku_id: NotRequired[Snowflake]
    slug: NotRequired[str]
    cover_image: NotRequired[str]
    flags: NotRequired[int]
    approximate_guild_count: NotRequired[int]
    approximate_user_install_count: NotRequired[int]
    redirect_urls: NotRequired[list[str]]
    interactions_endpoint_url: NotRequired[str | None]
    role_connections_verification_url: NotRequired[str | None]
    tags: NotRequired[list[str]]
    install_params: NotRequired[InstallParams]
    integration_types_config: NotRequired[dict[IntegrationTypes, IntegrationTypeConfig]]
    custom_install_url: NotRequired[str]
