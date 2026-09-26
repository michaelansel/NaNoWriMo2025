"""Rendering of the editor, unavailable and build comments, and check-run conclusions.

Golden files live in ``tests/github/golden/``; a diff there is a change writers see.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from github_fakes import make_editor, make_finding, make_review

from nanoif.github.comments import MARKER_BUILD, MARKER_CONTINUITY, MARKER_STYLE
from nanoif.github.report import (
    MAX_LISTED,
    BuildStats,
    RunInfo,
    collect_build_stats,
    editor_conclusion,
    header_line,
    render_build,
    render_editor,
    render_not_run,
    render_pending,
    render_unavailable,
    structure_annotations,
    structure_conclusion,
)
from nanoif.schemas.artifacts import validate_artifact

GOLDEN = Path(__file__).resolve().parent / "golden"
RUN = RunInfo("4242", "https://github.com/owner/story/actions/runs/4242")

UNITS_PARTIAL = [
    {"passage": "Day 1 EV", "status": "reviewed", "reason": None, "tokens": 1500},
    {
        "passage": "The weir",
        "status": "error",
        "reason": "provider timeout after 2 attempts",
        "tokens": None,
    },
    {
        "passage": "The dark crossing",
        "status": "skipped",
        "reason": "too long (24,512 tokens)",
        "tokens": None,
    },
]
STRUCTURE = [
    {
        "level": "error",
        "code": "broken-link",
        "file": "src/EV-20261103.twee",
        "line": 7,
        "passage": "The weir",
        "message": "'The weir' links to 'The mill', which does not exist",
    },
    {
        "level": "warning",
        "code": "orphan",
        "file": "src/EV-20261104.twee",
        "line": 12,
        "passage": "The toll",
        "message": "'The toll' is not reachable from Start",
    },
    {
        "level": "info",
        "code": "story-data-format",
        "file": None,
        "line": None,
        "passage": None,
        "message": "StoryData format-version differs from the pinned Harlowe",
    },
]
STATS = BuildStats(
    (
        ("Playable story", "play.html", 204800),
        ("Proofread", "proofread.html", 51200),
        ("Story map", "graph.html", None),
    ),
    16,
    5,
)


def _cases():
    clean = make_review(make_editor(), make_editor("style"))
    findings = make_review(
        make_editor(
            findings=[
                make_finding(),
                make_finding(
                    key="f-00c0ffee",
                    severity="critical",
                    description="Pip is twelve in one passage and eleven in the other.",
                    passages=(("Hollin Reach", "h3"), ("The widow's door", "h4")),
                    quotes=(
                        ("Hollin Reach", "Wren's brother was twelve"),
                        ("The widow's door", "Eleven years old and out after the bell"),
                    ),
                ),
            ],
            suppressed=[make_finding(key="f-5eed5eed", severity="minor")],
            unverified=[make_finding(key="f-0badf00d", description="A quote that is not there.")],
        ),
        make_editor("style"),
    )
    partial = make_review(
        make_editor(status="error", units=UNITS_PARTIAL, findings=[make_finding()]),
        make_editor("style"),
    )
    skipped = make_review(
        make_editor(),
        make_editor(
            "style", status="skipped", units=[], reason="StoryData has no storyStyle block"
        ),
    )
    rechecked = make_review(
        make_editor(units=[UNITS_PARTIAL[0]]),
        make_editor("style", units=[UNITS_PARTIAL[0]]),
        mode="passage",
    )
    return {
        "continuity_partial_passage": (rechecked, "continuity"),
        "continuity_ok_clean": (clean, "continuity"),
        "continuity_ok_findings": (findings, "continuity"),
        "continuity_partial_error": (partial, "continuity"),
        "style_skipped": (skipped, "style"),
    }


CASES = _cases()


@pytest.mark.intent("AC-continuity-review-3", "AC-continuity-review-5")
@pytest.mark.parametrize("name", sorted(CASES))
def test_editor_comment_matches_golden(name):
    review, editor = CASES[name]
    validate_artifact(review, "ai_review")
    rendered = render_editor(review, editor, RUN)
    assert rendered.body == (GOLDEN / f"{name}.md").read_text(encoding="utf-8")


@pytest.mark.intent("AC-continuity-review-9")
def test_unavailable_matches_golden():
    rendered = render_unavailable("continuity", "exe runner offline", RUN)
    assert rendered.body == (GOLDEN / "continuity_unavailable.md").read_text(encoding="utf-8")
    assert rendered.check.conclusion == "failure"
    assert rendered.check.name == "Continuity Editor"


@pytest.mark.intent("AC-continuity-review-28")
def test_not_run_matches_golden():
    rendered = render_not_run("continuity", "the build failed", "d" * 40, RUN)
    assert rendered.body == (GOLDEN / "continuity_not_run.md").read_text(encoding="utf-8")
    check = rendered.check
    assert (check.name, check.conclusion) == ("Continuity Editor", "failure")
    assert check.title == "Continuity Editor: did not run"
    assert "commit ddddddd: the build failed" in check.summary
    assert MARKER_CONTINUITY not in check.text


@pytest.mark.intent("AC-continuity-review-28")
def test_not_run_shows_no_earlier_result_as_current():
    body = render_not_run("style", "the AI runner check failed", "d" * 40, RUN).body
    assert body.startswith(MARKER_STYLE + "\n### Style Editor: did not run\n")
    assert "finding" not in body.lower()
    assert "No earlier result is shown" in body


@pytest.mark.intent("AC-build-and-deploy-5", "AC-structure-check-21")
def test_build_comment_matches_golden():
    rendered = render_build(STRUCTURE, STATS, RUN, build_ok=True)
    assert rendered.body == (GOLDEN / "build_structure_error.md").read_text(encoding="utf-8")


@pytest.mark.intent("AC-build-and-deploy-7")
def test_build_failed_comment_matches_golden():
    rendered = render_build([], None, RUN, build_ok=False)
    assert rendered.body == (GOLDEN / "build_failed.md").read_text(encoding="utf-8")


@pytest.mark.intent("AC-build-and-deploy-7", "AC-structure-check-18")
@pytest.mark.parametrize(
    "crashed, golden",
    [(False, "build_structure_not_reached.md"), (True, "build_structure_crashed.md")],
)
def test_build_comment_without_a_structure_result_matches_golden(crashed, golden):
    rendered = render_build(None, None, RUN, build_ok=False, structure_crashed=crashed)
    assert rendered.body == (GOLDEN / golden).read_text(encoding="utf-8")
    assert "0 errors" not in rendered.body and "Preview" not in rendered.body
    check = rendered.check
    assert (check.name, check.conclusion) == ("Structure", "failure")
    assert check.title == "Structure check did not run"
    assert check.annotations == ()


@pytest.mark.intent("AC-structure-check-18")
def test_structure_crash_after_a_good_build_still_offers_the_preview():
    rendered = render_build(None, STATS, RUN, build_ok=True, structure_crashed=True)
    assert "**The structure check could not run**, so this commit has no structure result." in (
        rendered.body
    )
    assert "**Preview:**" in rendered.body
    assert rendered.check.conclusion == "failure"


@pytest.mark.intent("AC-continuity-review-7")
@pytest.mark.parametrize(
    "status, findings, conclusion",
    [
        ("ok", [], "success"),
        ("ok", [make_finding()], "neutral"),
        ("error", [], "failure"),
        ("error", [make_finding()], "failure"),
        ("skipped", [], "failure"),
    ],
)
def test_check_run_conclusion_mapping(status, findings, conclusion):
    editor = make_editor(status=status, findings=findings)
    assert editor_conclusion(editor) == conclusion
    review = make_review(editor, make_editor("style"))
    assert render_editor(review, "continuity", RUN).check.conclusion == conclusion


@pytest.mark.intent("AC-continuity-review-7", "AC-continuity-review-30", "ADR-022")
@pytest.mark.parametrize(
    "status, findings, conclusion",
    [("ok", [], "failure"), ("ok", [make_finding()], "failure"), ("error", [], "failure")],
)
def test_single_passage_recheck_is_partial_and_never_success(status, findings, conclusion):
    # ADR-022: a partial result concludes failure whatever the editor status, so it can
    # never replace an earlier failure on the same commit with something greener.
    units = [{"passage": "Day 1 EV", "status": "reviewed", "reason": None, "tokens": 9}]
    if status == "error":
        units = [{"passage": "Day 1 EV", "status": "error", "reason": "HTTP 502", "tokens": None}]
    editor = make_editor(status=status, units=units, findings=findings)
    assert editor_conclusion(editor, mode="passage") == conclusion
    review = make_review(editor, make_editor("style"), mode="passage")
    rendered = render_editor(review, "continuity", RUN)
    assert rendered.check.conclusion == conclusion
    if status == "ok":
        assert rendered.body.splitlines()[1] == (
            "### Continuity Editor: only Day 1 EV was re-checked"
        )
        assert "No findings" not in rendered.body


@pytest.mark.intent("AC-continuity-review-8")
def test_no_findings_appears_only_for_a_clean_ok_editor():
    for name, (review, editor) in CASES.items():
        body = render_editor(review, editor, RUN).body
        clean = name == "continuity_ok_clean"
        assert ("No findings" in body) is clean, name
    assert "No findings" not in render_unavailable("style", "x", RUN).body
    assert "No findings" not in render_pending("style", RUN)
    assert "No findings" not in render_not_run("style", "x", "d" * 40, RUN).body


@pytest.mark.intent("AC-continuity-review-8")
def test_error_editor_first_visible_line_says_unavailable_and_how_to_retry():
    review, _ = CASES["continuity_partial_error"]
    body = render_editor(review, "continuity", RUN).body
    lines = body.splitlines()
    assert lines[0] == MARKER_CONTINUITY
    assert lines[1] == "### Continuity Editor: partially unavailable"
    assert "Retry with `/check-continuity`" in body
    assert "*The weir*: could not check: provider timeout" in body
    assert "*The dark crossing*: could not check (skipped): too long" in body


@pytest.mark.intent("AC-continuity-review-8")
def test_all_units_failed_is_unavailable_not_partial():
    units = [{"passage": "The weir", "status": "error", "reason": "HTTP 502", "tokens": None}]
    review = make_review(make_editor(status="error", units=units), make_editor("style"))
    body = render_editor(review, "continuity", RUN).body
    assert body.splitlines()[1] == "### Continuity Editor: unavailable"


@pytest.mark.intent("AC-continuity-review-6")
def test_header_line_follows_contract_f():
    review, _ = CASES["continuity_ok_findings"]
    editor = review["editors"][0]
    assert header_line(review, editor, RUN) == (
        "Continuity Editor · 2 passages reviewed · 2 findings, 1 suppressed · "
        "12,345 in / 678 out tokens · ≈ $0.0042 · exe (gpt-oss-120b) · "
        "[run #4242](https://github.com/owner/story/actions/runs/4242)"
    )


@pytest.mark.intent("AC-continuity-review-6")
def test_unknown_cost_is_said_not_guessed():
    review = make_review()
    review["llm"]["usd_known"] = False
    assert "cost unknown" in header_line(review, review["editors"][0], RUN)


def test_model_text_is_sanitized_in_the_comment():
    hostile = make_finding(
        description="Ping @wren-writer <img src=x onerror=alert(1)> ![p](https://e.invalid/p.png)",
        quotes=(("Day 1 EV", "[click](javascript:alert(1))"),),
    )
    review = make_review(make_editor(findings=[hostile]), make_editor("style"))
    body = render_editor(review, "continuity", RUN).body
    assert "@wren-writer" not in body and "<img" not in body
    assert "javascript:" not in body and "e.invalid" not in body


def test_long_finding_lists_are_capped_with_a_pointer_to_the_artifact():
    many = [make_finding(key=f"f-{i:08x}", severity="minor") for i in range(MAX_LISTED + 3)]
    review = make_review(make_editor(findings=many), make_editor("style"))
    body = render_editor(review, "continuity", RUN).body
    assert f"#### Minor ({MAX_LISTED + 3})" in body
    assert "…and 3 more in the `ai-review` artifact" in body
    assert body.count("/dismiss f-") == MAX_LISTED


def test_editor_check_payload_text_has_no_marker():
    review, _ = CASES["style_skipped"]
    check = render_editor(review, "style", RUN).check
    assert MARKER_STYLE not in check.text and check.title == "Style Editor: unavailable"


def test_pending_body_has_marker_and_run_link():
    body = render_pending("style", RUN)
    assert body.startswith(MARKER_STYLE + "\n### Style Editor: running")
    assert "run #4242" in body


@pytest.mark.intent("AC-structure-check-20")
def test_structure_conclusion_is_failure_only_on_errors():
    assert structure_conclusion(STRUCTURE) == "failure"
    assert structure_conclusion(STRUCTURE[1:]) == "neutral"
    assert structure_conclusion(STRUCTURE[2:]) == "success"
    assert structure_conclusion([]) == "success"


@pytest.mark.intent("AC-structure-check-20")
def test_structure_annotations_map_levels_and_skip_fileless_findings():
    annotations = structure_annotations(STRUCTURE)
    assert annotations == [
        {
            "path": "src/EV-20261103.twee",
            "start_line": 7,
            "end_line": 7,
            "annotation_level": "failure",
            "title": "broken-link",
            "message": "'The weir' links to 'The mill', which does not exist",
        },
        {
            "path": "src/EV-20261104.twee",
            "start_line": 12,
            "end_line": 12,
            "annotation_level": "warning",
            "title": "orphan",
            "message": "'The toll' is not reachable from Start",
        },
    ]
    check = render_build(STRUCTURE, STATS, RUN, True).check
    assert check.name == "Structure" and len(check.annotations) == 2
    assert render_build([], STATS, RUN, True).body.startswith(MARKER_BUILD)


@pytest.mark.intent("AC-build-and-deploy-5")
def test_collect_build_stats_reads_sizes_and_index(tmp_path):
    (tmp_path / "play.html").write_bytes(b"x" * 2048)
    index = {
        "base_ref": "HEAD",
        "base_sha": "c" * 40,
        "story_title": "The Last Ferry",
        "paths": [],
        "passages": [],
        "broken_links": [],
        "cycles": [],
    }
    (tmp_path / "allpaths-index.json").write_text(__import__("json").dumps(index))
    stats = collect_build_stats(tmp_path)
    assert stats.sizes[0] == ("Playable story", "play.html", 2048)
    assert stats.sizes[1][2] is None
    assert (stats.passage_count, stats.path_count) == (0, 0)


def test_collect_build_stats_without_index_reports_unknown_counts(tmp_path):
    stats = collect_build_stats(tmp_path)
    assert stats.passage_count is None and stats.path_count is None
    assert "? passages" in render_build([], stats, RUN, True).body


def test_run_info_from_env():
    run = RunInfo.from_env(
        {
            "GITHUB_RUN_ID": "7",
            "GITHUB_REPOSITORY": "owner/story",
            "GITHUB_SERVER_URL": "https://github.com",
        }
    )
    assert run.label == "[run #7](https://github.com/owner/story/actions/runs/7)"
    assert RunInfo.from_env({}).label == "local run"


@pytest.mark.intent("AC-continuity-review-31")
def test_cap_reached_names_the_reset_date_instead_of_a_retry():
    reason = "monthly AI spend cap reached: $10.00 of $10.00 in 2026-11 (resets 2026-12-01 UTC)"
    review = make_review(
        make_editor(status="skipped", units=[], reason=reason),
        make_editor("style", status="skipped", units=[], reason=reason),
    )
    review["llm"].update(
        month="2026-11", month_usd=10.0, month_usd_known=True, month_cap_usd=10.0,
        month_cap_reached=True,
    )
    validate_artifact(review, "ai_review")
    rendered = render_editor(review, "continuity", RUN)
    assert rendered.body.splitlines()[1] == "### Continuity Editor: unavailable"
    assert reason in rendered.body
    assert "AI review resumes on 2026-12-01 UTC" in rendered.body
    assert "Retry with" not in rendered.body and "to re-run" not in rendered.body
    assert editor_conclusion(review["editors"][0], review["mode"]) == "failure"
