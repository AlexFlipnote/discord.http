from sphinx.application import Sphinx
from docutils import nodes
from docutils.nodes import document


def setup(app: Sphinx) -> dict:
    app.connect("html-page-context", add_seo_tags, priority=600)

    return {
        "version": "0.1",
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }


def add_seo_tags(
    app: Sphinx,
    pagename: str,
    templatename: str,
    context: dict,
    doctree: document | None
) -> None:
    # Just to make sure that metatags is not None
    if not context.get("metatags", None):
        context["metatags"] = ""

    meta_title = context.get("docstitle", "no title")
    meta_description = "Python library that handles interactions from Discord POST requests."

    if doctree is not None:
        # Extract the title from the first section or title node
        title_node = doctree.next_node(nodes.title)
        if title_node and pagename not in ("index"):
            meta_title = f"{title_node.astext()} - {meta_title}"

        # Extract the first paragraph for the meta description
        paragraph_node = doctree.next_node(nodes.paragraph)
        if paragraph_node:

            _text = paragraph_node.astext().replace("\n", " ")
            if len(_text) > 160:
                _text = f"{_text[:160].strip()}..."

            meta_description = _text

    context["metatags"] += (
        f'<meta content="{meta_title}" property="og:title">'
    )

    context["metatags"] += (
        f'<meta content="{meta_description}" name="description">'
        f'<meta content="{meta_description}" property="og:description">'
    )

    context["metatags"] += (
        '<meta property="og:image" content="/_static/favicon.ico">'
    )

    context["metatags"] += (
        '<meta name="theme-color" content="#14bae4">'
        '<meta property="og:locale" content="en_GB">'
        '<meta name="keywords" content="discord, http, api, interaction, quart, webhook, slash>'
        '<meta name="revisit-after" content="2 days">'
    )
