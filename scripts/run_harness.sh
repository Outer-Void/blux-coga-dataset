#!/usr/bin/env bash
set -euo pipefail

COGA_CMD=${COGA_CMD:-coga}
ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)

if ! command -v jq >/dev/null 2>&1; then
  echo "jq is required for canonical JSON comparison." >&2
  exit 1
fi

status=0

for fixture_dir in "${ROOT_DIR}"/fixtures/*; do
  if [[ ! -d "${fixture_dir}" ]]; then
    continue
  fi

  problem_path="${fixture_dir}/problem.json"
  expected_thought="${fixture_dir}/expected_thought_artifact.json"
  expected_verdict="${fixture_dir}/expected_reasoning_verdict.json"

  actual_thought=$(mktemp)
  actual_verdict=$(mktemp)

  "${COGA_CMD}" \
    --problem "${problem_path}" \
    --output-thought "${actual_thought}" \
    --output-verdict "${actual_verdict}"

  if ! diff -u <(jq -S . "${expected_thought}") <(jq -S . "${actual_thought}"); then
    status=1
  fi

  if ! diff -u <(jq -S . "${expected_verdict}") <(jq -S . "${actual_verdict}"); then
    status=1
  fi

  rm -f "${actual_thought}" "${actual_verdict}"
done

exit ${status}
