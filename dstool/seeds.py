"""Seeds: authored (or imported and reviewed) families of records, expanded into drafts.

A seed file holds one family: an instruction and an input with `${param}` placeholders, and numbered
variants that supply the parameters. Substitution is strict: a placeholder without a parameter and a
parameter that no placeholder uses are both errors. A string that is exactly one placeholder takes the
parameter's JSON value (number, list, object …); anywhere else the parameter must be a string or number.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dstool.common import Config, DsError, load_json, sha256_text
from dstool.schemas import SEED, check

PLACEHOLDER = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")
WHOLE = re.compile(r"^\$\{([A-Za-z_][A-Za-z0-9_]*)\}$")


@dataclass(frozen=True)
class Draft:
    record_id: str
    family: str
    variant: str
    category: str
    split: str
    instruction: str
    input: dict[str, Any]
    tags: tuple[str, ...]
    origin: str
    license: dict[str, Any]
    source: str | None
    seed_path: str
    seed_sha256: str
    retired: bool


def _names(value: Any, out: set[str]) -> None:
    if isinstance(value, str):
        out.update(PLACEHOLDER.findall(value))
    elif isinstance(value, list):
        for v in value:
            _names(v, out)
    elif isinstance(value, dict):
        for k, v in value.items():
            _names(k, out)
            _names(v, out)


def _subst(value: Any, params: dict[str, Any], where: str) -> Any:
    if isinstance(value, str):
        whole = WHOLE.match(value)
        if whole:
            return params[whole[1]]

        def one(m: re.Match[str]) -> str:
            v = params[m[1]]
            if isinstance(v, bool) or not isinstance(v, (str, int, float)):
                raise DsError("SEED", f"{where}: ${{{m[1]}}} is embedded in text, so it must be a string or number")
            return str(v)

        return PLACEHOLDER.sub(one, value)
    if isinstance(value, list):
        return [_subst(v, params, where) for v in value]
    if isinstance(value, dict):
        return {_subst(k, params, where): _subst(v, params, where) for k, v in value.items()}
    return value


def load_seed(config: Config, path: Path) -> list[Draft]:
    doc = load_json(path)
    rel = path.relative_to(config.root).as_posix()
    check(SEED, doc, rel)
    if doc["category"] not in config.categories:
        raise DsError("SEED", f"{rel}: unknown category {doc['category']!r}")
    if path.stem != doc["family"]:
        raise DsError("SEED", f"{rel}: file name must be the family id ({doc['family']}.json)")
    wanted: set[str] = set()
    _names(doc["instruction"], wanted)
    _names(doc["input"], wanted)
    seen: set[str] = set()
    drafts = []
    seed_sha = sha256_text(path.read_text(encoding="utf-8"))
    for variant in doc["variants"]:
        where = f"{rel} variant {variant['id']}"
        if variant["id"] in seen:
            raise DsError("SEED", f"{where}: duplicate variant id")
        seen.add(variant["id"])
        params = variant["params"]
        missing, unused = sorted(wanted - set(params)), sorted(set(params) - wanted)
        if missing or unused:
            raise DsError("SEED", f"{where}: missing parameters {missing}, unused parameters {unused}")
        drafts.append(
            Draft(
                record_id=f"{config.prefix}:{doc['family']}:{variant['id']}",
                family=doc["family"],
                variant=variant["id"],
                category=doc["category"],
                split=doc["split"],
                instruction=_subst(doc["instruction"], params, where),
                input=_subst(doc["input"], params, where),
                tags=tuple(doc.get("tags", [])),
                origin=doc["origin"],
                license=doc.get("license", config.raw["license"]),
                source=doc.get("source"),
                seed_path=rel,
                seed_sha256=seed_sha,
                retired=bool(variant.get("retired", False)),
            )
        )
    return drafts


def load_all(config: Config) -> tuple[list[Draft], list[dict[str, Any]]]:
    """Every approved draft, plus a list of seeds left out (pending review) with the reason."""
    drafts: list[Draft] = []
    excluded: list[dict[str, Any]] = []
    families: dict[str, str] = {}
    for path in sorted(config.path("seeds").rglob("*.json")):
        doc = load_json(path)
        rel = path.relative_to(config.root).as_posix()
        family = doc.get("family")
        if family in families:
            raise DsError("SEED", f"{rel}: family {family!r} is also defined in {families[family]}")
        families[str(family)] = rel
        if doc.get("review", {}).get("status") != "approved":
            check(SEED, doc, rel)
            excluded.append({"seed": rel, "reason": "review pending"})
            continue
        drafts.extend(load_seed(config, path))
    return drafts, excluded
