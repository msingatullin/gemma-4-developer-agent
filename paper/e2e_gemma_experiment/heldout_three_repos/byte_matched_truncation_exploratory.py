#!/usr/bin/env python3
"""Exploratory post-hoc equal-byte-budget head/tail family vs B2.

NOT part of the preregistered heldout benchmark. Uses optimistic oracle choice
of five head/tail budget splits per task, which favors truncation baselines.
"""
from collections import Counter
from pathlib import Path
import importlib.util,json,re

def diag(s):
    return Counter(x.strip() for x in s.splitlines()
                   if x.lstrip().startswith(('E ','E\t','> ','FAILED ','ERROR '))
                   or re.match(r'^[\w.]+(?:Error|Exception|Warning|Exit|Interrupt):',x.strip()))
def headers(s):
    return Counter(x.strip() for x in s.splitlines()
                   if re.match(r'^_{3,}\s*.*?\s*_{3,}$',x.strip()))
def summary(s):
    return Counter(x.strip() for x in s.splitlines()
                   if x.strip().startswith(('FAILED ','ERROR ')))
def match(x,y):
    for fn in (diag,headers,summary):
        a,b=fn(x),fn(y)
        if any(b[k]<v for k,v in a.items()):return False
    return True
def by_budget(s,budget,prefix_share):
    assert 0<=prefix_share<=1
    lines=s.splitlines(keepends=True)
    headcap=int(budget*prefix_share)
    head=[]; size=0
    for i,line in enumerate(lines):
        b=len(line.encode())
        if size+b>headcap:break
        head.append((i,line));size+=b
    tail=[];tail_size=0
    for i in range(len(lines)-1,len(head)-1,-1):
        b=len(lines[i].encode())
        if size+tail_size+b>budget:break
        tail.append((i,lines[i]));tail_size+=b
    out=''.join(y for _,y in head)+''.join(y for _,y in reversed(tail))
    assert len(out.encode())<=budget
    return out

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
src=HERE.parents[1]/'traceback_compressor.py'
s=importlib.util.spec_from_file_location('compressor',src)
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
fixtures=[
 ('development',ROOT/'real_repo_sample/REAL_LOG_FIXTURES_5REPOS_20261111.json'),
 ('prospective',HERE/'REAL_LOG_FIXTURES_HELDOUT_20261111.json'),
]
rows=[]
for group,src in fixtures:
 data=json.loads(src.read_text())
 for key,item in data['fixtures'].items():
  if not key.endswith('/red'):continue
  raw=item['text']
  b2=m.filter_pytest_log_v2(raw)
  budget=len(b2.encode())
  assert match(raw,b2)
  a={}
  for frac in (0,0.25,0.5,0.75,1):
   trunc=by_budget(raw,budget,frac)
   a[str(frac)]={'full_integrity':match(raw,trunc),'output_bytes':len(trunc.encode()),'budget_bytes':budget}
  rows.append({'instance_id':key.rsplit('/',1)[0],'group':group,'b2_bytes':budget,'raw_bytes':len(raw.encode()),'truncation':a,'oracle_best_full_integrity':any(v['full_integrity'] for v in a.values())})
print('RESULTS')
for x in rows:
 print(x['group'],x['instance_id'],'raw',x['raw_bytes'],'b2bytes',x['b2_bytes'],'baseline_by_share',[(k,v['full_integrity']) for k,v in x['truncation'].items()],'oracle_success',x['oracle_best_full_integrity'])
for group in ('development','prospective','all'):
 a=[x for x in rows if x['group']==group or group=='all']
 print('SUM',group,'oracle_best_tail+head',sum(x['oracle_best_full_integrity'] for x in a),'/',len(a),'B2',len(a),'/',len(a))
out={'experiment_id':'PAPER-EXPLORATORY-MATCHED-BYTE-HEADTAIL-20261111-02','scope':'Posthoc exploratory five head/tail variants capped to each issue B2 output byte budget (whole-line truncation); per-issue oracle best unfairly favors baseline. Not preregistered or model token-equivalent.','rows':rows}
(HERE/'byte_matched_truncation_exploratory_result.json').write_text(json.dumps(out,indent=2)+'\n')
