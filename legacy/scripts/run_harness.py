#!/usr/bin/env python3
import json
import os
import shutil
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


def _with_pythonpath(env: dict[str, str], extra_path: Path) -> dict[str, str]:
    updated = dict(env)
    current = updated.get('PYTHONPATH')
    updated['PYTHONPATH'] = str(extra_path) if not current else os.pathsep.join([str(extra_path), current])
    return updated


def resolve_engine_entrypoint():
    repo = os.environ.get('BLUX_COGA_REPO')
    if not repo:
        sibling = ROOT.parent / 'blux-coga'
        if sibling.exists():
            repo = str(sibling)
    if repo:
        repo_path = Path(repo)
        if not repo_path.exists():
            print(f'Ignoring BLUX_COGA_REPO={repo_path}: path does not exist.', file=sys.stderr)
        else:
            src_path = repo_path / 'src'
            venv_bin = repo_path / '.venv' / 'bin' / 'blux-coga'
            if venv_bin.exists():
                return [str(venv_bin)], str(repo_path), dict(os.environ), 'repo .venv script'
            venv_python = repo_path / '.venv' / 'bin' / 'python'
            if venv_python.exists():
                env = _with_pythonpath(dict(os.environ), src_path) if src_path.exists() else dict(os.environ)
                return [str(venv_python), '-m', 'blux_coga'], str(repo_path), env, 'repo .venv module'
            if src_path.exists():
                return [sys.executable, '-m', 'blux_coga'], str(repo_path), _with_pythonpath(dict(os.environ), src_path), 'repo source checkout via PYTHONPATH'
            return [sys.executable, '-m', 'blux_coga'], str(repo_path), dict(os.environ), 'current python module in repo'
    binary = os.environ.get('BLUX_COGA_BIN') or shutil.which('blux-coga')
    if binary:
        return [binary], str(ROOT), dict(os.environ), 'installed blux-coga script'
    return [sys.executable, '-m', 'blux_coga'], str(ROOT), dict(os.environ), 'current python module'


def build_engine_cmd(problem_path: Path, output_dir: Path):
    base_cmd, cwd, env, descriptor = resolve_engine_entrypoint()
    cmd = [*base_cmd, 'run', '--input', str(problem_path), '--output-dir', str(output_dir)]
    profile = os.environ.get('PROFILE_ID')
    profile_file = os.environ.get('PROFILE_FILE')
    if profile:
        cmd += ['--profile', profile]
    if profile_file:
        cmd += ['--profile-file', profile_file]
    return cmd, cwd, env, descriptor


status = 0
engine_cmd, engine_cwd, engine_env, engine_descriptor = build_engine_cmd(ROOT / 'fixtures' / MATRIX['fixtures'][0] / 'problem.json', Path('/tmp/placeholder'))
print(f'Using engine entrypoint: {engine_descriptor}', file=sys.stderr)
print('Command template: ' + ' '.join(engine_cmd[:-2] + ['<OUTPUT_DIR>']), file=sys.stderr)
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
        cmd, cwd, env, _ = build_engine_cmd(fixture_dir / 'problem.json', out)
        try:
            subprocess.run(cmd, cwd=cwd, env=env, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        except FileNotFoundError as exc:
            print(f'Unable to locate engine command: {exc}', file=sys.stderr)
            sys.exit(1)
        except subprocess.CalledProcessError as exc:
            if exc.stdout:
                print(exc.stdout, end='')
            if exc.stderr:
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
