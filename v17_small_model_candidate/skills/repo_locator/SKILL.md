---
name: repo_locator
description: Deterministic AST and BM25 lexical repository locator for finding exact defect locations and function line spans without reading whole files.
---

# Repository Locator Skill

Use the AST + BM25 repository locator to find the implementation files and symbols for any issue statement without searching tests or documentation:

```bash
python3 /tmp/ast_locator.py --query "SPECIFIC_IDENTIFIERS_FROM_ISSUE"
```

Or search directly with git grep excluding test and documentation trees:

```bash
git grep -n -i "SPECIFIC_TOKEN" -- ':!tests/*' ':!docs/*' ':!examples/*' | head -20
```
