"""Exports: the only way records leave the repository for training or evaluation.

`training` is the one training generation path. It reads only the training splits (train, validation),
and refuses to run if any record it would emit is protected: in a protected split, carrying the canary,
or locked to a protected split. Protected splits (test, holdout, adversarial, regression) can only be
exported for `evaluation`, and keep their canary so leaks into a training corpus can be detected.
"""

from __future__ import annotations

from typing import Any

from dstool.build import load_lock
from dstool.common import PROTECTED_SPLITS, SPLITS, TRAINING_SPLITS, Config, DsError, canonical
from dstool.validate import read_split

TRAINING_FIELDS = ("record_id", "category", "split", "task", "input", "expected")


def training_records(config: Config, splits: tuple[str, ...] = TRAINING_SPLITS) -> list[dict[str, Any]]:
    bad = [s for s in splits if s not in TRAINING_SPLITS]
    if bad:
        raise DsError("PROTECTED_SPLIT", f"{bad} are protected and can never be exported for training")
    lock = load_lock(config)["records"]
    out = []
    for split in splits:
        for r in read_split(config, split):
            locked = lock.get(r["record_id"], {}).get("split")
            if r["split"] in PROTECTED_SPLITS or r.get("canary") or locked in PROTECTED_SPLITS:
                raise DsError("PROTECTED_RECORD", f"{r['record_id']} is protected; refusing to emit it for training")
            if config.canary in canonical(r):
                raise DsError("PROTECTED_RECORD", f"{r['record_id']} contains the canary")
            out.append({k: r[k] for k in TRAINING_FIELDS})
    return out


def evaluation_records(config: Config, splits: tuple[str, ...]) -> list[dict[str, Any]]:
    unknown = [s for s in splits if s not in SPLITS]
    if unknown:
        raise DsError("USAGE", f"unknown splits {unknown}")
    return [r for split in splits for r in read_split(config, split)]


def to_jsonl(records: list[dict[str, Any]]) -> str:
    return "".join(canonical(r) + "\n" for r in records)
