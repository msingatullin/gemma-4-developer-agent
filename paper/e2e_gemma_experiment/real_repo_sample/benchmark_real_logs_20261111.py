#!/usr/bin/env python3
"""Predefined audit on five actual external issue red/green CPU pytest logs."""
from pathlib import Path
from collections import Counter
import json, hashlib, importlib.util, re
root=Path('/opt/kaggle/gemma-paper-cpu-runs')
source=Path('/opt/kaggle/gemma-paper/paper/traceback_compressor.py')
spec=importlib.util.spec_from_file_location('compressor',source)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
names={'flask4045':'pallets__flask-4045','flask4992':'pallets__flask-4992','flask5063':'pallets__flask-5063','requests1963':'psf__requests-1963','requests2148':'psf__requests-2148'}
def diag(s):
    return Counter(x.strip() for x in s.splitlines() if x.lstrip().startswith(('E ','E\t','> ','FAILED ','ERROR ')) or re.match(r'^[\w.]+(?:Error|Exception|Warning|Exit|Interrupt):',x.strip()))
def headers(s):
    return Counter(x.strip() for x in s.splitlines() if re.match(r'^_{3,}\s*.*?\s*_{3,}$',x.strip()))
def subset(a,b):
    return all(b[k]>=v for k,v in a.items())
rows=[]
for folder,task in names.items():
    for phase in ('red','green'):
        p=root/folder/(phase+'.log')
        assert p.is_file(),p
        raw=p.read_text(errors='replace')
        for variant,fn in [('v1',m.filter_pytest_log),('v2',m.filter_pytest_log_v2)]:
            output=fn(raw)
            pass_diag=subset(diag(raw),diag(output))
            pass_header=subset(headers(raw),headers(output))
            raw_failed=[s.strip() for s in raw.splitlines() if s.strip().startswith(('FAILED ','ERROR '))]
            out_failed=[s.strip() for s in output.splitlines() if s.strip().startswith(('FAILED ','ERROR '))]
            pass_summary=subset(Counter(raw_failed),Counter(out_failed))
            row={'instance_id':task,'phase':phase,'variant':variant,'source_sha256':hashlib.sha256(raw.encode()).hexdigest(),'raw_bytes':len(raw.encode()),'result_bytes':len(output.encode()),'saved_percent':round(100*(1-len(output.encode())/max(1,len(raw.encode()))),2),'diagnostic_lines':sum(diag(raw).values()),'failure_headers':sum(headers(raw).values()),'summary_lines':len(raw_failed),'diagnostic_integrity_pass':pass_diag,'headers_integrity_pass':pass_header,'summary_integrity_pass':pass_summary,'changed':raw!=output}
            assert pass_diag and pass_header and pass_summary,row
            rows.append(row)
for variant in ('v1','v2'):
    subset_rows=[r for r in rows if r['variant']==variant]
    red=[r for r in subset_rows if r['phase']=='red']
    print(variant, 'n',len(subset_rows),'red_n',len(red),'original_bytes',sum(r['raw_bytes'] for r in red),'compressed_bytes',sum(r['result_bytes'] for r in red),'corpus_red_saving_pct',round(100*(1-sum(r['result_bytes'] for r in red)/sum(r['raw_bytes'] for r in red)),2),'changed_red',sum(r['changed'] for r in red),'integrity',all(r['diagnostic_integrity_pass'] and r['headers_integrity_pass'] and r['summary_integrity_pass'] for r in subset_rows))
    print('red rows',[(r['instance_id'],r['raw_bytes'],r['result_bytes'],r['saved_percent']) for r in red])
data={'experiment_id':'PAPER-REAL-LOG-CPU-20261111-01','design':'Retrospective, five real upstream issues across two independent repositories, red/green logs from previously established offline patch verifier; no model inference; no hidden benchmark claim','logs_sha256':'', 'source_code_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'rows':rows}
out=Path('/opt/kaggle/gemma-paper-kaggle-cli/heldout-cpu-real-logs-20261111/real_log_integrity_results.json')
out.write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n')
print('RESULTS',out,'size',out.stat().st_size,'PASS',len(rows),'of',len(rows))
