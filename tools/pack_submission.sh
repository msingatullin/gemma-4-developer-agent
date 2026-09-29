#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
SUBMISSION_DIR="$ROOT_DIR/submission"
OUTPUT_ZIP="$ROOT_DIR/submission.zip"

echo "=== Packaging Gemma 4 Developer Agent Submission ==="

# 1. Run validation
python3 "$SCRIPT_DIR/validate_submission.py"

# 2. Build ZIP
cd "$SUBMISSION_DIR"
rm -f "$OUTPUT_ZIP"

zip -r "$OUTPUT_ZIP" . -x "*.DS_Store" "*__pycache__*" "*.git*"

echo "✅ Created: $OUTPUT_ZIP"
unzip -l "$OUTPUT_ZIP"
