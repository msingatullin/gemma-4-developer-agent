---
name: repo_locator
description: Portable filename-first repository search with optional AST/BM25 locator.
---

# Repository Locator

The skill archive contains `ast_locator.py`. **Its presence in the submission archive does not imply it is mounted at `/tmp/ast_locator.py` inside the Kaggle task sandbox.** Never invoke that path without checking that it exists.

Use one `run_command` with quoted placeholders replaced by actual issue-derived identifiers:

```bash
if [ -f /tmp/ast_locator.py ]; then
  python3 /tmp/ast_locator.py --query "ISSUE_IDENTIFIERS" --top-k 3
else
  echo FILENAME_HITS
  git ls-files '*.py' | grep -i -F "ONE_EXACT_IDENTIFIER" | grep -Ev '(^|/)(tests?|docs?|examples?)/' | head -10
  echo CONTENT_FILE_HITS
  git grep -i -l -F "ONE_EXACT_IDENTIFIER" -- '*.py' ':!tests/**' ':!**/tests/**' ':!**/test_*.py' ':!docs/**' ':!**/docs/**' ':!examples/**' ':!**/examples/**' | head -20
fi
```

Inspect filename hits first; then look at listed implementation modules. This fallback uses Git pathspec matching nested `.py` paths. If the issue concerns documentation examples, deliberately include `docs_src/` in the search. No test oracle, `target_file`, gold patch, or answer key may be passed to the agent. No workspace scripts or repo pollution. This fallback is not a BM25 result and does not prove issue resolution.
