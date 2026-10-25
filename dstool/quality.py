"""Deterministic quality scoring.

Gates (a record failing one is not built at all): schema-valid, reproducible (two engine runs agree),
privacy scan clean, hidden-reasoning scan clean.

Scored components, each 0-1 (or null when it does not apply), averaged into `score`:

| component | 1.0 when | otherwise |
|---|---|---|
| instruction_length | 60-1500 characters | 0.5 |
| grounding | the instruction names at least one identifier or path from the input | 0.0 |
| evidence | the request carries evidence (CogA capabilities that take evidence) | 0.0; null when not applicable |
| informative | the output says something: findings, uncertainty sources, a non-empty changeset, an error | 0.5 |
| distinct | the record's highest similarity to another family in the same split is below 0.5 | 1 - similarity, scaled |

Records under the dataset's `quality_threshold` are excluded from the build and listed in the manifest.
"""

from __future__ import annotations

from typing import Any


def _identifiers(value: Any, out: set[str]) -> None:
    if isinstance(value, dict):
        for k, v in value.items():
            if k in ("id", "path", "task", "capability") and isinstance(v, str) and len(v) >= 3:
                out.add(v.lower())
            _identifiers(v, out)
    elif isinstance(value, list):
        for v in value:
            _identifiers(v, out)


def grounding(instruction: str, input_doc: dict[str, Any]) -> float:
    names: set[str] = set()
    _identifiers(input_doc, names)
    files = input_doc.get("workspace", {}).get("files", {}) if isinstance(input_doc.get("workspace"), dict) else {}
    names.update(p.lower() for p in files)
    text = instruction.lower()
    return 1.0 if any(n in text for n in names) else 0.0


def score(components: dict[str, float | None]) -> float:
    values = [v for v in components.values() if v is not None]
    return round(sum(values) / len(values), 4) if values else 0.0


def components(
    instruction: str, input_doc: dict[str, Any], *, evidence: float | None, informative: float, max_similarity: float
) -> dict[str, float | None]:
    return {
        "instruction_length": 1.0 if 60 <= len(instruction) <= 1500 else 0.5,
        "grounding": grounding(instruction, input_doc),
        "evidence": evidence,
        "informative": informative,
        "distinct": 1.0 if max_similarity < 0.5 else round(max(0.0, 1.0 - max_similarity) * 2, 4),
    }
