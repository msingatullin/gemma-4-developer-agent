#!/usr/bin/env python3
"""
Deterministic Lexical / BM25 / AST Repository Locator (Optimized v2)
Designed for Small LLM (Gemma 4 E4B) SWE-bench task navigation.

Features:
1. Pure Python 3.9+ (zero heavyweight dependencies).
2. AST extraction of classes, functions, methods, decorators, CLI commands, docstrings, and symbol names.
3. Stem-aware filename matching (e.g. 'blueprint' matches 'src/flask/blueprints.py').
4. CLI command extraction (@click.command, @cli.command("name")).
5. BM25 (Okapi) ranking with structural AST boosts.
6. Execution time: < 0.5s on Flask/Requests, < 2.0s on Django.
"""

import os
import re
import ast
import math
import time
from pathlib import Path
from collections import Counter, defaultdict

STOPWORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are",
    "aren't", "as", "at", "be", "because", "been", "before", "being", "below", "between", "both",
    "but", "by", "can't", "cannot", "could", "couldn't", "did", "didn't", "do", "does", "doesn't",
    "doing", "don't", "down", "during", "each", "few", "for", "from", "further", "had", "hadn't",
    "has", "hasn't", "have", "haven't", "having", "he", "he'd", "he'll", "he's", "her", "here",
    "here's", "hers", "herself", "him", "himself", "his", "how", "how's", "i", "i'd", "i'll", "i'm",
    "i've", "if", "in", "into", "is", "isn't", "it", "it's", "its", "itself", "let's", "me", "more",
    "most", "mustn't", "my", "myself", "no", "nor", "not", "of", "off", "on", "once", "only", "or",
    "other", "ought", "our", "ours", "ourselves", "out", "over", "own", "same", "shan't", "she",
    "she'd", "she'll", "she's", "should", "shouldn't", "so", "some", "such", "than", "that", "that's",
    "the", "their", "theirs", "them", "themselves", "then", "there", "there's", "these", "they",
    "they'd", "they'll", "they're", "they've", "this", "those", "through", "to", "too", "under",
    "until", "up", "very", "was", "wasn't", "we", "we'd", "we'll", "we're", "we've", "were", "weren't",
    "what", "what's", "when", "when's", "where", "where's", "which", "while", "who", "who's", "whom",
    "why", "why's", "with", "won't", "would", "wouldn't", "you", "you'd", "you'll", "you're", "you've",
    "your", "yours", "yourself", "yourselves", "self", "none", "true", "false", "return", "def", "class",
    "import", "from", "as", "pass", "raise", "try", "except", "finally", "with", "assert", "lambda"
}

IGNORE_DIRS = {
    ".git", ".github", ".pytest_cache", "__pycache__", "venv", ".venv", "env",
    "build", "dist", "docs", "doc", "htmlcov", "egg-info"
}


def clean_stem(word: str) -> str:
    """Simple rule-based stemming for code identifiers."""
    w = word.lower()
    for suffix in ("ing", "ies", "es", "s", "ed"):
        if w.endswith(suffix) and len(w) > len(suffix) + 2:
            return w[:-len(suffix)]
    return w


def tokenize_code(text: str) -> list[str]:
    """Tokenizes code and text, expanding snake_case and camelCase."""
    if not text:
        return []
    raw_tokens = re.findall(r'[a-zA-Z0-9_]+', text)
    tokens = []
    for tok in raw_tokens:
        tok_lower = tok.lower()
        if tok_lower not in STOPWORDS and len(tok_lower) > 1:
            tokens.append(tok_lower)
            stem = clean_stem(tok_lower)
            if stem != tok_lower and len(stem) > 1:
                tokens.append(stem)

        # Split snake_case
        parts = tok.split("_")
        if len(parts) > 1:
            for p in parts:
                p_lower = p.lower()
                if p_lower not in STOPWORDS and len(p_lower) > 1:
                    tokens.append(p_lower)

        # Split camelCase
        camel_parts = re.findall(r'[A-Z]?[a-z]+|[A-Z]+(?=[A-Z][a-z]|\b)', tok)
        if len(camel_parts) > 1:
            for cp in camel_parts:
                cp_lower = cp.lower()
                if cp_lower not in STOPWORDS and len(cp_lower) > 1:
                    tokens.append(cp_lower)
    return tokens


class ASTRepoIndexer:
    """Indexes a repository using Python AST into searchable structural documents."""

    def __init__(self, repo_root: Path):
        self.repo_root = Path(repo_root)
        self.file_docs = {}
        self.corpus_size = 0
        self.doc_lengths = {}
        self.avg_doc_len = 0.0
        self.df = defaultdict(int)

    def index(self):
        start_time = time.time()
        py_files = []
        for root, dirs, files in os.walk(self.repo_root):
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS and not d.endswith(".egg-info")]
            for f in files:
                if f.endswith(".py"):
                    py_files.append(Path(root) / f)

        total_tokens = 0
        for p in py_files:
            rel_path = str(p.relative_to(self.repo_root))
            try:
                content = p.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue

            # Path tokens
            path_tokens = tokenize_code(rel_path)
            stem_name = clean_stem(p.stem)
            path_tokens.append(stem_name)

            symbols = []
            func_records = []
            body_tokens = []
            cli_commands = []

            try:
                tree = ast.parse(content, filename=rel_path)
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        symbols.append(node.name)
                        doc = ast.get_docstring(node) or ""
                        f_tokens = tokenize_code(node.name) * 4 + tokenize_code(doc) * 2
                        body_tokens.extend(f_tokens)

                        # Check for CLI command decorators e.g. @cli.command("routes") or @click.command
                        for dec in getattr(node, "decorator_list", []):
                            if isinstance(dec, ast.Call):
                                for arg in dec.args:
                                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                                        cli_commands.append(arg.value.lower())
                                        f_tokens.extend([arg.value.lower()] * 5)

                        func_records.append({
                            "name": node.name,
                            "start_line": getattr(node, "lineno", 1),
                            "end_line": getattr(node, "end_lineno", getattr(node, "lineno", 1) + 20),
                            "tokens": set(f_tokens)
                        })
                    elif isinstance(node, ast.ClassDef):
                        symbols.append(node.name)
                        doc = ast.get_docstring(node) or ""
                        c_tokens = tokenize_code(node.name) * 4 + tokenize_code(doc) * 2
                        body_tokens.extend(c_tokens)
            except Exception:
                body_tokens = tokenize_code(content)

            all_doc_tokens = path_tokens * 6 + body_tokens
            token_counts = Counter(all_doc_tokens)
            self.file_docs[rel_path] = {
                "token_counts": token_counts,
                "symbols": symbols,
                "functions": func_records,
                "cli_commands": cli_commands,
                "stem": stem_name,
                "length": len(all_doc_tokens)
            }
            total_tokens += len(all_doc_tokens)
            for term in token_counts:
                self.df[term] += 1

        self.corpus_size = len(self.file_docs)
        self.doc_lengths = {p: d["length"] for p, d in self.file_docs.items()}
        self.avg_doc_len = (total_tokens / self.corpus_size) if self.corpus_size > 0 else 1.0
        elapsed = time.time() - start_time
        return self.corpus_size, elapsed


class BM25Locator:
    """Ranks repository files and AST definitions for a given issue statement."""

    def __init__(self, indexer: ASTRepoIndexer, k1: float = 1.5, b: float = 0.75):
        self.indexer = indexer
        self.k1 = k1
        self.b = b

    def query(self, problem_statement: str, top_k_files: int = 5, top_k_symbols: int = 3) -> dict:
        q_tokens = tokenize_code(problem_statement)
        q_counts = Counter(q_tokens)
        q_stems = set(q_tokens)

        # File references
        file_hints = set(re.findall(r'([a-zA-Z0-9_\-]+\.py)\b', problem_statement))

        # Symbol references in backticks
        symbol_hints = set(re.findall(r'`([a-zA-Z0-9_\.]+)`', problem_statement))
        cleaned_symbol_hints = set()
        for sh in symbol_hints:
            for sub in sh.split("."):
                if sub.lower() not in STOPWORDS and len(sub) > 2:
                    cleaned_symbol_hints.add(sub.lower())
                    cleaned_symbol_hints.add(clean_stem(sub.lower()))

        # Command references like "flask routes" or "python -m pytest"
        cmd_matches = set(re.findall(r'\b(?:flask|manage\.py|pytest)\s+([a-zA-Z0-9_\-]+)\b', problem_statement.lower()))

        scores = {}
        N = self.indexer.corpus_size
        avgdl = self.indexer.avg_doc_len

        for rel_path, doc in self.indexer.file_docs.items():
            score = 0.0
            doc_len = doc["length"]
            t_counts = doc["token_counts"]

            for q_term, q_tf in q_counts.items():
                if q_term in t_counts:
                    df_val = self.indexer.df[q_term]
                    idf = math.log(1.0 + (N - df_val + 0.5) / (df_val + 0.5))
                    tf_val = t_counts[q_term]
                    numerator = tf_val * (self.k1 + 1.0)
                    denominator = tf_val + self.k1 * (1.0 - self.b + self.b * (doc_len / avgdl))
                    score += idf * (numerator / denominator)

            # Heuristic Boosts
            # 1. Exact file mention in problem statement
            basename = os.path.basename(rel_path)
            if basename in file_hints:
                score += 50.0

            # 2. Stem match on filename (e.g. 'blueprint' matches 'blueprints.py')
            if doc["stem"] in q_stems and len(doc["stem"]) > 3:
                score += 35.0

            # 3. CLI command match (e.g. 'flask routes' matches cli.py with 'routes')
            for cmd in cmd_matches:
                if cmd in doc["cli_commands"]:
                    score += 40.0

            # 4. Downweight test files
            if "test" in rel_path.lower() or "tests/" in rel_path:
                score *= 0.15

            # 5. Symbol match boost
            matched_symbols = []
            for func in doc["functions"]:
                f_name = func["name"]
                f_lower = f_name.lower()
                f_stem = clean_stem(f_lower)
                if f_lower in cleaned_symbol_hints or f_stem in cleaned_symbol_hints:
                    score += 25.0
                    matched_symbols.append((f_name, func["start_line"], func["end_line"]))
                elif any(qt in func["tokens"] for qt in q_counts):
                    matched_symbols.append((f_name, func["start_line"], func["end_line"]))

            scores[rel_path] = (score, matched_symbols[:top_k_symbols])

        ranked = sorted(scores.items(), key=lambda x: x[1][0], reverse=True)

        results = []
        for path, (s, syms) in ranked[:top_k_files]:
            results.append({
                "file": path,
                "score": round(s, 2),
                "suggested_symbols": [{"name": s[0], "start_line": s[1], "end_line": s[2]} for s in syms]
            })

        return {
            "top_files": results,
            "top_file": results[0]["file"] if results else None
        }


def format_locator_hint(locator_result: dict) -> str:
    """Formats top-ranked files and function hints into an agent prompt block."""
    lines = ["## Recommended Defect Locations (AST + BM25 Lexical Ranking)"]
    for i, item in enumerate(locator_result.get("top_files", [])[:3], 1):
        f = item["file"]
        syms = item["suggested_symbols"]
        if syms:
            sym_str = ", ".join([f"`{s['name']}` (L{s['start_line']}-{s['end_line']})" for s in syms])
            lines.append(f"{i}. `{f}` -> symbols: {sym_str}")
        else:
            lines.append(f"{i}. `{f}`")
    return "\n".join(lines)
