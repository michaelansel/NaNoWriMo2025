"""Merging a ``/check-continuity passage=<name>`` result into the PR's last full review.

A single-passage re-check must never make the editors' checks green while other changed
passages still have findings (AC-continuity-review-7).
"""

from __future__ import annotations

import json

import pytest
from github_fakes import HEAD_SHA, make_editor, make_finding, make_review

from nanoif.cli import main
from nanoif.github.merge import HEAD_SHA_FILE, merge_passage_review
from nanoif.github.report import RunInfo, render_editor
from nanoif.schemas.artifacts import validate_artifact

RUN = RunInfo("4242", "https://github.com/owner/story/actions/runs/4242")
X = "Back at the ferry"


def _unit(passage, status="reviewed", reason=None):
    return {"passage": passage, "status": status, "reason": reason, "tokens": 900}


WEIR_FINDING = make_finding(
    key="f-00c0ffee",
    description="The weir is upstream in one passage and downstream in the other.",
    passages=(("The weir", "h3"), ("Hollin Reach", "h4")),
    quotes=(("The weir", "upstream of the mill"), ("Hollin Reach", "downstream of the mill")),
)
FERRY_FINDING = make_finding(
    key="f-1a2b3c4d", passages=(("Day 1 EV", "h1"), (X, "h2"))
)


def _previous(**overrides):
    continuity = make_editor(
        units=[_unit("The weir"), _unit(X)],
        findings=[WEIR_FINDING, FERRY_FINDING],
    )
    style = make_editor("style", units=[_unit("The weir"), _unit(X)])
    review = make_review(continuity, style)
    review.update(overrides)
    return review


def _update(continuity=None, style=None):
    return make_review(
        continuity or make_editor(units=[_unit(X)]),
        style or make_editor("style", units=[_unit(X)]),
        mode="passage",
    )


@pytest.mark.intent("AC-continuity-review-7")
def test_clean_recheck_keeps_other_passages_findings_and_the_check_stays_neutral():
    merged = merge_passage_review(_previous(), _update(), X)
    validate_artifact(merged, "ai_review")
    continuity = merged["editors"][0]
    assert merged["mode"] == "changed"
    assert [u["passage"] for u in continuity["units"]] == ["The weir", X]
    assert [f["key"] for f in continuity["findings"]] == ["f-00c0ffee"]
    assert render_editor(merged, "continuity", RUN).check.conclusion == "neutral"
    assert render_editor(merged, "style", RUN).check.conclusion == "success"


def test_merge_takes_this_runs_usage_and_commit():
    update = _update()
    update["llm"]["prompt_tokens"] = 7
    update["generated_at"] = "2026-11-03T08:00:00Z"
    merged = merge_passage_review(_previous(), update, X)
    assert merged["llm"]["prompt_tokens"] == 7
    assert merged["generated_at"] == "2026-11-03T08:00:00Z"


@pytest.mark.intent("AC-continuity-review-7")
def test_finding_that_another_unit_may_have_reported_is_kept():
    shared = make_finding(key="f-5eed5eed", passages=(("The weir", "h3"), (X, "h2")))
    previous = _previous()
    previous["editors"][0]["findings"].append(shared)
    merged = merge_passage_review(previous, _update(), X)
    assert "f-5eed5eed" in [f["key"] for f in merged["editors"][0]["findings"]]


def test_recheck_findings_replace_the_same_key_and_clear_it_from_unverified():
    fresh = make_finding(key="f-1a2b3c4d", severity="critical", passages=(("Day 1 EV", "h1"), (X, "h2")))
    previous = _previous()
    previous["editors"][0]["unverified"] = [make_finding(key="f-1a2b3c4d")]
    update = _update(continuity=make_editor(units=[_unit(X)], findings=[fresh]))
    continuity = merge_passage_review(previous, update, X)["editors"][0]
    keys = [(f["key"], f["severity"]) for f in continuity["findings"]]
    assert keys == [("f-00c0ffee", "major"), ("f-1a2b3c4d", "critical")]
    assert continuity["unverified"] == []


@pytest.mark.intent("AC-continuity-review-7", "AC-continuity-review-8")
def test_recheck_that_failed_makes_the_merged_editor_an_error():
    failed = make_editor(
        status="error",
        units=[_unit(X, "error", "LLMTransportError: HTTP 502 (after one re-attempt)")],
        reason="1 of 1 unit(s) not reviewed (1 error)",
    )
    merged = merge_passage_review(_previous(), _update(continuity=failed), X)
    continuity = merged["editors"][0]
    assert continuity["status"] == "error"
    assert continuity["reason"] == "1 of 2 unit(s) not reviewed (1 error)"
    assert render_editor(merged, "continuity", RUN).check.conclusion == "failure"


def test_error_on_another_passage_is_kept_after_a_clean_recheck():
    previous = _previous()
    previous["editors"][0]["units"][0] = _unit("The weir", "error", "HTTP 502")
    previous["editors"][0]["status"] = "error"
    continuity = merge_passage_review(previous, _update(), X)["editors"][0]
    assert continuity["status"] == "error"


def test_merging_into_a_partial_review_stays_partial():
    previous = _update()
    weir = _update(
        continuity=make_editor(units=[_unit("The weir")]),
        style=make_editor("style", units=[_unit("The weir")]),
    )
    merged = merge_passage_review(previous, weir, "The weir")
    assert merged["mode"] == "passage"
    assert [u["passage"] for u in merged["editors"][0]["units"]] == [X, "The weir"]


def test_a_skipped_editor_takes_this_runs_result():
    skipped = make_editor("style", status="skipped", units=[], reason="StoryData has no storyStyle")
    merged = merge_passage_review(_previous(), _update(style=skipped), X)
    assert merged["editors"][1] == skipped


def test_merge_does_not_modify_its_inputs():
    previous, update = _previous(), _update()
    before = json.dumps(previous), json.dumps(update)
    merge_passage_review(previous, update, X)
    assert (json.dumps(previous), json.dumps(update)) == before


# -- the CLI ---------------------------------------------------------------------------


def _write(path, review):
    path.write_text(json.dumps(review))
    return path


def _previous_dir(tmp_path, review, sha=HEAD_SHA):
    folder = tmp_path / "previous"
    folder.mkdir()
    _write(folder / "ai-review.json", review)
    if sha is not None:
        (folder / HEAD_SHA_FILE).write_text(sha + "\n")
    return folder


def _merge_args(update, out, *extra):
    return [
        "github",
        "merge-review",
        "--review",
        str(update),
        "--passage",
        X,
        "--out",
        str(out),
        *extra,
    ]


@pytest.mark.intent("AC-continuity-review-7")
def test_merge_review_cli_merges_a_review_of_the_same_commit(tmp_path, capsys):
    update = _write(tmp_path / "ai-review.json", _update())
    folder = _previous_dir(tmp_path, _previous())
    args = _merge_args(update, update, "--previous-dir", str(folder), "--head-sha", HEAD_SHA)
    assert main(args) == 0
    merged = json.loads(update.read_text())
    assert merged["mode"] == "changed" and len(merged["editors"][0]["findings"]) == 1
    assert "merged" in capsys.readouterr().out


@pytest.mark.intent("AC-continuity-review-7")
@pytest.mark.parametrize(
    "setup, message",
    [
        ("none", "no earlier AI review"),
        ("other-commit", "is for commit ddddddd"),
        ("no-sha", "does not say which commit"),
    ],
)
def test_merge_review_cli_publishes_partial_without_a_matching_review(
    tmp_path, capsys, setup, message
):
    update = _write(tmp_path / "ai-review.json", _update())
    out = tmp_path / "out.json"
    extra = ["--head-sha", HEAD_SHA]
    if setup == "other-commit":
        extra += ["--previous-dir", str(_previous_dir(tmp_path, _previous(), "d" * 40))]
    elif setup == "no-sha":
        extra += ["--previous-dir", str(_previous_dir(tmp_path, _previous(), None))]
    assert main(_merge_args(update, out, *extra)) == 0
    assert json.loads(out.read_text()) == _update()
    assert message in capsys.readouterr().out


def test_merge_review_cli_with_an_unreadable_earlier_review_publishes_partial(tmp_path, capsys):
    update = _write(tmp_path / "ai-review.json", _update())
    folder = _previous_dir(tmp_path, {"version": 1})
    out = tmp_path / "out.json"
    extra = ["--previous-dir", str(folder), "--head-sha", HEAD_SHA]
    assert main(_merge_args(update, out, *extra)) == 0
    assert json.loads(out.read_text())["mode"] == "passage"
    assert "cannot read the earlier AI review" in capsys.readouterr().err


def test_merge_review_cli_refuses_a_review_that_is_not_a_passage_recheck(tmp_path, capsys):
    update = _write(tmp_path / "ai-review.json", _previous())
    assert main(_merge_args(update, tmp_path / "out.json")) == 2
    assert "mode 'passage'" in capsys.readouterr().err
