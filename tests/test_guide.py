"""The writer's guide page: ``WRITERS-GUIDE.md`` rendered to ``writers-guide.html`` (ADR-027)."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import pytest

from nanoif.errors import BuildError
from nanoif.formats.guide import build_guide

REPO = Path(__file__).resolve().parents[1]
FIXTURE = REPO / "tests" / "fixtures" / "guide" / "WRITERS-GUIDE.md"


def render(tmp_path: Path, source: Path = FIXTURE) -> str:
    out = build_guide(source, tmp_path / "dist")
    assert out == tmp_path / "dist" / "writers-guide.html"
    return out.read_text(encoding="utf-8")


def guide(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "WRITERS-GUIDE.md"
    path.write_text(text, encoding="utf-8")
    return path


@pytest.mark.intent("AC-output-formats-21", "ADR-027")
def test_every_block_of_the_guide_appears_on_the_page(tmp_path):
    html = render(tmp_path)
    assert "<title>Guide for the Weir</title>" in html
    assert re.search(r"<h1[^>]*>Guide for the Weir</h1>", html)
    assert "<strong>River Wardens</strong>" in html
    assert '<h2 id="naming-your-file">Naming your file</h2>' in html
    assert '<h2 id="before-you-merge">Before you merge</h2>' in html
    assert "<th>You want to say</th>" in html
    assert "<li>Click the pencil icon to edit\nthe passage where your part begins.</li>" in html


@pytest.mark.intent("AC-output-formats-21", "ADR-027")
def test_escaped_pipe_stays_inside_its_table_cell(tmp_path):
    html = render(tmp_path)
    assert (
        "<td><code>pin: River Wardens = green pennant | &quot;the green pennant&quot; "
        "@ The crossing</code></td>"
    ) in html


@pytest.mark.intent("ADR-027")
def test_raw_markup_and_code_blocks_are_escaped(tmp_path):
    html = render(tmp_path)
    assert "<script>" not in html
    assert "Raw markup stays text: &lt;script&gt;alert(&quot;toll&quot;)&lt;/script&gt;" in html
    assert "&lt;script&gt;alert(&quot;weir&quot;)&lt;/script&gt;\n[[Go to the weir-&gt;The weir]]" in html


@pytest.mark.intent("AC-output-formats-21", "ADR-027")
def test_task_list_checkboxes_are_shown_but_not_clickable(tmp_path):
    html = render(tmp_path)
    boxes = re.findall(r"<input[^>]*type=\"checkbox\"[^>]*>", html)
    assert len(boxes) == 2
    assert all("disabled" in box for box in boxes)
    assert sum("checked" in box for box in boxes) == 1
    assert "<code>Day &lt;N&gt; &lt;INITIALS&gt;</code>" in html


@pytest.mark.intent("AC-output-formats-23", "ADR-027")
def test_heading_and_https_links_are_kept_as_written(tmp_path):
    html = render(tmp_path)
    assert '<a href="#naming-your-file">the naming rules</a>' in html
    assert '<a href="https://example.com/ferry">the ferry site</a>' in html


@pytest.mark.intent("AC-output-formats-23", "ADR-027")
@pytest.mark.parametrize(
    "target",
    ["story-overrides.txt", "src/", "CONTRIBUTING.md", "http://example.com", "mailto:ev@example.com", "#nope"],
)
def test_a_link_that_cannot_work_on_the_site_fails_and_names_the_line(tmp_path, target):
    source = guide(tmp_path, f"# Guide\n\n## Steps\n\nIntro.\n\nSee [this]({target}).\n")
    with pytest.raises(BuildError) as excinfo:
        build_guide(source, tmp_path / "dist")
    message = str(excinfo.value)
    assert "WRITERS-GUIDE.md:7" in message
    assert target in message
    assert not (tmp_path / "dist" / "writers-guide.html").exists()


@pytest.mark.intent("AC-output-formats-23", "ADR-027")
def test_an_image_link_is_checked_too(tmp_path):
    source = guide(tmp_path, "# Guide\n\n![the weir](weir.png)\n")
    with pytest.raises(BuildError, match=r"WRITERS-GUIDE\.md:3.*weir\.png"):
        build_guide(source, tmp_path / "dist")


@pytest.mark.intent("AC-output-formats-21", "ADR-027", "ADR-018")
@pytest.mark.parametrize(
    ("text", "reason"),
    [
        (None, "cannot read"),
        ("", "empty"),
        ("  \n\n", "empty"),
        ("## Only a section\n\nText.\n", "level-1 heading"),
    ],
)
def test_an_unusable_guide_fails_and_writes_nothing(tmp_path, text, reason):
    source = tmp_path / "WRITERS-GUIDE.md"
    if text is not None:
        source.write_text(text, encoding="utf-8")
    with pytest.raises(BuildError, match=reason) as excinfo:
        build_guide(source, tmp_path / "dist")
    assert "WRITERS-GUIDE.md" in str(excinfo.value)
    assert not (tmp_path / "dist" / "writers-guide.html").exists()


@pytest.mark.intent("AC-output-formats-21", "ADR-018")
def test_a_guide_that_is_not_utf8_fails(tmp_path):
    source = tmp_path / "WRITERS-GUIDE.md"
    source.write_bytes(b"# Gu\xefde\n")
    with pytest.raises(BuildError, match="UTF-8"):
        build_guide(source, tmp_path / "dist")


@pytest.mark.intent("AC-output-formats-21", "AC-output-formats-23")
def test_the_repository_guide_builds(tmp_path):
    source = tmp_path / "WRITERS-GUIDE.md"
    shutil.copy(REPO / "WRITERS-GUIDE.md", source)
    html = render(tmp_path, source)
    assert "<title>Writer's Guide</title>" in html or "<title>Writer&#39;s Guide</title>" in html


@pytest.mark.intent("AC-output-formats-24")
def test_page_keeps_wide_content_inside_its_own_box(tmp_path):
    html = render(tmp_path)
    assert '<meta name="viewport" content="width=device-width, initial-scale=1.0">' in html
    style = html[html.index("<style>") : html.index("</style>")]
    assert re.search(r"body\s*\{[^}]*font-size:\s*1(rem|6px)", style)
    assert re.search(r"table\s*\{[^}]*overflow-x:\s*auto", style)
    assert re.search(r"pre\s*\{[^}]*overflow-x:\s*auto", style)


@pytest.mark.intent("AC-output-formats-22", "AC-output-formats-2")
def test_landing_page_has_a_for_writers_section_linking_the_guide():
    html = (REPO / "landing" / "index.html").read_text(encoding="utf-8")
    sections = re.findall(r"<section[^>]*>(.*?)</section>", html, flags=re.S)
    writers = [s for s in sections if re.search(r"<h2>\s*For writers\s*</h2>", s)]
    assert len(writers) == 1
    first_link = re.search(r'<a href="([^"]+)"', writers[0])
    assert first_link and first_link.group(1) == "writers-guide.html"
