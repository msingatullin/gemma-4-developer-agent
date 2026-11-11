"""CLI: python -m gemma4_verified_context {slice,check,compress} ..."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

from .core import check_syntax, compress_log, slice_source


def main(argv=None):
    ap=argparse.ArgumentParser(description="Zero-inference safeguards for local coding agents")
    sub=ap.add_subparsers(dest="action",required=True)
    a=sub.add_parser("slice",help="AST slice a fully qualified Python method/class")
    a.add_argument("file")
    a.add_argument("symbol",help="e.g. Blueprint.add_url_rule")
    a.add_argument("--context-lines",type=int,default=0)
    a.add_argument("--metadata",action="store_true")
    b=sub.add_parser("check",help="syntax-check a Python file without executing it")
    b.add_argument("file")
    c=sub.add_parser("compress",help="write compacted pytest log to stdout")
    c.add_argument("file")
    c.add_argument("--metadata",action="store_true")
    ns=ap.parse_args(argv)
    try:
        raw=Path(ns.file).read_text(encoding="utf-8")
        if ns.action=="slice":
            result=slice_source(raw,ns.symbol,ns.context_lines)
            if ns.metadata:
                print(json.dumps(result.metadata(),ensure_ascii=False),file=sys.stderr)
            sys.stdout.write(result.text)
            return 0 if not result.returned_full_source else 2
        if ns.action=="check":
            result=check_syntax(raw,ns.file)
            print(json.dumps(result.__dict__,ensure_ascii=False))
            return 0 if result.passed else 1
        if ns.action=="compress":
            result=compress_log(raw)
            if ns.metadata:
                print(json.dumps(result.metadata(),ensure_ascii=False),file=sys.stderr)
            sys.stdout.write(result.text)
            return 0
    except (OSError,UnicodeDecodeError,ValueError,TypeError) as exc:
        print(f"{type(exc).__name__}: {exc}",file=sys.stderr)
        return 2
    return 2


if __name__=="__main__":
    raise SystemExit(main())
