#!/usr/bin/env python3
"""Run positive and adversarial certificate checks on authentic pytest logs.

Input fixtures are immutable source-controlled JSON. The unchanged compressor
is loaded from its original source. No network/model access or gold test patches.
"""
from collections import defaultdict
from pathlib import Path
import importlib.util
import hashlib
import json
import random
import sys

D=Path(__file__).resolve().parent
SRC=Path(sys.argv[1]) if len(sys.argv)>1 else Path('/opt/kaggle/gemma-paper/paper/traceback_compressor.py')
FIXTURES=[Path(x) for x in sys.argv[2:]] if len(sys.argv)>2 else [
 Path('/opt/kaggle/gemma-paper-kaggle-cli/baseline-comparison-5repos-20261111/REAL_LOG_FIXTURES_5REPOS_20261111.json'),
 Path('/opt/kaggle/gemma-paper-kaggle-cli/holdout3-20261111/REAL_LOG_FIXTURES_HOLDOUT3_20261111.json')]
sys.path.insert(0,str(D))
from diagnostic_certificate import produce,verify,extract,canonical_json,SCHEMA_VERSION
spec=importlib.util.spec_from_file_location('frozen_compressor',SRC)
compressor=importlib.util.module_from_spec(spec);spec.loader.exec_module(compressor)
suite={'experiment_id':'PAPER-CERT-REAL11-20261111-001',
       'protocol':'paper/verification_certificate/CERTIFICATE_TEST_PROTOCOL_20261111.md',
       'compressor_sha256':hashlib.sha256(SRC.read_bytes()).hexdigest(),
       'fixture_fingerprints':{},'rows':[],
       'adversarial_cases':0,'adversarial_correctly_rejected':0}
fx={}
for p in FIXTURES:
 suite['fixture_fingerprints'][p.name]=hashlib.sha256(p.read_bytes()).hexdigest()
 data=json.loads(p.read_text())
 for key,val in data['fixtures'].items():
  name,phase=key.rsplit('/',1)
  if phase!='red':continue
  if name in fx:raise ValueError('duplicate instance')
  raw=val['text']
  assert hashlib.sha256(raw.encode()).hexdigest()==val['sha256']
  fx[name]=raw
assert len(fx)==11
rejects=defaultdict(int)

def tamper(name,raw,output,cert,changed_out=None,changed_in=None,changed_cert=None):
    c=changed_cert if changed_cert is not None else cert
    o=changed_out if changed_out is not None else output
    i=changed_in if changed_in is not None else raw
    suite['adversarial_cases']+=1
    if verify(i,o,c):
        raise AssertionError('ADVERSARIAL_BYPASS '+name)
    suite['adversarial_correctly_rejected']+=1
    rejects[name.split(':')[-1]]+=1

for i,(name,raw) in enumerate(sorted(fx.items())):
    out=compressor.filter_pytest_log_v2(raw)
    cert=produce(raw,out)
    assert cert['verdict']=='PASS',(name,[(k,len(v)) for k,v in extract(raw).items()])
    assert verify(raw,out,cert)
    assert verify(raw,out,canonical_json(cert))
    groups=extract(out)
    diagnost=sorted(groups['diagnostic'].keys())
    headers=sorted(groups['failure_headers'].keys())
    summ=sorted(groups['test_summaries'].keys())
    assert diagnost and headers and summ,name
    row={'instance_id':name,'source_sha256':cert['source_sha256'],
         'result_sha256':cert['result_sha256'],
         'raw_fallback':cert['raw_fallback'],
         'source_bytes':cert['source_utf8_bytes'],
         'result_bytes':cert['result_utf8_bytes'],
         'diagnostic_distinct':len(diagnost),
         'headers_distinct':len(headers),
         'summaries_distinct':len(summ),
         'verdict':'PASS'}
    suite['rows'].append(row)

    def delete_line(s,line):
        ls=s.splitlines(keepends=True)
        for j,v in enumerate(ls):
            if v.strip()==line:
                del ls[j]
                return ''.join(ls)
        raise AssertionError('line not found')
    for label,lines in (('diag',diagnost),('header',headers),('summary',summ)):
        target=lines[0]
        tamper(name+':delete_'+label,raw,out,cert,changed_out=delete_line(out,target))
        tamper(name+':duplicate_'+label,raw,out,cert,changed_out=out+'\n'+target+'\n')
    tamper(name+':ordinary_payload',raw,out,cert,changed_out=out+'\nINTEGRITY_TAMPERING_NON_EVIDENCE')
    tamper(name+':changed_input',raw,out,cert,changed_in=raw+'\nUNTRUSTED_RAW_INPUT')
    forged=dict(cert,verdict='FAIL')
    tamper(name+':forged_verdict',raw,out,cert,changed_cert=forged)
    forged=dict(cert,source_sha256='0'*64)
    tamper(name+':forged_sha',raw,out,cert,changed_cert=forged)
    forged=dict(cert,schema_version='pytest-diagnostic-integrity-v0')
    tamper(name+':wrong_version',raw,out,cert,changed_cert=forged)
    forged=dict(cert,source_selected_evidence={})
    tamper(name+':forged_evidence',raw,out,cert,changed_cert=forged)
    tamper(name+':invalid_json',raw,out,cert,changed_cert='{"schema_version": ')
    tamper(name+':duplicate_json_key',raw,out,cert,changed_cert='{"verdict":"PASS","verdict":"PASS"}')
    tamper(name+':invalid_cert',raw,out,cert,changed_cert=42)
    assert not verify(raw,out,{'verdict':'PASS'}),name
suite['adversarial_reason_counts']=dict(rejects)
suite['certified']=sum(r['verdict']=='PASS' for r in suite['rows'])
suite['raw_fallbacks']=sum(r['raw_fallback'] for r in suite['rows'])
raw_bytes=sum(r['source_bytes'] for r in suite['rows'])
out_bytes=sum(r['result_bytes'] for r in suite['rows'])
suite['corpus_byte_reduction_pct']=round(100*(1-out_bytes/raw_bytes),2)
assert suite['certified']==11
assert suite['adversarial_correctly_rejected']==suite['adversarial_cases']
p=D/'certificate_validation_report_20261111.json'
p.write_text(json.dumps(suite,indent=2)+'\n')
print('CERTIFICATION_PASS',suite['certified'],'of',len(suite['rows']))
print('CORRUPTION_REJECTION_PASS',suite['adversarial_correctly_rejected'],'of',suite['adversarial_cases'])
print('FALLBACKS',suite['raw_fallbacks'],'BYTES_REDUCTION',suite['corpus_byte_reduction_pct'])
print('COMPRESSOR_SHA',suite['compressor_sha256'])
print('REPORT',p)
