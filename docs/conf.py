import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.abspath(".."))
sys.path.append(os.path.abspath("extensions"))

project = "discord_http"
copyright = f"2024-{datetime.now().year}, AlexFlipnote"
author = "AlexFlipnote"
release = "0.0.1"

extensions = [
    # Sphinx's own extensions
    "sphinx.ext.autodoc",
    "sphinx.ext.extlinks",
    "sphinx.ext.napoleon",
    "sphinx.ext.intersphinx",

    # Third party extensions
    "sphinx_autodoc_typehints",
    "myst_parser",
    "seo_support",
    "flipnote",
]

exclude_patterns = ["_build", "theme", "Thumbs.db", ".DS_Store"]
html_static_path = ["_static"]
html_theme = "flipnote"
html_title = "discord.http docs"
html_short_title = "discord.http"
html_favicon = "favicon.ico"
master_doc = "index"
suppress_warnings = ["ref.python"]

# theme/, registered by extensions/flipnote.py
html_theme_options = {
    "nav_links": [
        ("Getting started", "pages/getting_started"),
        ("API", "pages/api"),
        ("Events", "pages/events"),
    ],
    "nav_more": [
        ("Gateway", "pages/gateway"),
        ("HTTP backend", "pages/backend"),
        ("Style guide", "pages/format"),
        ("Contributing", "pages/contribute"),
        ("License", "pages/license"),
    ],
    "github_url": "https://github.com/AlexFlipnote/discord.http",
    "discord_url": "https://discord.gg/yqb7vATbjH",
}

toc_object_entries_show_parents = "hide"

typehints_use_signature_return = True
napoleon_use_ivar = True
autodoc_typehints = "description"
set_type_checking_flag = True
autoclass_content = "class"
autodoc_default_options = {
    "members": True,
    "member-order": "bysource",
    "inherited-members": True,
    "undoc-members": False,
    "show-inheritance": True,
}

source_suffix = {
    ".rst": "restructuredtext",
    ".txt": "markdown",
    ".md": "markdown",
}

intersphinx_mapping = {
    "py": ("https://docs.python.org/3", None),
    "aio": ("https://docs.aiohttp.org/en/stable/", None),
}

# Link tree
extlinks = {
    "github": ("https://github.com/AlexFlipnote/discord.http%s", "%s"),
    "discord": ("https://discord.gg/yqb7vATbjH%s", "%s"),
}
