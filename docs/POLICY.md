# Dataset Policy

## Purpose

This repository detects drift in `blux-coga`; it does **not** define or legislate reasoning behavior. The engine contract lives in the real `Outer-Void/blux-coga` repository, and this dataset mirrors deterministic outputs from that engine.

## Current mapping

- Engine repo: `Outer-Void/blux-coga`
- Engine branch: `main`
- Verified engine commit for this dataset pass: `10b5b8e32f59f07f93a85d647d6f326acb7c1bc2`
- Package release: `blux-coga` `1.0.0`
- Engine line: `CogA-1.0-pro`
- Contract version: `1.0`
- Schema version: `1.0`
- Reasoning pack coverage here: `default@1.0`

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
5. Run `BLUX_COGA_REPO=/path/to/blux-coga ./scripts/run_harness.sh`.
6. Run `python ./scripts/export_fixtures.py --output dist/blux-coga-dataset.jsonl`.
7. Update docs and schemas in the same change if fixture structure or expectations changed.

When `BLUX_COGA_REPO` points at a source checkout, the dataset harness treats `<repo>/src` as the canonical import root and still invokes the engine through `blux-coga run --input ... --output-dir ...`. This removes reliance on older undocumented wrapper assumptions.

## Determinism requirements

- Expected artifacts must be direct engine outputs.
- Compatibility history may be documented, but only runnable current-engine outputs should be required by the harness.
- The repo should remain export-friendly: one fixture maps deterministically to a single export row containing `problem`, `thought_artifact`, `reasoning_verdict`, and `metadata`.
- Deterministic export means compact JSONL with stable fixture order, stable key order, and byte-identical re-runs.

## Drift discipline

If verification shows drift, do not patch expectations casually. Re-run the actual engine, confirm the contract change, then update fixtures, schemas, export docs, and version mapping together.
