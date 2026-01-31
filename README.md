# blux-coga-dataset

Deterministic fixtures and regression cases for blux-coga live here.
These datasets do not define reasoning behavior; they detect drift over time.
Fixtures should only be updated on deliberate model/version changes.

## Phase 0 (Hygiene Lock)
- No dataset fixtures are included yet.
- No fixture automation is enabled in Phase 0.

## Phase 1 (Dataset Charter + Fixture Schema Baseline)
- Schemas live in `schemas/` and define the fixture contract.
- Minimal fixtures live in `fixtures/`, organized by scenario.

## Harness (optional minimal)
Run the tiny harness script after wiring CogA output to the expected schema:

```sh
COGA_CMD=coga ./scripts/run_harness.sh
```

The harness expects the `coga` command to accept `--problem`, `--output-thought`,
and `--output-verdict` flags, writing JSON that matches the schemas in
`schemas/`. Replace `COGA_CMD` with a wrapper if your invocation differs.
