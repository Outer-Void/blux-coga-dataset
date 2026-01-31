#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
MATRIX_PATH="${ROOT_DIR}/fixtures/fixture_matrix.json"

if [[ ! -f "${MATRIX_PATH}" ]]; then
  echo "Missing fixture matrix at ${MATRIX_PATH}." >&2
  exit 1
fi

if ! command -v jq >/dev/null 2>&1; then
  echo "jq is required for fixture verification." >&2
  exit 1
fi

mapfile -t models < <(jq -r '.model_versions[]' "${MATRIX_PATH}")
mapfile -t packs < <(jq -r '.reasoning_packs[]' "${MATRIX_PATH}")

status=0

for fixture_dir in "${ROOT_DIR}"/fixtures/*; do
  if [[ ! -d "${fixture_dir}" ]]; then
    continue
  fi

  if [[ ! -f "${fixture_dir}/problem.json" ]]; then
    echo "Missing problem.json in ${fixture_dir##*/}." >&2
    status=1
    continue
  fi

  for model in "${models[@]}"; do
    for pack in "${packs[@]}"; do
      expected_dir="${fixture_dir}/expected/${model}/${pack}"
      expected_thought="${expected_dir}/expected_thought_artifact.json"
      expected_verdict="${expected_dir}/expected_reasoning_verdict.json"

      if [[ ! -f "${expected_thought}" || ! -f "${expected_verdict}" ]]; then
        echo "Missing expected outputs for ${fixture_dir##*/} (${model}/${pack})." >&2
        status=1
      fi
    done
  done
done

exit ${status}
