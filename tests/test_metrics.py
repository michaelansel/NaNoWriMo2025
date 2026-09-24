"""Tests for ``nanoif.twee.prose`` and ``nanoif.formats.metrics``."""

import json

import pytest

from nanoif.cli import main
from nanoif.errors import BuildError
from nanoif.formats.metrics import MetricsConfig, build_metrics, calculate_metrics
from nanoif.formats.metrics.compute import distribution, statistics
from nanoif.twee.files import passage_locations
from nanoif.twee.parse import parse_twee_dir
from nanoif.twee.prose import prose_text, word_count

# --- prose and word counts -----------------------------------------------------------


@pytest.mark.intent("AC-output-formats-12")
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("This is a test", 4),
        ("Click [[here->Target]] to continue", 4),
        ("Go [[Target<-back now]] please", 4),
        ("Pick [[the red door|Red Door]]", 4),
        ("Hello (set: $foo to 5) world", 2),
        ('Then (link-goto: "open it", "Hall") slowly', 4),
        ("<span id='x'>Two words</span>", 2),
        ("", 0),
    ],
)
def test_word_count(text, expected):
    assert word_count(text) == expected


@pytest.mark.intent("AC-output-formats-12")
def test_prose_text_uses_link_display_text():
    assert prose_text("It's [[sunny->Day 30 AB]] or [[raining]].") == "It's sunny or raining."


# --- statistics ----------------------------------------------------------------------


@pytest.mark.intent("AC-output-formats-13")
def test_statistics_and_distribution():
    assert statistics([]) == {"min": 0, "mean": 0.0, "median": 0.0, "max": 0}
    assert statistics([1, 2, 6]) == {"min": 1, "mean": 3, "median": 2, "max": 6}
    assert distribution([0, 100, 101, 300, 301, 500, 501, 1000, 1001, 5000]) == {
        "0-100": 2,
        "101-300": 2,
        "301-500": 2,
        "501-1000": 2,
        "1000+": 2,
    }


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture
def story(tmp_path):
    src = tmp_path / "src"
    write(src / "StoryData.twee", ':: StoryData\n{"ifid": "X", "start": "Start"}\n')
    write(src / "StoryTitle.twee", ":: StoryTitle\nWord Count Story\n")
    write(src / "Start.twee", ":: Start\none two [[Day 1 AB]] [[Day 1 CD]]\n")
    write(src / "AB-20251101.twee", ":: Day 1 AB\nthree four five\n\n:: Aside\nsix\n")
    write(src / "CD-20251101.twee", ":: Day 1 CD\n" + "word " * 120 + "\n")
    write(src / "PathIdDisplay.twee", ":: PathIdDisplay [footer]\nlots of footer words here\n")
    write(src / "StoryStyles.twee", ":: Footer [footer]\nmore footer\n\n:: Sheet [stylesheet]\nbody {}\n")
    return tmp_path


@pytest.mark.intent("AC-output-formats-12", "AC-output-formats-13")
def test_calculate_metrics_counts_prose_and_files(story):
    graph = parse_twee_dir(story / "src")
    metrics = calculate_metrics(graph, passage_locations(story / "src"), top_n=2)
    assert metrics["story_name"] == "Word Count Story"
    assert metrics["passage_count"] == 4
    assert metrics["total_words"] == 8 + 3 + 1 + 120  # links count as the words a reader sees
    assert metrics["file_count"] == 3
    assert metrics["files"] == [
        {"name": "AB-20251101.twee", "word_count": 4, "passage_count": 2},
        {"name": "CD-20251101.twee", "word_count": 120, "passage_count": 1},
        {"name": "Start.twee", "word_count": 8, "passage_count": 1},
    ]
    assert metrics["file_stats"] == {"min": 4, "mean": 44, "median": 8, "max": 120}
    assert metrics["top_passages"] == [{"name": "Day 1 CD", "word_count": 120}, {"name": "Start", "word_count": 8}]
    assert metrics["passage_distribution"]["101-300"] == 1


@pytest.mark.intent("AC-output-formats-12")
def test_calculate_metrics_excludes_footer_passages(story):
    graph = parse_twee_dir(story / "src")
    names = {p["name"] for p in calculate_metrics(graph, passage_locations(story / "src"), top_n=50)["top_passages"]}
    assert "PathIdDisplay" not in names and "Footer" not in names


@pytest.mark.intent("AC-output-formats-14")
def test_calculate_metrics_include_and_exclude_filters(story):
    graph = parse_twee_dir(story / "src")
    locations = passage_locations(story / "src")
    only_ab = calculate_metrics(graph, locations, include=["AB-"])
    assert only_ab["passage_count"] == 2 and only_ab["total_words"] == 4
    assert only_ab["filters"] == {"include": ["AB-"], "exclude": []}
    no_cd = calculate_metrics(graph, locations, exclude=["CD-", "Start"])
    assert [f["name"] for f in no_cd["files"]] == ["AB-20251101.twee"]


@pytest.mark.intent("AC-output-formats-13")
def test_build_metrics_writes_page(story):
    graph = parse_twee_dir(story / "src")
    write(story / "lib" / "artifacts" / "story_graph.json", json.dumps(graph))
    result = build_metrics(
        MetricsConfig(
            src_dir=story / "src",
            story_graph_path=story / "lib" / "artifacts" / "story_graph.json",
            output_dir=story / "dist",
        )
    )
    html = result.html_path.read_text()
    assert "<title>Writing Metrics - Word Count Story</title>" in html
    assert ">132<" in html
    assert "Day 1 CD" in html


def test_build_metrics_missing_graph_is_an_error(story):
    with pytest.raises(BuildError, match="story_graph not found"):
        build_metrics(MetricsConfig(story / "src", story / "missing.json", story / "dist"))


@pytest.mark.intent("AC-output-formats-14")
def test_cli_build_metrics(story, capsys):
    write(story / "lib" / "artifacts" / "story_graph.json", json.dumps(parse_twee_dir(story / "src")))
    assert main(["build", "metrics", "--repo", str(story), "--exclude", "CD-"]) == 0
    assert "Metrics: 12 words in 3 passages across 2 files" in capsys.readouterr().out
