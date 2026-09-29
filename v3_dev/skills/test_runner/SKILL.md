---
name: test_runner
description: Instructions and guidelines for running focused regression tests with pytest, capturing concise tracebacks, and verifying patches without polluting terminal output.
---

# Test Runner Skill

When reproducing a bug or verifying a patch, always run targeted tests rather than the entire test suite to conserve execution time and avoid context overflows.

### Best Practices:
1. **Target Specific Tests**: Run single test files or specific test functions:
   ```bash
   pytest path/to/test_file.py -k "test_function_name" -v --tb=short
   ```
2. **Limit Traceback Noise**: Use `--tb=short` or `--tb=line` to keep error traces compact.
3. **Check Return Codes**: Exit code 0 means tests passed; exit code 1 means assertion failure (useful for reproduction before fix).
4. **Clean State**: Do not leave temporary test artifacts or cache files behind.
