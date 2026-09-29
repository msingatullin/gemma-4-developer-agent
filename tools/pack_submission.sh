#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

TARGET_DIR="${1:-$ROOT_DIR/submission}"
if [[ ! "$TARGET_DIR" = /* ]]; then
    TARGET_DIR="$ROOT_DIR/$TARGET_DIR"
fi

OUTPUT_ZIP="${2:-$ROOT_DIR/submission.zip}"
if [[ ! "$OUTPUT_ZIP" = /* ]]; then
    OUTPUT_ZIP="$ROOT_DIR/$OUTPUT_ZIP"
fi

echo "=== Packaging Gemma 4 Developer Agent Submission from $TARGET_DIR ==="

# 1. Run validation
python3 "$SCRIPT_DIR/validate_submission.py" "$TARGET_DIR"

# 2. Build ZIP
cd "$TARGET_DIR"
rm -f "$OUTPUT_ZIP"

zip -r "$OUTPUT_ZIP" . -x "*.DS_Store" "*__pycache__*" "*.git*"

echo "✅ Created: $OUTPUT_ZIP"
unzip -l "$OUTPUT_ZIP"
