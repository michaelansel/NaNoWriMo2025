"""The review runner: retries, errors, budget, skipped editors, dismissals, artifact shape."""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

import pytest
from review_helpers import FIXTURES, answer, path_finding

from nanoif.errors import ReviewConfigError
from nanoif.eval.run import prepare_eval_repo
from nanoif.llm.errors import LLMBudgetExceeded
from nanoif.llm.fake import FakeLLM
from nanoif.review.findings import finding_key
from nanoif.review.runner import BUDGET_EXHAUSTED, load_dismissals, review
from nanoif.schemas.artifacts import validate_artifact
from nanoif.twee.passages import content_hash

ENV = {"NANOIF_RUNNER": "local"}
TOLL, WEIR = "The toll", "The weir"
TOLL_QUOTE = "Captain Marsh stood in the stern with one boot on the gunwale"
WEIR_QUOTE = "She saw him go over."


@pytest.fixture(scope="session")
def built_eval_repo(tmp_path_factory) -> Path:
    root = tmp_path_factory.mktemp("built") / "story"
    prepare_eval_repo(FIXTURES / "eval-story", root)
    return root


@pytest.fixture
def repo(built_eval_repo, tmp_path) -> Path:
    target = tmp_path / "story"
    shutil.copytree(built_eval_repo, target)
    return target


def ids(repo: Path) -> dict[str, str]:
    mapping = json.loads((repo / "dist" / "allpaths-passage-mapping.json").read_text())
    return mapping["name_to_id"]


def marsh_answer(repo: Path, severity: str = "critical") -> dict:
    pid = ids(repo)
    return answer(
        path_finding(
            pid[WEIR],
            [(pid[TOLL], TOLL_QUOTE), (pid[WEIR], WEIR_QUOTE)],
            finding_type="death_then_alive",
            severity=severity,
        )
    )


def run(repo: Path, fake, **kwargs) -> dict:
    kwargs.setdefault("env", ENV)
    kwargs.setdefault("max_workers", 1)
    return review(repo, kwargs.pop("mode", "passage"), client=fake, **kwargs)


def test_output_validates_and_records_shas_usage_and_runner(repo):
    fake = FakeLLM({f"continuity:{TOLL}": marsh_answer(repo), f"style:{TOLL}": answer()})
    artifact = run(repo, fake, passage=TOLL, now=datetime(2026, 11, 3, 12, tzinfo=UTC))
    validate_artifact(artifact, "ai_review")
    assert artifact["generated_at"] == "2026-11-03T12:00:00Z"
    assert len(artifact["commit_sha"]) == 40
    changes = json.loads((repo / "dist" / "changes.json").read_text())
    assert artifact["base_sha"] == changes["base_sha"]
    assert artifact["llm"]["runner"] == "local"
    assert artifact["llm"]["calls"] == 2
    continuity, style = artifact["editors"]
    assert (continuity["status"], style["status"]) == ("ok", "ok")
    assert continuity["units"] == [
        {"passage": TOLL, "status": "reviewed", "reason": None, "tokens": continuity["units"][0]["tokens"]}
    ]
    finding = continuity["findings"][0]
    assert finding["key"] == finding_key("death_then_alive", TOLL, WEIR)
    assert finding["severity"] == "critical"
    assert finding["passages"][0]["file"] == "src/EV-20261104.twee"
    assert finding["routes_seen"] == 1


def test_transport_error_then_success_is_reviewed(repo):
    fake = FakeLLM({f"continuity:{TOLL}": [FakeLLM.transport_error(), marsh_answer(repo)]})
    artifact = run(repo, fake, passage=TOLL, editors=("continuity",))
    editor = artifact["editors"][0]
    assert editor["status"] == "ok"
    assert editor["units"][0]["status"] == "reviewed"
    assert len(editor["findings"]) == 1
    assert len(fake.calls) == 2


def test_error_twice_marks_the_unit_and_the_editor_error(repo):
    fake = FakeLLM(
        {f"continuity:{TOLL}": [FakeLLM.transport_error("down"), FakeLLM.truncated()]}
    )
    artifact = run(repo, fake, passage=TOLL, editors=("continuity",))
    editor = artifact["editors"][0]
    assert editor["status"] == "error"
    assert editor["findings"] == []
    unit = editor["units"][0]
    assert unit["status"] == "error"
    assert unit["reason"].startswith("LLMTruncatedError")
    assert "1 of 1 unit(s) not reviewed" in editor["reason"]


def test_budget_exhausted_mid_run_skips_the_remaining_units(repo):
    calls = []

    def script(call):
        calls.append(call.tag)
        if len(calls) == 3:
            raise LLMBudgetExceeded("over", spent=10, budget=10, projected=20)
        return answer()

    artifact = run(repo, FakeLLM(script), mode="all", editors=("continuity", "style"))
    continuity, style = artifact["editors"]
    statuses = [unit["status"] for unit in continuity["units"] + style["units"]]
    assert statuses[:2] == ["reviewed", "reviewed"]
    assert set(statuses[2:]) == {"skipped"}
    assert all(u["reason"] == BUDGET_EXHAUSTED for u in (continuity["units"] + style["units"])[2:])
    assert continuity["status"] == "error" and style["status"] == "error"
    assert len(calls) == 3


def test_unit_over_budget_after_truncation_is_skipped_too_long(repo):
    env = {**ENV, "NANOIF_REVIEW_UNIT_BUDGET": "5"}
    fake = FakeLLM({})
    artifact = run(repo, fake, passage=TOLL, editors=("continuity",), env=env)
    editor = artifact["editors"][0]
    assert editor["status"] == "error"
    assert editor["units"], "every covering route is listed"
    assert {u["status"] for u in editor["units"]} == {"skipped"}
    assert all(u["reason"].startswith("too long (") for u in editor["units"])
    assert fake.calls == []


def test_style_is_skipped_without_story_style(repo):
    (repo / "src" / "StoryData.twee").write_text(
        ':: StoryData\n{"ifid": "7C1E4B2A-9D3F-4A6B-8E5C-2F7A9B1D3C4E", "start": "Start"}\n',
        encoding="utf-8",
    )
    fake = FakeLLM({f"continuity:{TOLL}": answer()})
    artifact = run(repo, fake, passage=TOLL)
    style = artifact["editors"][1]
    assert style["status"] == "skipped"
    assert "storyStyle" in style["reason"]
    assert style["units"] == [] and style["findings"] == []
    assert [c.tag for c in fake.calls] == [f"continuity:{TOLL}"]


def write_dismissal(repo: Path, toll_hash: str, weir_hash: str) -> Path:
    path = repo / "ai" / "dismissals.jsonl"
    path.parent.mkdir(exist_ok=True)
    record = {
        "key": finding_key("death_then_alive", TOLL, WEIR),
        "type": "death_then_alive",
        "passages": [TOLL, WEIR],
        "hashes": [toll_hash, weir_hash],
        "by": "writer",
        "reason": "Marsh's ghost, on purpose",
    }
    path.write_text(json.dumps(record) + "\n", encoding="utf-8")
    return path


def passage_hash(repo: Path, name: str) -> str:
    graph = json.loads((repo / "lib" / "artifacts" / "story_graph.json").read_text())
    return content_hash(graph["passages"][name]["content"])


def test_dismissal_suppresses_only_when_both_hashes_match(repo):
    toll, weir = passage_hash(repo, TOLL), passage_hash(repo, WEIR)
    write_dismissal(repo, toll, weir)
    fake = FakeLLM({f"continuity:{TOLL}": marsh_answer(repo)})
    editor = run(repo, fake, passage=TOLL, editors=("continuity",))["editors"][0]
    assert editor["findings"] == []
    assert [f["key"] for f in editor["suppressed"]] == [finding_key("death_then_alive", TOLL, WEIR)]
    assert editor["status"] == "ok"

    write_dismissal(repo, toll, "0" * 16)
    fake = FakeLLM({f"continuity:{TOLL}": marsh_answer(repo)})
    editor = run(repo, fake, passage=TOLL, editors=("continuity",))["editors"][0]
    assert len(editor["findings"]) == 1 and editor["suppressed"] == []


def test_corrupt_dismissals_file_is_an_error(tmp_path):
    path = tmp_path / "dismissals.jsonl"
    path.write_text('{"key": "f-12345678", "hashes": {"A": "x"}}\nnot json\n', encoding="utf-8")
    with pytest.raises(ReviewConfigError, match=":2:"):
        load_dismissals(path)
    path.write_text('{"key": "f-12345678"}\n', encoding="utf-8")
    with pytest.raises(ReviewConfigError, match="hashes"):
        load_dismissals(path)
    assert load_dismissals(tmp_path / "absent.jsonl") == {}


def test_same_key_from_every_route_unit_is_one_finding(repo):
    env = {**ENV, "NANOIF_REVIEW_UNIT_BUDGET": "1800"}

    def script(call):
        return marsh_answer(repo) if call.tag.startswith(f"continuity:{TOLL}#") else answer()

    artifact = run(repo, FakeLLM(script), passage=TOLL, editors=("continuity",), env=env)
    editor = artifact["editors"][0]
    assert len(editor["units"]) >= 2, "budget should force a route split"
    assert all(u["status"] == "reviewed" for u in editor["units"])
    assert len(editor["findings"]) == 1
    assert editor["findings"][0]["routes_seen"] == len(editor["units"])


def test_mode_changed_reviews_every_changed_passage(repo):
    fake = FakeLLM(lambda call: answer())
    artifact = run(repo, fake, mode="changed", editors=("style",))
    changed = json.loads((repo / "dist" / "changes.json").read_text())["changed"]
    assert [u["passage"] for u in artifact["editors"][0]["units"]] == sorted(changed)
    assert artifact["mode"] == "changed"


def test_config_errors(repo):
    fake = FakeLLM({})
    with pytest.raises(ReviewConfigError):
        run(repo, fake, passage=TOLL, editors=("grammar",))
    with pytest.raises(ReviewConfigError):
        run(repo, fake, passage=TOLL, env={"NANOIF_RUNNER": "laptop"})
    with pytest.raises(ReviewConfigError):
        run(repo, fake, passage="StoryData")
