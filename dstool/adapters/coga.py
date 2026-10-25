"""CogA 2 adapter. Input: {"capability": "reason.*", "request": <coga.request>}.

Expected: {"kind": "artifact", "output": <coga.artifact>} or {"kind": "error", "output": {"code", "message",
"details"}}. Artifacts are validated against the artifact schema the installed engine ships.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from dstool.adapters import require_version
from dstool.common import Config, DsError
from dstool.schemas import check

EVIDENCE_CAPABILITIES = ("reason.analyze", "reason.critique", "reason.risk", "reason.compare")
INPUT = {
    "type": "object",
    "additionalProperties": False,
    "required": ["capability", "request"],
    "properties": {
        "capability": {
            "enum": [
                "reason.analyze",
                "reason.plan",
                "reason.compare",
                "reason.decompose",
                "reason.critique",
                "reason.rank",
                "reason.risk",
            ]
        },
        "request": {},
    },
}
ERROR = {
    "type": "object",
    "additionalProperties": False,
    "required": ["code", "message", "details"],
    "properties": {
        "code": {"type": "string", "pattern": "^[A-Z_]+$"},
        "message": {"type": "string"},
        "details": {"type": "object"},
    },
}


class CogaAdapter:
    def check_engines(self, config: Config) -> None:
        try:
            from blux_coga.reason import ENGINE_VERSION
        except ImportError:
            raise DsError("ENGINE_MISSING", "blux-coga is not installed (pip install the pinned commit)") from None
        require_version(config, "coga", ENGINE_VERSION)

    def check_input(self, input_doc: dict[str, Any], where: str) -> None:
        check(INPUT, input_doc, where)

    def generate(self, input_doc: dict[str, Any]) -> dict[str, Any]:
        from blux_coga.reason import CogaError, run

        request = json.loads(json.dumps(input_doc["request"]))
        try:
            return {"kind": "artifact", "output": run(input_doc["capability"], request)}
        except CogaError as exc:
            return {"kind": "error", "output": {"code": exc.code, "message": exc.message, "details": exc.details}}

    def check_expected(self, expected: dict[str, Any], where: str) -> None:
        import blux_coga.reason as reason

        if expected.get("kind") == "error":
            check(ERROR, expected.get("output"), where)
            return
        if expected.get("kind") != "artifact":
            raise DsError("SCHEMA", f"{where}: expected.kind must be artifact or error")
        artifact = expected["output"]
        schemas = Path(reason.__file__).parent / "schemas"
        schema = json.loads((schemas / f"{artifact.get('capability')}.artifact.v1.json").read_text())
        check(schema, artifact, where)

    def rejected(self, expected: dict[str, Any]) -> bool:
        return bool(expected["kind"] == "error")

    def evidence(self, input_doc: dict[str, Any]) -> float | None:
        if input_doc["capability"] not in EVIDENCE_CAPABILITIES:
            return None
        return 1.0 if input_doc["request"].get("evidence") else 0.0

    def informative(self, expected: dict[str, Any]) -> float:
        out = expected["output"]
        if expected["kind"] == "error":
            return 1.0 if out.get("code") else 0.0
        said = out.get("findings") or out.get("uncertainty", {}).get("sources") or out.get("result", {}).get("findings")
        return 1.0 if said else 0.5
