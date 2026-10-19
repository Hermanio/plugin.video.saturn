#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat <<'USAGE'
Build an installable Kodi add-on zip for Saturn: one top-level directory
named after the add-on id, holding the add-on and nothing else.

  ./package.sh                 -> dist/plugin.video.saturn-<version>.zip
  ./package.sh /tmp/out        write the zip somewhere else
USAGE
}

case "${1:-}" in -h|--help) usage; exit 0 ;; esac

ADDON_ID="plugin.video.saturn"
SHIPPED=(addon.py addon.xml LICENSE icon.png fanart.jpg banner.png
         clearlogo.png resources)
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT_DIR="$(mkdir -p "${1:-${SRC_DIR}/dist}" && cd "${1:-${SRC_DIR}/dist}" && pwd)"

VERSION="$(tr '\n' ' ' < "${SRC_DIR}/addon.xml" \
    | sed -n 's/.*<addon[^>]*[[:space:]]version="\([0-9][^"]*\)".*/\1/p')"
if [[ -z "${VERSION}" ]]; then
    echo "error: could not parse version from addon.xml" >&2
    exit 1
fi
ZIP_PATH="${OUT_DIR}/${ADDON_ID}-${VERSION}.zip"

STAGE="$(mktemp -d)"
trap 'rm -rf "${STAGE}"' EXIT
mkdir "${STAGE}/${ADDON_ID}"
( cd "${SRC_DIR}" && cp -r "${SHIPPED[@]}" "${STAGE}/${ADDON_ID}/" )
find "${STAGE}" -name '__pycache__' -type d -prune -exec rm -rf {} +
find "${STAGE}" -type f -exec chmod 644 {} +
find "${STAGE}" -type d -exec chmod 755 {} +
find "${STAGE}" -exec touch -d @315532800 {} +

rm -f "${ZIP_PATH}"
( cd "${STAGE}" && find "${ADDON_ID}" | LC_ALL=C sort \
    | TZ=UTC zip -q -X "${ZIP_PATH}" -@ )

echo "Built ${ZIP_PATH}"
echo "  sha256: $(sha256sum "${ZIP_PATH}" | cut -d' ' -f1)"
