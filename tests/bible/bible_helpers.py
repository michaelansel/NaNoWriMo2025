"""Builders for Story Bible tests: a small v2 cache, extraction answers, scripted fakes."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from nanoif.llm.errors import LLMSpendCapReached
from nanoif.llm.fake import FakeLLM
from nanoif.twee.passages import content_hash
from tests.conftest import git

DAY1 = "Day 1 EV"
CROSSING = "The crossing"
HOLLIN = "Hollin Reach"
WIDOW = "The widow's door"

TEXTS = {
    DAY1: (
        "Old Tam was already up, coaxing the stove, her grey braid tucked into the collar. "
        "Tamsin Reeve had carried it across the river every working day of those forty years."
    ),
    CROSSING: (
        "Captain Oriel Marsh stood in the stern with one boot on the gunwale, the way he always "
        "stood. The green pennant of the River Wardens hung limp at its mast. "
        '"Old Tam paid the month on the first."'
    ),
    HOLLIN: "Wren's brother was twelve and had never in his life been where he was supposed to be.",
    WIDOW: '"Eleven years old and out after the bell with a key in his fist." Pip had gone.',
}

PROMPT_HASHES = {
    "bible_extract": "0123456789ab",
    "bible_resolve": "0123456789ab",
    "bible_reconcile": "0123456789ab",
}


def fact(fid: str, claim: str, quote: str, passage: str, kind: str = "trait", dup=None):
    return {
        "id": fid,
        "claim": claim,
        "quote": quote,
        "passage": passage,
        "kind": kind,
        "duplicate_of": dup,
    }


def entity(slug: str, name: str, etype: str, facts: list, **extra: Any) -> dict[str, Any]:
    data = {
        "slug": slug,
        "name": name,
        "type": etype,
        "aliases": [],
        "role": None,
        "passages": sorted({f["passage"] for f in facts}),
        "next_n": 1 + max((int(f["id"].split("#")[1]) for f in facts), default=0),
        "reconcile": "done",
        "merged_into": None,
        "facts": facts,
        "retired": [],
    }
    data.update(extra)
    return data


def passage_record(name: str, fact_ids: list[str], mentions: list[str]) -> dict[str, Any]:
    return {
        "content_hash": content_hash(TEXTS[name]),
        "file": "src/EV-20261101.twee",
        "summary": f"Summary of {name}.",
        "mentions": mentions,
        "references": [],
        "fact_ids": fact_ids,
        "dropped": {"unverified_quote": 0, "state": 0, "generic_entity": 0},
    }


def small_cache() -> dict[str, Any]:
    """A valid v2 cache: Tam, Pip (with a conflict), Marsh, the River Wardens."""
    tam = entity(
        "tamsin-reeve",
        "Tamsin Reeve",
        "character",
        [
            fact("tamsin-reeve#1", "Tam has a grey braid", "her grey braid", DAY1),
            fact(
                "tamsin-reeve#2",
                "Tamsin Reeve has carried the lantern for forty years",
                "every working day of those forty years",
                DAY1,
                "event",
            ),
        ],
        aliases=["Old Tam", "Tam"],
        role="ferry keeper",
        passages=[DAY1, CROSSING],
    )
    pip = entity(
        "pip-halloway",
        "Pip Halloway",
        "character",
        [
            fact("pip-halloway#1", "Pip is twelve", "Wren's brother was twelve", HOLLIN),
            fact("pip-halloway#2", "Pip is eleven", "Eleven years old", WIDOW),
        ],
        aliases=["Pip"],
    )
    marsh = entity(
        "oriel-marsh",
        "Oriel Marsh",
        "character",
        [
            fact(
                "oriel-marsh#1",
                "Oriel Marsh is a captain",
                "Captain Oriel Marsh stood in the stern",
                CROSSING,
                "relationship",
            )
        ],
        aliases=["Captain Marsh", "Marsh"],
    )
    wardens = entity("river-wardens", "River Wardens", "group", [], passages=[CROSSING])
    return {
        "version": 2,
        "extraction": {
            "commit": "a" * 40,
            "extracted_at": "2026-11-02T08:00:00Z",
            "mode": "incremental",
            "profile": "fake",
            "model": "fake-model",
            "prompt_hashes": dict(PROMPT_HASHES),
            "usd": 0.01,
            "usd_known": True,
        },
        "passages": {
            DAY1: passage_record(DAY1, ["tamsin-reeve#1", "tamsin-reeve#2"], ["tamsin-reeve"]),
            CROSSING: passage_record(
                CROSSING, ["oriel-marsh#1"], ["oriel-marsh", "river-wardens", "tamsin-reeve"]
            ),
            HOLLIN: passage_record(HOLLIN, ["pip-halloway#1"], ["pip-halloway"]),
            WIDOW: passage_record(WIDOW, ["pip-halloway#2"], ["pip-halloway"]),
        },
        "entities": {e["slug"]: e for e in (tam, pip, marsh, wardens)},
        "resolution": {
            "tamsin reeve": "tamsin-reeve",
            "old tam": "tamsin-reeve",
            "tam": "tamsin-reeve",
            "pip halloway": "pip-halloway",
            "pip": "pip-halloway",
            "oriel marsh": "oriel-marsh",
            "captain marsh": "oriel-marsh",
            "marsh": "oriel-marsh",
            "river wardens": "river-wardens",
        },
        "conflicts": {
            "c-pip-halloway-1": {
                "id": "c-pip-halloway-1",
                "entity": "pip-halloway",
                "fact_ids": ["pip-halloway#1", "pip-halloway#2"],
                "note": "Pip is twelve in one passage and eleven in another.",
                "status": "open",
            }
        },
    }


def clone(data: dict[str, Any]) -> dict[str, Any]:
    return copy.deepcopy(data)


# -- scripted extraction runs ----------------------------------------------------------

EMPTY = {"summary": "Nothing named.", "entities": [], "references": []}
CAP = LLMSpendCapReached(
    "cap",
    reason="monthly AI spend cap reached: $10.00 of $10.00 in 2026-11 (resets 2026-12-01 UTC)",
    month_usd=10.0,
    cap_usd=10.0,
)


def ent(name, facts=(), aliases=(), etype="character", role=None):
    return {
        "name": name,
        "type": etype,
        "aliases": list(aliases),
        "role": role,
        "facts": [{"claim": c, "quote": q, "kind": k} for c, q, k in facts],
    }


ANSWERS = {
    DAY1: {
        "summary": "Tam is up before Wren.",
        "entities": [
            ent(
                "Tamsin Reeve",
                [
                    ("Tam has a grey braid", "her grey braid", "trait"),
                    ("Tam carried the lantern for forty years", "every working day of those forty years", "event"),
                    ("Tam coaxes the stove", "coaxing the stove", "state"),
                    ("Tam is kind", "Tam was kind to everyone", "trait"),
                ],
                aliases=["Old Tam"],
                role="ferry keeper",
            ),
            ent("no one"),
        ],
        "references": [{"quote": "her grey braid", "pronoun": "her", "entity": "Tamsin Reeve"}],
    },
    CROSSING: {
        "summary": "Marsh stops the ferry.",
        "entities": [
            ent("Oriel Marsh", [("Oriel Marsh is a captain", "Captain Oriel Marsh stood in the stern", "relationship")],
                aliases=["Captain Marsh"]),
            ent("River Wardens", etype="group"),
            ent("Old Tam"),
        ],
        "references": [],
    },
    HOLLIN: {
        "summary": "Pip is twelve.",
        "entities": [ent("Pip Halloway", [("Pip is twelve", "Wren's brother was twelve", "trait")], aliases=["Pip"])],
        "references": [],
    },
    WIDOW: {
        "summary": "Pip is eleven.",
        "entities": [ent("Pip", [("Pip is eleven", "Eleven years old", "trait")])],
        "references": [],
    },
}


def verdicts(user, special):
    slugs = [line.split()[1].rstrip(":") for line in user.splitlines() if line.startswith("ENTITY ")]
    return {"entities": [special.get(s, {"slug": s, "duplicates": [], "conflicts": []}) for s in slugs]}


def scripted(answers=ANSWERS, fail=(), reconcile=None, resolve=None, halt_on=None):
    reconcile = reconcile or {}

    def respond(call):
        if call.tag.startswith("bible-extract:"):
            name = call.tag.split(":", 1)[1]
            if name == halt_on:
                return CAP
            if name in fail:
                return FakeLLM.transport_error()
            return answers.get(name, EMPTY)
        if call.tag == "bible-resolve":
            return resolve or {"merges": [], "drop": []}
        if isinstance(reconcile, Exception):
            return reconcile
        return verdicts(call.user, reconcile)

    return FakeLLM(respond)


PIP_CONFLICT = {
    "pip-halloway": {
        "slug": "pip-halloway",
        "duplicates": [],
        "conflicts": [{"a": "pip-halloway#1", "b": "pip-halloway#2", "note": "twelve or eleven"}],
    }
}


class CappedLLM(FakeLLM):
    """A fake whose spend check always refuses, recording the estimate it was given."""

    def check_spend(self, estimate_usd: float = 0.0) -> None:
        self.estimates = [*getattr(self, "estimates", []), estimate_usd]
        raise CAP


# -- story repositories -----------------------------------------------------------------

STORY_DATA = ':: StoryData\n{"ifid": "7C1E4B2A-9D3F-4A6B-8E5C-2F7A9B1D3C4E", "start": "Day 1 EV"}\n'


def write_story(repo: Path, texts=TEXTS) -> None:
    """Write the passages as one prose file plus StoryData and StoryTitle."""
    src = repo / "src"
    src.mkdir(parents=True, exist_ok=True)
    body = "\n\n".join(f":: {name}\n\n{text}" for name, text in texts.items())
    (src / "EV-20261101.twee").write_text(body + "\n", encoding="utf-8")
    (src / "StoryData.twee").write_text(STORY_DATA, encoding="utf-8")
    (src / "StoryTitle.twee").write_text(":: StoryTitle\nThe Lantern Crossing\n", encoding="utf-8")


def write_cache(repo: Path, data=None) -> Path:
    path = repo / "ai" / "story-bible-cache.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(small_cache() if data is None else data), encoding="utf-8")
    return path


def commit(root: Path) -> str:
    """Commit everything and return the new HEAD."""
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "story")
    return git(root, "rev-parse", "HEAD").strip()
