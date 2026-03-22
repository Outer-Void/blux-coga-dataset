#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MATRIX = json.loads((ROOT / 'fixtures' / 'fixture_matrix.json').read_text())
SCHEMAS = ROOT / 'schemas'

repo = os.environ.get('BLUX_COGA_REPO')
if not repo:
    sibling = ROOT.parent / 'blux-coga'
    if sibling.exists():
        repo = str(sibling)
if repo:
    sys.path.insert(0, str(Path(repo) / 'src'))
try:
    from blux_coga.contracts.schema import validate_schema
except Exception:
    def validate_schema(schema, data):
        t = schema.get('type')
        allowed = t if isinstance(t, list) else [t]
        if data is None:
            if 'null' not in allowed:
                raise AssertionError('Unexpected null value')
            return
        if 'enum' in schema and data not in schema['enum']:
            raise AssertionError('Value not in enum')
        if 'allOf' in schema:
            for clause in schema['allOf']:
                if 'if' in clause and 'then' in clause:
                    props = clause['if'].get('properties', {})
                    if isinstance(data, dict) and all(k in data and data[k] in v.get('enum', []) for k, v in props.items()):
                        validate_schema(clause['then'], data)
                else:
                    validate_schema(clause, data)
        if 'object' in allowed:
            if not isinstance(data, dict):
                raise AssertionError('Expected object')
            for key in schema.get('required', []):
                if key not in data:
                    raise AssertionError(f'Missing key: {key}')
            properties = schema.get('properties', {})
            for key, value in data.items():
                if key in properties:
                    validate_schema(properties[key], value)
                elif schema.get('additionalProperties') is False:
                    raise AssertionError(f'Unexpected key: {key}')
                elif isinstance(schema.get('additionalProperties'), dict):
                    validate_schema(schema['additionalProperties'], value)
        if 'array' in allowed:
            if not isinstance(data, list):
                raise AssertionError('Expected array')
            item_schema = schema.get('items')
            if item_schema:
                for item in data:
                    validate_schema(item_schema, item)
        if 'string' in allowed and data is not None and not isinstance(data, str):
            raise AssertionError('Expected string')
        if 'boolean' in allowed and data is not None and not isinstance(data, bool):
            raise AssertionError('Expected boolean')

schemas = {name: json.loads((SCHEMAS / name).read_text()) for name in [
    'fixture.schema.json',
    'fixture_metadata.schema.json',
    'thought_artifact.schema.json',
    'reasoning_verdict.schema.json',
]}
status = 0
for fixture_name in MATRIX['fixtures']:
    fixture_dir = ROOT / 'fixtures' / fixture_name
    for fname, schema_name in [
        ('problem.json', 'fixture.schema.json'),
        ('metadata.json', 'fixture_metadata.schema.json'),
    ]:
        path = fixture_dir / fname
        if not path.exists():
            print(f'Missing {fname} in {fixture_name}.', file=sys.stderr)
            status = 1
            continue
        try:
            validate_schema(schemas[schema_name], json.loads(path.read_text()))
        except Exception as exc:
            print(f'Schema failure in {path.relative_to(ROOT)}: {exc}', file=sys.stderr)
            status = 1
    expected_dir = fixture_dir / 'expected' / MATRIX['canonical_model_version'] / MATRIX['reasoning_packs'][0]
    for fname, schema_name in [
        ('thought_artifact.json', 'thought_artifact.schema.json'),
        ('reasoning_verdict.json', 'reasoning_verdict.schema.json'),
    ]:
        path = expected_dir / fname
        if not path.exists():
            print(f'Missing {path.relative_to(ROOT)}.', file=sys.stderr)
            status = 1
            continue
        try:
            validate_schema(schemas[schema_name], json.loads(path.read_text()))
        except Exception as exc:
            print(f'Schema failure in {path.relative_to(ROOT)}: {exc}', file=sys.stderr)
            status = 1
sys.exit(status)
