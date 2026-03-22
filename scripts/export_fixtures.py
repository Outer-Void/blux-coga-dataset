#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MATRIX = json.loads((ROOT / 'fixtures' / 'fixture_matrix.json').read_text())
model = MATRIX['canonical_model_version']
pack = MATRIX['reasoning_packs'][0]
records = []
for fixture_name in MATRIX['fixtures']:
    fixture_dir = ROOT / 'fixtures' / fixture_name
    expected_dir = fixture_dir / 'expected' / model / pack
    records.append({
        'problem': json.loads((fixture_dir / 'problem.json').read_text()),
        'thought_artifact': json.loads((expected_dir / 'thought_artifact.json').read_text()),
        'reasoning_verdict': json.loads((expected_dir / 'reasoning_verdict.json').read_text()),
        'metadata': json.loads((fixture_dir / 'metadata.json').read_text()),
    })
print(json.dumps(records, indent=2))
