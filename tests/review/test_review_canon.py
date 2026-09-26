"""The Continuity Editor with the Story Bible canon: slices, quotes, suppression, status."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from review_helpers import FIXTURES, answer, path_finding

from nanoif.bible.assemble import load_bible
from nanoif.bible.canon import write_canon_pack
from nanoif.bible.source import bible_passages
from nanoif.errors import ArtifactValidationError, BuildError
from nanoif.eval.run import prepare_eval_repo
from nanoif.github.report import RunInfo, render_editor
from nanoif.llm.fake import FakeLLM
from nanoif.review.runner import review
from nanoif.schemas.artifacts import validate_artifact

ENV = {"NANOIF_RUNNER": "local"}
HOLLIN, WIDOW, DAY1 = "Hollin Reach", "The widow's door", "Day 1 EV"
HOLLIN_QUOTE = "Wren's brother was twelve"
WIDOW_QUOTE = "Eleven years old and out after the bell"
RUN = RunInfo(run_id="77", url="https://example.invalid/runs/77")


@pytest.fixture(scope="module")
def built(tmp_path_factory) -> Path:
    root = tmp_path_factory.mktemp("canon") / "story"
    prepare_eval_repo(FIXTURES / "eval-story", root)
    return root


@pytest.fixture
def repo(built, tmp_path) -> Path:
    target = tmp_path / "story"
    shutil.copytree(built, target)
    return target


def fact(fid, claim, quote, passage, kind="trait"):
    return {"id": fid, "claim": claim, "quote": quote, "passage": passage, "kind": kind,
            "duplicate_of": None}


def write_bible(repo: Path, overrides: str = "") -> None:
    """Save a small v2 cache for the eval story and build the canon pack from it."""
    hashes = {p.name: p.content_hash for p in bible_passages(repo)}

    def entity(slug, name, facts, aliases):
        return {"slug": slug, "name": name, "type": "character", "aliases": aliases, "role": None,
                "passages": sorted({f["passage"] for f in facts}), "next_n": len(facts) + 1,
                "reconcile": "done", "merged_into": None, "facts": facts, "retired": []}

    pip = [fact("pip-halloway#1", "Pip is twelve", HOLLIN_QUOTE, HOLLIN),
           fact("pip-halloway#2", "Pip is eleven", WIDOW_QUOTE, WIDOW)]
    tam = [fact("tamsin-reeve#1", "Tam has carried the lantern for forty years",
                "every working day of those forty years", DAY1, "event")]

    def record(name, ids, mentions):
        return {"content_hash": hashes[name], "file": "src/EV-20261101.twee", "summary": "",
                "mentions": mentions, "references": [], "fact_ids": ids,
                "dropped": {"unverified_quote": 0, "state": 0, "generic_entity": 0}}

    cache = {
        "version": 2,
        "extraction": {"commit": "b" * 40, "extracted_at": "2026-11-05T06:00:00Z",
                       "mode": "full", "profile": "fake", "model": "fake-model",
                       "prompt_hashes": {k: "0" * 12 for k in
                                         ("bible_extract", "bible_resolve", "bible_reconcile")},
                       "usd": None, "usd_known": False},
        "passages": {
            DAY1: record(DAY1, ["tamsin-reeve#1"], ["tamsin-reeve"]),
            HOLLIN: record(HOLLIN, ["pip-halloway#1"], ["pip-halloway"]),
            WIDOW: record(WIDOW, ["pip-halloway#2"], ["pip-halloway"]),
        },
        "entities": {"pip-halloway": entity("pip-halloway", "Pip Halloway", pip, ["Pip"]),
                     "tamsin-reeve": entity("tamsin-reeve", "Tamsin Reeve", tam, ["Old Tam", "Tam"])},
        "resolution": {"pip": "pip-halloway", "tam": "tamsin-reeve"},
        "conflicts": {"c-pip-halloway-1": {"id": "c-pip-halloway-1", "entity": "pip-halloway",
                                           "fact_ids": ["pip-halloway#1", "pip-halloway#2"],
                                           "note": "twelve or eleven", "status": "open"}},
    }
    path = repo / "ai" / "story-bible-cache.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(cache), encoding="utf-8")
    (repo / "story-overrides.txt").write_text(overrides, encoding="utf-8")
    write_canon_pack(load_bible(repo, path), repo / "dist" / "canon-pack.json")


def ids(repo: Path) -> dict[str, str]:
    return json.loads((repo / "dist" / "allpaths-passage-mapping.json").read_text())["name_to_id"]


def canon_finding(repo: Path) -> dict:
    raw = path_finding("", [(ids(repo)[HOLLIN], HOLLIN_QUOTE)], description="Pip's age differs.")
    raw["source"] = "canon"
    raw["other"] = {"passage_id": None, "fact_id": "pip-halloway#2"}
    return raw


def run(repo: Path, respond) -> tuple[dict, FakeLLM]:
    fake = FakeLLM(respond)
    artifact = review(repo, "passage", HOLLIN, editors=("continuity",), client=fake, env=ENV,
                      max_workers=1)
    validate_artifact(artifact, "ai_review")
    return artifact, fake


@pytest.mark.intent("ADR-020")
def test_each_unit_gets_its_canon_slice_without_quotes(repo):
    write_bible(repo)
    artifact, fake = run(repo, lambda call: answer())
    (call,) = fake.calls
    assert "<<<BEGIN CANON [B]>>>" in call.user
    assert f"pip-halloway#2  Pip Halloway: Pip is eleven  [{ids(repo)[WIDOW]}]" in call.user
    assert "pip-halloway#1" not in call.user
    assert WIDOW_QUOTE not in call.user.split("<<<BEGIN CANON [B]>>>")[1]


@pytest.mark.intent("AC-continuity-review-36", "ADR-020")
def test_review_records_which_canon_it_used(repo):
    write_bible(repo)
    artifact, _ = run(repo, lambda call: answer())
    assert artifact["canon"] == {
        "status": "used",
        "extracted_at": "2026-11-05T06:00:00Z",
        "commit": "b" * 40,
        "facts_offered": 2,
        "stale_excluded": 0,
        "passages_not_in_bible": [],
    }


@pytest.mark.intent("AC-continuity-review-36", "AC-story-bible-28")
def test_passages_not_in_the_bible_and_stale_facts_are_counted(repo):
    write_bible(repo)
    for name, old, new in (
        ("EV-20261102.twee", "Eleven years old", "Eleven years  old"),
        ("EV-20261102.twee", "Wren's brother was twelve", "Wren's brother was twelve,"),
    ):
        source = repo / "src" / name
        text = source.read_text(encoding="utf-8")
        assert old in text
        source.write_text(text.replace(old, new), encoding="utf-8")
    artifact, fake = run(repo, lambda call: answer())
    assert artifact["canon"]["stale_excluded"] == 1
    assert artifact["canon"]["facts_offered"] == 1
    assert artifact["canon"]["passages_not_in_bible"] == [HOLLIN]
    assert "pip-halloway#2" not in fake.calls[0].user


@pytest.mark.intent("ADR-020")
def test_canon_finding_carries_the_facts_quote_as_its_second_quote(repo):
    write_bible(repo)
    artifact, _ = run(repo, lambda call: answer(canon_finding(repo)))
    (finding,) = artifact["editors"][0]["findings"]
    assert finding["canon_fact_id"] == "pip-halloway#2"
    assert finding["quotes"] == [
        {"passage": HOLLIN, "text": HOLLIN_QUOTE},
        {"passage": WIDOW, "text": WIDOW_QUOTE},
    ]


@pytest.mark.intent("AC-continuity-review-14", "ADR-020")
@pytest.mark.parametrize(
    ("line", "label"),
    [
        ("intentional-conflict: c-pip-halloway-1\n", "c-pip-halloway-1"),
        ("intentional-conflict: pip-age = Pip | Eleven years old\n", "pip-age"),
    ],
)
def test_finding_on_an_intentional_conflict_is_suppressed_with_the_reason(repo, line, label):
    write_bible(repo, line)
    artifact, _ = run(repo, lambda call: answer(canon_finding(repo)))
    editor = artifact["editors"][0]
    assert editor["findings"] == [] and editor["status"] == "ok"
    (suppressed,) = editor["suppressed"]
    assert suppressed["suppressed_reason"] == f"intentional-conflict:{label}"
    body = render_editor(artifact, "continuity", RUN).body
    assert "0 findings, 1 suppressed" in body


@pytest.mark.intent("AC-continuity-review-36")
def test_without_a_saved_extraction_the_review_says_path_only(repo):
    artifact, fake = run(repo, lambda call: answer())
    assert artifact["canon"]["status"] == "no_cache"
    assert "CANON" not in fake.calls[0].user
    body = render_editor(artifact, "continuity", RUN).body
    assert "No saved Story Bible extraction: checked against earlier passages only" in body


@pytest.mark.intent("AC-continuity-review-36")
def test_header_states_the_canon_used(repo):
    write_bible(repo)
    artifact, _ = run(repo, lambda call: answer())
    artifact["canon"]["passages_not_in_bible"] = [HOLLIN]
    artifact["canon"]["stale_excluded"] = 2
    body = render_editor(artifact, "continuity", RUN).body
    assert (
        "Story Bible of 2026-11-05 (bbbbbbbb): 2 established facts offered, 2 out of date left "
        "out; not in the Bible yet: Hollin Reach"
    ) in body
    style = render_editor({**artifact, "editors": [{**artifact["editors"][0], "name": "style"}]},
                          "style", RUN).body
    assert "Story Bible of" not in style


@pytest.mark.intent("AC-continuity-review-36")
@pytest.mark.parametrize("content", [None, "{}", "not json"])
def test_missing_or_invalid_canon_pack_stops_the_review(repo, content):
    pack = repo / "dist" / "canon-pack.json"
    if content is None:
        pack.unlink()
    else:
        pack.write_text(content, encoding="utf-8")
    fake = FakeLLM(lambda call: answer())
    with pytest.raises((BuildError, ArtifactValidationError)):
        review(repo, "passage", HOLLIN, editors=("continuity",), client=fake, env=ENV)
    assert fake.calls == []


def test_style_only_review_needs_no_canon_pack(repo):
    (repo / "dist" / "canon-pack.json").unlink()
    fake = FakeLLM(lambda call: answer())
    artifact = review(repo, "passage", HOLLIN, editors=("style",), client=fake, env=ENV)
    assert "canon" not in artifact
