# Dataset Policy

## Purpose

This repository detects drift in `blux-coga`; it does **not** define or legislate reasoning behavior. The engine contract lives in the real `Outer-Void/blux-coga` repository, and this dataset mirrors deterministic outputs from that engine.

## Current mapping

- Engine line: `CogA-1.0-pro`
- Contract version: `1.0`
- Schema version: `1.0`
- Reasoning pack coverage here: `default`

## Naming policy

Use the exact engine version naming convention everywhere:

- `CogA-<major>.<minor>`
- `CogA-<major>.<minor>-pro`

Lowercase `coga-*` paths and mixed naming are stale and should not be reintroduced.

## Fixture update workflow

1. Update or add a real `ProblemSpec` in `problem.json`.
2. Keep `metadata.json` in sync with the expected engine line and scenario metadata.
3. Regenerate expected artifacts by running the real engine through the canonical file-based path.
4. Run `./scripts/verify_fixtures.sh`.
5. Run `./scripts/run_harness.sh` against a local `blux-coga` checkout or installed binary.
6. Update docs and schemas in the same change if fixture structure or expectations changed.

## Determinism requirements

- Expected artifacts must be direct engine outputs.
- Compatibility history may be documented, but only runnable current-engine outputs should be required by the harness.
- The repo should remain export-friendly: one fixture maps deterministically to `problem`, `thought_artifact`, `reasoning_verdict`, and `metadata`.
