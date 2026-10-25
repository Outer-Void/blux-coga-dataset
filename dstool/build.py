"""Build: seeds -> engine -> gates -> dedup -> contamination -> quality -> split lock -> data files + manifest.

Every step is deterministic, so building twice gives byte-identical files (`build --check` proves it in CI).
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dstool import quality, similarity
from dstool.adapters import Adapter, load
from dstool.common import (
    PROTECTED_SPLITS,
    SPLITS,
    TOOL_NAME,
    TOOL_VERSION,
    TRAINING_SPLITS,
    Config,
    DsError,
    canonical,
    load_json,
    sha256_of,
    sha256_text,
)
from dstool.scan import privacy_hits, private_terms, reasoning_hits
from dstool.schemas import LOCK, check, record_schema
from dstool.seeds import Draft, load_all


@dataclass
class Result:
    records: list[dict[str, Any]] = field(default_factory=list)
    excluded: list[dict[str, Any]] = field(default_factory=list)
    retired: list[str] = field(default_factory=list)
    contamination: dict[str, Any] = field(default_factory=dict)


def _content(record: dict[str, Any]) -> dict[str, Any]:
    return {"task": record["task"], "input": record["input"], "expected": record["expected"]}


def make_record(config: Config, draft: Draft, expected: dict[str, Any]) -> dict[str, Any]:
    record: dict[str, Any] = {
        "schema": "blux.dataset-record",
        "schema_version": 1,
        "dataset": config.dataset_id,
        "dataset_version": config.raw["version"],
        "record_id": draft.record_id,
        "family": draft.family,
        "variant": draft.variant,
        "category": draft.category,
        "split": draft.split,
        "task": {"instruction": draft.instruction},
        "input": draft.input,
        "expected": expected,
        "provenance": {
            "origin": draft.origin,
            "authors": list(config.raw["authors"]),
            "license": draft.license,
            "seed": {"path": draft.seed_path, "sha256": draft.seed_sha256},
            "generator": {"name": TOOL_NAME, "version": TOOL_VERSION},
            "engines": list(config.raw["engines"]),
            "created": config.raw["release_date"],
            "review": {"status": "approved"},
        },
        "quality": {"score": 0.0, "threshold": config.raw["quality_threshold"], "components": {}},
        "hashes": {
            "input_sha256": sha256_of(draft.input),
            "expected_sha256": sha256_of(expected),
            "content_sha256": "",
        },
        "tags": list(draft.tags),
        "canary": config.canary if draft.split in PROTECTED_SPLITS else None,
    }
    if draft.source:
        record["provenance"]["source"] = draft.source
    record["hashes"]["content_sha256"] = sha256_of(_content(record))
    return record


def gates(config: Config, adapter: Adapter, record: dict[str, Any], terms: list[str]) -> list[str]:
    """Problems that keep a record out of the dataset entirely (schema, privacy, hidden reasoning)."""
    problems = []
    try:
        check(record_schema(config.categories), record, record["record_id"])
        adapter.check_input(record["input"], record["record_id"])
        adapter.check_expected(record["expected"], record["record_id"])
    except DsError as exc:
        problems.append(exc.message)
    problems += privacy_hits(_content(record), terms)
    problems += reasoning_hits(record, rejected=adapter.rejected(record["expected"]))
    return problems


def dedup(records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    """Exact duplicates (same normalized tokens): dropped within a split, a hard failure across splits."""
    kept, dropped, problems = [], [], []
    first: dict[str, dict[str, Any]] = {}
    for r in records:
        key = similarity.exact_key(similarity.tokens(r["task"]["instruction"], r["input"]))
        other = first.get(key)
        if other is None:
            first[key] = r
            kept.append(r)
        elif other["split"] == r["split"]:
            dropped.append({"record_id": r["record_id"], "reason": "duplicate", "duplicate_of": other["record_id"]})
        else:
            problems.append(
                f"exact duplicate across splits: {other['record_id']} ({other['split']}) and "
                f"{r['record_id']} ({r['split']})"
            )
    return kept, dropped, problems


def contamination(records: list[dict[str, Any]], threshold: float) -> tuple[dict[str, Any], dict[str, float]]:
    """Cross-split near duplicates and split-spanning families (hard failures); nearest same-split neighbours."""
    toks = {r["record_id"]: similarity.tokens(r["task"]["instruction"], r["input"]) for r in records}
    sh = {rid: similarity.shingles(t) for rid, t in toks.items()}
    problems: list[str] = []
    by_id = {r["record_id"]: r for r in records}
    nearest_same: dict[str, float] = dict.fromkeys(by_id, 0.0)
    nearest_cross: dict[str, tuple[float, str | None]] = dict.fromkeys(by_id, (0.0, None))
    for a, b in itertools.combinations(sorted(by_id), 2):
        ra, rb = by_id[a], by_id[b]
        if ra["family"] == rb["family"]:
            continue
        sim = similarity.jaccard(sh[a], sh[b])
        if ra["split"] == rb["split"]:
            nearest_same[a] = max(nearest_same[a], sim)
            nearest_same[b] = max(nearest_same[b], sim)
        else:
            if sim >= threshold:
                problems.append(f"near duplicate across splits ({sim:.3f}): {a} ({ra['split']}) ~ {b} ({rb['split']})")
            for x, y in ((a, b), (b, a)):
                if sim > nearest_cross[x][0]:
                    nearest_cross[x] = (sim, y)
    families: dict[str, set[str]] = {}
    for r in records:
        families.setdefault(r["family"], set()).add(r["split"])
    problems += [f"family {f} spans splits {sorted(s)}" for f, s in families.items() if len(s) > 1]
    protected = {
        rid: {
            "nearest_training_record": nearest_cross[rid][1]
            if by_id.get(str(nearest_cross[rid][1]), {}).get("split") in TRAINING_SPLITS
            else None,
            "max_similarity_to_other_splits": round(nearest_cross[rid][0], 4),
        }
        for rid in sorted(by_id)
        if by_id[rid]["split"] in PROTECTED_SPLITS
    }
    report = {
        "threshold": threshold,
        "method": "Jaccard of 4-token shingles over the normalized instruction and input; exact = identical tokens",
        "problems": sorted(problems),
        "protected": protected,
        "max_cross_split_similarity": round(max((v[0] for v in nearest_cross.values()), default=0.0), 4),
    }
    return report, nearest_same


def load_lock(config: Config) -> dict[str, Any]:
    path = config.path("splits.lock.json")
    if not path.exists():
        return {"schema": "blux.dataset-split-lock", "dataset": config.dataset_id, "records": {}}
    lock = load_json(path)
    check(LOCK, lock, "splits.lock.json")
    return lock  # type: ignore[no-any-return]


def lock_problems(lock: dict[str, Any], records: list[dict[str, Any]], retired: list[str]) -> list[str]:
    """Split locking and immutability: a locked id keeps its split and content forever."""
    problems = []
    locked = lock["records"]
    built = {r["record_id"]: r for r in records}
    for rid, r in built.items():
        entry = locked.get(rid)
        if entry is None:
            problems.append(f"{rid} is not in splits.lock.json (run `python -m dstool lock --update`)")
        elif entry["status"] == "retired":
            problems.append(f"{rid} was retired; ids are never reused (add a new variant instead)")
        elif entry["split"] != r["split"]:
            problems.append(f"{rid} is locked to {entry['split']} but its seed now says {r['split']}")
        elif entry["content_sha256"] != r["hashes"]["content_sha256"]:
            problems.append(
                f"{rid} changed after it was locked; records are immutable (retire it and add a new "
                "variant, or restore the seed / engine pin)"
            )
    for rid, entry in locked.items():
        if entry["status"] == "active" and rid not in built:
            if rid in retired:
                problems.append(f"{rid} is newly retired (run `python -m dstool lock --update`)")
            else:
                problems.append(f"{rid} is locked but no longer built; retire it explicitly in its seed")
    return problems


def update_lock(
    config: Config, lock: dict[str, Any], records: list[dict[str, Any]], retired: list[str]
) -> dict[str, Any]:
    locked = dict(lock["records"])
    for r in records:
        entry = locked.get(r["record_id"])
        if entry is not None and (
            entry["status"] == "retired"
            or entry["split"] != r["split"]
            or entry["content_sha256"] != r["hashes"]["content_sha256"]
        ):
            raise DsError("IMMUTABLE", lock_problems(lock, [r], [])[0])
        if entry is None:
            locked[r["record_id"]] = {
                "split": r["split"],
                "content_sha256": r["hashes"]["content_sha256"],
                "status": "active",
                "since": config.raw["version"],
            }
    for rid in retired:
        if rid in locked:
            locked[rid] = {**locked[rid], "status": "retired"}
    return {**lock, "records": dict(sorted(locked.items()))}


def run(config: Config, *, adapter: Adapter | None = None) -> Result:
    adapter = adapter or load(config.raw["adapter"])
    adapter.check_engines(config)
    drafts, excluded = load_all(config)
    terms = private_terms(config.root)
    result = Result(excluded=excluded)
    candidates = []
    for draft in sorted(drafts, key=lambda d: d.record_id):
        if draft.retired:
            result.retired.append(draft.record_id)
            continue
        adapter.check_input(draft.input, draft.record_id)
        expected = adapter.generate(draft.input)
        if canonical(adapter.generate(draft.input)) != canonical(expected):
            raise DsError("NOT_REPRODUCIBLE", f"{draft.record_id}: two engine runs disagree")
        record = make_record(config, draft, expected)
        problems = gates(config, adapter, record, terms)
        if problems:
            raise DsError("GATE", f"{draft.record_id}: " + "; ".join(problems[:5]))
        candidates.append(record)
    candidates, dropped, exact_problems = dedup(candidates)
    result.excluded.extend(dropped)
    report, nearest = contamination(candidates, config.raw["near_duplicate_threshold"])
    report["problems"] = sorted(report["problems"] + exact_problems)
    report["duplicates_dropped"] = dropped
    if report["problems"]:
        raise DsError("CONTAMINATION", "; ".join(report["problems"][:10]))
    for record in candidates:
        comps = quality.components(
            record["task"]["instruction"],
            record["input"],
            evidence=adapter.evidence(record["input"]),
            informative=adapter.informative(record["expected"]),
            max_similarity=nearest[record["record_id"]],
        )
        record["quality"] = {
            "score": quality.score(comps),
            "threshold": config.raw["quality_threshold"],
            "components": comps,
        }
        if record["quality"]["score"] < config.raw["quality_threshold"]:
            result.excluded.append(
                {"record_id": record["record_id"], "reason": "quality", "score": record["quality"]["score"]}
            )
        else:
            result.records.append(record)
    result.contamination = report
    return result


def outputs(config: Config, result: Result) -> dict[Path, str]:
    """The exact bytes of every generated file."""
    files: dict[Path, str] = {}
    entries = {}
    for split in SPLITS:
        lines = [canonical(r) for r in result.records if r["split"] == split]
        text = "".join(line + "\n" for line in lines)
        files[config.path("data", f"{split}.jsonl")] = text
        entries[f"data/{split}.jsonl"] = {"sha256": sha256_text(text), "records": len(lines)}
    report_text = canonical_pretty(result.contamination)
    files[config.path("data", "contamination.json")] = report_text
    entries["data/contamination.json"] = {"sha256": sha256_text(report_text), "records": 0}
    by_split = {s: sum(r["split"] == s for r in result.records) for s in SPLITS}
    by_category = {
        c: {s: sum(r["category"] == c and r["split"] == s for r in result.records) for s in SPLITS}
        for c in config.categories
    }
    manifest = {
        "schema": "blux.dataset-manifest",
        "dataset": config.dataset_id,
        "version": config.raw["version"],
        "release_date": config.raw["release_date"],
        "license": config.raw["license"],
        "generator": {"name": TOOL_NAME, "version": TOOL_VERSION},
        "engines": config.raw["engines"],
        "canary": config.canary,
        "splits": by_split,
        "categories": by_category,
        "files": entries,
        "records_sha256": sha256_of([[r["record_id"], r["hashes"]["content_sha256"]] for r in result.records]),
        "record_count": len(result.records),
        "protected_splits": list(PROTECTED_SPLITS),
        "training_splits": list(TRAINING_SPLITS),
        "excluded": result.excluded,
    }
    files[config.path("data", "manifest.json")] = canonical_pretty(manifest)
    return files


def canonical_pretty(doc: Any) -> str:
    import json

    return json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
