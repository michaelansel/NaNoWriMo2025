"""The writer's guide page: ``WRITERS-GUIDE.md`` rendered to ``writers-guide.html`` (ADR-027).

This is the only module that turns Markdown into HTML. The parser is CommonMark with raw HTML
off, plus pipe tables, task lists and GitHub-style heading ids. Every link and image target must
be an ``https://`` URL or a ``#fragment`` naming a heading on the page; anything else fails the
build, because a relative link works either on GitHub or on the site, never both.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from nanoif.errors import BuildError
from nanoif.formats.common import html_environment

if TYPE_CHECKING:
    from markdown_it import MarkdownIt
    from markdown_it.token import Token

OUTPUT_NAME = "writers-guide.html"
TEMPLATE_NAME = "writers-guide.html.jinja2"


def _parser() -> MarkdownIt:
    try:
        from markdown_it import MarkdownIt
        from mdit_py_plugins.anchors import anchors_plugin
        from mdit_py_plugins.tasklists import tasklists_plugin
    except ImportError as exc:
        raise BuildError(f"writer's guide: the Markdown renderer is not installed ({exc})") from exc
    return (
        MarkdownIt("commonmark", {"html": False})
        .enable("table")
        .use(tasklists_plugin)
        .use(anchors_plugin, min_level=1, max_level=6)
    )


def _read(source: Path) -> str:
    try:
        text = source.read_bytes().decode("utf-8")
    except OSError as exc:
        raise BuildError(f"{source.name}: cannot read the writer's guide ({exc})") from exc
    except UnicodeDecodeError as exc:
        raise BuildError(f"{source.name}: the writer's guide is not UTF-8 ({exc})") from exc
    if not text.strip():
        raise BuildError(f"{source.name}: the writer's guide is empty")
    return text


def _title(tokens: list[Token], source: Path) -> str:
    for index, token in enumerate(tokens):
        if token.type == "heading_open" and token.tag == "h1":
            inline = tokens[index + 1]
            return "".join(child.content for child in inline.children or [])
    raise BuildError(f"{source.name}: the writer's guide has no level-1 heading for its title")


def _check_links(tokens: list[Token], source: Path) -> None:
    headings = {
        str(token.attrGet("id")) for token in tokens if token.type == "heading_open"
    }
    for token in tokens:
        line = token.map[0] + 1 if token.map else 0
        for child in token.children or []:
            if child.type == "link_open":
                target = str(child.attrGet("href") or "")
            elif child.type == "image":
                target = str(child.attrGet("src") or "")
            else:
                continue
            if target.startswith("https://"):
                continue
            if target.startswith("#") and target[1:] in headings:
                continue
            reason = (
                "matches no heading on the page"
                if target.startswith("#")
                else "is not an https:// address or a #heading on the page"
            )
            raise BuildError(
                f"{source.name}:{line}: link target {target!r} {reason}; "
                "name a repository file in `code` instead of linking it"
            )


def build_guide(source: Path, out_dir: Path) -> Path:
    """Render the writer's guide to ``<out_dir>/writers-guide.html``.

    The page is rendered in full before anything is written, so a failure leaves no partial page.

    Args:
        source: ``WRITERS-GUIDE.md``.
        out_dir: Build output directory.

    Returns:
        The written page.

    Raises:
        BuildError: The guide is missing, unreadable, not UTF-8, empty, has no level-1 heading,
            or has a link target other than ``https://`` or a heading on the page; or the
            Markdown renderer is not installed.
    """
    markdown = _parser()
    text = _read(source)
    env: dict = {}
    tokens = markdown.parse(text, env)
    title = _title(tokens, source)
    _check_links(tokens, source)
    body = markdown.renderer.render(tokens, markdown.options, env)
    page = html_environment().get_template(TEMPLATE_NAME).render(title=title, body=body)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / OUTPUT_NAME
    out.write_text(page, encoding="utf-8")
    return out
