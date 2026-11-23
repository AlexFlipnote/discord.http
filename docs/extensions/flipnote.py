import ast
import inspect
import sys

from functools import cache
from pathlib import Path
from types import ModuleType
from typing import Any, ForwardRef

from docutils import nodes
from sphinx.addnodes import pending_xref
from sphinx.application import Sphinx
from sphinx.builders.html import StandaloneHTMLBuilder
from sphinx.environment import BuildEnvironment
from sphinx.ext.intersphinx import missing_reference
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
    builder = app.builder
    # Only HTML builders can render a fragment, and only they fire html-page-context
    if not isinstance(builder, StandaloneHTMLBuilder):
        return ""
    toc = document_toc(app.env, docname, builder.tags)
    top = next(iter(toc.findall(nodes.bullet_list)), None)
    if top is None:
        return ""
    items = [child for child in top.children if isinstance(child, nodes.list_item)]
    # No single title above everything, like the front page
    if len(items) > 1:
        return builder.render_partial(top)["fragment"]
    inner = next((child for child in items[0].children if isinstance(child, nodes.bullet_list)), None) if items else None
    if inner is None:
        return ""
    return builder.render_partial(inner)["fragment"]


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


@cache
def _type_checking_names(module: ModuleType) -> dict[str, Any]:
    """The names a module imports under ``if TYPE_CHECKING:``."""
    ns = {"__name__": module.__name__, "__package__": module.__package__}
    for node in ast.parse(inspect.getsource(module)).body:
        if isinstance(node, ast.If) and isinstance(node.test, ast.Name) and node.test.id == "TYPE_CHECKING":
            exec(compile(ast.Module(node.body, []), module.__file__ or module.__name__, "exec"), ns)
    return ns


def resolve_namedtuple_hints(_app: Sphinx, _what: str, _name: str, obj: object, *_args: object) -> None:
    """
    Resolves string annotations on a NamedTuple's fields before sphinx_autodoc_typehints reads them.

    The generated __new__ lives in a fake "namedtuple_X" module, so sphinx_autodoc_typehints
    can't find the real module's TYPE_CHECKING imports and warns on names like "User".
    """
    if not (inspect.isclass(obj) and issubclass(obj, tuple) and hasattr(obj, "_fields")):
        return
    annotations = getattr(obj.__new__, "__annotations__", {})
    module = sys.modules.get(obj.__module__)
    if module is None or not any(isinstance(v, str | ForwardRef) for v in annotations.values()):
        return

    ns = {**_type_checking_names(module), **vars(module)}
    for key, value in annotations.items():
        if isinstance(value, ForwardRef):
            value = value.__forward_arg__
        if isinstance(value, str):
            annotations[key] = eval(value, ns)


def link_none(
    app: Sphinx,
    env: BuildEnvironment,
    node: pending_xref,
    contnode: nodes.TextElement,
) -> nodes.reference | None:
    """
    Links None in parameter types, which look it up as a class.

    Python's inventory has None as py:data, so the class lookup misses and Sphinx prints it unlinked.
    Signatures already look it up as py:obj, this retries the parameters the same way.
    """
    if node.get("refdomain") != "py" or node.get("reftype") != "class" or node.get("reftarget") != "None":
        return None
    node["reftype"] = "obj"
    return missing_reference(app, env, node, contnode)


def add_context(
    app: Sphinx,
    pagename: str,
    _templatename: str,
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
    # Before sphinx_autodoc_typehints (500) reads the annotations
    app.connect("autodoc-process-signature", resolve_namedtuple_hints, priority=400)
    # Before Sphinx's builtin_resolver (900), which would return None unlinked
    app.connect("missing-reference", link_none, priority=800)

    return {
        "version": "0.1",
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
