#!/usr/bin/env python3
"""Replay 88 pre-registered format perturbations and 11 unchanged original logs.

Also test v2 certificate against at least 50 deliberate tamper cases; this is
a deterministic software contract check, NOT new independent SWEBench tasks.
"""
import hashlib
import json
import sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import run_chaos_experiment as challenge
import robust_evidence_guard as rg

def main():
 src=challenge.load_py(challenge.SOURCE,"original_compressor_for_guard")
 real=challenge.load_corpus()
 baseline=json.loads((HERE/'legacy_chaos_results_20261111.json').read_text())
 assert baseline['legacy_oracle_fail']==10 and baseline['legacy_certificate_false_accepts']==10
 baseline_by_key={(r['case'],r['family']):r for r in baseline['rows']}
 rows=[]
 authentic_rows=[]
 tamper_rejected=0
 tamper_attempts=0

 def negative(name,raw,out,cert,modified_out=None,modified_raw=None,modified_cert=None):
    nonlocal tamper_rejected,tamper_attempts
    tamper_attempts+=1
    u=raw if modified_raw is None else modified_raw
    v=out if modified_out is None else modified_out
    c=cert if modified_cert is None else modified_cert
    if rg.verify(u,v,c):
        raise AssertionError('TAMPER_FALSE_ACCEPT:'+name)
    tamper_rejected+=1

 for j,(case,raw) in enumerate(sorted(real.items())):
    old=src.filter_pytest_log_v2(raw)
    output,meta=rg.guard(raw,src.filter_pytest_log_v2)
    assert output==old,(case,'original changed')
    cert=rg.produce_certificate(raw,output)
    assert cert['verdict']=="PASS" and rg.verify(raw,output,rg.serialize(cert))
    authentic_rows.append({'instance_id':case,'original_output_sha256':hashlib.sha256(old.encode()).hexdigest(),
       'guarded_output_sha256':hashlib.sha256(output.encode()).hexdigest(),
       'raw_bytes':len(raw.encode()),'out_bytes':len(output.encode()),'guarded_unchanged':True})
    for typ in challenge.TYPES:
       actual=challenge.transform(raw,typ)
       oldout=src.filter_pytest_log_v2(actual)
       guarded,gmeta=rg.guard(actual,src.filter_pytest_log_v2)
       okay,reason=challenge.agrees(actual,guarded)
       if not okay:raise AssertionError((case,typ,reason))
       cert=rg.produce_certificate(actual,guarded)
       assert rg.verify(actual,guarded,rg.serialize(cert))
       assert rg.verify(actual,guarded,cert)
       previous=baseline_by_key[(case,typ)]
       assert previous['output_sha256']==hashlib.sha256(oldout.encode()).hexdigest()
       rows.append({
         'instance_id':case,'family':typ,
         'old_oracle_pass':previous['independent_oracle_pass'],
         'old_cert_false_accept':previous['legacy_false_accept'],
         'guarded_oracle_pass':True,'guard_fallback':gmeta['fallback'],
         'guard_reason':gmeta['reason'],
         'raw_input_sha256':hashlib.sha256(actual.encode()).hexdigest(),
         'raw_output_sha256':hashlib.sha256(oldout.encode()).hexdigest(),
         'guard_output_sha256':hashlib.sha256(guarded.encode()).hexdigest(),
         'new_certificate_version':cert['schema_version'],
         'new_certificate_verified':True,
         'raw_bytes':len(actual.encode()),'guarded_out_bytes':len(guarded.encode()),
       })
       # Each known distinct certificate attack must be rejected.
       negative(case+typ+':mutated_output',actual,guarded,cert,modified_out=guarded+'\ncorrupted outside diagnostics')
       negative(case+typ+':mutated_input',actual,guarded,cert,modified_raw=actual+'\ncorrupted input')
       negative(case+typ+':false_version',actual,guarded,cert,modified_cert=dict(cert,schema_version='v1'))
       negative(case+typ+':false_digest',actual,guarded,cert,modified_cert=dict(cert,output_utf8_sha256='0'*64))
       negative(case+typ+':wrong_verdict',actual,guarded,cert,modified_cert=dict(cert,verdict='FAIL'))
       negative(case+typ+':bad_json',actual,guarded,cert,modified_cert='{"verdict":')
       negative(case+typ+':duplicate_json_keys',actual,guarded,cert,modified_cert='{"verdict":"PASS","verdict":"PASS"}')
       negative(case+typ+':tamper_evidence',actual,guarded,cert,modified_cert=dict(cert,source_evidence={}))
 assert len(rows)==88 and len(authentic_rows)==11
 assert tamper_attempts==88*8 and tamper_rejected==tamper_attempts
 assert sum(not r['old_oracle_pass'] for r in rows)==10
 assert sum(r['guarded_oracle_pass'] for r in rows)==88
 assert sum(r['old_cert_false_accept'] for r in rows)==10
 assert sum(r['guard_fallback'] for r in rows)>=10
 assert all(r['guarded_unchanged'] for r in authentic_rows)
 rawbytes=sum(r['raw_bytes'] for r in authentic_rows)
 outbytes=sum(r['out_bytes'] for r in authentic_rows)
 expected_reduction=round(100*(1-outbytes/rawbytes),2)
 assert expected_reduction==72.01,(expected_reduction,rawbytes,outbytes)
 results={
 'experiment_id':'PAPER-CHAOS-20261111-001',
 'prospective_protocol':'paper/robustness_challenge/PROTOCOL_20261111.md',
 'statistical_scope':'88 synthetic format shifts of same 11 genuine upstream failures; NOT 88 independent real tasks.',
 'legacy_88_pass':baseline['legacy_oracle_pass'],
 'legacy_88_fail':baseline['legacy_oracle_fail'],
 'legacy_certificate_false_accept':baseline['legacy_certificate_false_accepts'],
 'guarded_88_pass':88,
 'guarded_88_fail':0,
 'guarded_raw_fallbacks':sum(r['guard_fallback'] for r in rows),
 'old_raw_fallbacks':sum(r['baseline_raw_fallback'] for r in baseline['rows']),
 'tamper_controls_rejected':tamper_rejected,
 'tamper_controls_total':tamper_attempts,
 'original_11_byte_identical':True,
 'original_11_unchanged_reduction_pct':expected_reduction,
 'frozen_compressor_sha256':hashlib.sha256(challenge.SOURCE.read_bytes()).hexdigest(),
 'guard_sha256':hashlib.sha256((HERE/'robust_evidence_guard.py').read_bytes()).hexdigest(),
 'by_family':{typ:{'n':sum(x['family']==typ for x in rows),
   'original_pass':sum(x['family']==typ and x['old_oracle_pass'] for x in rows),
   'guard_pass':sum(x['family']==typ and x['guarded_oracle_pass'] for x in rows),
   'guard_fallbacks':sum(x['family']==typ and x['guard_fallback'] for x in rows)}
   for typ in challenge.TYPES},
 'authentic_baseline_rows':authentic_rows,
 'synthetic_rows':rows,
 }
 p=HERE/'robust_guard_results_20261111.json'
 p.write_text(json.dumps(results,indent=2,ensure_ascii=False)+'\n')
 print('OLD',results['legacy_88_pass'],'/88 | NEW',results['guarded_88_pass'],'/88')
 print('FALLBACKS',results['old_raw_fallbacks'],'->',results['guarded_raw_fallbacks'])
 print('FALSE_LEGACY_CERT_PASSES',results['legacy_certificate_false_accept'])
 print('NEW_CERT_TAMPER_REJECTED',results['tamper_controls_rejected'],'/',results['tamper_controls_total'])
 print('ORIGINAL_11_BYTE_IDENTICAL',results['original_11_byte_identical'],'SAVED',expected_reduction,'%')
 print('FAMILY',json.dumps(results['by_family'],sort_keys=True))
 print('REPORT',p)

if __name__=='__main__':main()
