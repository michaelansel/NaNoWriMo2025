"""The eval story and its truth.json agree with each other.

This runs before any prompt eval means anything: every passage the manifest cites exists,
every quote is verbatim, the counts match the PM manifest, and the twee compiles (all link
targets resolve). The twee reader here is deliberately minimal and local so this test does
not depend on ``nanoif.twee``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import jsonschema
import pytest

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "eval-story"
SRC = FIXTURE / "src"
SCHEMA_PATH = (
    Path(__file__).resolve().parent.parent / "nanoif" / "schemas" / "llm" / "truth.schema.json"
)

HEADER = re.compile(r"^:: *(?P<name>[^\[\{]+?)\s*(\[[^\]]*\])?\s*(\{.*\})?\s*$")
LINK = re.compile(r"\[\[(?P<inner>.+?)\]\]")
PROSE_FILE = re.compile(r"^EV-2026110(?P<day>[1-9])\.twee$")
ENTRY = re.compile(r"^Day (?P<day>\d+) EV$")
IFID = re.compile(r"^[0-9A-F]{8}-[0-9A-F]{4}-4[0-9A-F]{3}-[89AB][0-9A-F]{3}-[0-9A-F]{12}$")
INFRA = {"Start", "StoryData", "StoryTitle"}
NO_BLANK_AFTER_HEADER = {"StoryData", "StoryTitle"}
FORBIDDEN_2025 = ("Javlyn", "Jerrick", "Rosie", "Tavlae", "mansel", "KEB")


def read_passages(path: Path) -> dict[str, str]:
    """Split one twee file into ``{name: body}`` with bodies stripped of outer blank lines."""
    passages: dict[str, str] = {}
    name: str | None = None
    lines: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        match = HEADER.match(line) if line.startswith("::") else None
        if match:
            if name is not None:
                passages[name] = "\n".join(lines).strip("\n")
            name = match.group("name").strip()
            lines = []
        elif name is not None:
            lines.append(line)
    if name is not None:
        passages[name] = "\n".join(lines).strip("\n")
    return passages


def link_targets(body: str) -> list[str]:
    """Return link targets: the rightmost ``->`` segment, else the whole link."""
    targets = []
    for match in LINK.finditer(body):
        inner = match.group("inner")
        targets.append(inner.rsplit("->", 1)[-1].strip() if "->" in inner else inner.strip())
    return targets


@pytest.fixture(scope="module")
def truth() -> dict:
    return json.loads((FIXTURE / "truth.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def files() -> dict[str, dict[str, str]]:
    return {path.name: read_passages(path) for path in sorted(SRC.glob("*.twee"))}


@pytest.fixture(scope="module")
def passages(files) -> dict[str, str]:
    merged: dict[str, str] = {}
    for per_file in files.values():
        merged.update(per_file)
    return merged


@pytest.fixture(scope="module")
def prose(passages) -> dict[str, str]:
    return {name: body for name, body in passages.items() if name not in INFRA}


def by_type(truth, kind):
    return [e for e in truth["entities"] if e["type"] == kind]


def entity_names(truth) -> set[str]:
    return {e["name"] for e in truth["entities"]}


# -- manifest shape --------------------------------------------------------------


def test_truth_validates_against_its_schema(truth):
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.validate(truth, schema)


def test_ids_are_unique(truth):
    for section in (
        "entities",
        "facts",
        "contradictions",
        "pronoun_cases",
        "defects",
        "clean_paths",
    ):
        ids = [item["id"] for item in truth[section]]
        assert len(ids) == len(set(ids)), f"duplicate ids in {section}"
    assert len(entity_names(truth)) == len(truth["entities"])


# -- fixture files ---------------------------------------------------------------


def test_prose_files_follow_the_naming_convention(files, truth):
    prose_files = [
        name for name in files if name not in ("Start.twee", "StoryData.twee", "StoryTitle.twee")
    ]
    assert prose_files, "no prose files"
    entries = []
    for name in prose_files:
        match = PROSE_FILE.match(name)
        assert match, f"{name} is not EV-2026110N.twee"
        first = next(iter(files[name]))
        assert first == f"Day {match.group('day')} EV", f"{name} must start with its Day passage"
        entries.append(first)
    assert entries == truth["story"]["entry_passages"]


def test_storydata_is_valid_and_matches_truth(passages, truth):
    data = json.loads(passages["StoryData"])
    assert IFID.match(data["ifid"]), "IFID must be an uppercase UUID v4"
    assert data["format"] == "Harlowe"
    assert data["format-version"] == "3.3.9"
    assert data["start"] == "Start"
    assert data["start"] in passages
    style = data["storyStyle"]
    assert style["perspective"] == truth["story"]["perspective"]
    assert style["protagonist"] == truth["story"]["protagonist"]
    assert style["tense"] == truth["story"]["tense"]
    assert truth["story"]["protagonist"] in entity_names(truth)
    assert passages["StoryTitle"].strip() == truth["story"]["title"]


def test_passage_count_is_about_fifteen(prose):
    assert 14 <= len(prose) <= 16, sorted(prose)


def test_no_duplicate_passage_names(files):
    seen: dict[str, str] = {}
    for file_name, per_file in files.items():
        for name in per_file:
            assert name not in seen, f"{name} defined in both {seen[name]} and {file_name}"
            seen[name] = file_name


def test_every_link_resolves_and_every_passage_is_reachable(passages):
    inbound: dict[str, int] = {name: 0 for name in passages}
    for name, body in passages.items():
        for target in link_targets(body):
            assert target in passages, f"{name!r} links to missing passage {target!r}"
            inbound[target] += 1
    assert "Day 1 EV" in link_targets(passages["Start"])
    orphans = [n for n, count in inbound.items() if count == 0 and n not in INFRA]
    assert orphans == [], f"unreachable passages: {orphans}"


def test_story_has_two_endings_and_branching(prose):
    endings = [name for name, body in prose.items() if not link_targets(body)]
    assert sorted(endings) == ["Day 4 EV", "The last ferry"]
    forks = [name for name, body in prose.items() if len(link_targets(body)) >= 2]
    assert len(forks) >= 3, forks


def test_twee_formatting_rules(files):
    for file_name, _ in files.items():
        text = (SRC / file_name).read_text(encoding="utf-8")
        assert text.endswith("\n") and not text.endswith("\n\n"), (
            f"{file_name}: one trailing newline"
        )
        lines = text.split("\n")[:-1]
        for i, line in enumerate(lines):
            assert line == line.rstrip(), f"{file_name}:{i + 1} trailing whitespace"
            if line.startswith("::"):
                assert line.startswith(":: "), f"{file_name}:{i + 1} space after ::"
                name = HEADER.match(line).group("name").strip()
                if name not in NO_BLANK_AFTER_HEADER:
                    assert lines[i + 1] == "", f"{file_name}:{i + 1} blank line after header"
                if i > 0:
                    assert lines[i - 1] == "", f"{file_name}:{i + 1} blank line before header"
            if line == "" and i > 0:
                assert lines[i - 1] != "", f"{file_name}:{i + 1} consecutive blank lines"
            if line.startswith("[[") and i > 0 and not lines[i - 1].startswith("[["):
                assert lines[i - 1] == "", f"{file_name}:{i + 1} blank line before link block"
            if line.startswith("[[") and i + 1 < len(lines) and lines[i + 1] != "":
                assert lines[i + 1].startswith("[["), (
                    f"{file_name}:{i + 1} link block must be contiguous"
                )


def test_no_names_from_a_real_writing_year(passages):
    corpus = "\n".join(passages.values()) + (FIXTURE / "truth.json").read_text(encoding="utf-8")
    for token in FORBIDDEN_2025:
        flags = 0 if token.isupper() else re.IGNORECASE
        assert not re.search(rf"\b{token}\b", corpus, flags), f"{token} must not appear"


# -- counts from the PM manifest -------------------------------------------------


def test_entity_counts(truth):
    assert len(by_type(truth, "character")) == 8
    assert len(by_type(truth, "location")) == 4
    assert len(by_type(truth, "item")) == 3
    assert len(by_type(truth, "group")) == 1


def test_reference_kinds_are_all_covered(truth):
    kinds = {k for e in by_type(truth, "character") for k in e["reference_kinds"]}
    assert {
        "dialogue_only",
        "possessive_only",
        "indirect",
        "titled",
        "nickname",
        "pronoun",
    } <= kinds
    protagonist = next(e for e in truth["entities"] if e["name"] == truth["story"]["protagonist"])
    assert "pronoun" in protagonist["reference_kinds"]
    nicknamed = [e for e in by_type(truth, "character") if "nickname" in e["reference_kinds"]]
    assert all(e["aliases"] for e in nicknamed)
    dialogue_only = [
        e for e in by_type(truth, "character") if e["reference_kinds"] == ["dialogue_only"]
    ]
    assert len(dialogue_only) == 1
    possessive_only = [
        e for e in by_type(truth, "character") if e["reference_kinds"] == ["possessive_only"]
    ]
    assert len(possessive_only) == 1


def test_one_location_has_two_names_and_one_item_is_owned(truth):
    assert any(e["aliases"] for e in by_type(truth, "location"))
    owned = [e for e in by_type(truth, "item") if e.get("owner")]
    assert len(owned) == 1
    assert owned[0]["owner"] in entity_names(truth)


def test_fact_contradiction_pronoun_distractor_scene_defect_and_path_counts(truth):
    assert len(truth["facts"]) == 25
    assert len(truth["contradictions"]) == 3
    assert sum(c["intentional"] for c in truth["contradictions"]) == 1
    assert {c["scope"] for c in truth["contradictions"]} == {
        "same_path",
        "cross_branch",
        "within_passage",
    }
    resolvable = [p for p in truth["pronoun_cases"] if p["expected"] is not None]
    ambiguous = [p for p in truth["pronoun_cases"] if p["expected"] is None]
    assert (len(resolvable), len(ambiguous)) == (6, 2)
    assert {d["phrase"] for d in truth["distractors"]} == {"no one", "the man", "thirteen people"}
    assert len(truth["scene_state"]) == 4
    assert sorted(d["type"] for d in truth["defects"]) == sorted(
        ["name_typo", "death_then_alive", "world_rule", "timeline", "pov_slip", "tense_slip"]
    )
    assert len(truth["clean_paths"]) == 2


# -- cross-references between truth and prose ------------------------------------


def cited_passages(truth):
    for e in truth["entities"]:
        yield from e["passages"]
    for f in truth["facts"]:
        yield f["passage"]
    for c in truth["contradictions"]:
        yield from c["passages"]
    for p in truth["pronoun_cases"]:
        yield p["passage"]
    for d in truth["distractors"]:
        yield d["passage"]
    for s in truth["scene_state"]:
        yield s["passage"]
    for d in truth["defects"]:
        yield from d["passages"]
    for path in truth["clean_paths"]:
        yield from path["route"]


def test_every_cited_passage_exists(truth, passages):
    missing = sorted({name for name in cited_passages(truth) if name not in passages})
    assert missing == []


def test_entity_and_fact_cross_references(truth):
    names = entity_names(truth)
    for fact in truth["facts"]:
        assert fact["entity"] in names, fact["id"]
    for case in truth["pronoun_cases"]:
        assert case["expected"] is None or case["expected"] in names, case["id"]
    for state in truth["scene_state"]:
        assert state["entity"] in names


def test_every_evidence_phrase_is_verbatim(truth, passages):
    for fact in truth["facts"]:
        assert fact["evidence_phrase"] in passages[fact["passage"]], fact["id"]


def test_contradiction_and_defect_quotes_are_verbatim(truth, passages):
    for item in truth["contradictions"] + truth["defects"]:
        for quote in item["quotes"]:
            assert any(quote in passages[p] for p in item["passages"]), f"{item['id']}: {quote!r}"


def test_pronoun_distractor_and_scene_sentences_are_verbatim(truth, passages):
    for case in truth["pronoun_cases"]:
        assert case["sentence"] in passages[case["passage"]], case["id"]
        assert re.search(rf"\b{case['pronoun']}\b", case["sentence"]), case["id"]
    for item in truth["distractors"]:
        assert item["sentence"] in passages[item["passage"]], item["phrase"]
        assert item["phrase"].lower() in item["sentence"].lower()
    for state in truth["scene_state"]:
        assert state["statement"] in passages[state["passage"]], state["statement"]


def test_distractor_phrases_are_not_entities(truth):
    names = {n.lower() for e in truth["entities"] for n in [e["name"], *e["aliases"]]}
    for item in truth["distractors"]:
        assert item["phrase"].lower() not in names


def test_entity_passages_mention_the_entity(truth, passages):
    for entity in truth["entities"]:
        forms = [entity["name"], *entity["aliases"]]
        forms += [re.sub(r"^the ", "", f, flags=re.IGNORECASE) for f in forms]
        for name in entity["passages"]:
            haystack = f"{name}\n{passages[name]}"
            assert any(
                re.search(rf"\b{re.escape(form)}", haystack, re.IGNORECASE) for form in forms
            ), f"{entity['name']} not mentioned in {name!r}"


def test_defect_typo_is_a_near_miss_of_a_real_name(truth, passages):
    typo = next(d for d in truth["defects"] if d["type"] == "name_typo")
    assert "Tamsin Reave" in passages[typo["passages"][0]]
    assert "Tamsin Reeve" in passages["Day 1 EV"]


def test_clean_paths_are_valid_routes_free_of_planted_defects(truth, passages):
    for path in truth["clean_paths"]:
        route = path["route"]
        assert route[0] == "Start"
        for here, there in zip(route, route[1:], strict=False):
            assert there in link_targets(passages[here]), f"{path['id']}: {here!r} -> {there!r}"
        assert not link_targets(passages[route[-1]]), f"{path['id']} does not end at an ending"
        # A planted defect or contradiction is visible on a route only when every passage
        # it spans is on that route; the rule-establishing side alone is fine.
        for d in truth["defects"]:
            assert not set(d["passages"]) <= set(route), f"{path['id']} sees {d['id']}"
        for c in truth["contradictions"]:
            if not c["intentional"]:
                assert not set(c["passages"]) <= set(route), f"{path['id']} sees {c['id']}"


def test_same_path_contradiction_shares_a_route(truth, passages):
    same_path = next(c for c in truth["contradictions"] if c["scope"] == "same_path")
    first, second = same_path["passages"]
    seen, frontier = set(), [first]
    while frontier:
        name = frontier.pop()
        if name in seen:
            continue
        seen.add(name)
        frontier.extend(link_targets(passages[name]))
    assert second in seen, f"{second!r} is not downstream of {first!r}"


# -- overrides -----------------------------------------------------------------


def test_overrides_exercise_all_four_directives(truth, passages):
    text = (FIXTURE / "story-overrides.txt").read_text(encoding="utf-8")
    directives: dict[str, list[str]] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, _, payload = line.partition(":")
        assert payload.strip(), f"empty directive {line!r}"
        directives.setdefault(key.strip(), []).append(payload.strip())
    assert set(directives) == {"alias", "not-entity", "pin", "intentional-conflict"}

    names = entity_names(truth)
    canonical, _, aliases = directives["alias"][0].partition("=")
    assert canonical.strip() in names
    assert all(a.strip() for a in aliases.split(","))

    all_forms = {n.lower() for e in truth["entities"] for n in [e["name"], *e["aliases"]]}
    assert directives["not-entity"][0].lower() not in all_forms

    entity, _, rest = directives["pin"][0].partition("=")
    claim, _, quoted = rest.partition("|")
    quote, _, passage = quoted.partition("@")
    assert entity.strip() in names and claim.strip()
    assert passage.strip() in passages
    assert quote.strip().strip('"') in passages[passage.strip()]

    intentional = {c["id"] for c in truth["contradictions"] if c["intentional"]}
    assert directives["intentional-conflict"][0] in intentional
