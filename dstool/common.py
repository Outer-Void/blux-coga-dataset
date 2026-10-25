"""Shared helpers: errors, canonical JSON, hashing, configuration."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

TOOL_NAME = "dstool"
TOOL_VERSION = "1.0.0"
SPLITS = ("train", "validation", "test", "holdout", "adversarial", "regression")
TRAINING_SPLITS = ("train", "validation")
PROTECTED_SPLITS = ("test", "holdout", "adversarial", "regression")


class DsError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def canonical(doc: Any) -> str:
    return json.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_of(doc: Any) -> str:
    return sha256_text(canonical(doc))


def _no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise DsError("INVALID_JSON", f"duplicate key {key!r}")
        out[key] = value
    return out


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_no_duplicates)
    except (OSError, ValueError) as exc:
        if isinstance(exc, DsError):
            raise DsError(exc.code, f"{path}: {exc.message}") from None
        raise DsError("INVALID_JSON", f"{path}: {exc}") from None


def dump_json(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


@dataclass(frozen=True)
class Config:
    root: Path
    raw: dict[str, Any]

    @property
    def dataset_id(self) -> str:
        return str(self.raw["dataset_id"])

    @property
    def prefix(self) -> str:
        return str(self.raw["id_prefix"])

    @property
    def categories(self) -> list[str]:
        return [c["id"] for c in self.raw["categories"]]

    @property
    def canary(self) -> str:
        return str(self.raw["canary"])

    def path(self, *parts: str) -> Path:
        return self.root.joinpath(*parts)


def load_config(root: Path) -> Config:
    from dstool.schemas import CONFIG, check

    raw = load_json(root / "dataset.json")
    check(CONFIG, raw, "dataset.json")
    return Config(root.resolve(), raw)
