"""cA 2 adapter (with DAT for validation-aware steps).

Input:

    {"workspace": {"files": {"path": "text", ...}, "executable": ["path", ...]},
     "steps": [step, ...]}

Steps run in order against one throw-away workspace (`ws`, so results never contain a real path):

- `{"capability": C, "request": R}`: run cA capability C with R (workspace set to `ws`) -> `result` or `error`.
  With `"dat": {"fail_on": S, "profile": P}`, DAT runs first (`dat P`: quality by default, or security or
  audit) and its report becomes R.report
  (-> `dat-report`, then `result` or `error`).
- `{"command": "dat", "fail_on": S, "profile": P}`: DAT (`dat P`, quality by default) -> `dat-report`.
- `{"command": "rollback", "step": i}`: `ca rollback` of the changeset step i applied -> `rollback` or `error`.
- `{"command": "interrupt", "capability": C, "request": R, "after_writes": n}`: C in a child process killed
  after n file writes -> `interrupted`.
- `{"command": "recover"}`: `ca recover` -> `recovery`.

Expected: {"steps": [{"kind", "output"}, ...], "final_tree": [{"path", "mode", "sha256"}, ...]}.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from dstool.adapters import engine_pin, require_version
from dstool.common import Config, DsError
from dstool.schemas import check

CAPS = [
    "artifact.construct",
    "artifact.modify",
    "artifact.repair",
    "artifact.validate",
    "code.patch",
    "repo.patch",
    "config.generate",
]
SEV = {"enum": ["info", "low", "medium", "high", "critical"]}
PROFILE = {"enum": ["quality", "security", "audit"]}
DAT = {
    "type": "object",
    "additionalProperties": False,
    "required": ["fail_on"],
    "properties": {"fail_on": SEV, "profile": PROFILE},
}
STEP = {
    "oneOf": [
        {
            "type": "object",
            "additionalProperties": False,
            "required": ["capability", "request"],
            "properties": {
                "capability": {"enum": CAPS},
                "request": {"type": "object"},
                "dat": DAT,
            },
        },
        {
            "type": "object",
            "additionalProperties": False,
            "required": ["command", "fail_on"],
            "properties": {"command": {"const": "dat"}, "fail_on": SEV, "profile": PROFILE},
        },
        {
            "type": "object",
            "additionalProperties": False,
            "required": ["command", "step"],
            "properties": {"command": {"const": "rollback"}, "step": {"type": "integer", "minimum": 0}},
        },
        {
            "type": "object",
            "additionalProperties": False,
            "required": ["command", "capability", "request", "after_writes"],
            "properties": {
                "command": {"const": "interrupt"},
                "capability": {"enum": CAPS},
                "request": {"type": "object"},
                "after_writes": {"type": "integer", "minimum": 1},
            },
        },
        {
            "type": "object",
            "additionalProperties": False,
            "required": ["command"],
            "properties": {"command": {"const": "recover"}},
        },
    ]
}
INPUT = {
    "type": "object",
    "additionalProperties": False,
    "required": ["workspace", "steps"],
    "properties": {
        "workspace": {
            "type": "object",
            "additionalProperties": False,
            "required": ["files"],
            "properties": {
                "files": {"type": "object", "additionalProperties": {"type": "string"}},
                "executable": {"type": "array", "items": {"type": "string"}, "uniqueItems": True},
            },
        },
        "steps": {"type": "array", "minItems": 1, "maxItems": 12, "items": STEP},
    },
}
KINDS = ("result", "error", "dat-report", "rollback", "interrupted", "recovery")
CRASH = """
import os, sys
from pathlib import Path
from blux_ca.construction import workspace as wsmod
real, count, limit = wsmod._replace, {"n": 0}, int(sys.argv[1])
def crash(src, dst):
    if ".ca" not in Path(dst).parts:
        count["n"] += 1
        if count["n"] > limit:
            os._exit(137)
    real(src, dst)
wsmod._replace = crash
from blux_ca.construction.cli import main
sys.exit(main(sys.argv[2:]))
"""


class CaAdapter:
    def __init__(self) -> None:
        self.dat = os.environ.get("DSTOOL_DAT", "dat")

    def check_engines(self, config: Config) -> None:
        try:
            from blux_ca.construction import ENGINE_VERSION
        except ImportError:
            raise DsError("ENGINE_MISSING", "blux-ca is not installed (pip install the pinned commit)") from None
        require_version(config, "ca", ENGINE_VERSION)
        engine_pin(config, "dat")
        try:
            out = subprocess.run([self.dat, "version"], capture_output=True, check=True, timeout=60).stdout
        except (OSError, subprocess.CalledProcessError) as exc:
            raise DsError("ENGINE_MISSING", f"DAT is not runnable ({self.dat}): {exc}") from None
        require_version(config, "dat", json.loads(out)["version"])

    def check_input(self, input_doc: dict[str, Any], where: str) -> None:
        check(INPUT, input_doc, where)
        for i, step in enumerate(input_doc["steps"]):
            if "workspace" in step.get("request", {}):
                raise DsError("SEED", f"{where}: step {i} must not name a workspace (it is always ws)")
            if step.get("command") == "rollback" and step["step"] >= i:
                raise DsError("SEED", f"{where}: step {i} rolls back a later step")

    def _dat(self, cwd: Path, fail_on: str, profile: str = "quality") -> dict[str, Any]:
        proc = subprocess.run(
            [self.dat, profile, "ws", "--format", "json", "--fail-on", fail_on],
            cwd=cwd,
            capture_output=True,
            timeout=600,
            check=False,
        )
        if proc.returncode not in (0, 1):
            raise DsError("ENGINE_FAILED", f"DAT failed (exit {proc.returncode}): {proc.stderr[-400:]!r}")
        return json.loads(proc.stdout)  # type: ignore[no-any-return]

    def generate(self, input_doc: dict[str, Any]) -> dict[str, Any]:
        from blux_ca.construction import CaError, api
        from blux_ca.construction.workspace import Workspace

        with tempfile.TemporaryDirectory(prefix="dstool-ca-") as tmp:
            base = Path(tmp)
            ws = base / "ws"
            ws.mkdir()
            spec = input_doc["workspace"]
            for rel, text in spec["files"].items():
                target = ws / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(text, encoding="utf-8")
                os.chmod(target, 0o755 if rel in spec.get("executable", []) else 0o644)
            out: list[dict[str, Any]] = []
            applied: dict[int, str] = {}
            for i, step in enumerate(input_doc["steps"]):
                command = step.get("command")
                if command == "dat":
                    out.append(
                        {
                            "kind": "dat-report",
                            "output": self._dat(base, step["fail_on"], step.get("profile", "quality")),
                        }
                    )
                    continue
                if command == "recover":
                    out.append({"kind": "recovery", "output": Workspace(ws).recover()})
                    continue
                if command == "rollback":
                    try:
                        undo, entry = Workspace(ws).rollback(applied[step["step"]])
                        out.append(
                            {
                                "kind": "rollback",
                                "output": {
                                    "changeset": undo,
                                    "ledger": {k: entry[k] for k in ("seq", "tree_before", "tree_after")},
                                },
                            }
                        )
                    except (CaError, KeyError) as exc:
                        out.append({"kind": "error", "output": _error(exc)})
                    continue
                request = {**json.loads(json.dumps(step["request"])), "workspace": "ws"}
                if command == "interrupt":
                    (base / "req.json").write_text(json.dumps(request))
                    cmd = [sys.executable, "-c", CRASH, str(step["after_writes"]), _cli(step["capability"]), "req.json"]
                    proc = subprocess.run(cmd, cwd=base, capture_output=True, timeout=120, check=False)
                    out.append(
                        {
                            "kind": "interrupted",
                            "output": {
                                "exit_code": proc.returncode,
                                "journal_left": (ws / ".ca" / "journal.json").exists(),
                            },
                        }
                    )
                    continue
                if "dat" in step:
                    report = self._dat(base, step["dat"]["fail_on"], step["dat"].get("profile", "quality"))
                    out.append({"kind": "dat-report", "output": report})
                    request["report"] = report
                try:
                    result = api.run(step["capability"], request, base=base)
                    out.append({"kind": "result", "output": result})
                    if result.get("status") == "applied":
                        applied[i] = result["changeset"]["changeset_id"]
                except CaError as exc:
                    out.append({"kind": "error", "output": _error(exc)})
            workspace = Workspace(ws)
            tree = []
            for rel, _st in workspace.files():
                state = workspace.read(rel)
                tree.append({"path": rel, "mode": state.mode, "sha256": state.sha256})
            return {"steps": out, "final_tree": tree}

    def check_expected(self, expected: dict[str, Any], where: str) -> None:
        from blux_ca.construction import spec

        check(
            {
                "type": "object",
                "additionalProperties": False,
                "required": ["steps", "final_tree"],
                "properties": {
                    "steps": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["kind", "output"],
                            "properties": {"kind": {"enum": list(KINDS)}},
                        },
                    },
                    "final_tree": {"type": "array"},
                },
            },
            expected,
            where,
        )
        for i, step in enumerate(expected["steps"]):
            if step["kind"] == "result":
                check(spec.output_schema(step["output"]["capability"]), step["output"], f"{where} step {i}")
                if step["output"]["certified"] is not False:
                    raise DsError("SCHEMA", f"{where} step {i}: cA results are never certified")
            elif step["kind"] == "error":
                check(
                    {"type": "object", "required": ["code", "message", "details"]}, step["output"], f"{where} step {i}"
                )
            elif step["kind"] == "rollback":
                check(spec.CHANGESET, step["output"]["changeset"], f"{where} step {i}")
            elif step["kind"] == "dat-report" and step["output"].get("contract") != "dat.report":
                raise DsError("SCHEMA", f"{where} step {i}: not a dat.report")

    def rejected(self, expected: dict[str, Any]) -> bool:
        return any(s["kind"] == "error" for s in expected["steps"])

    def evidence(self, input_doc: dict[str, Any]) -> float | None:
        return None

    def informative(self, expected: dict[str, Any]) -> float:
        for step in expected["steps"]:
            if step["kind"] in ("error", "rollback", "interrupted", "recovery", "dat-report"):
                return 1.0
            out = step["output"]
            if out.get("contract") == "ca.check" or out.get("findings") or not out["changeset"]["noop"]:
                return 1.0
        return 0.5


def _error(exc: Exception) -> dict[str, Any]:
    code = getattr(exc, "code", "UNKNOWN_CHANGESET")
    return {"code": code, "message": getattr(exc, "message", str(exc)), "details": getattr(exc, "details", {})}


def _cli(capability: str) -> str:
    from blux_ca.construction.cli import COMMANDS

    return str({v: k for k, v in COMMANDS.items()}[capability])
