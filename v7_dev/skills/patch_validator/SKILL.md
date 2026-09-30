---
name: patch_validator
description: Guidelines and checks for inspecting git diff quality before submitting a patch, ensuring zero leftover debug prints, conflict markers, or unintended files.
---

# Patch Validator Skill

Before invoking `submit_patch()`, always run a pre-submission diff audit:

### 1. Check Modified Files:
```bash
git status --short
```
Verify that ONLY legitimate source code files (under the library directory) are listed. No test files, no untracked scratch files.

### 2. Check for Clean Diff:
```bash
git diff
```
Ensure that:
- No temporary `print(...)` statements or debugging logs were added.
- No merge conflict markers (`<<<<<<<`, `=======`, `>>>>>>>`) exist.
- Code indentation strictly matches the surrounding file conventions.
- Only the minimum lines necessary to resolve the issue are changed.
