"""Import external material as a seed. Imports are never used automatically.

An imported seed is written with `origin: imported` and `review.status: pending`, and the build skips it.
It needs an explicit licence and source, must pass the privacy scan, and can only target the train,
validation or test splits: holdout, adversarial and regression are authored only. `promote` marks a
seed approved once a named person has reviewed it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from dstool.common import Config, DsError, dump_json, load_json
from dstool.scan import privacy_hits, private_terms
from dstool.schemas import SEED, check
from dstool.seeds import load_seed

IMPORT_SPLITS = ("train", "validation", "test")


def import_seed(
    config: Config,
    source_file: Path,
    *,
    family: str,
    category: str,
    split: str,
    license_spdx: str,
    license_name: str,
    source: str,
) -> Path:
    if split not in IMPORT_SPLITS:
        raise DsError("PROTECTED_SPLIT", f"imports may target {IMPORT_SPLITS}, not {split}")
    doc = load_json(source_file)
    if not isinstance(doc, dict) or not {"instruction", "input", "variants"} <= set(doc):
        raise DsError("IMPORT", "the file must hold instruction, input and variants")
    hits = privacy_hits({k: doc[k] for k in ("instruction", "input", "variants")}, private_terms(config.root))
    if hits:
        raise DsError("PRIVACY", "refusing to import: " + "; ".join(hits[:5]))
    seed: dict[str, Any] = {
        "schema": "blux.dataset-seed",
        "family": family,
        "category": category,
        "split": split,
        "origin": "imported",
        "review": {"status": "pending"},
        "source": source,
        "license": {"spdx": license_spdx, "name": license_name},
        "instruction": doc["instruction"],
        "input": doc["input"],
        "variants": doc["variants"],
    }
    if "tags" in doc:
        seed["tags"] = doc["tags"]
    target = config.path("seeds", "imported", f"{family}.json")
    if target.exists() or any(config.path("seeds").rglob(f"{family}.json")):
        raise DsError("IMPORT", f"family {family} already exists")
    check(SEED, seed, str(target))
    dump_json(target, seed)
    return target


def promote(config: Config, family: str, reviewer: str, note: str | None = None) -> Path:
    matches = list(config.path("seeds").rglob(f"{family}.json"))
    if len(matches) != 1:
        raise DsError("PROMOTE", f"no single seed for family {family}")
    doc = load_json(matches[0])
    if doc["review"]["status"] == "approved":
        raise DsError("PROMOTE", f"{family} is already approved")
    doc["review"] = {"status": "approved", "reviewer": reviewer, **({"note": note} if note else {})}
    dump_json(matches[0], doc)
    load_seed(config, matches[0])  # still a valid seed
    return matches[0]
