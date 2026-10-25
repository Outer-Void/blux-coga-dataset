"""Validate the committed dataset without regenerating it.

Checks every record (schema, adapter input/expected schemas, hashes, id/family/variant agreement, split file,
canary), the privacy and hidden-reasoning gates, exact and near-duplicate contamination across splits, the
split lock, and the manifest's file hashes and counts. `build --check` separately proves the files are
exactly what the pinned engines produce.
"""

from __future__ import annotations

from typing import Any

from dstool.adapters import Adapter, load
from dstool.build import _content, contamination, dedup, gates, load_lock, lock_problems
from dstool.common import PROTECTED_SPLITS, SPLITS, Config, DsError, load_json, sha256_of, sha256_text
from dstool.scan import private_terms
from dstool.schemas import MANIFEST, check


def read_split(config: Config, split: str) -> list[dict[str, Any]]:
    import json

    path = config.path("data", f"{split}.jsonl")
    if not path.exists():
        return []
    records = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        try:
            records.append(json.loads(line))
        except ValueError as exc:
            raise DsError("INVALID_JSON", f"data/{split}.jsonl line {n}: {exc}") from None
    return records


def read_all(config: Config) -> list[dict[str, Any]]:
    return [r for split in SPLITS for r in read_split(config, split)]


def validate(config: Config, adapter: Adapter | None = None) -> dict[str, Any]:
    adapter = adapter or load(config.raw["adapter"])
    terms = private_terms(config.root)
    problems: list[str] = []
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for split in SPLITS:
        for r in read_split(config, split):
            rid = r.get("record_id", "?")
            records.append(r)
            problems += [f"{rid}: {p}" for p in gates(config, adapter, r, terms)]
            if rid in seen:
                problems.append(f"{rid}: duplicate record id")
            seen.add(rid)
            if r.get("split") != split:
                problems.append(f"{rid}: stored in data/{split}.jsonl but its split is {r.get('split')}")
            if rid != f"{config.prefix}:{r.get('family')}:{r.get('variant')}":
                problems.append(f"{rid}: id does not match family and variant")
            if not isinstance(r.get("hashes"), dict):
                continue
            if r["hashes"].get("content_sha256") != sha256_of(_content(r)):
                problems.append(f"{rid}: content_sha256 does not match the record")
            if r["hashes"].get("input_sha256") != sha256_of(r["input"]):
                problems.append(f"{rid}: input_sha256 does not match")
            if r["hashes"].get("expected_sha256") != sha256_of(r["expected"]):
                problems.append(f"{rid}: expected_sha256 does not match")
            want = config.canary if split in PROTECTED_SPLITS else None
            if r.get("canary") != want:
                problems.append(f"{rid}: canary must be {'the dataset canary' if want else 'null'} in {split}")
            if r.get("quality", {}).get("score", 0) < config.raw["quality_threshold"]:
                problems.append(f"{rid}: quality score below the threshold")
    _, dropped, exact = dedup(records)
    problems += exact + [f"{d['record_id']}: duplicate of {d['duplicate_of']}" for d in dropped]
    report, _ = contamination(records, config.raw["near_duplicate_threshold"])
    problems += report["problems"]
    retired = [rid for rid, e in load_lock(config)["records"].items() if e["status"] == "retired"]
    problems += lock_problems(load_lock(config), records, retired)
    manifest_path = config.path("data", "manifest.json")
    if manifest_path.exists():
        manifest = load_json(manifest_path)
        check(MANIFEST, manifest, "data/manifest.json")
        for rel, entry in manifest["files"].items():
            path = config.path(rel)
            if not path.exists() or sha256_text(path.read_text(encoding="utf-8")) != entry["sha256"]:
                problems.append(f"manifest: {rel} does not match its recorded sha256")
        if manifest["record_count"] != len(records):
            problems.append("manifest: record_count does not match the data files")
        if manifest["canary"] != config.canary:
            problems.append("manifest: canary does not match dataset.json")
    else:
        problems.append("data/manifest.json is missing")
    return {"records": len(records), "problems": problems, "ok": not problems}
