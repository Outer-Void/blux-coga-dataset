# blux-coga-dataset

Deterministic fixtures and regression cases for blux-coga live here.
These datasets do not define reasoning behavior; they detect drift over time.
Fixtures should only be updated on deliberate model/version changes.

**Dataset Tag:** CogA V1.0 Dataset

## Phase 0 (Hygiene Lock)
- No dataset fixtures are included yet.
- No fixture automation is enabled in Phase 0.

## Phase 1 (Dataset Charter + Fixture Schema Baseline)
- Schemas live in `schemas/` and define the fixture contract.
- Minimal fixtures live in `fixtures/`, organized by scenario.

## Phase 3 (Multi-option Fixtures)
- Multi-option reasoning fixtures live in `fixtures/options_basic`,
  `fixtures/comparison_basic`, and `fixtures/non_directive_regression`.
- These fixtures enforce non-directive behavior when multiple options are present.

## Phase 4 (Acceptance Harness Integration)
- Selected fixtures include a `report.json` acceptance artifact for harness checks.
- The harness compares `report.json` output when present to lock Phase 4 behavior.

## Phase 5 (Reasoning Pack Coverage)
- Expected outputs live under `fixtures/<case>/expected/<model_version>/<reasoning_pack>/`.
- Packs in scope: `default`, `strict-mini`.

## Phase 6 (Bounded Depth + UNCLEAR Determinism)
- Fixtures cover bounded option enumeration, deterministic tie-breaking, and minimal-delta choices.

## Phase 7 (Compatibility Coverage)
- Archived outputs for CogA-0.4 through CogA-1.0-pro are stored under the same expected path.

## Phase 8 (CI Gating + Fixture Law)
- Use `scripts/verify_fixtures.sh` to ensure all matrix entries exist.
- Use the harness to detect drift; CI should run both.

## Phase 9 (Release Candidate Dataset Freeze)
- Fixture schema and directory conventions are locked in `fixtures/fixture_matrix.json`.
- Platform guidance lives in `docs/PLATFORMS.md`.

## Phase 10 (CogA V1.0 Dataset Lock)
- Dataset coverage includes ambiguity, contradiction, assumptions, multi-option comparison,
  non-directive compliance, and refusal cases.

## Harness (optional minimal)
Run the tiny harness script after wiring CogA output to the expected schema:

```sh
COGA_CMD=coga ./scripts/run_harness.sh
```

The harness expects the `coga` command to accept `--problem`, `--output-thought`,
`--output-verdict`, and optionally `--output-report` flags, writing JSON that
matches the schemas in `schemas/` plus `report.json` when present. Replace
`COGA_CMD` with a wrapper if your invocation differs.

Override the default model version or reasoning pack with:

```sh
MODEL_VERSION=coga-1.0 REASONING_PACK=default COGA_CMD=coga ./scripts/run_harness.sh
```

Profile-specific fixtures can declare `required_profile_id` (and optional
`required_profile_version`) in `problem.json`. When present, expected outputs
may live under:

```
fixtures/<case>/expected/<model_version>/<profile_id>/<reasoning_pack>/
```

Run the harness with profile context by setting `PROFILE_ID` (and optionally
`PROFILE_VERSION`):

```sh
PROFILE_ID=pro PROFILE_VERSION=2024-09 MODEL_VERSION=coga-1.0 REASONING_PACK=default COGA_CMD=coga ./scripts/run_harness.sh
```
