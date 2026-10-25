#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MATRIX = json.loads((ROOT / 'fixtures' / 'fixture_matrix.json').read_text())
MODEL = MATRIX['canonical_model_version']
PACK = MATRIX['reasoning_packs'][0]
CANONICAL_EXPORT = ROOT / 'exports' / 'blux-coga-dataset.jsonl'


def stable_json(data):
    return json.dumps(data, sort_keys=True, separators=(',', ':'))


def build_record(fixture_name):
    fixture_dir = ROOT / 'fixtures' / fixture_name
    expected_dir = fixture_dir / 'expected' / MODEL / PACK
    return {
        'problem': json.loads((fixture_dir / 'problem.json').read_text()),
        'thought_artifact': json.loads((expected_dir / 'thought_artifact.json').read_text()),
        'reasoning_verdict': json.loads((expected_dir / 'reasoning_verdict.json').read_text()),
        'metadata': json.loads((fixture_dir / 'metadata.json').read_text()),
    }


def canonical_fixture_order():
    fixture_names = list(MATRIX['fixtures'])
    if len(fixture_names) != len(set(fixture_names)):
        raise SystemExit('fixture_matrix.json contains duplicate fixture names.')
    return fixture_names


def main():
    parser = argparse.ArgumentParser(description='Export fixtures as deterministic JSONL.')
    parser.add_argument(
        '--output',
        type=Path,
        default=CANONICAL_EXPORT,
        help=f'Canonical export path (must be {CANONICAL_EXPORT.relative_to(ROOT)}).',
    )
    args = parser.parse_args()
    output_path = args.output.resolve()
    canonical_path = CANONICAL_EXPORT.resolve()
    if output_path != canonical_path:
        raise SystemExit(
            f'Non-canonical export path blocked: {args.output}. '
            f'Use {CANONICAL_EXPORT.relative_to(ROOT)}.'
        )

    lines = [stable_json(build_record(fixture_name)) for fixture_name in canonical_fixture_order()]
    payload = ''.join(line + '\n' for line in lines)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(payload, encoding='utf-8', newline='\n')
    sys.stdout.write(f'Wrote {args.output.relative_to(ROOT)}\n')


if __name__ == '__main__':
    main()
