"""`python -m dstool`: build, validate, lock, card, export, import, promote, stats, schemas.

Exit codes: 0 ok; 1 a check failed (stale files, invalid records, contamination); 2 usage; 3 error.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dstool import build, card, export, importer, schemas
from dstool.common import SPLITS, DsError, dump_json, load_config
from dstool.validate import read_all, validate

ROOT = Path(__file__).resolve().parent.parent


def _write_or_check(files: dict[Path, str], check: bool) -> int:
    stale = []
    for path, text in sorted(files.items()):
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if current != text:
            stale.append(path.relative_to(ROOT).as_posix())
            if not check:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")
    if check and stale:
        print("stale (regenerate):", *stale, sep="\n  ")
        return 1
    print("up to date" if not stale else f"wrote {len(stale)} files")
    return 0


def published_schemas(config_categories: list[str]) -> dict[Path, str]:
    docs = {
        "record.v1.schema.json": schemas.record_schema(config_categories),
        "seed.v1.schema.json": schemas.SEED,
        "manifest.v1.schema.json": schemas.MANIFEST,
        "split-lock.v1.schema.json": schemas.LOCK,
        "config.v1.schema.json": schemas.CONFIG,
    }
    return {
        ROOT / "schemas" / name: json.dumps(
            {"$schema": "https://json-schema.org/draft/2020-12/schema", "$id": f"urn:outervoid:dataset:{name}", **doc},
            indent=2,
            sort_keys=True,
        )
        + "\n"
        for name, doc in docs.items()
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="dstool", description="BLUX dataset engineering tool")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("build", help="generate data/ from seeds with the pinned engines")
    p.add_argument("--check", action="store_true", help="exit 1 if the committed files differ")
    sub.add_parser("validate", help="validate the committed data without regenerating it")
    p = sub.add_parser("lock", help="check or extend splits.lock.json")
    p.add_argument("--update", action="store_true", help="add new records and retirements (never changes a locked one)")
    p = sub.add_parser("card", help="generate README.md (the dataset card)")
    p.add_argument("--check", action="store_true")
    p = sub.add_parser("schemas", help="publish schemas/*.json")
    p.add_argument("--check", action="store_true")
    p = sub.add_parser("export", help="export records for training or evaluation")
    p.add_argument("--purpose", required=True, choices=["training", "evaluation"])
    p.add_argument("--splits", help="comma-separated (training: train,validation only)")
    p.add_argument("-o", "--output", required=True)
    p = sub.add_parser("import", help="import a seed for review (never used until promoted)")
    p.add_argument("file")
    for name in ("family", "category", "split", "license-spdx", "license-name", "source"):
        p.add_argument(f"--{name}", required=True)
    p = sub.add_parser("promote", help="approve a reviewed seed")
    p.add_argument("family")
    p.add_argument("--reviewer", required=True)
    p.add_argument("--note")
    sub.add_parser("stats", help="record counts by split and category")
    args = parser.parse_args(argv)
    try:
        config = load_config(ROOT)
        if args.command == "build":
            result = build.run(config)
            lock = build.load_lock(config)
            problems = build.lock_problems(lock, result.records, result.retired)
            if problems:
                print("split lock:", *problems[:20], sep="\n  ")
                return 1
            return _write_or_check(build.outputs(config, result), args.check)
        if args.command == "validate":
            report = validate(config)
            print(json.dumps(report, indent=2))
            return 0 if report["ok"] else 1
        if args.command == "lock":
            result = build.run(config)
            lock = build.load_lock(config)
            if args.update:
                dump_json(
                    config.path("splits.lock.json"), build.update_lock(config, lock, result.records, result.retired)
                )
                print("splits.lock.json updated")
                return 0
            problems = build.lock_problems(lock, result.records, result.retired)
            print("\n".join(problems) or "split lock ok")
            return 1 if problems else 0
        if args.command == "card":
            return _write_or_check({ROOT / "README.md": card.render(config)}, args.check)
        if args.command == "schemas":
            return _write_or_check(published_schemas(config.categories), args.check)
        if args.command == "export":
            splits = tuple(s for s in (args.splits or "").split(",") if s)
            if args.purpose == "training":
                records = export.training_records(config, splits or ("train", "validation"))
            else:
                records = export.evaluation_records(config, splits or SPLITS)
            Path(args.output).write_text(export.to_jsonl(records), encoding="utf-8")
            print(f"{len(records)} records -> {args.output}")
            return 0
        if args.command == "import":
            path = importer.import_seed(
                config,
                Path(args.file),
                family=args.family,
                category=args.category,
                split=args.split,
                license_spdx=args.license_spdx,
                license_name=args.license_name,
                source=args.source,
            )
            print(f"imported for review: {path.relative_to(ROOT)} (review: pending)")
            return 0
        if args.command == "promote":
            path = importer.promote(config, args.family, args.reviewer, args.note)
            print(f"approved: {path.relative_to(ROOT)}")
            return 0
        records = read_all(config)
        table: dict[str, dict[str, int]] = {}
        for r in records:
            table.setdefault(r["category"], dict.fromkeys(SPLITS, 0))[r["split"]] += 1
        print(json.dumps({"records": len(records), "by_category": table}, indent=2))
        return 0
    except DsError as exc:
        print(f"dstool: {exc.code}: {exc.message}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
