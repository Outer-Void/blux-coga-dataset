---
pretty_name: BLUX CogA Dataset
license: other
license_name: BLUX Proprietary License
tags:
  - reasoning
  - deterministic-ai
  - evaluation
task_categories:
  - text-generation
---

# blux-coga-dataset

Deterministic drift-detection fixtures for the real `Outer-Void/blux-coga` engine live here. This repo does **not** define reasoning behavior; it records real engine outputs so later runs can detect drift against the engine's current contract and boundary behavior.

## Engine mapping frozen by this dataset

- Canonical engine repo: `Outer-Void/blux-coga`
- Engine repo default branch: `main`
- Verified upstream commit for this finalization pass: `10b5b8e32f59f07f93a85d647d6f326acb7c1bc2`
- Canonical package name: `blux-coga`
- Canonical package version: `1.0.0`
- Canonical model version line: `CogA-1.0-pro`
- Dataset-to-engine mapping lock: `blux-coga-dataset v1.0 -> CogA-1.0-pro`
- Contract version: `1.0`
- Schema version: `1.0`
- Export contract version: `1.0`
- Reasoning pack coverage in this repo: `default@1.0`

The version naming convention is the exact engine convention from `run_header.model_version`: `CogA-<major>.<minor>` and `CogA-<major>.<minor>-pro`. This dataset freezes on the engine-correct capitalized `CogA-*` names everywhere and treats older names only as compatibility history.

## Fixture structure

Each fixture directory deterministically maps to one export record composed of four artifacts:

```text
fixtures/<fixture_name>/
  problem.json
  metadata.json
  expected/CogA-1.0-pro/default/
    thought_artifact.json
    reasoning_verdict.json
```

- `problem.json` is a real engine `ProblemSpec`, not a dataset-only prompt wrapper.
- `metadata.json` carries export metadata such as `fixture_id`, `scenario_type`, `model_version`, `contract_version`, `reasoning_pack_id`, `reasoning_pack_version`, `profile_id`, `profile_version`, `device`, and `expected_outcome`.
- Expected artifacts are raw engine-shaped `thought_artifact.json` and `reasoning_verdict.json` files.
- The repo validates that metadata and emitted `run_header` values agree.

## Fixture families

Current fixture coverage includes:

- `ambiguous`
- `assumptions`
- `bounded_options`
- `comparison`
- `contradiction`
- `non_directive_regression`
- `options`
- `stop_freeze`
- `tie_breaker`
- `unclear_min_delta`

Legacy model names `CogA-0.4` through `CogA-1.0` remain documented in `fixtures/fixture_matrix.json` as compatibility history only. They are **not** treated as runnable current-engine targets by the harness, because the current verified engine emits `CogA-1.0-pro`.

## Harness and verification

### Canonical verification workflow (single source of truth)

1) Validate fixture files and schemas:

```sh
python ./scripts/verify_fixtures.py
```

2) Re-run fixtures against the real local `blux-coga` engine:

Preferred invocation uses the engine repo's canonical CLI:

```sh
BLUX_COGA_REPO=/path/to/blux-coga python ./scripts/run_harness.py
```

The harness now prefers `blux-coga run --input ... --output-dir ...`, using either the repo-local `.venv` script, the repo source checkout via `PYTHONPATH=<repo>/src`, `python -m blux_coga`, or an installed `blux-coga` executable. Compatibility aliases like `./CogA.sh --in ... --out ...` belong to the engine repo, but the dataset harness freezes on the canonical `run` subcommand path.

### Deterministic JSONL export

```sh
python ./scripts/export_fixtures.py
```

The exporter emits one compact JSON object per line with stable key ordering, LF newlines, UTF-8 encoding, and stable fixture ordering taken from `fixtures/fixture_matrix.json`. Each line contains:

- `problem`
- `thought_artifact`
- `reasoning_verdict`
- `metadata`

Re-running the exporter with unchanged fixtures should produce byte-identical JSONL, which is the deterministic handoff format intended for later HuggingFace publication and training ingestion.

Canonical export artifact path for publication handoff:

- `exports/blux-coga-dataset.jsonl`
- optional determinism check: export twice and compare SHA-256 digests

Determinism check command sequence:

```sh
python ./scripts/export_fixtures.py
sha256sum exports/blux-coga-dataset.jsonl
python ./scripts/export_fixtures.py
sha256sum exports/blux-coga-dataset.jsonl
```

## Truth constraints for fixture updates

- Update fixtures only by rerunning the real engine.
- If engine behavior changes, refresh `problem.json`, `metadata.json`, expected artifacts, schemas, exports, and docs together in the same change.
- Do not introduce dataset harness flags that the real engine does not support.
- Do not store duplicate version directories unless they correspond to real archived engine outputs.
- This repo detects drift; it never becomes the source of truth for CogA reasoning semantics.

See `docs/POLICY.md` and `docs/PLATFORMS.md` for the operational policy and platform setup notes.

## HuggingFace dataset card summary (publication-ready)

- **What this dataset is:** deterministic fixture rows captured from real `blux-coga` engine runs for drift detection and training handoff.
- **What it maps to:** `Outer-Void/blux-coga` `main`, commit `10b5b8e32f59f07f93a85d647d6f326acb7c1bc2`, engine line `CogA-1.0-pro`, package `blux-coga==1.0.0`.
- **Row structure:** each JSONL row contains `problem`, `thought_artifact`, `reasoning_verdict`, and `metadata`.
- **License/proprietary note:** see `LICENSE`; this repository content is proprietary release material and is not a normative reasoning specification.
- **Provenance:** generated from local file-based runs of the real engine via `blux-coga run --input ... --output-dir ...`, then frozen as deterministic fixtures and deterministic JSONL export.
- **Reasoning structure:** each row keeps the engine-native separation of `thought_artifact` and `reasoning_verdict`, plus raw `problem` and run metadata for replay/audit.
- **Non-directive guarantee:** fixtures are generated from real engine behavior and validated by `non_directive_regression` and related scenarios; the dataset does not prescribe reasoning policy beyond captured engine outcomes.
- **Generation process:** run fixture/schema verification, run live harness against `blux-coga`, export deterministic canonical JSONL, then verify byte-identical repeat export.

## Script semantics

All operational scripts in `scripts/` are Python executables (`.py`) and are invoked with `python ./scripts/<name>.py`. There are no shell-script entrypoints in this dataset repository.
