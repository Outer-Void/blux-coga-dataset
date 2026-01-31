#!/usr/bin/env bash
set -euo pipefail

COGA_CMD=${COGA_CMD:-coga}
ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
MATRIX_PATH="${ROOT_DIR}/fixtures/fixture_matrix.json"

if [[ ! -f "${MATRIX_PATH}" ]]; then
  echo "Missing fixture matrix at ${MATRIX_PATH}." >&2
  exit 1
fi

if ! command -v jq >/dev/null 2>&1; then
  echo "jq is required for canonical JSON comparison." >&2
  exit 1
fi

DEFAULT_MODEL=$(jq -r '.default_model_version' "${MATRIX_PATH}")
DEFAULT_PACK=$(jq -r '.default_reasoning_pack' "${MATRIX_PATH}")
MODEL_VERSION=${MODEL_VERSION:-${DEFAULT_MODEL}}
REASONING_PACK=${REASONING_PACK:-${DEFAULT_PACK}}
PROFILE_ID=${PROFILE_ID:-}
PROFILE_VERSION=${PROFILE_VERSION:-}

status=0

for fixture_dir in "${ROOT_DIR}"/fixtures/*; do
  if [[ ! -d "${fixture_dir}" ]]; then
    continue
  fi

  problem_path="${fixture_dir}/problem.json"
  fixture_profile_id=$(jq -r '.required_profile_id // empty' "${problem_path}")
  fixture_profile_version=$(jq -r '.required_profile_version // empty' "${problem_path}")
  profile_id="${PROFILE_ID:-${fixture_profile_id}}"

  if [[ -n "${fixture_profile_id}" && -n "${PROFILE_ID}" && "${PROFILE_ID}" != "${fixture_profile_id}" ]]; then
    echo "Profile ID mismatch for ${fixture_dir##*/}: expected ${fixture_profile_id}, got ${PROFILE_ID}." >&2
    status=1
    continue
  fi

  if [[ -n "${fixture_profile_version}" && -n "${PROFILE_VERSION}" && "${PROFILE_VERSION}" != "${fixture_profile_version}" ]]; then
    echo "Profile version mismatch for ${fixture_dir##*/}: expected ${fixture_profile_version}, got ${PROFILE_VERSION}." >&2
    status=1
    continue
  fi

  if [[ -n "${fixture_profile_id}" && -z "${PROFILE_ID}" ]]; then
    echo "Fixture ${fixture_dir##*/} requires profile ${fixture_profile_id}; set PROFILE_ID to run." >&2
    status=1
    continue
  fi

  if [[ -n "${fixture_profile_version}" && -z "${PROFILE_VERSION}" ]]; then
    echo "Fixture ${fixture_dir##*/} requires profile version ${fixture_profile_version}; set PROFILE_VERSION to run." >&2
    status=1
    continue
  fi

  if [[ -n "${profile_id}" ]]; then
    expected_dir="${fixture_dir}/expected/${MODEL_VERSION}/${profile_id}/${REASONING_PACK}"
  else
    expected_dir="${fixture_dir}/expected/${MODEL_VERSION}/${REASONING_PACK}"
  fi
  expected_thought="${expected_dir}/expected_thought_artifact.json"
  expected_verdict="${expected_dir}/expected_reasoning_verdict.json"
  expected_report="${expected_dir}/report.json"

  if [[ ! -f "${expected_thought}" || ! -f "${expected_verdict}" ]]; then
    echo "Missing expected outputs for ${fixture_dir##*/} (${MODEL_VERSION}/${REASONING_PACK})." >&2
    status=1
    continue
  fi

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
