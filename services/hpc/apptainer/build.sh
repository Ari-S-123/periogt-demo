#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
DEF_FILE="${SCRIPT_DIR}/apptainer.def"
OUTPUT_FILE="${SCRIPT_DIR}/periogt.sif"
USE_FAKEROOT=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --fakeroot)
      USE_FAKEROOT=1
      shift
      ;;
    --output)
      OUTPUT_FILE="$2"
      shift 2
      ;;
    *)
      echo "Unknown argument: $1" >&2
      echo "Usage: $0 [--fakeroot] [--output /path/to/periogt.sif]" >&2
      exit 2
      ;;
  esac
done

if ! command -v apptainer >/dev/null 2>&1; then
  echo "apptainer not found on PATH. Load module or install Apptainer first." >&2
  exit 2
fi

mkdir -p "$(dirname "${OUTPUT_FILE}")"

CMD=(apptainer build)
if [[ "${USE_FAKEROOT}" -eq 1 ]]; then
  CMD+=(--fakeroot)
fi
CMD+=("${OUTPUT_FILE}" "${DEF_FILE}")

echo "Building Apptainer image..."
(
  cd "${REPO_ROOT}"
  "${CMD[@]}"
)

if command -v sha256sum >/dev/null 2>&1; then
  SHA="$(sha256sum "${OUTPUT_FILE}" | awk '{print $1}')"
elif command -v shasum >/dev/null 2>&1; then
  SHA="$(shasum -a 256 "${OUTPUT_FILE}" | awk '{print $1}')"
else
  SHA="(sha256 unavailable)"
fi

echo "Built image: ${OUTPUT_FILE}"
echo "SHA256: ${SHA}"

