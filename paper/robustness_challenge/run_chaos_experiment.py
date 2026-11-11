#!/usr/bin/env python3
"""Synthetic format-robustness tests on 11 fixed authentic upstream red logs.

Only origins are authentic failures; 88 transformations are deterministic
synthetic stress cases. A separately written ANSI and CI-aware evidence oracle
is intentionally independent of the existing source compressor/certificate.
"""
import collections
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
PAPER=HERE.parent
if not (PAPER/'traceback_compressor.py').exists():
    PAPER=Path('/opt/kaggle/gemma-paper/paper')
SOURCE=PAPER/'traceback_compressor.py'
CERT=PAPER/'verification_certificate/diagnostic_certificate.py'
FIXTURES=(
 PAPER/'e2e_gemma_experiment/real_repo_sample/REAL_LOG_FIXTURES_5REPOS_20261111.json',
 PAPER/'e2e_gemma_experiment/real_repo_sample/REAL_LOG_FIXTURES_HOLDOUT3_20261111.json',
)
# The public checkout contains all files. Older VPS source checkout predates
# the separately published resource and uses the frozen fixture snapshots.
if not CERT.exists():
    CERT=Path('/opt/kaggle/gemma-paper-kaggle-cli/cert-experiment-20261111/diagnostic_certificate.py')
if not all(p.exists() for p in FIXTURES):
    FIXTURES=(
      Path('/opt/kaggle/gemma-paper-kaggle-cli/baseline-comparison-5repos-20261111/REAL_LOG_FIXTURES_5REPOS_20261111.json'),
      Path('/opt/kaggle/gemma-paper-kaggle-cli/holdout3-20261111/REAL_LOG_FIXTURES_HOLDOUT3_20261111.json'),
    )
ANSI_RE=re.compile(r'\x1b\[[0-?]*[ -/]*[@-~]')
HEADER_RE=re.compile(r'^_{3,}\s*.*?\s*_{3,}$')
EXC_RE=re.compile(r'^[\w.]+(?:Error|Exception|Warning|Exit|Interrupt):')
TYPES=("ansi_critical","ansi_all","crlf","duplicate_diagnostic",
       "captured_stdout_sentinel","native_traceback","exception_group","ci_log_prefix")

def load_py(path,name):
 spec=importlib.util.spec_from_file_location(name,path)
 mod=importlib.util.module_from_spec(spec)
 sys.modules[name]=mod
 spec.loader.exec_module(mod)
 return mod

def standardized(text):
 lines=ANSI_RE.sub('',text).replace('\r\n','\n').replace('\r','\n').splitlines()
 return [re.sub(r'^\[worker-0\] ', '',l).strip() for l in lines]

def critical(line):
 return bool(line.startswith(('E ','E\t','> ','FAILED ','ERROR ')) or EXC_RE.match(line))

def oracle(text):
 lines=standardized(text)
 return {
  "diagnostic":collections.Counter(l for l in lines if critical(l)),
  "failure_headers":collections.Counter(l for l in lines if HEADER_RE.match(l)),
  "test_summaries":collections.Counter(l for l in lines if l.startswith(("FAILED ","ERROR ")))
 }

def agrees(original,candidate):
 a=oracle(original); b=oracle(candidate)
 if not a['diagnostic'] or not a['failure_headers'] or not a['test_summaries']:
  return False,"UNSUPPORTED"
 for k in a:
  if any(b[k][s]<count for s,count in a[k].items()):
   return False,"LOSS_"+k
 return True,"PASS"

def transform(raw,name):
 lines=raw.splitlines(keepends=True)
 if name=="ansi_critical":
  return ''.join(("\x1b[1;31m"+l.rstrip('\r\n')+"\x1b[0m"+("\n" if l.endswith('\n') else "")) if (critical(l.strip()) or HEADER_RE.match(l.strip())) else l for l in lines)
 if name=="ansi_all":
  return ''.join(("\x1b[33m"+l.rstrip('\r\n')+"\x1b[0m"+("\n" if l.endswith('\n') else "")) if l.strip() else l for l in lines)
 if name=="crlf":
  return raw.replace('\r\n','\n').replace('\n','\r\n')
 if name=="duplicate_diagnostic":
  for i,l in enumerate(lines):
   if l.strip().startswith(('E ', 'FAILED ', 'ERROR ')):
    lines.insert(i+1,l)
    return ''.join(lines)
  raise AssertionError("original log missing E or FAILED")
 if name=="captured_stdout_sentinel":
  pos=next((i for i,l in enumerate(lines) if 'short test summary info' in l), len(lines))
  lines[pos:pos]=['----------------------------- Captured stdout call -----------------------------\n',
                   '\x1b[33mSome tool output with the words failure, error, exception but no diagnostic syntax.\x1b[0m\n',
                   '------------------------------ End captured stdout ------------------------------\n']
  return ''.join(lines)
 if name=="native_traceback":
  return raw+'\nTraceback (most recent call last):\n  File "worker.py", line 44, in run\n    raise RuntimeError("new native issue")\nRuntimeError: synthetic native final diagnostic\n'
 if name=="exception_group":
  return raw+'\nExceptionGroup: synthetic task errors (2 sub-exceptions)\n'
 if name=="ci_log_prefix":
  return ''.join(('[worker-0] '+l) if l.strip() else l for l in lines)
 raise ValueError(name)

def load_corpus():
 outputs={}
 for p in FIXTURES:
  obj=json.loads(p.read_text())
  for name,phase in ((key.rsplit('/',1)) for key in obj['fixtures']):
   if phase!="red":continue
   raw=obj['fixtures'][name+'/red']['text']
   assert hashlib.sha256(raw.encode()).hexdigest()==obj['fixtures'][name+'/red']['sha256']
   assert name not in outputs
   outputs[name]=raw
 assert len(outputs)==11
 return outputs

def run():
 m=load_py(SOURCE,'unchanged_B2')
 c=load_py(CERT,'legacy_cert')
 sources=load_corpus()
 rows=[]
 baselines=[]
 for case,raw in sorted(sources.items()):
  base=m.filter_pytest_log_v2(raw)
  ok,reason=agrees(raw,base)
  assert ok,(case,reason)
  baselines.append((case,hashlib.sha256(base.encode()).hexdigest(),len(base.encode())))
  for kind in TYPES:
   transformed=transform(raw,kind)
   assert transformed!=raw,(case,kind)
   expected=oracle(transformed)
   assert expected['diagnostic'] and expected['failure_headers'] and expected['test_summaries'],(case,kind)
   output=m.filter_pytest_log_v2(transformed)
   intact,reason=agrees(transformed,output)
   cert=c.produce(transformed,output)
   legacy_approved=c.verify(transformed,output,cert)
   rows.append({
      'case':case,'family':kind,
      'input_sha256':hashlib.sha256(transformed.encode()).hexdigest(),
      'output_sha256':hashlib.sha256(output.encode()).hexdigest(),
      'input_bytes':len(transformed.encode()),
      'output_bytes':len(output.encode()),
      'baseline_raw_fallback':transformed==output,
      'independent_oracle_pass':intact,'oracle_reason':reason,
      'legacy_certificate_pass':legacy_approved,
      'legacy_false_accept':bool(legacy_approved and not intact)})
 assert len(rows)==88
 report={'experiment_id':'PAPER-CHAOS-20261111-001',
    'scope':'88 deterministic synthetic format transformations of 11 previously known real red logs. NOT 88 independent upstream cases.',
    'transformation_families':list(TYPES),
    'source_compressor_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
    'source_certificate_sha256':hashlib.sha256(CERT.read_bytes()).hexdigest(),
    'corpus_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in FIXTURES},
    'original_baselines':[{'case':case,'B2_output_sha256':digest,'B2_output_bytes':size} for case,digest,size in baselines],
    'legacy_oracle_pass':sum(r['independent_oracle_pass'] for r in rows),
    'legacy_oracle_fail':sum(not r['independent_oracle_pass'] for r in rows),
    'legacy_certificate_false_accepts':sum(r['legacy_false_accept'] for r in rows),
    'legacy_raw_fallbacks':sum(r['baseline_raw_fallback'] for r in rows),
    'by_family':{kind:{'n':sum(r['family']==kind for r in rows),
      'oracle_pass':sum(r['family']==kind and r['independent_oracle_pass'] for r in rows),
      'false_accept':sum(r['family']==kind and r['legacy_false_accept'] for r in rows)} for kind in TYPES},
    'rows':rows,
 }
 p=HERE/'legacy_chaos_results_20261111.json'
 p.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 print('TOTAL',len(rows),'ORACLE_PASS',report['legacy_oracle_pass'],'FAIL',report['legacy_oracle_fail'],
       'FALSE_CERT_ACCEPTS',report['legacy_certificate_false_accepts'],'RAW_FALLBACKS',report['legacy_raw_fallbacks'])
 print('FAMILIES',json.dumps(report['by_family'],sort_keys=True))
 print('REPORT',p)

if __name__=='__main__':
 run()
