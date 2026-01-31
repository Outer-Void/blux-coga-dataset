# Fixture Update Policy (CogA V1.0 Dataset)

## Purpose
Fixtures detect drift. They do **not** define reasoning behavior. Updates must be
intentional, reviewed, and tied to explicit model/version changes.

## Fixture Matrix
- The authoritative matrix is `fixtures/fixture_matrix.json`.
- Expected outputs must exist at:
  `fixtures/<case>/expected/<model_version>/<reasoning_pack>/`.
- Compatibility coverage includes `coga-0.4` through `coga-1.0-pro`.

## Update Workflow
1. Add or update fixture `problem.json`.
2. Run the harness to generate actual outputs from the target model/version.
3. Compare canonical JSON against expected outputs.
4. If updating expected outputs, document the reason and keep changes minimal.
5. Run `scripts/verify_fixtures.sh` to ensure the matrix is complete.

## CI Gating
- CI must run `scripts/verify_fixtures.sh` to ensure all matrix entries exist.
- CI must run `scripts/run_harness.sh` to detect drift for the selected model and pack.
- Any diff or missing expected output fails the build.

## Report Artifacts
- `report.json` is optional and used only for selected fixtures.
- When present, it is compared byte-for-byte (canonicalized with `jq -S`).
