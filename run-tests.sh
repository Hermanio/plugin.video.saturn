#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat <<'USAGE'
The test runner for Saturn.

  ./run-tests.sh          static + unit tests, no network     (~3s)
  ./run-tests.sh api      the live ERR API                    (~30s)
  ./run-tests.sh check    build the zip, run the Kodi checker (~70s)
  ./run-tests.sh all      every level, in that order

The first run creates .venv and installs tests/requirements.txt.
USAGE
}

ADDON_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="${ADDON_DIR}/.venv"
PY="${VENV}/bin/python"

STAMP="$(cat "${ADDON_DIR}/tests/requirements.txt"; echo "${VENV}")"
if [[ "$(cat "${VENV}/.stamp" 2>/dev/null)" != "${STAMP}" ]]; then
    echo "==> installing test dependencies into ${VENV}"
    python3 -m venv --clear "${VENV}"
    "${PY}" -m pip install -q -r "${ADDON_DIR}/tests/requirements.txt"
    printf '%s' "${STAMP}" > "${VENV}/.stamp"
fi

cd "${ADDON_DIR}"
pytest() { "${PY}" -m pytest tests -q "$@"; }

case "${1:-fast}" in
    fast) pytest -m 'not integration and not compliance' ;;
    api) pytest -m integration ;;
    check) pytest -m compliance ;;
    all) for level in fast api check; do "$0" "${level}"; done ;;
    -h|--help) usage ;;
    *) usage >&2; exit 2 ;;
esac
