# Legacy: the frozen CogA 1.0 drift fixtures

`legacy/` holds dataset v1.0, the drift-detection fixtures for the frozen CogA 1.0 contract (`blux-coga
run`, `CogA-1.0-pro`). They moved there unchanged in Stage 08, and their scripts resolve paths relative to
`legacy/`:

```bash
python legacy/scripts/verify_fixtures.py                          # layout, schemas, metadata
BLUX_COGA_BIN=blux-coga python legacy/scripts/run_harness.py      # re-run against the real 1.0 engine
python legacy/scripts/export_fixtures.py                          # byte-identical legacy/exports/*.jsonl
```

CI still runs the first two on every push, and blux-coga's own CI runs the harness at a pinned commit of this
repository.

## Stage 08 audit of v1.0

| finding | status |
|---|---|
| **The card called it `text-generation`.** CogA 1.0's outputs are fixed template strings, not generated text. | v2's card claims no such task. |
| **No fixture covers CogA 1.0's plain "stop" path.** Changing that response does not fail the harness (found in Stage 06). | v1.0 is frozen; v2 is a separate dataset. |
| **The schemas are copies.** `legacy/schemas/*.json` duplicate CogA 1.0's own schemas, and both copies have drifted from the engine's. | v2 validates artifacts against the schema the pinned engine ships, so there is no copy to drift. |
| **The key `thought_artifact` names a 1.0 output.** It is not model reasoning, but the name reads like it. | v2 has no such key, and its scan rejects reasoning-named keys. |
| **There were no splits, licence metadata per row, dedup, contamination checks or CI.** | v2 has all of them (docs/ENGINEERING.md). |

The original v1.0 policy and platform notes are in `legacy/POLICY.md` and `legacy/docs/`.
