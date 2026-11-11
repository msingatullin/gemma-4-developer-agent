#!/usr/bin/env python3
"""Versioned SHA256 evidence certificate for deterministic pytest log compression.

Uses only Python stdlib. This is a selected-string/byte-digest contract, not
full semantic equivalence or cryptographic sender authentication.
"""
from collections import Counter
import hashlib
import json
import re

SCHEMA_VERSION="pytest-diagnostic-integrity-v1"
GROUPS=("diagnostic","failure_headers","test_summaries")

def _digest(content):
    return hashlib.sha256(content.encode("utf-8")).hexdigest()

def _bytes(content):
    return len(content.encode("utf-8"))

def extract(content):
    if not isinstance(content,str):
        raise TypeError("expected text")
    lines=content.splitlines()
    return {
        "diagnostic":Counter(x.strip() for x in lines
            if x.lstrip().startswith(("E ","E\t","> ","FAILED ","ERROR "))
            or re.match(r'^[\w.]+(?:Error|Exception|Warning|Exit|Interrupt):',x.strip())),
        "failure_headers":Counter(x.strip() for x in lines
            if re.match(r'^_{3,}\s*.*?\s*_{3,}$',x.strip())),
        "test_summaries":Counter(x.strip() for x in lines
            if x.strip().startswith(("FAILED ","ERROR "))),
    }

def _fingerprint(x):
    return {k:[[s,count] for s,count in sorted(x[k].items())] for k in GROUPS}

def produce(raw, compressed):
    if not isinstance(raw,str) or not isinstance(compressed,str):
        raise TypeError("raw and output must be text")
    source=extract(raw)
    target=extract(compressed)
    equivalent=all(source[k]==target[k] for k in GROUPS)
    return {
        "schema_version":SCHEMA_VERSION,
        "source_sha256":_digest(raw),
        "result_sha256":_digest(compressed),
        "source_utf8_bytes":_bytes(raw),
        "result_utf8_bytes":_bytes(compressed),
        "raw_fallback":raw==compressed,
        "selected_evidence_equal":equivalent,
        "source_selected_evidence":_fingerprint(source),
        "result_selected_evidence":_fingerprint(target),
        "verdict":"PASS" if equivalent else "FAIL",
    }

def _reject_duplicate_json_keys(items):
    result={}
    for k,v in items:
        if k in result:raise ValueError("duplicate JSON key")
        result[k]=v
    return result

def verify(raw, compressed, certificate):
    """Verify with independently supplied raw+output and metadata; fail closed."""
    if isinstance(certificate,(bytes,str)):
        try:
            certificate=json.loads(certificate,object_pairs_hook=_reject_duplicate_json_keys)
        except (UnicodeError,ValueError,TypeError):
            return False
    if not isinstance(certificate,dict):
        return False
    try:
        actual=produce(raw,compressed)
    except (ValueError,TypeError):
        return False
    # Reject unknown keys and forged verdict, stale hash or altered line counts.
    return (certificate==actual and actual["verdict"]=="PASS")

def canonical_json(certificate):
    return json.dumps(certificate,sort_keys=True,separators=(",",":"),ensure_ascii=False)+"\n"
