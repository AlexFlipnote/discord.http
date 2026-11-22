from pathlib import Path

from docutils import nodes
from sphinx.application import Sphinx
from sphinx.environment.adapters.toctree import document_toc

THEME_PATH = Path(__file__).resolve().parent.parent / "theme"


def _title(app: Sphinx, docname: str) -> str:
    title = app.env.titles.get(docname)
    return title.astext() if title else docname


def _parent_of(app: Sphinx, docname: str) -> str | None:
    """The page whose toctree lists this one, the root doesn't count as a section."""
    for parent, children in app.env.toctree_includes.items():
        if docname in children and parent != app.config.root_doc:
            return parent
    return None


def _page_contents(app: Sphinx, docname: str) -> str:
    """The page's headings and API objects, without the page title above them."""
    toc = document_toc(app.env, docname, app.builder.tags)
    top = next(iter(toc.findall(nodes.bullet_list)), None)
    if top is None:
        return ""
    items = [child for child in top.children if isinstance(child, nodes.list_item)]
    # No single title above everything, like the front page
    if len(items) > 1:
        return app.builder.render_partial(top)["fragment"]
    inner = next((child for child in items[0].children if isinstance(child, nodes.bullet_list)), None) if items else None
    if inner is None:
        return ""
    return app.builder.render_partial(inner)["fragment"]


def strip_code_blank_lines(app: Sphinx, doctree: nodes.document) -> None:
    """
    Strips blank lines around code blocks, Sphinx keeps them for the line numbers.

    The README examples are included from a marker at the end of the ```py line, so they start with its newline.
    """
    for block in doctree.findall(nodes.literal_block):
        text = block.astext()
        lines = text.split("\n")
        while lines and not lines[0].strip():
            lines.pop(0)
        while lines and not lines[-1].strip():
            lines.pop()
        stripped = "\n".join(lines)
        if stripped != text:
            block.children = []
            block += nodes.Text(stripped)
            block.rawsource = stripped


def add_context(
    app: Sphinx,
    pagename: str,
    templatename: str,
    context: dict,
    doctree: nodes.document | None,
) -> None:
    if doctree is None or pagename not in app.env.titles:
        context["panel"] = None
        return

    # A page with pages of its own (API components) is a section itself
    if app.env.toctree_includes.get(pagename) and pagename != app.config.root_doc:
        section = pagename
    else:
        section = _parent_of(app, pagename)

    pages = []
    if section:
        for doc in app.env.toctree_includes[section]:
            if doc in app.env.titles:
                pages.append({
                    "title": _title(app, doc),
                    "link": context["pathto"](doc),
                    "current": doc == pagename,
                })

    context["panel"] = {
        "section": {
            "docname": section,
            "title": _title(app, section),
            "link": context["pathto"](section),
            "current": section == pagename,
        } if section else None,
        "pages": pages,
        "contents": _page_contents(app, pagename),
    }


def setup(app: Sphinx) -> dict:
    app.add_html_theme("flipnote", str(THEME_PATH))
    app.connect("doctree-read", strip_code_blank_lines)
    app.connect("html-page-context", add_context)

    return {
        "version": "0.1",
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
