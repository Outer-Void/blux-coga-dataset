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
        schema_type = schema.get('type')
        allowed_types = schema_type if isinstance(schema_type, list) else [schema_type]
        if data is None:
            if 'null' not in allowed_types:
                raise AssertionError('Unexpected null value.')
            return
        if 'enum' in schema and data not in schema['enum']:
            raise AssertionError('Value not in enum.')
        if 'allOf' in schema:
            for clause in schema['allOf']:
                if 'if' in clause and 'then' in clause:
                    props = clause['if'].get('properties', {})
                    if isinstance(data, dict) and all(k in data and data[k] in v.get('enum', []) for k, v in props.items()):
                        validate_schema(clause['then'], data)
                else:
                    validate_schema(clause, data)
        if 'object' in allowed_types:
            if not isinstance(data, dict):
                raise AssertionError('Expected object.')
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
        if 'array' in allowed_types:
            if not isinstance(data, list):
                raise AssertionError('Expected array.')
            item_schema = schema.get('items')
            if item_schema:
                for item in data:
                    validate_schema(item_schema, item)
        if 'string' in allowed_types and data is not None and not isinstance(data, str):
            raise AssertionError('Expected string.')
        if 'boolean' in allowed_types and data is not None and not isinstance(data, bool):
            raise AssertionError('Expected boolean.')
        if 'integer' in allowed_types and data is not None and (not isinstance(data, int) or isinstance(data, bool)):
            raise AssertionError('Expected integer.')
        if 'number' in allowed_types and data is not None and (not isinstance(data, (int, float)) or isinstance(data, bool)):
            raise AssertionError('Expected number.')


schemas = {name: json.loads((SCHEMAS / name).read_text()) for name in [
    'fixture.schema.json',
    'fixture_metadata.schema.json',
    'thought_artifact.schema.json',
    'reasoning_verdict.schema.json',
    'export_record.schema.json',
]}
status = 0
expected_statuses = {'COMPLETE', 'UNCLEAR', 'REFUSE'}
seen_fixture_ids = set()
for fixture_name in MATRIX['fixtures']:
    fixture_dir = ROOT / 'fixtures' / fixture_name
    problem_path = fixture_dir / 'problem.json'
    metadata_path = fixture_dir / 'metadata.json'
    expected_dir = fixture_dir / 'expected' / MATRIX['canonical_model_version'] / MATRIX['reasoning_packs'][0]
    thought_path = expected_dir / 'thought_artifact.json'
    verdict_path = expected_dir / 'reasoning_verdict.json'

    loaded = {}
    for path, schema_name in [
        (problem_path, 'fixture.schema.json'),
        (metadata_path, 'fixture_metadata.schema.json'),
        (thought_path, 'thought_artifact.schema.json'),
        (verdict_path, 'reasoning_verdict.schema.json'),
    ]:
        if not path.exists():
            print(f'Missing {path.relative_to(ROOT)}.', file=sys.stderr)
            status = 1
            continue
        try:
            loaded[path.name] = json.loads(path.read_text())
            validate_schema(schemas[schema_name], loaded[path.name])
        except Exception as exc:
            print(f'Schema failure in {path.relative_to(ROOT)}: {exc}', file=sys.stderr)
            status = 1

    if {'metadata.json', 'thought_artifact.json', 'reasoning_verdict.json'} - loaded.keys():
        continue

    metadata = loaded['metadata.json']
    thought = loaded['thought_artifact.json']
    verdict = loaded['reasoning_verdict.json']
    run_headers = [thought['run_header'], verdict['run_header']]

    if metadata['fixture_id'] in seen_fixture_ids:
        print(f'Duplicate fixture_id detected: {metadata["fixture_id"]}', file=sys.stderr)
        status = 1
    seen_fixture_ids.add(metadata['fixture_id'])

    if metadata['scenario_type'] != fixture_name:
        print(f'Scenario mismatch in {metadata_path.relative_to(ROOT)}: expected {fixture_name}, got {metadata["scenario_type"]}', file=sys.stderr)
        status = 1
    if metadata['model_version'] != MATRIX['canonical_model_version']:
        print(f'Metadata model_version mismatch in {metadata_path.relative_to(ROOT)}', file=sys.stderr)
        status = 1
    if metadata['contract_version'] != MATRIX['contract_version']:
        print(f'Metadata contract_version mismatch in {metadata_path.relative_to(ROOT)}', file=sys.stderr)
        status = 1
    if metadata['reasoning_pack_id'] != MATRIX['reasoning_packs'][0]:
        print(f'Metadata reasoning_pack_id mismatch in {metadata_path.relative_to(ROOT)}', file=sys.stderr)
        status = 1
    if metadata['expected_outcome'] not in expected_statuses:
        print(f'Unexpected expected_outcome in {metadata_path.relative_to(ROOT)}: {metadata["expected_outcome"]}', file=sys.stderr)
        status = 1
    if metadata['expected_outcome'] != verdict['status']:
        print(f'Expected outcome/status mismatch in {fixture_name}: metadata={metadata["expected_outcome"]}, verdict={verdict["status"]}', file=sys.stderr)
        status = 1

    for header in run_headers:
        if header['model_version'] != metadata['model_version']:
            print(f'run_header.model_version mismatch in {fixture_name}', file=sys.stderr)
            status = 1
        if header['contract_version'] != metadata['contract_version']:
            print(f'run_header.contract_version mismatch in {fixture_name}', file=sys.stderr)
            status = 1
        if header['reasoning_pack_id'] != metadata['reasoning_pack_id']:
            print(f'run_header.reasoning_pack_id mismatch in {fixture_name}', file=sys.stderr)
            status = 1
        if header['reasoning_pack_version'] != metadata['reasoning_pack_version']:
            print(f'run_header.reasoning_pack_version mismatch in {fixture_name}', file=sys.stderr)
            status = 1
        if header['schema_version'] != MATRIX['schema_version']:
            print(f'run_header.schema_version mismatch in {fixture_name}', file=sys.stderr)
            status = 1

    if thought['run_header'] != verdict['run_header']:
        print(f'run_header mismatch between artifacts in {fixture_name}', file=sys.stderr)
        status = 1

    export_record = {
        'problem': loaded['problem.json'],
        'thought_artifact': thought,
        'reasoning_verdict': verdict,
        'metadata': metadata,
    }
    try:
        validate_schema(schemas['export_record.schema.json'], export_record)
    except Exception as exc:
        print(f'Export record schema failure in {fixture_name}: {exc}', file=sys.stderr)
        status = 1

sys.exit(status)
