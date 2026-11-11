#!/usr/bin/env python3
"""Optional ANSI/CI-aware fail-open guard for frozen B2 pytest compressor.

Protects selected diagnostic/failure header/summary line multiplicity and
exposes a versioned tamper-evident evidence certificate.
This is NOT full semantic equivalence or cryptographic sender authentication.
Only Python standard library is required.
"""
from collections import Counter
import hashlib
import json
import re

SCHEMA="pytest-diagnostic-integrity-v2-ansi-ci"
ANSI=re.compile(r'\x1b\[[0-?]*[ -/]*[@-~]')
CI=re.compile(r'^\[worker-0\] ')
HEADER=re.compile(r'^_{3,}\s*.*?\s*_{3,}$')
EXCEPTION=re.compile(r'^[\w.]+(?:Error|Exception|Warning|Exit|Interrupt):')
GROUPS=("diagnostic","failure_headers","test_summaries")

def normalize_lines(text):
    if not isinstance(text,str):raise TypeError("expected str")
    text=ANSI.sub("",text).replace("\r\n","\n").replace("\r","\n")
    return [CI.sub("",line).strip() for line in text.splitlines()]

def evidence(text):
    lines=normalize_lines(text)
    return {
      "diagnostic":Counter(s for s in lines if s.startswith(("E ","E\t","> ","FAILED ","ERROR ")) or EXCEPTION.match(s)),
      "failure_headers":Counter(s for s in lines if HEADER.match(s)),
      "test_summaries":Counter(s for s in lines if s.startswith(("FAILED ","ERROR "))),
    }

def _comparable(raw,compressed):
    a=evidence(raw);b=evidence(compressed)
    if not all(a[g] for g in GROUPS):
        return False,"unsupported_evidence_format",a,b
    if any(a[g]!=b[g] for g in GROUPS):
        return False,"selected_evidence_multiplicity_mismatch",a,b
    return True,"verified",a,b

def guard(raw,compressor):
    """Return (safe_output, metadata). Unchanged compressor receives raw text.

    If selected normalized markers differ or format unsupported, return EXACT
    input bytes. For positive cases existing source output remains unchanged.
    """
    if not isinstance(raw,str):raise TypeError("expected string input")
    candidate=compressor(raw)
    if not isinstance(candidate,str):
        raise TypeError("compressor output must be string")
    verified,reason,_,_=_comparable(raw,candidate)
    if not verified:
        return raw,{"fallback":True,"reason":reason}
    return candidate,{"fallback":raw==candidate,"reason":"verified_selected_diagnostics"}

def _fingerprint(counts):
    return {key:[[s,n] for s,n in sorted(counts[key].items())] for key in GROUPS}

def produce_certificate(raw,output):
    is_ok,reason,a,b=_comparable(raw,output)
    return {
       "schema_version":SCHEMA,
       "source_utf8_sha256":hashlib.sha256(raw.encode()).hexdigest(),
       "output_utf8_sha256":hashlib.sha256(output.encode()).hexdigest(),
       "source_utf8_bytes":len(raw.encode()),
       "output_utf8_bytes":len(output.encode()),
       "raw_fallback":raw==output,
       "source_evidence":_fingerprint(a),
       "output_evidence":_fingerprint(b),
       "verdict":"PASS" if is_ok else "FAIL",
       "reason":reason,
    }

def _reject_duplicates(pairs):
    out={}
    for k,v in pairs:
        if k in out:raise ValueError("duplicate JSON key")
        out[k]=v
    return out

def verify(raw,output,record):
    """Independently recompute all fields; no reliance on producer verdict."""
    if isinstance(record,(str,bytes)):
        try: record=json.loads(record,object_pairs_hook=_reject_duplicates)
        except (ValueError,TypeError,UnicodeError): return False
    if not isinstance(record,dict):return False
    try: expected=produce_certificate(raw,output)
    except (TypeError,UnicodeError):return False
    return expected["verdict"]=="PASS" and record==expected

def serialize(cert):
    return json.dumps(cert,ensure_ascii=False,sort_keys=True,separators=(",",":"))+"\n"
