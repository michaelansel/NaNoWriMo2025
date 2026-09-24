"""Model- and story-derived text cannot inject HTML, links, images, mentions or markers."""

from __future__ import annotations

import pytest

from nanoif.github.sanitize import ZWJ, sanitize


def test_script_tags_are_escaped():
    out = sanitize('Wren said <script>alert("x")</script>')
    assert "<script" not in out and "&lt;script&gt;" in out


def test_mentions_are_neutralized_but_emails_are_left():
    out = sanitize("Ask @wren-writer and @octo/team; mail tamsin@ferry.invalid")
    assert "@wren-writer" not in out and f"@{ZWJ}wren-writer" in out
    assert f"@{ZWJ}octo/team" in out
    assert "tamsin@ferry.invalid" in out


def test_javascript_link_keeps_text_and_loses_target():
    out = sanitize("[click me](javascript:alert(1))")
    assert out == "click me"


def test_images_are_dropped_to_alt_text():
    assert sanitize("before ![the weir](https://evil.invalid/x.png) after") == (
        "before the weir after"
    )


def test_bare_urls_are_put_in_code_spans_so_they_do_not_link():
    out = sanitize("see https://evil.invalid/path?q=1 now")
    assert out == "see `https://evil.invalid/path?q=1` now"


def test_reference_definitions_and_stray_brackets_cannot_form_links():
    out = sanitize("[x][ref]\n[ref]: https://evil.invalid", inline=False)
    assert "evil.invalid" not in out
    assert "\\[x\\]" in out


def test_blocked_schemes_are_rewritten_even_outside_links():
    out = sanitize("data:text/html,hi and FILE:///etc/passwd")
    assert "blocked-data:" in out and "blocked-file:" in out


def test_forged_sticky_marker_is_escaped():
    assert "<!--" not in sanitize("<!-- nano:continuity --> fake")


def test_backticks_cannot_close_code_spans():
    assert "`" not in sanitize("use `rm -rf` here")


def test_inline_collapses_newlines_so_headings_cannot_start():
    assert sanitize("fine\n\n## Heading\n- item") == "fine ## Heading - item"


@pytest.mark.parametrize("text, cap", [("x" * 50, 10), ("word " * 100, 40)])
def test_length_is_capped_with_an_ellipsis(text, cap):
    out = sanitize(text, max_chars=cap)
    assert len(out) <= cap and out.endswith("…")


def test_none_and_empty_become_empty_string():
    assert sanitize(None) == "" and sanitize("") == ""


def test_ampersand_is_escaped_first_so_entities_do_not_double_decode():
    assert sanitize("&lt;b&gt;") == "&amp;lt;b&amp;gt;"
