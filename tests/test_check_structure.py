"""Tests for ``nanoif check structure`` and the overrides parser."""

import json

import pytest

from nanoif.check.overrides import Override, OverrideError, parse_overrides
from nanoif.check.structure import Finding, check_structure, format_findings
from nanoif.cli import main
from nanoif.schemas.artifacts import validate_artifact

STORY_DATA = {
    "ifid": "0683974A-9DD8-4A14-BC84-C9519DDDA688",
    "format": "Harlowe",
    "format-version": "3.3.9",
    "start": "Start",
    "storyStyle": {"perspective": "third-person", "protagonist": "Rowan", "tense": "past"},
}


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def make_story(root, story_data=None):
    """A valid two-writer story under root/src."""
    src = root / "src"
    defaults = {
        "StoryData.twee": ":: StoryData\n" + json.dumps(story_data or STORY_DATA, indent=2) + "\n",
        "StoryTitle.twee": ":: StoryTitle\nTest Story\n",
        "Start.twee": ":: Start\n\nBegin. [[Day 1 AB]] or [[Day 1 CD]]\n",
        "StoryStyles.twee": ":: StoryStylesheet [stylesheet]\nbody {}\n\n:: Footer [footer]\nfooter text\n",
        "PathIdDisplay.twee": ":: PathIdDisplay [footer]\n<span></span>\n",
        "AB-20261101.twee": ":: Day 1 AB\n\nMorning.\n\n[[Stay]]\n\n:: Stay [ending]\n\nThe end.\n",
        "CD-20261101.twee": ":: Day 1 CD\n\nEvening.\n",
    }
    for name, text in defaults.items():
        write(src / name, text)
    return src


def codes(findings, level=None):
    return [f.code for f in findings if level is None or f.level == level]


def test_valid_story_has_only_the_expected_dead_end(tmp_path):
    findings = check_structure(make_story(tmp_path))
    assert findings == [
        Finding("info", "dead-end", "src/CD-20261101.twee", 1, "Day 1 CD",
                "'Day 1 CD' has no links; tag it [ending] if it is meant to end the story"),
    ]


def test_broken_link_is_an_error_with_file_and_line(tmp_path):
    src = make_story(tmp_path)
    write(src / "CD-20261101.twee", ":: Day 1 CD\n\nEvening.\n\nThen [[go on->Nowhere]].\n")
    findings = check_structure(src)
    broken = [f for f in findings if f.code == "broken-link"]
    assert broken == [
        Finding("error", "broken-link", "src/CD-20261101.twee", 5, "Day 1 CD",
                "'Day 1 CD' links to 'Nowhere', which does not exist"),
    ]


def test_broken_link_in_harlowe_macro(tmp_path):
    src = make_story(tmp_path)
    write(src / "CD-20261101.twee", ':: Day 1 CD\n\n(link-goto: "Leave", "Gone")\n')
    assert [(f.code, f.line) for f in check_structure(src) if f.level == "error"] == [("broken-link", 3)]


def test_duplicate_passage_is_an_error(tmp_path):
    src = make_story(tmp_path)
    write(src / "CD-20261102.twee", ":: Day 2 CD\n\n[[Stay]]\n\n:: Stay\n\nA second Stay.\n")
    duplicates = [f for f in check_structure(src) if f.code == "duplicate-passage"]
    assert duplicates == [
        Finding("error", "duplicate-passage", "src/CD-20261102.twee", 5, "Stay",
                "passage 'Stay' is also declared at src/AB-20261101.twee:7"),
    ]


def test_orphan_is_a_warning_but_footer_and_stylesheet_are_not(tmp_path):
    src = make_story(tmp_path)
    write(src / "CD-20261102.twee", ":: Day 2 CD\n\nNobody links here.\n")
    findings = check_structure(src)
    assert [(f.code, f.passage) for f in findings if f.code == "orphan-passage"] == [("orphan-passage", "Day 2 CD")]
    assert all(f.passage not in {"Footer", "PathIdDisplay", "StoryStylesheet"} for f in findings)


def test_passages_reached_only_through_orphans_are_orphans(tmp_path):
    src = make_story(tmp_path)
    write(src / "CD-20261102.twee", ":: Day 2 CD\n\n[[Deeper]]\n\n:: Deeper [ending]\n\nx\n")
    assert sorted(f.passage for f in check_structure(src) if f.code == "orphan-passage") == ["Day 2 CD", "Deeper"]


def test_orphans_are_measured_from_story_data_start(tmp_path):
    data = {**STORY_DATA, "start": "Day 1 CD"}
    findings = check_structure(make_story(tmp_path, story_data=data))
    assert sorted(f.passage for f in findings if f.code == "orphan-passage") == ["Day 1 AB", "Start", "Stay"]


def test_dead_end_tagged_ending_is_not_reported(tmp_path):
    src = make_story(tmp_path)
    write(src / "CD-20261101.twee", ":: Day 1 CD [ending]\n\nEvening.\n")
    assert codes(check_structure(src)) == []


@pytest.mark.parametrize(
    ("story_data_text", "message"),
    [
        ("{not json", "StoryData is not valid JSON"),
        ("[1, 2]", "must be a JSON object"),
        (json.dumps({**STORY_DATA, "ifid": "not-a-uuid"}), "ifid must be a UUID"),
        (json.dumps({k: v for k, v in STORY_DATA.items() if k != "ifid"}), "ifid must be a UUID"),
        (json.dumps({**STORY_DATA, "start": "Nowhere"}), "start passage 'Nowhere' does not exist"),
        (json.dumps({**STORY_DATA, "storyStyle": "third"}), "storyStyle must be a JSON object"),
        (json.dumps({**STORY_DATA, "storyStyle": {"tense": "later"}}), "storyStyle.tense must be one of"),
        (json.dumps({**STORY_DATA, "storyStyle": {"perspective": "omniscient"}}), "storyStyle.perspective"),
        (json.dumps({**STORY_DATA, "storyStyle": {"protagonist": " "}}), "storyStyle.protagonist"),
    ],
)
def test_invalid_story_data_is_an_error(tmp_path, story_data_text, message):
    src = make_story(tmp_path)
    write(src / "StoryData.twee", ":: StoryData\n" + story_data_text + "\n")
    errors = [f for f in check_structure(src) if f.level == "error"]
    assert [f.code for f in errors] == ["story-data-invalid"]
    assert message in errors[0].message
    assert errors[0].file == "src/StoryData.twee" and errors[0].line == 1


def test_missing_story_data_is_an_error_and_start_defaults_to_start(tmp_path):
    src = make_story(tmp_path)
    (src / "StoryData.twee").unlink()
    findings = check_structure(src)
    assert codes(findings, "error") == ["story-data-missing"]
    assert "orphan-passage" not in codes(findings)


def test_unknown_story_style_key_is_a_warning(tmp_path):
    data = {**STORY_DATA, "storyStyle": {**STORY_DATA["storyStyle"], "mood": "grim"}}
    findings = check_structure(make_story(tmp_path, story_data=data))
    assert [(f.level, f.code) for f in findings if f.code.startswith("story")] == [("warning", "story-style-unknown-key")]


def test_story_data_without_story_style_is_valid(tmp_path):
    data = {k: v for k, v in STORY_DATA.items() if k != "storyStyle"}
    assert codes(check_structure(make_story(tmp_path, story_data=data)), "error") == []


@pytest.mark.parametrize("name", ["chapter-one.twee", "AB-2026110.twee", "AB-20261341.twee", "AB_20261101.twee", "Notes.twee"])
def test_file_naming_drift_is_a_warning(tmp_path, name):
    src = make_story(tmp_path)
    write(src / name, ":: Something\n\nx\n")
    naming = [f for f in check_structure(src) if f.code == "file-naming"]
    assert [(f.level, f.file) for f in naming] == [("warning", f"src/{name}")]


def test_infra_and_generated_files_are_not_naming_drift(tmp_path):
    src = make_story(tmp_path)
    write(src / "PathIdLookup.twee", ":: PathIdLookup [script]\nwindow.x = 1;\n")
    assert "file-naming" not in codes(check_structure(src))


def test_prose_file_without_day_passage_is_a_warning(tmp_path):
    src = make_story(tmp_path)
    write(src / "AB-20261102.twee", ":: The next morning\n\nx\n")
    write(src / "CD-20261102.twee", ":: Day 2 AB\n\nWrong initials.\n")
    missing = [f for f in check_structure(src) if f.code == "missing-day-passage"]
    assert [(f.level, f.file) for f in missing] == [
        ("warning", "src/AB-20261102.twee"),
        ("warning", "src/CD-20261102.twee"),
    ]


def test_unreadable_file_is_an_error(tmp_path):
    src = make_story(tmp_path)
    (src / "AB-20261102.twee").write_bytes(b":: Day 2 AB\n\n\xff\xfe\n")
    assert [(f.code, f.file) for f in check_structure(src) if f.level == "error"] == [("unreadable-file", "src/AB-20261102.twee")]


# --- overrides -----------------------------------------------------------------------


def test_parse_overrides_accepts_every_directive_and_skips_comments():
    text = (
        "# writer overrides\n"
        "\n"
        "alias: Rowan = Ro\n"
        "not-entity: Morning\n"
        "  pin: Rowan is left-handed\n"
        "intentional-conflict: the bridge is both old and new\n"
    )
    assert parse_overrides(text) == (
        [
            Override("alias", "Rowan = Ro", 3),
            Override("not-entity", "Morning", 4),
            Override("pin", "Rowan is left-handed", 5),
            Override("intentional-conflict", "the bridge is both old and new", 6),
        ],
        [],
    )


def test_parse_overrides_reports_bad_lines_with_numbers():
    text = "alias: A = B\nrename: A -> B\njust some words\npin:\n: nothing\n"
    overrides, errors = parse_overrides(text)
    assert overrides == [Override("alias", "A = B", 1)]
    assert errors == [
        OverrideError(2, "unknown directive 'rename' (known: alias, intentional-conflict, not-entity, pin)"),
        OverrideError(3, "expected `directive: payload`"),
        OverrideError(4, "pin: needs a payload after the colon"),
        OverrideError(5, "expected `directive: payload`"),
    ]


def test_overrides_errors_are_structure_errors(tmp_path):
    src = make_story(tmp_path)
    overrides = tmp_path / "story-overrides.txt"
    write(overrides, "# ok\nalias: A = B\nbogus: x\n")
    findings = check_structure(src, overrides_path=overrides)
    assert [(f.level, f.code, f.file, f.line) for f in findings if f.level == "error"] == [
        ("error", "overrides-syntax", "story-overrides.txt", 3)
    ]


def test_missing_overrides_file_is_fine(tmp_path):
    assert codes(check_structure(make_story(tmp_path), overrides_path=tmp_path / "story-overrides.txt"), "error") == []


# --- output formats and CLI ------------------------------------------------------------

SAMPLE = [
    Finding("error", "broken-link", "src/AB-20261101.twee", 5, "Day 1 AB", "'Day 1 AB' links to 'X, y: z', which does not exist"),
    Finding("warning", "story-data-missing", None, None, None, "no StoryData passage"),
    Finding("info", "dead-end", "src/CD-20261101.twee", 1, "Day 1 CD", "100% done\nreally"),
]


def test_format_text():
    assert format_findings(SAMPLE, "text").splitlines() == [
        "error: src/AB-20261101.twee:5: [broken-link] 'Day 1 AB' links to 'X, y: z', which does not exist",
        "warning: <story>: [story-data-missing] no StoryData passage",
        "info: src/CD-20261101.twee:1: [dead-end] 100% done",
        "really",
    ]
    assert format_findings([], "text") == ""


def test_format_github_annotations_are_escaped():
    assert format_findings(SAMPLE, "github").splitlines() == [
        "::error file=src/AB-20261101.twee,line=5,title=broken-link::'Day 1 AB' links to 'X, y: z', which does not exist",
        "::warning title=story-data-missing::no StoryData passage",
        "::notice file=src/CD-20261101.twee,line=1,title=dead-end::100%25 done%0Areally",
    ]


def test_format_json_matches_schema():
    document = json.loads(format_findings(SAMPLE, "json"))
    validate_artifact(document, "structure_findings")
    assert document[0] == {
        "level": "error",
        "code": "broken-link",
        "file": "src/AB-20261101.twee",
        "line": 5,
        "passage": "Day 1 AB",
        "message": "'Day 1 AB' links to 'X, y: z', which does not exist",
    }
    assert json.loads(format_findings([], "json")) == []


def test_format_unknown_is_an_error():
    with pytest.raises(ValueError, match="unknown format"):
        format_findings(SAMPLE, "xml")


def test_findings_are_sorted_errors_first(tmp_path):
    src = make_story(tmp_path)
    write(src / "notes.twee", ":: Loose\n\n[[Nowhere]]\n")
    levels = [f.level for f in check_structure(src)]
    assert levels == sorted(levels, key=["error", "warning", "info"].index)
    assert levels[0] == "error"


def test_cli_exits_1_on_errors_and_0_with_exit_zero(tmp_path, capsys):
    src = make_story(tmp_path)
    write(src / "CD-20261101.twee", ":: Day 1 CD\n\n[[Nowhere]]\n")
    assert main(["check", "structure", str(src)]) == 1
    captured = capsys.readouterr()
    assert "error: src/CD-20261101.twee:3: [broken-link]" in captured.out
    assert "1 error(s), 0 warning(s), 1 info" in captured.err  # its only link is broken: also a dead end
    assert main(["check", "structure", str(src), "--format", "github", "--exit-zero"]) == 0
    assert "::error file=src/CD-20261101.twee,line=3,title=broken-link::" in capsys.readouterr().out


def test_cli_warnings_only_exit_0(tmp_path, capsys):
    src = make_story(tmp_path)
    write(src / "chapter.twee", ":: Loose [ending]\n\nx\n")
    assert main(["check", "structure", str(src), "--format", "json"]) == 0
    document = json.loads(capsys.readouterr().out)
    assert {f["code"] for f in document} == {"file-naming", "orphan-passage", "dead-end"}


def test_cli_default_overrides_path_is_next_to_src(tmp_path, capsys):
    src = make_story(tmp_path)
    write(tmp_path / "story-overrides.txt", "nonsense line\n")
    assert main(["check", "structure", str(src)]) == 1
    assert "[overrides-syntax]" in capsys.readouterr().out
