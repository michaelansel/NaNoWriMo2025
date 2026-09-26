"""``nanoif ai review`` and ``nanoif ai eval`` exit codes and output."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from review_helpers import FIXTURES, answer, path_finding

from nanoif.cli import main
from nanoif.eval.run import prepare_eval_repo
from nanoif.graph.ids import passage_id_mapping
from nanoif.llm.fake import FakeLLM
from nanoif.schemas.artifacts import load_artifact
from nanoif.twee.parse import parse_twee_dir

TOLL = "The toll"


@pytest.fixture(scope="module")
def built(tmp_path_factory) -> Path:
    root = tmp_path_factory.mktemp("cli") / "story"
    prepare_eval_repo(FIXTURES / "eval-story", root)
    return root


@pytest.fixture
def repo(built, tmp_path) -> Path:
    target = tmp_path / "story"
    shutil.copytree(built, target)
    return target


@pytest.fixture
def no_llm_env(monkeypatch):
    monkeypatch.setenv("NANOIF_LLM_PROFILE", "custom")
    for key in ("BASE_URL", "API_KEY", "MODEL"):
        monkeypatch.delenv(f"NANOIF_LLM_{key}", raising=False)
    monkeypatch.delenv("NANOIF_RUNNER", raising=False)
    monkeypatch.delenv("NANOIF_REVIEW_UNIT_BUDGET", raising=False)


def review_args(repo: Path, *extra: str) -> list[str]:
    return ["ai", "review", "--repo", str(repo), "--passage", TOLL, *extra]


def test_exit_0_when_every_editor_is_ok(repo, capsys, no_llm_env):
    fake = FakeLLM(lambda call: answer())
    assert main(review_args(repo), client=fake) == 0
    out = capsys.readouterr().out
    assert "continuity: ok, 1 of 1 units reviewed, 0 finding(s)" in out
    assert "style: ok, 1 of 1 units reviewed" in out
    artifact = load_artifact(repo / "dist" / "ai-review.json", "ai_review")
    assert artifact["mode"] == "passage"


@pytest.mark.intent("AC-continuity-review-8")
def test_exit_1_when_an_editor_errors(repo, capsys, no_llm_env):
    fake = FakeLLM(lambda call: FakeLLM.transport_error("gateway down"))
    out_path = repo / "out" / "review.json"
    assert main(review_args(repo, "--editors", "continuity", "--out", str(out_path)), client=fake) == 1
    assert "continuity: error, 0 of 1 units reviewed" in capsys.readouterr().out
    artifact = load_artifact(out_path, "ai_review")
    assert artifact["editors"][0]["units"][0]["status"] == "error"


def test_exit_1_when_an_editor_is_skipped(repo, capsys, no_llm_env):
    (repo / "src" / "StoryData.twee").write_text(
        ':: StoryData\n{"ifid": "7C1E4B2A-9D3F-4A6B-8E5C-2F7A9B1D3C4E"}\n', encoding="utf-8"
    )
    fake = FakeLLM(lambda call: answer())
    assert main(review_args(repo), client=fake) == 1
    assert "style: skipped (StoryData has no storyStyle" in capsys.readouterr().out


def test_exit_2_on_usage_and_config_errors(repo, capsys, no_llm_env):
    fake = FakeLLM(lambda call: answer())
    assert main(["ai", "review", "--repo", str(repo), "--passage", "Nowhere"], client=fake) == 2
    assert "ai review could not run" in capsys.readouterr().err
    assert main(review_args(repo, "--mode", "all"), client=fake) == 2
    assert main(review_args(repo, "--editors", "grammar"), client=fake) == 2
    assert main(review_args(repo)) == 2
    assert "NANOIF_LLM_BASE_URL" in capsys.readouterr().err
    with pytest.raises(SystemExit) as exc:
        main(["ai", "review", "--repo", str(repo), "--mode", "sometimes"])
    assert exc.value.code == 2
    assert not (repo / "dist" / "ai-review.json").exists()


def test_exit_2_when_the_story_is_not_built(tmp_path, capsys, no_llm_env):
    fake = FakeLLM(lambda call: answer())
    assert main(["ai", "review", "--repo", str(tmp_path), "--mode", "all"], client=fake) == 2
    assert "story_graph not found" in capsys.readouterr().err


# -- eval ----------------------------------------------------------------------------


def planted_defects_llm() -> FakeLLM:
    """A fake that reports three planted defects with verbatim quotes and nothing else."""
    graph = parse_twee_dir(FIXTURES / "eval-story" / "src")
    pid = passage_id_mapping(graph["passages"])
    marsh = path_finding(
        pid["The weir"],
        [
            (pid[TOLL], "Captain Marsh stood in the stern with one boot on the gunwale, the way he always stood, dry, with his hat on."),
            (pid["The weir"], "She saw him go over."),
        ],
        finding_type="death_then_alive",
        severity="critical",
    )

    def slip(finding_type: str, quote: str) -> dict:
        return {
            "type": finding_type,
            "description": "Leaves the house style.",
            "severity": "minor",
            "confidence": "high",
            "quotes": [{"text": quote}],
        }

    script = {
        "bible-resolve": {"merges": [], "drop": []},
        f"continuity:{TOLL}": answer(marsh),
        "style:Gull Chapel at dusk": answer(
            slip("pov_slip", "I could hear the bell still humming in the beams above us")
        ),
        "style:The last ferry": answer(
            slip("tense_slip", "Wren steps aboard and takes the pole from Tam's hands")
        ),
    }
    empty_bible = {"summary": "", "entities": [], "references": []}

    def respond(call):
        if call.tag.startswith("bible-extract:"):
            return empty_bible
        return script.get(call.tag, answer())

    return FakeLLM(respond)


def test_eval_scores_planted_defects(tmp_path, capsys, no_llm_env):
    out = tmp_path / "results" / "eval-results.json"
    status = main(
        ["ai", "eval", "--repo", str(FIXTURES.parents[1]), "--out", str(out)],
        client=planted_defects_llm(),
    )
    assert status == 0
    scores = json.loads(out.read_text())
    assert scores["metrics"]["defects_detected"] == 3
    assert scores["metrics"]["defect_severity_matches"] == 3
    assert scores["metrics"]["clean_path_false_positives"] == 0
    assert scores["extraction"]["status"] == "ok"
    assert scores["entities"]["reported"] == 0 and scores["entities"]["recall"] == 0.0
    assert "skipped_metrics" not in scores
    assert [e["status"] for e in scores["review"]["editors"]] == ["ok", "ok"]
    rows = {row["id"]: row["detected"] for row in scores["defects"]["per_defect"]}
    assert rows["d-marsh-alive"] and rows["d-pov"] and rows["d-tense"]
    assert not rows["d-lantern-rule"]
    markdown = (tmp_path / "results" / "eval-results.md").read_text()
    assert "d-marsh-alive found" in markdown
    assert "Extraction: ok." in markdown
    assert "Defects detected | 3" in capsys.readouterr().out
    load_artifact(tmp_path / "results" / "eval-ai-review.json", "ai_review")


def test_eval_diffs_against_a_baseline(tmp_path, capsys, no_llm_env):
    baseline = tmp_path / "baseline.json"
    baseline.write_text(
        json.dumps({"profile": "exe", "metrics": {"defects_detected": 4, "entity_recall": 1.0}})
    )
    out = tmp_path / "eval-results.json"
    status = main(
        ["ai", "eval", "--repo", str(FIXTURES.parents[1]), "--out", str(out), "--baseline", str(baseline)],
        client=planted_defects_llm(),
    )
    assert status == 1
    assert "Baseline: regressions in defects_detected" in out.with_suffix(".md").read_text()
    assert "eval below baseline" in capsys.readouterr().err


def test_eval_without_llm_config_exits_2_with_the_reason(tmp_path, capsys, no_llm_env):
    status = main(["ai", "eval", "--repo", str(FIXTURES.parents[1]), "--out", str(tmp_path / "e.json")])
    assert status == 2
    err = capsys.readouterr().err
    assert err.startswith("eval could not run: ")
    assert "NANOIF_LLM_BASE_URL" in err
    assert not (tmp_path / "e.json").exists()


def test_eval_with_a_failing_model_reports_incomplete(tmp_path, capsys, no_llm_env):
    fake = FakeLLM(lambda call: FakeLLM.transport_error("gateway down"))
    status = main(
        ["ai", "eval", "--repo", str(FIXTURES.parents[1]), "--out", str(tmp_path / "e.json")],
        client=fake,
    )
    assert status == 1
    assert "eval incomplete" in capsys.readouterr().err
    scores = json.loads((tmp_path / "e.json").read_text())
    assert scores["review"]["editors"][0]["status"] == "error"
