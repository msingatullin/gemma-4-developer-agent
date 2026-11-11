#!/usr/bin/env python3
from pathlib import Path
from collections import Counter
import json,re,hashlib,importlib.util,statistics

ROOT=Path('/opt/kaggle/gemma-paper')
FX=Path(__file__).with_name('REAL_LOG_FIXTURES_20261111.json')
SRC=ROOT/'paper/traceback_compressor.py'
spec=importlib.util.spec_from_file_location('compressor',SRC)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
fixtures=json.loads(FX.read_text())['fixtures']

def diag(s):
    return Counter(x.strip() for x in s.splitlines()
                   if x.lstrip().startswith(('E ','E\t','> ','FAILED ','ERROR '))
                   or re.match(r'^[\w.]+(?:Error|Exception|Warning|Exit|Interrupt):',x.strip()))
def headers(s):
    return Counter(x.strip() for x in s.splitlines()
                   if re.match(r'^_{3,}\s*.*?\s*_{3,}$',x.strip()))
def summaries(s):
    return Counter(x.strip() for x in s.splitlines()
                   if x.strip().startswith(('FAILED ','ERROR ')))
def recall(orig,out,fn):
    a,b=fn(orig),fn(out)
    den=sum(a.values())
    if den==0:return 1.0
    return sum(min(v,b[k]) for k,v in a.items())/den
def identity(s):return s
def head35(s):return '\n'.join(s.splitlines()[:35])
def tail35(s):return '\n'.join(s.splitlines()[-35:])
def tail20(s):return '\n'.join(s.splitlines()[-20:])
def naive_diag(s):
    keep=[]
    for x in s.splitlines():
        st=x.strip()
        if x.lstrip().startswith(('E ','E\t','> ','FAILED ','ERROR ')) or re.match(r'^[\w.]+(?:Error|Exception|Warning|Exit|Interrupt):',st):
            keep.append(x)
    return '\n'.join(keep)
methods={'raw':identity,'head35':head35,'tail35':tail35,'tail20':tail20,'naive_diag':naive_diag,'ours_v1':m.filter_pytest_log,'ours_v2_B2':m.filter_pytest_log_v2}
rows=[]
for key,v in fixtures.items():
    task,phase=key.rsplit('/',1)
    if phase!='red':continue
    raw=v['text']
    assert hashlib.sha256(raw.encode()).hexdigest()==v['sha256']
    for name,fn in methods.items():
        out=fn(raw)
        row={
          'instance_id':task,'method':name,
          'raw_bytes':len(raw.encode()),'out_bytes':len(out.encode()),
          'saved_pct':100*(1-len(out.encode())/len(raw.encode())),
          'diag_recall':recall(raw,out,diag),
          'header_recall':recall(raw,out,headers),
          'summary_recall':recall(raw,out,summaries),
          'all_integrity': recall(raw,out,diag)==1 and recall(raw,out,headers)==1 and recall(raw,out,summaries)==1,
        }
        rows.append(row)

agg={}
for name in methods:
    rr=[r for r in rows if r['method']==name]
    agg[name]={
      'n_logs':len(rr),
      'corpus_saved_pct':round(100*(1-sum(r['out_bytes'] for r in rr)/sum(r['raw_bytes'] for r in rr)),2),
      'mean_diag_recall_pct':round(100*statistics.mean(r['diag_recall'] for r in rr),2),
      'mean_header_recall_pct':round(100*statistics.mean(r['header_recall'] for r in rr),2),
      'mean_summary_recall_pct':round(100*statistics.mean(r['summary_recall'] for r in rr),2),
      'logs_full_integrity':sum(r['all_integrity'] for r in rr),
      'n':len(rr),
    }

print(json.dumps(agg,indent=2))
for name in methods:
    print('\n',name)
    for r in [x for x in rows if x['method']==name]:
        print(r['instance_id'],f"save={r['saved_pct']:.1f}% diag={r['diag_recall']:.2f} hdr={r['header_recall']:.2f} sum={r['summary_recall']:.2f} full={r['all_integrity']}")
out={'experiment_id':'PAPER-BASELINE-CMP-20261111-01','scope':'Retrospective comparison on five authentic failing pytest logs from two upstream repositories. Metrics use exact-multiplicity selected diagnostic/header/summary markers. This does not measure model solve rate or semantic completeness.','methods':list(methods),'aggregate':agg,'rows':rows}
Path(__file__).with_name('baseline_comparison_results.json').write_text(json.dumps(out,indent=2)+'\n')
