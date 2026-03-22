# blux-coga-dataset

Deterministic drift-detection fixtures for the real `Outer-Void/blux-coga` engine live here. This repo does **not** define reasoning behavior; it records real engine outputs so later runs can detect drift against the engine's current contract and boundary behavior.

## Engine line mapped by this dataset

- Canonical engine repo: `Outer-Void/blux-coga`
- Canonical model version line: `CogA-1.0-pro`
- Contract version: `1.0`
- Schema version: `1.0`
- Reasoning pack coverage in this repo: `default`

The version naming convention is the exact engine convention from `run_header.model_version`: `CogA-<major>.<minor>` and `CogA-<major>.<minor>-pro`. This dataset now uses the engine-correct capitalized `CogA-*` names everywhere.

## Fixture structure

Each fixture directory is export-ready and maps deterministically to four records:

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

Legacy model names `CogA-0.4` through `CogA-1.0` remain documented in `fixtures/fixture_matrix.json` as compatibility history only. They are **not** treated as runnable current-engine targets by the harness, because the current local engine emits `CogA-1.0-pro`.

## Harness and verification

### Verify fixture completeness and schemas

```sh
./scripts/verify_fixtures.sh
```

### Re-run the dataset against the real engine

Preferred invocation uses the engine repo's canonical file-based runner:

```sh
BLUX_COGA_REPO=../blux-coga ./scripts/run_harness.sh
```

If `../blux-coga` exists, the harness auto-detects it and uses `./CogA.sh --in ... --out ...`. Otherwise it falls back to an installed `blux-coga` binary.

### Export-ready JSON assembly

```sh
python ./scripts/export_fixtures.py
```

That script prints an array of records shaped as:

- `problem`
- `thought_artifact`
- `reasoning_verdict`
- `metadata`

which is the deterministic internal structure intended for later JSONL export and HuggingFace publication.

## Truth constraints for fixture updates

- Update fixtures only by rerunning the real engine.
- If engine behavior changes, refresh `problem.json`, `metadata.json`, expected artifacts, schemas, and docs together when needed.
- Do not introduce harness-only flags that the real engine does not support.
- Do not store duplicate version directories unless they correspond to real archived engine outputs.

See `docs/POLICY.md` and `docs/PLATFORMS.md` for the operational policy and platform setup notes.
