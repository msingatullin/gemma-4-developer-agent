---
name: ast_indexer
description: Guidance on using Python AST and symbol indexing techniques to inspect function signatures, class hierarchies, and import statements without reading entire source files.
---

# AST Indexer Skill

When navigating large repositories, avoid reading multi-thousand line files entirely. Use python one-liners or targeted grep to inspect AST structure:

### Inspecting Class & Function Definitions:
```bash
python3 -c "import ast; tree = ast.parse(open('target.py').read()); print([node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.ClassDef))])"
```

### Finding Function Line Numbers:
```bash
python3 -c "import ast; tree = ast.parse(open('target.py').read()); print([(node.name, node.lineno) for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)])"
```

Use line numbers obtained from this analysis to read only the relevant slice of the file with `read_file(path, start_line, end_line)`.
