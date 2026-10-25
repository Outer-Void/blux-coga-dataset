"""Engine adapters: turn a draft's input into the engine's real output (the record's `expected`)."""

from __future__ import annotations

from typing import Any, Protocol

from dstool.common import Config, DsError


class Adapter(Protocol):
    def check_engines(self, config: Config) -> None: ...
    def check_input(self, input_doc: dict[str, Any], where: str) -> None: ...
    def generate(self, input_doc: dict[str, Any]) -> dict[str, Any]: ...
    def check_expected(self, expected: dict[str, Any], where: str) -> None: ...
    def rejected(self, expected: dict[str, Any]) -> bool: ...
    def evidence(self, input_doc: dict[str, Any]) -> float | None: ...
    def informative(self, expected: dict[str, Any]) -> float: ...


def load(name: str) -> Adapter:
    if name == "coga":
        from dstool.adapters.coga import CogaAdapter

        return CogaAdapter()
    if name == "ca":
        from dstool.adapters.ca import CaAdapter

        return CaAdapter()
    raise DsError("CONFIG", f"unknown adapter {name!r}")


def engine_pin(config: Config, name: str) -> dict[str, Any]:
    for engine in config.raw["engines"]:
        if engine["name"] == name:
            return engine  # type: ignore[no-any-return]
    raise DsError("CONFIG", f"dataset.json pins no {name!r} engine")


def require_version(config: Config, name: str, installed: str) -> None:
    pinned = engine_pin(config, name)["version"]
    if installed != pinned:
        raise DsError(
            "ENGINE_MISMATCH",
            f"{name} {installed} is installed but dataset.json pins {pinned}; "
            "records are only reproducible with the pinned engine",
        )
