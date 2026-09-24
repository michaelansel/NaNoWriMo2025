"""Pure scoring of extraction and review results against the eval story's ``truth.json``.

Nothing here touches the network or the file system. ``run_scoring`` takes the parsed
manifest and a *results* object built by the CLI from extractor and reviewer output:

.. code-block:: text

    results = {
      "entities":  [{"name": str, "type": str?, "aliases": [str]?}],
      "facts":     [{"entity": str?, "claim": str, "passage": str?, "evidence_phrase": str?}],
      "conflicts": [{"passages": [str], "intentional": bool?}],
      "pronouns":  [{"passage": str, "sentence": str, "entity": str | None}],   # optional
      "findings":  [{"type": str, "passages": [str], "severity": str, "route": [str]?}],
      "usage":     <LLMClient.usage_summary()>                                  # optional
    }

Every section is optional; a missing section scores as empty, never as perfect.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

CLAIM_OVERLAP_THRESHOLD = 0.6

# Defect types that are also contradictions between passages; a reported conflict that
# lands on one of these is a true positive for conflict precision.
CONFLICT_LIKE_DEFECTS = frozenset({"death_then_alive", "world_rule", "timeline"})

_STOPWORDS = frozenset(
    """
    a an and are as at be by for from had has have he her his in is it its of on or she that
    the their there this to was were with
    """.split()
)


# -- normalization ---------------------------------------------------------------


def normalize_name(name: str) -> str:
    """Case-fold an entity name or alias, dropping a leading article and possessive.

    Args:
        name: Raw name as written by the model or the manifest.

    Returns:
        A comparable key, for example ``"old mill"`` for ``"The Old Mill's"``.
    """
    key = name.casefold().strip()
    key = re.sub(r"^(the|a|an)\s+", "", key)
    key = re.sub(r"['’]s\b", "", key)
    key = re.sub(r"[^\w\s]", " ", key)
    return re.sub(r"\s+", " ", key).strip()


def tokens(text: str) -> set[str]:
    """Return content tokens of a claim: case-folded, stopwords dropped, plural ``s`` trimmed."""
    words = re.findall(r"[a-z0-9]+", text.casefold())
    return {w[:-1] if len(w) > 3 and w.endswith("s") else w for w in words if w not in _STOPWORDS}


def claim_overlap(reference: str, candidate: str) -> float:
    """Fraction of the reference claim's content tokens present in the candidate.

    Args:
        reference: The truth claim.
        candidate: The model's claim.

    Returns:
        A value in ``[0, 1]``; ``0`` when the reference has no content tokens.
    """
    ref = tokens(reference)
    if not ref:
        return 0.0
    return len(ref & tokens(candidate)) / len(ref)


def _forms(name: str, aliases: Iterable[str] = ()) -> set[str]:
    return {normalize_name(n) for n in (name, *aliases) if n and normalize_name(n)}


def _entity_index(truth: Mapping[str, Any]) -> dict[str, str]:
    """Map every normalized truth name and alias to its canonical entity name."""
    index: dict[str, str] = {}
    for entity in truth["entities"]:
        for form in _forms(entity["name"], entity.get("aliases", ())):
            index.setdefault(form, entity["name"])
    return index


def _canonical(index: Mapping[str, str], name: str | None) -> str | None:
    if not name:
        return None
    return index.get(normalize_name(name))


def _passage_set(names: Iterable[str]) -> frozenset[str]:
    return frozenset(n.strip() for n in names if n and n.strip())


def _ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


# -- sections --------------------------------------------------------------------


def score_entities(
    truth: Mapping[str, Any], entities: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    """Alias-aware, case-insensitive entity recall and precision.

    Args:
        truth: Parsed ``truth.json``.
        entities: Extracted entities with ``name`` and optional ``aliases``/``type``.

    Returns:
        ``recall``, ``precision``, ``matched``, ``missed``, ``spurious``, ``distractor_hits``,
        and ``by_type`` recall per entity type.
    """
    index = _entity_index(truth)
    distractors = {normalize_name(d["phrase"]) for d in truth.get("distractors", [])}
    matched: set[str] = set()
    spurious: list[str] = []
    distractor_hits: list[str] = []
    for entity in entities:
        forms = _forms(entity.get("name", ""), entity.get("aliases", ()))
        hits = {index[f] for f in forms if f in index}
        if hits:
            matched |= hits
        else:
            spurious.append(entity.get("name", ""))
        if forms & distractors:
            distractor_hits.append(entity.get("name", ""))
    by_type: dict[str, dict[str, Any]] = {}
    for entity in truth["entities"]:
        bucket = by_type.setdefault(entity["type"], {"expected": 0, "found": 0})
        bucket["expected"] += 1
        bucket["found"] += entity["name"] in matched
    for bucket in by_type.values():
        bucket["recall"] = _ratio(bucket["found"], bucket["expected"])
    missed = [e["name"] for e in truth["entities"] if e["name"] not in matched]
    return {
        "expected": len(truth["entities"]),
        "reported": len(entities),
        "matched": sorted(matched),
        "missed": missed,
        "spurious": spurious,
        "distractor_hits": distractor_hits,
        "recall": _ratio(len(matched), len(truth["entities"])),
        "precision": _ratio(len(entities) - len(spurious), len(entities)),
        "by_type": by_type,
    }


def _fact_matches(
    truth_fact: Mapping[str, Any], candidate: Mapping[str, Any], index: Mapping[str, str]
) -> bool:
    cand_entity = _canonical(index, candidate.get("entity"))
    if cand_entity is not None and cand_entity != truth_fact["entity"]:
        return False
    claim = candidate.get("claim", "") or ""
    evidence = candidate.get("evidence_phrase", "") or ""
    phrase = normalize_name(truth_fact["evidence_phrase"])
    if phrase and (phrase in normalize_name(evidence) or phrase in normalize_name(claim)):
        return True
    return claim_overlap(truth_fact["claim"], claim) >= CLAIM_OVERLAP_THRESHOLD


def _scene_state_hit(candidate: Mapping[str, Any], statements: Sequence[str]) -> bool:
    claim = candidate.get("claim", "") or ""
    evidence = candidate.get("evidence_phrase", "") or ""
    for statement in statements:
        key = normalize_name(statement)
        if key and (key in normalize_name(evidence) or key in normalize_name(claim)):
            return True
        if claim_overlap(statement, claim) >= CLAIM_OVERLAP_THRESHOLD:
            return True
    return False


def score_facts(truth: Mapping[str, Any], facts: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Fact recall with fuzzy claim matching, and precision against scene-state traps.

    A truth fact is recalled when some reported fact for the same entity (alias-aware, or
    with no entity given) contains its ``evidence_phrase`` or shares at least
    ``CLAIM_OVERLAP_THRESHOLD`` of its claim's content tokens.

    Args:
        truth: Parsed ``truth.json``.
        facts: Reported facts.

    Returns:
        ``recall``, ``precision`` (reported facts that match some truth fact),
        ``scene_state_leaks`` (reported facts that restate a scene-state trap), and lists.
    """
    index = _entity_index(truth)
    statements = [s["statement"] for s in truth.get("scene_state", [])]
    recalled: list[str] = []
    missed: list[str] = []
    used: set[int] = set()
    for truth_fact in truth["facts"]:
        hit = next(
            (i for i, cand in enumerate(facts) if _fact_matches(truth_fact, cand, index)), None
        )
        if hit is None:
            missed.append(truth_fact["id"])
        else:
            recalled.append(truth_fact["id"])
            used.add(hit)
    leaks = [cand.get("claim", "") for cand in facts if _scene_state_hit(cand, statements)]
    return {
        "expected": len(truth["facts"]),
        "reported": len(facts),
        "recalled": recalled,
        "missed": missed,
        "recall": _ratio(len(recalled), len(truth["facts"])),
        "precision": _ratio(len(used), len(facts)),
        "scene_state_leaks": len(leaks),
        "scene_state_leak_claims": leaks,
        "scene_state_precision": _ratio(len(facts) - len(leaks), len(facts)),
    }


def _conflict_targets(truth: Mapping[str, Any]) -> list[dict[str, Any]]:
    targets = [
        {"id": c["id"], "passages": _passage_set(c["passages"]), "intentional": c["intentional"]}
        for c in truth.get("contradictions", [])
    ]
    targets += [
        {"id": d["id"], "passages": _passage_set(d["passages"]), "intentional": False}
        for d in truth.get("defects", [])
        if d["type"] in CONFLICT_LIKE_DEFECTS
    ]
    return targets


def score_conflicts(
    truth: Mapping[str, Any], conflicts: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    """Conflict recall over planted contradictions and precision over all planted targets.

    A reported conflict matches a target when it cites every passage the target spans.

    Args:
        truth: Parsed ``truth.json``.
        conflicts: Reported conflicts with ``passages`` and optional ``intentional``.

    Returns:
        ``recall`` (contradictions found), ``precision`` (reports that land on a
        contradiction or conflict-like defect), ``intentional_flagged``, and lists.
    """
    contradictions = truth.get("contradictions", [])
    targets = _conflict_targets(truth)
    reported = [
        (_passage_set(c.get("passages", ())), bool(c.get("intentional"))) for c in conflicts
    ]
    found: list[str] = []
    intentional_flagged = 0
    for contradiction in contradictions:
        span = _passage_set(contradiction["passages"])
        hits = [flag for passages, flag in reported if span <= passages]
        if hits:
            found.append(contradiction["id"])
            if contradiction["intentional"] and any(hits):
                intentional_flagged += 1
    true_positives = sum(
        1 for passages, _flag in reported if any(t["passages"] <= passages for t in targets)
    )
    intentional_total = sum(1 for c in contradictions if c["intentional"])
    return {
        "expected": len(contradictions),
        "reported": len(conflicts),
        "found": found,
        "missed": [c["id"] for c in contradictions if c["id"] not in found],
        "recall": _ratio(len(found), len(contradictions)),
        "precision": _ratio(true_positives, len(conflicts)),
        "intentional_expected": intentional_total,
        "intentional_flagged": intentional_flagged,
    }


def _finding_matches_defect(finding: Mapping[str, Any], defect: Mapping[str, Any]) -> bool:
    if finding.get("type") != defect["type"]:
        return False
    return bool(_passage_set(finding.get("passages", ())) & _passage_set(defect["passages"]))


def score_defects(
    truth: Mapping[str, Any], findings: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    """Per-defect detection given editor findings ``{type, passages, severity}``.

    Args:
        truth: Parsed ``truth.json``.
        findings: Reported findings.

    Returns:
        ``detected`` count, ``severity_matches`` count, ``detection_rate``, and a
        per-defect list with the matching finding when there is one.
    """
    rows = []
    for defect in truth.get("defects", []):
        match = next((f for f in findings if _finding_matches_defect(f, defect)), None)
        rows.append(
            {
                "id": defect["id"],
                "type": defect["type"],
                "detected": match is not None,
                "severity_ok": match is not None
                and match.get("severity") == defect["expected_severity"],
                "expected_severity": defect["expected_severity"],
                "reported_severity": match.get("severity") if match else None,
            }
        )
    detected = sum(r["detected"] for r in rows)
    return {
        "expected": len(rows),
        "detected": detected,
        "severity_matches": sum(r["severity_ok"] for r in rows),
        "detection_rate": _ratio(detected, len(rows)),
        "per_defect": rows,
    }


def _matches_planted(finding: Mapping[str, Any], truth: Mapping[str, Any]) -> str | None:
    """Return the id of the planted item a finding lands on, or ``None``."""
    passages = _passage_set(finding.get("passages", ()))
    for defect in truth.get("defects", []):
        if _finding_matches_defect(finding, defect):
            return defect["id"]
    for contradiction in truth.get("contradictions", []):
        if _passage_set(contradiction["passages"]) <= passages:
            return contradiction["id"]
    return None


def score_clean_paths(
    truth: Mapping[str, Any], findings: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    """Count findings on clean routes that do not land on any planted item.

    A finding is on a clean route when its ``route`` equals that route, or, without a
    ``route``, when every passage it cites lies on the route. A finding that lands on the
    intentional contradiction is not a false positive but is counted as an
    ``intentional_leak`` (the overrides file should have suppressed it).

    Args:
        truth: Parsed ``truth.json``.
        findings: Reported findings.

    Returns:
        ``false_positives`` count, ``intentional_leaks`` count, and per-path details.
    """
    intentional = {c["id"] for c in truth.get("contradictions", []) if c["intentional"]}
    per_path: dict[str, list[dict[str, Any]]] = {}
    false_positives = 0
    intentional_leaks = 0
    for path in truth.get("clean_paths", []):
        route = list(path["route"])
        route_set = set(route)
        rows: list[dict[str, Any]] = []
        for finding in findings:
            declared = finding.get("route")
            on_route = (
                list(declared) == route
                if declared is not None
                else bool(_passage_set(finding.get("passages", ())))
                and _passage_set(finding.get("passages", ())) <= route_set
            )
            if not on_route:
                continue
            planted = _matches_planted(finding, truth)
            kind = (
                "planted"
                if planted and planted not in intentional
                else "intentional_leak"
                if planted
                else "false_positive"
            )
            rows.append(
                {
                    "type": finding.get("type"),
                    "passages": sorted(_passage_set(finding.get("passages", ()))),
                    "kind": kind,
                    "planted": planted,
                }
            )
            false_positives += kind == "false_positive"
            intentional_leaks += kind == "intentional_leak"
        per_path[path["id"]] = rows
    return {
        "paths": len(per_path),
        "false_positives": false_positives,
        "intentional_leaks": intentional_leaks,
        "per_path": per_path,
    }


def score_pronouns(
    truth: Mapping[str, Any], pronouns: Sequence[Mapping[str, Any]] | None
) -> dict[str, Any]:
    """Score pronoun resolutions ``{passage, sentence, entity}`` against the planted cases.

    Args:
        truth: Parsed ``truth.json``.
        pronouns: Reported resolutions, or ``None`` when the run produced none.

    Returns:
        ``scored`` (whether anything was reported), resolvable and ambiguous correctness
        counts, and ``accuracy`` over all cases.
    """
    cases = truth.get("pronoun_cases", [])
    if pronouns is None:
        return {
            "scored": False,
            "expected": len(cases),
            "resolvable_correct": 0,
            "ambiguous_correct": 0,
            "accuracy": 0.0,
        }
    index = _entity_index(truth)
    resolvable_correct = 0
    ambiguous_correct = 0
    for case in cases:
        sentence = case["sentence"].casefold()
        reported = next(
            (
                p
                for p in pronouns
                if p.get("passage") == case["passage"]
                and (
                    sentence in (p.get("sentence") or "").casefold()
                    or (p.get("sentence") or "").casefold() in sentence
                )
                and p.get("sentence")
            ),
            None,
        )
        if reported is None:
            continue
        answer = _canonical(index, reported.get("entity"))
        if case["expected"] is None:
            ambiguous_correct += reported.get("entity") is None
        else:
            resolvable_correct += answer == case["expected"]
    total_correct = resolvable_correct + ambiguous_correct
    return {
        "scored": True,
        "expected": len(cases),
        "resolvable_expected": sum(1 for c in cases if c["expected"] is not None),
        "ambiguous_expected": sum(1 for c in cases if c["expected"] is None),
        "resolvable_correct": resolvable_correct,
        "ambiguous_correct": ambiguous_correct,
        "accuracy": _ratio(total_correct, len(cases)),
    }


def totals_block(usage: Mapping[str, Any] | None) -> dict[str, Any]:
    """Normalize a ``usage_summary()`` dict into the report's cost block.

    Args:
        usage: The summary, or ``None`` when the run recorded nothing.

    Returns:
        Token counts, USD, and provider fields with zero defaults.
    """
    usage = usage or {}
    return {
        "calls": int(usage.get("calls", 0)),
        "prompt_tokens": int(usage.get("prompt_tokens", 0)),
        "completion_tokens": int(usage.get("completion_tokens", 0)),
        "reasoning_tokens": int(usage.get("reasoning_tokens", 0)),
        "total_tokens": int(usage.get("total_tokens", 0)),
        "usd": float(usage.get("usd", 0.0)),
        "usd_known": bool(usage.get("usd_known", False)),
        "profile": usage.get("profile"),
        "model": usage.get("model"),
    }


def run_scoring(truth: Mapping[str, Any], results: Mapping[str, Any]) -> dict[str, Any]:
    """Score a results object against the manifest.

    Args:
        truth: Parsed ``truth.json``.
        results: The results object described in the module docstring.

    Returns:
        Per-section detail under ``entities``, ``facts``, ``conflicts``, ``defects``,
        ``pronouns``, ``clean_paths``, ``totals``, plus a flat ``metrics`` dict that the
        report and baseline diff consume.
    """
    findings = list(results.get("findings", []) or [])
    sections = {
        "entities": score_entities(truth, list(results.get("entities", []) or [])),
        "facts": score_facts(truth, list(results.get("facts", []) or [])),
        "conflicts": score_conflicts(truth, list(results.get("conflicts", []) or [])),
        "defects": score_defects(truth, findings),
        "pronouns": score_pronouns(truth, results.get("pronouns")),
        "clean_paths": score_clean_paths(truth, findings),
        "totals": totals_block(results.get("usage")),
    }
    metrics = {
        "entity_recall": sections["entities"]["recall"],
        "entity_precision": sections["entities"]["precision"],
        "distractor_hits": len(sections["entities"]["distractor_hits"]),
        "fact_recall": sections["facts"]["recall"],
        "fact_precision": sections["facts"]["precision"],
        "scene_state_leaks": sections["facts"]["scene_state_leaks"],
        "conflict_recall": sections["conflicts"]["recall"],
        "conflict_precision": sections["conflicts"]["precision"],
        "intentional_flagged": sections["conflicts"]["intentional_flagged"],
        "defects_detected": sections["defects"]["detected"],
        "defect_severity_matches": sections["defects"]["severity_matches"],
        "pronoun_accuracy": sections["pronouns"]["accuracy"],
        "clean_path_false_positives": sections["clean_paths"]["false_positives"],
        "intentional_leaks": sections["clean_paths"]["intentional_leaks"],
        "total_tokens": sections["totals"]["total_tokens"],
        "usd": sections["totals"]["usd"],
    }
    return {**sections, "metrics": metrics}
