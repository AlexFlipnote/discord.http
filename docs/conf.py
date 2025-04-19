import os
import sys

sys.path.insert(0, os.path.abspath(".."))
sys.path.append(os.path.abspath("extensions"))

project = "discord_http"
copyright = "2024, AlexFlipnote"
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
]

exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]
pygments_style = "sphinx"

html_static_path = ["_static"]
html_theme = "furo"
html_title = "discord.http docs"
html_favicon = "favicon.ico"
master_doc = "index"

autodoc_typehints = "description"
typehints_use_signature_return = True

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
