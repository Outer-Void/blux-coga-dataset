"""Stage 08 gates: every record validates, splits are not contaminated, protected splits never reach a training
path, records are immutable and split-locked, and builds are reproducible. Shared by both BLUX datasets."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from dstool import build, export, importer
from dstool.__main__ import main
from dstool.adapters import load
from dstool.common import PROTECTED_SPLITS, SPLITS, TRAINING_SPLITS, Config, DsError, canonical, load_config
from dstool.scan import privacy_hits, reasoning_hits
from dstool.validate import read_all, read_split, validate

ROOT = Path(__file__).resolve().parents[1]
CONFIG = load_config(ROOT)
RECORDS = read_all(CONFIG)


def engines_available() -> bool:
    try:
        load(CONFIG.raw["adapter"]).check_engines(CONFIG)
    except DsError:
        return False
    return True


needs_engines = pytest.mark.skipif(not engines_available(), reason="the pinned engines are not installed")


def copy_repo(tmp_path: Path) -> Config:
    dst = tmp_path / "repo"
    for name in ("dstool", "seeds", "data", "dataset.json", "splits.lock.json", "LICENSE"):
        src = ROOT / name
        if src.is_dir():
            shutil.copytree(src, dst / name, ignore=shutil.ignore_patterns("__pycache__"))
        else:
            dst.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst / name)
    return load_config(dst)


def rewrite(config: Config, split: str, records: list[dict[str, Any]]) -> None:
    config.path("data", f"{split}.jsonl").write_text("".join(canonical(r) + "\n" for r in records), encoding="utf-8")


# All records validate -----------------------------------------------------------------------------------------


def test_every_committed_record_validates() -> None:
    report = validate(CONFIG)
    assert report["ok"], report["problems"][:20]
    assert report["records"] == len(RECORDS) > 0


def test_every_split_and_category_is_populated() -> None:
    splits = {r["split"] for r in RECORDS}
    assert splits == set(SPLITS)
    assert {r["category"] for r in RECORDS} == set(CONFIG.categories)
    trained = {r["category"] for r in RECORDS if r["split"] == "train"}
    adversarial_only = {c for c in CONFIG.categories if c.startswith("adversarial")}
    assert trained | adversarial_only == set(CONFIG.categories)


def test_ids_are_immutable_format_and_unique() -> None:
    ids = [r["record_id"] for r in RECORDS]
    assert len(ids) == len(set(ids))
    assert all(i == f"{CONFIG.prefix}:{r['family']}:{r['variant']}" for i, r in zip(ids, RECORDS, strict=True))


def test_every_record_carries_provenance_and_licence() -> None:
    for r in RECORDS:
        prov = r["provenance"]
        assert prov["license"] == CONFIG.raw["license"] and prov["review"]["status"] == "approved"
        assert prov["engines"] == CONFIG.raw["engines"] and prov["seed"]["path"].startswith("seeds/")
        assert (ROOT / prov["seed"]["path"]).is_file()


# Contamination ------------------------------------------------------------------------------------------------


def test_no_contamination_across_splits() -> None:
    report, _ = build.contamination(RECORDS, CONFIG.raw["near_duplicate_threshold"])
    assert report["problems"] == []
    _, dropped, problems = build.dedup(RECORDS)
    assert dropped == [] and problems == []
    committed = json.loads(CONFIG.path("data", "contamination.json").read_text())
    assert committed["max_cross_split_similarity"] < CONFIG.raw["near_duplicate_threshold"]


def test_families_never_span_splits() -> None:
    families: dict[str, set[str]] = {}
    for r in RECORDS:
        families.setdefault(r["family"], set()).add(r["split"])
    assert all(len(s) == 1 for s in families.values())


def test_a_protected_record_copied_into_train_is_caught(tmp_path: Path) -> None:
    config = copy_repo(tmp_path)
    protected = next(r for r in RECORDS if r["split"] == "holdout")
    leaked = {
        **protected,
        "split": "train",
        "record_id": f"{CONFIG.prefix}:leaked-copy:01",
        "family": "leaked-copy",
        "variant": "01",
        "canary": None,
    }
    rewrite(config, "train", [*read_split(config, "train"), leaked])
    problems = " ".join(validate(config)["problems"])
    assert "exact duplicate across splits" in problems and "not in splits.lock.json" in problems


def test_a_near_duplicate_across_splits_is_caught() -> None:
    base = next(r for r in RECORDS if r["split"] == "train")
    near = json.loads(json.dumps(base))
    near.update(record_id=f"{CONFIG.prefix}:near-copy:01", family="near-copy", split="test")
    near["task"]["instruction"] = base["task"]["instruction"] + " Please."
    report, _ = build.contamination([base, near], CONFIG.raw["near_duplicate_threshold"])
    assert any("near duplicate across splits" in p for p in report["problems"])


def test_canary_marks_every_protected_record_and_nothing_else() -> None:
    for r in RECORDS:
        assert (r["canary"] == CONFIG.canary) == (r["split"] in PROTECTED_SPLITS)


# Protected splits never reach training ------------------------------------------------------------------------


def test_the_training_export_holds_no_protected_record() -> None:
    out = export.training_records(CONFIG)
    text = export.to_jsonl(out)
    assert {r["split"] for r in out} <= set(TRAINING_SPLITS)
    assert CONFIG.canary not in text
    protected = [r for r in RECORDS if r["split"] in PROTECTED_SPLITS]
    assert protected
    for r in protected:
        assert r["record_id"] not in text
        assert canonical(r["expected"]) not in text and canonical(r["input"]) not in text


@pytest.mark.parametrize("split", PROTECTED_SPLITS)
def test_protected_splits_cannot_be_exported_for_training(split: str, tmp_path: Path) -> None:
    with pytest.raises(DsError) as info:
        export.training_records(CONFIG, (split,))
    assert info.value.code == "PROTECTED_SPLIT"
    assert main(["export", "--purpose", "training", "--splits", split, "-o", str(tmp_path / "x.jsonl")]) == 3
    assert not (tmp_path / "x.jsonl").exists()


def test_a_protected_record_moved_into_train_is_refused_by_the_export(tmp_path: Path) -> None:
    config = copy_repo(tmp_path)
    holdout = read_split(config, "holdout")
    moved = {**holdout[0], "split": "train", "canary": None}
    rewrite(config, "train", [*read_split(config, "train"), moved])
    with pytest.raises(DsError) as info:
        export.training_records(config)
    assert info.value.code == "PROTECTED_RECORD"  # the split lock still says holdout


def test_imports_cannot_target_protected_splits_and_are_never_built_unreviewed(tmp_path: Path) -> None:
    config = copy_repo(tmp_path)
    seed = json.loads(next(config.path("seeds").rglob("*.json")).read_text())
    src = tmp_path / "external.json"
    src.write_text(json.dumps({k: seed[k] for k in ("instruction", "input", "variants")}))
    for split in ("holdout", "regression", "adversarial"):
        with pytest.raises(DsError):
            importer.import_seed(
                config,
                src,
                family="ext-one",
                category=seed["category"],
                split=split,
                license_spdx="CC-BY-4.0",
                license_name="CC BY 4.0",
                source="unit test",
            )
    path = importer.import_seed(
        config,
        src,
        family="ext-one",
        category=seed["category"],
        split="train",
        license_spdx="CC-BY-4.0",
        license_name="CC BY 4.0",
        source="unit test",
    )
    doc = json.loads(path.read_text())
    assert doc["review"] == {"status": "pending"} and doc["origin"] == "imported"
    from dstool.seeds import load_all

    drafts, excluded = load_all(config)
    assert not [d for d in drafts if d.family == "ext-one"]
    assert excluded == [{"seed": "seeds/imported/ext-one.json", "reason": "review pending"}]


def test_private_data_cannot_be_imported(tmp_path: Path) -> None:
    config = copy_repo(tmp_path)
    src = tmp_path / "leak.json"
    src.write_text(json.dumps({"instruction": "Mail jane.doe@corp-internal.io about it", "input": {}, "variants": []}))
    with pytest.raises(DsError) as info:
        importer.import_seed(
            config,
            src,
            family="ext-leak",
            category=CONFIG.categories[0],
            split="train",
            license_spdx="CC0-1.0",
            license_name="CC0",
            source="unit test",
        )
    assert info.value.code == "PRIVACY"


# Privacy and hidden reasoning ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "contact jane.doe@corp-internal.io",
        "call +1 415-555-0199",
        "host 34.117.59.81",
        "see /home/alice/notes.txt",
        "C:\\Users\\bob\\key",
        "AKIAIOSFODNN7EXAMPLE",
        "-----BEGIN RSA PRIVATE KEY-----",
    ],
)
def test_privacy_scan_catches_personal_data(text: str) -> None:
    assert privacy_hits({"t": text}, [])


@pytest.mark.parametrize("text", ["ops@example.com", "192.0.2.10", "/home/user/project", "10.0.0.5", "v3.2.0"])
def test_privacy_scan_allows_documentation_values(text: str) -> None:
    assert privacy_hits({"t": text}, []) == []


def test_private_terms_file_is_honoured() -> None:
    assert privacy_hits({"t": "the Bluebird roadmap"}, ["bluebird"])


def test_hidden_reasoning_is_rejected() -> None:
    base = {"split": "train", "input": {"request": {}}, "expected": {}}
    assert reasoning_hits({**base, "expected": {"chain_of_thought": "..."}}, rejected=False)
    assert reasoning_hits({**base, "task": {"instruction": "<thinking>step one</thinking>"}}, rejected=False)
    smuggled = {"split": "adversarial", "input": {"request": {"items": [{"scratchpad": "x"}]}}}
    assert reasoning_hits(smuggled, rejected=True) == []  # a rejected attempt is recorded, not reasoning
    assert reasoning_hits(smuggled, rejected=False)
    assert reasoning_hits({**smuggled, "split": "train"}, rejected=True)


def test_no_committed_record_contains_reasoning_or_private_data() -> None:
    adapter = load(CONFIG.raw["adapter"])
    for r in RECORDS:
        assert reasoning_hits(r, rejected=adapter.rejected(r["expected"])) == [], r["record_id"]
        assert privacy_hits({k: r[k] for k in ("task", "input", "expected")}, []) == [], r["record_id"]


# Split lock and immutability ----------------------------------------------------------------------------------


def test_lock_covers_exactly_the_built_records() -> None:
    lock = build.load_lock(CONFIG)["records"]
    active = {k for k, v in lock.items() if v["status"] == "active"}
    assert active == {r["record_id"] for r in RECORDS}
    for r in RECORDS:
        assert lock[r["record_id"]]["split"] == r["split"]
        assert lock[r["record_id"]]["content_sha256"] == r["hashes"]["content_sha256"]


def test_locked_records_cannot_change_split_or_content() -> None:
    lock = build.load_lock(CONFIG)
    r = json.loads(json.dumps(RECORDS[0]))
    moved = {**r, "split": "test" if r["split"] != "test" else "train"}
    assert "is locked to" in build.lock_problems(lock, [moved], [])[0]
    r["task"]["instruction"] += " (edited)"
    r["hashes"]["content_sha256"] = build.sha256_of(build._content(r))
    assert "immutable" in build.lock_problems(lock, [r], [])[0]
    with pytest.raises(DsError):
        build.update_lock(CONFIG, lock, [r], [])
    gone = build.lock_problems(lock, RECORDS[1:], [])
    assert any("no longer built" in p for p in gone)


def test_retired_ids_are_never_reused() -> None:
    lock = build.load_lock(CONFIG)
    rid = RECORDS[0]["record_id"]
    retired = build.update_lock(CONFIG, lock, RECORDS[1:], [rid])
    assert retired["records"][rid]["status"] == "retired"
    assert any("never reused" in p for p in build.lock_problems(retired, RECORDS, []))


# Reproducibility ----------------------------------------------------------------------------------------------


def test_generated_files_are_current() -> None:
    assert main(["schemas", "--check"]) == 0
    assert main(["card", "--check"]) == 0


@needs_engines
def test_a_build_reproduces_the_committed_files_byte_for_byte(tmp_path: Path) -> None:
    config = copy_repo(tmp_path)  # a different absolute path, too
    result = build.run(config)
    assert build.lock_problems(build.load_lock(config), result.records, result.retired) == []
    for path, text in build.outputs(config, result).items():
        committed = ROOT / path.relative_to(config.root)
        assert committed.read_text(encoding="utf-8") == text, committed


@needs_engines
def test_a_changed_seed_is_caught_by_the_lock(tmp_path: Path) -> None:
    config = copy_repo(tmp_path)
    seed_path = next(config.path("seeds").rglob("*.json"))
    seed = json.loads(seed_path.read_text())
    seed["instruction"] += " Answer carefully."
    seed_path.write_text(json.dumps(seed, indent=2))
    result = build.run(config)
    problems = build.lock_problems(build.load_lock(config), result.records, result.retired)
    assert problems and all("immutable" in p for p in problems)
