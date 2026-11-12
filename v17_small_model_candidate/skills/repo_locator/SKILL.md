---
name: repo_locator
description: Portable repository localization with an optional AST/BM25 helper and a safe built-in git-grep fallback.
---

# Repository Locator Skill

The skill directory contains `ast_locator.py`, but the Kaggle task workspace is isolated from the submission package. **Do not assume** a copy exists at `/tmp/ast_locator.py`. The current candidate does not prove that staging.

Use one `run_command` call with issue-derived strings replacing the placeholders:

```bash
if [ -f /tmp/ast_locator.py ]; then
  python3 /tmp/ast_locator.py --query "ISSUE_IDENTIFIERS" --top-k 3
else
  git grep -n -i -F "ONE_EXACT_IDENTIFIER" -- '*.py' ':!**/tests/**' ':!**/test_*.py' ':!**/docs/**' | head -25
fi
```

The fallback searches nested Python implementation paths using Git pathspecs (not a shell-expanded root-only glob). If the exact term has no hits, try one alternate identifier or error string. For tasks explicitly concerning documentation examples, include the appropriate `docs_src/` paths. Never create locator scripts or other scratch files inside the task repository. A clean fallback is **not** evidence that BM25 ran, nor that the agent solved the task.
