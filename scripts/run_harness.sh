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
  expected_report="${fixture_dir}/report.json"

  actual_thought=$(mktemp)
  actual_verdict=$(mktemp)
  actual_report=""

  if [[ -f "${expected_report}" ]]; then
    actual_report=$(mktemp)
    "${COGA_CMD}" \
      --problem "${problem_path}" \
      --output-thought "${actual_thought}" \
      --output-verdict "${actual_verdict}" \
      --output-report "${actual_report}"
  else
    "${COGA_CMD}" \
      --problem "${problem_path}" \
      --output-thought "${actual_thought}" \
      --output-verdict "${actual_verdict}"
  fi

  if ! diff -u <(jq -S . "${expected_thought}") <(jq -S . "${actual_thought}"); then
    status=1
  fi

  if ! diff -u <(jq -S . "${expected_verdict}") <(jq -S . "${actual_verdict}"); then
    status=1
  fi

  if [[ -n "${actual_report}" ]]; then
    if ! diff -u <(jq -S . "${expected_report}") <(jq -S . "${actual_report}"); then
      status=1
    fi
    rm -f "${actual_report}"
  fi

  rm -f "${actual_thought}" "${actual_verdict}"
done

exit ${status}
