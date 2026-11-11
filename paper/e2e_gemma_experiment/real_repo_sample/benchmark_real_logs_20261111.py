#!/usr/bin/env python3
"""Predefined audit on five actual external issue red/green CPU pytest logs."""
from pathlib import Path
from collections import Counter
import json, hashlib, importlib.util, re
root=Path('/opt/kaggle/gemma-paper-cpu-runs')
fixtures_path=Path(__file__).with_name('REAL_LOG_FIXTURES_20261111.json')
fixture_data=json.loads(fixtures_path.read_text())['fixtures'] if fixtures_path.exists() else None
source=Path(__file__).resolve().parents[2]/'traceback_compressor.py'
if not source.is_file():
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
        p=root/folder/(('rerun-'+phase+'.log') if folder=='requests1963' else (phase+'.log'))
        assert p.is_file() or fixture_data is not None,p
        raw=(fixture_data[task+'/'+phase]['text'] if fixture_data is not None else p.read_text(errors='replace'))
        if fixture_data is not None:
            assert hashlib.sha256(raw.encode()).hexdigest()==fixture_data[task+'/'+phase]['sha256']
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
data={'experiment_id':'PAPER-REAL-LOG-CPU-20261111-01','design':'Retrospective, five real upstream issues across two repositories, red/green logs from offline patch verifier; requests1963 corrected rerun logs; no model inference, no heldout pre-registration claim','logs_sha256':'', 'source_code_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'rows':rows}
out=Path(__file__).with_name('real_log_integrity_results_20261111.json')
out.write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n')
print('RESULTS',out,'size',out.stat().st_size,'PASS',len(rows),'of',len(rows))
