#!/usr/bin/env python3
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MATRIX = json.loads((ROOT / 'fixtures' / 'fixture_matrix.json').read_text())
MODEL_VERSION = os.environ.get('MODEL_VERSION', MATRIX['canonical_model_version'])
REASONING_PACK = os.environ.get('REASONING_PACK', MATRIX['reasoning_packs'][0])


def stable(data):
    return json.dumps(data, sort_keys=True, separators=(',', ':'))


def engine_cmd(problem_path: Path, output_dir: Path):
    repo = os.environ.get('BLUX_COGA_REPO')
    if not repo:
        sibling = ROOT.parent / 'blux-coga'
        if sibling.exists():
            repo = str(sibling)
    profile = os.environ.get('PROFILE_ID')
    profile_file = os.environ.get('PROFILE_FILE')
    if repo:
        repo_path = Path(repo)
        venv_python = repo_path / '.venv' / 'bin' / 'python'
        if venv_python.exists():
            cmd = [str(venv_python), '-m', 'blux_coga', '--input', str(problem_path), '--output-dir', str(output_dir)]
        else:
            cmd = [str(repo_path / 'CogA.sh'), '--in', str(problem_path), '--out', str(output_dir)]
        cwd = repo
    else:
        binary = os.environ.get('BLUX_COGA_BIN', 'blux-coga')
        cmd = [binary, '--input', str(problem_path), '--output-dir', str(output_dir)]
        cwd = str(ROOT)
    if profile:
        cmd += ['--profile', profile]
    if profile_file:
        cmd += ['--profile-file', profile_file]
    return cmd, cwd

status = 0
for fixture_name in MATRIX['fixtures']:
    fixture_dir = ROOT / 'fixtures' / fixture_name
    expected_dir = fixture_dir / 'expected' / MODEL_VERSION / REASONING_PACK
    thought_expected = expected_dir / 'thought_artifact.json'
    verdict_expected = expected_dir / 'reasoning_verdict.json'
    if not thought_expected.exists() or not verdict_expected.exists():
        print(f'Missing expected outputs for {fixture_name} ({MODEL_VERSION}/{REASONING_PACK}).', file=sys.stderr)
        status = 1
        continue
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / 'out'
        cmd, cwd = engine_cmd(fixture_dir / 'problem.json', out)
        try:
            subprocess.run(cmd, cwd=cwd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        except FileNotFoundError as exc:
            print(f'Unable to locate engine command: {exc}', file=sys.stderr)
            sys.exit(1)
        except subprocess.CalledProcessError as exc:
            print(exc.stdout, end='')
            print(exc.stderr, end='', file=sys.stderr)
            status = 1
            continue
        actual_thought = json.loads((out / 'thought_artifact.json').read_text())
        actual_verdict = json.loads((out / 'reasoning_verdict.json').read_text())
        expected_thought = json.loads(thought_expected.read_text())
        expected_verdict = json.loads(verdict_expected.read_text())
        if stable(actual_thought) != stable(expected_thought):
            print(f'Thought artifact mismatch: {fixture_name}', file=sys.stderr)
            status = 1
        if stable(actual_verdict) != stable(expected_verdict):
            print(f'Reasoning verdict mismatch: {fixture_name}', file=sys.stderr)
            status = 1
sys.exit(status)
