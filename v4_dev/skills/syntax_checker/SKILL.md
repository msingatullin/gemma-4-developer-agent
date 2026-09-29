---
name: syntax_checker
description: Instructions for verifying Python syntax and compilation integrity on modified files using py_compile before running pytest or submitting.
---

# Syntax Checker Skill

Whenever you modify a Python file using `edit_file` or `write_file`, immediately verify that the file compiles cleanly without syntax or indentation errors:

### Verification Command:
```bash
python3 -m py_compile <path_to_modified_file.py>
```

- If return code is **0**: The file has valid Python syntax.
- If return code is **non-zero**: A `SyntaxError` or `IndentationError` exists. Fix the formatting or indentation immediately using `edit_file` before attempting to run tests.
