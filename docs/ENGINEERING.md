# Dataset engineering (`dstool`)

Both BLUX datasets, blux-coga-dataset and blux-ca-dataset, are built by the same toolkit, `dstool/`. The
two repositories keep identical copies of it, and only `dataset.json`, the seeds and the engine adapter in
use differ. Nothing here is a prompt dump. Every record is the output of a pinned engine run on an
authored seed, and passes the gates below.

```text
seeds/<category>/<family>.json ──expand──▶ drafts ──pinned engine (twice)──▶ records
   ──gates (schema, privacy, hidden reasoning)──▶ dedup ──contamination──▶ quality ──split lock──▶
   data/<split>.jsonl + data/contamination.json + data/manifest.json ──▶ README.md (card)
```

## Files

| path | what | edited by |
|---|---|---|
| `dataset.json` | id, version, licence, authors, engine pins (with commits), categories, canary, thresholds, card text | people |
| `seeds/<category>/<family>.json` | one family: instruction + input templates, numbered variants | people (or `import` + review) |
| `splits.lock.json` | every record id ever issued: split, content hash, active/retired | `dstool lock --update` |
| `data/<split>.jsonl` | the records, one canonical JSON object per line, sorted by id | `dstool build` |
| `data/manifest.json` | counts, file hashes, records digest, engines, excluded records | `dstool build` |
| `data/contamination.json` | similarity report: each protected record's nearest record in another split | `dstool build` |
| `README.md` | the dataset card | `dstool card` |
| `schemas/*.v1.schema.json` | record, seed, manifest, split-lock and config schemas | `dstool schemas` |
| `legacy/` | the frozen 1.0 fixtures and their scripts | nobody (frozen) |

## Seeds

```json
{"schema": "blux.dataset-seed", "family": "plan-release-train", "category": "planning", "split": "train",
 "origin": "synthetic-authored", "review": {"status": "approved", "reviewer": "outer-void"},
 "instruction": "Order the work for the ${release} release ...",
 "input": {"capability": "reason.plan", "request": {"max_parallel": "${lanes}", "...": "..."}},
 "variants": [{"id": "01", "params": {"release": "spring", "lanes": 2}}, {"id": "02", "params": {"...": "..."}}]}
```

**Substitution** is strict:

- a placeholder without a parameter is an error, and so is a parameter no placeholder uses;
- a string that is exactly `${name}` takes the parameter's JSON value (so `"${lanes}"` becomes the number
  2);
- an embedded placeholder must be a string or a number.

**The family is the unit of splitting.** Every variant of a family is in the family's split, so variants
that differ only in names or numbers can never sit on both sides of a split boundary. The file name must
be the family id, and family ids are unique across the repository.

## Records

`record_id` is `<prefix>:<family>:<variant>`, for example `cg:plan-release-train:02`. Identity and content
are separate:

| hash | of |
|---|---|
| `hashes.input_sha256` | the input |
| `hashes.expected_sha256` | the engine output |
| `hashes.content_sha256` | `{task, input, expected}`, which is what immutability is checked against |

The version and provenance fields are outside the content hash, so releasing a new dataset version does
not "change" old records.

## Immutability and split locking

`splits.lock.json` holds every id ever issued, with its split and content hash. `dstool build` and
`dstool validate` fail when:

- a locked record changes split;
- a locked record's content changes, whether through a seed edit or a different engine output;
- a locked active record disappears without being retired;
- a record is built that is not in the lock;
- a retired id comes back.

`dstool lock --update` only adds new ids and marks retirements, and refuses to alter an existing entry. To
change a record, mark its variant `"retired": true` and add a new variant id. The old id stays in the lock
as `retired` and can never be reused.

This also guards against engine drift: a new engine that computes different outputs breaks the lock, so a
dataset only moves to a new engine together with an explicit new set of records.

## Splits

| split | protected | purpose |
|---|---|---|
| train | no | training |
| validation | no | model selection |
| test | yes | evaluation |
| holdout | yes | final, rarely-run evaluation |
| adversarial | yes | hostile, conflicting or malformed input |
| regression | yes | exact engine-behaviour pins |

`dstool export --purpose training` is the only training generation path. It reads train and validation
only, and stops (`PROTECTED_RECORD`) if a record it would emit:

- is in a protected split;
- is locked to a protected split, even if someone moved it into `train.jsonl`;
- carries the canary.

Asking it for a protected split fails (`PROTECTED_SPLIT`). Protected records export only with
`--purpose evaluation`, and keep their canary.

## Contamination controls

1. **Exact duplicates.** Records with the same normalized tokens (lower-cased, numbers folded to `0`, over
   the instruction and every key and string value of the input) are dropped within a split, and fail the
   build across splits.
2. **Near duplicates.** The Jaccard similarity of 4-token shingle sets is computed between every pair of
   records from different families. A cross-split pair at or above `near_duplicate_threshold` fails the
   build. `data/contamination.json` records the maximum, and each protected record's nearest neighbour.
3. **Families never span splits.**
4. **Canary.** Every protected record carries the dataset's canary GUID. If the GUID appears in a training
   corpus, that corpus has ingested protected records.
5. **Protected paths.** Imports cannot target holdout, adversarial or regression, and the training export
   refuses protected records (above).

## Quality

**Gates.** A record failing any of these stops the build:

- its schema and the adapter's input and expected schemas (for CogA, the artifact schema the pinned engine
  ships; for cA, its result and changeset schemas);
- reproducibility: two engine runs must agree;
- the privacy scan;
- the hidden-reasoning scan.

**Score.** The mean of the applicable components:

| component | |
|---|---|
| instruction length | 60–1500 characters |
| grounding | the instruction names something in the input |
| evidence | CogA capabilities that take evidence |
| informative output | findings, uncertainty, a non-empty changeset, or an error |
| distinctness | from other families in the same split |

Records under `quality_threshold` are excluded and listed in the manifest.

## Privacy and provenance

**Never automatic.** Nothing reaches a dataset without a seed in the repository. Imported material enters
through `dstool import`, which:

- requires a licence and a source;
- runs the privacy scan;
- writes the seed as `origin: imported, review: pending`.

The build skips pending seeds. `dstool promote FAMILY --reviewer NAME` approves one after a person has
looked at it.

**The privacy scan rejects:**

- e-mail addresses outside the example domains;
- phone numbers;
- IPv4 addresses outside the documentation, loopback and 10/8 ranges;
- home-directory paths;
- private keys and common credential formats;
- any term in an untracked `.private-terms` file. It is git-ignored, so private names are never published
  by listing them.

**Provenance.** Every record states:

- origin, authors and licence;
- the seed path and hash;
- the generator version;
- the engines, with their commits;
- the review status.

## No hidden reasoning

Records hold explicit inputs and engine outputs only, and there is no field for model reasoning. The scan
rejects keys that name reasoning (`thought`, `chain_of_thought`, `scratchpad`, `hidden_reasoning`,
`reasoning_trace`, `inner_monologue` …) and markers such as `<thinking>`.

There is one exception: an adversarial record may carry such a key inside its input request, with a short
value, when the engine rejected that request. The record shows a smuggling attempt being refused; it does
not store reasoning.

## Reproducibility

- **Determinism.** Every step is deterministic: sorted inputs, canonical JSON, no clock (dates come from
  `dataset.json`), and throw-away workspaces with fixed relative names.
- **`dstool build --check`** regenerates everything with the pinned engines and fails unless the result is
  byte-identical to the committed files.
- **Engine pin.** The build refuses to run against a different engine version (`ENGINE_MISMATCH`).
  `requirements.txt` installs the pinned commit.
- **Manifest.** `records_sha256` (over sorted `[record_id, content_sha256]` pairs) identifies a dataset
  version's contents in one value.

## Commands

```bash
python -m dstool build [--check]        # generate data/ (or prove it is current)
python -m dstool validate               # validate committed data without the engines
python -m dstool lock [--update]        # check, or extend, the split lock
python -m dstool card [--check]         # README.md
python -m dstool schemas [--check]      # schemas/
python -m dstool export --purpose training -o out/train.jsonl
python -m dstool export --purpose evaluation --splits test,holdout -o out/eval.jsonl
python -m dstool import FILE --family F --category C --split train --license-spdx X --license-name Y --source S
python -m dstool promote F --reviewer NAME
python -m dstool stats
```

Exit codes: 0 ok, 1 a check failed, 2 usage, 3 error.

To add records:

1. write a seed or a new variant;
2. `python -m dstool lock --update`;
3. `python -m dstool build`;
4. `python -m dstool card`;
5. commit the seed, the lock, `data/` and `README.md` together.
