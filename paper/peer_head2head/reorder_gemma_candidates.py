#!/usr/bin/env python3
"""Source-only deterministic re-ranking of Gemma 4 E4B published file predictions.
No gold data, patch text, repo checkout, or additional LLM calls are required.
"""
from __future__ import annotations
import re
STOP={'test','tests','python','django','sympy','core','base','util','utils','api','src','lib','main','code','new','file','issue','function','method','module','print','array','object','result','with','from','this','that','should','class','value','error','data','and','for','not','all','can','one'}

def normal_tokens(s):
    return re.findall(r'[a-z][a-z0-9]{2,}',re.sub(r'(?<=[a-z])(?=[A-Z])',' ',s).lower())

def features(issue,path,rank):
    path=path.replace('\\','/');issue_low=issue.lower()
    file_name=path.rsplit('/',1)[-1].removesuffix('.py')
    fparts=[t for t in normal_tokens(file_name) if t not in STOP]
    directories=[t for t in normal_tokens(path.rsplit('/',1)[0]) if t not in STOP]
    token_counts={t:len(re.findall(r'\b'+re.escape(t)+r'\b',issue_low)) for t in set(fparts+directories)}
    exp_filename=1 if re.search(r'(?<![\w])'+re.escape(path.rsplit('/',1)[-1])+r'(?![\w])',issue_low) else 0
    full_path=1 if re.search(r'(?<![\w])'+re.escape(path)+r'(?![\w])',issue_low) else 0
    exact_stem=1 if re.search(r'(?<![\w])'+re.escape(file_name.lower())+r'(?![\w])',issue_low) and len(file_name)>=5 else 0
    filename_hits=sum(min(token_counts.get(w,0),2) for w in fparts)
    dir_hits=sum(min(token_counts.get(w,0),1) for w in set(directories))
    explicit_symbol=1 if ' '+file_name.lower()+'(' in issue_low and len(file_name)>=4 else 0
    is_test=1 if re.search(r'(?:^|/)(tests?|testing)(?:/|$)|(?:^|/)test_',path) else 0
    return {'rank':rank,'full_path':full_path,'exp_filename':exp_filename,'exact_stem':exact_stem,
            'filename_hits':filename_hits,'dir_hits':dir_hits,'explicit_symbol':explicit_symbol,'is_test':is_test}

def rank_predictions(record, cfg):
    paths=record['pred_files']
    if not paths:return ''
    issue=record['problem_statement']
    scores=[]
    for idx,path in enumerate(paths):
        f=features(issue,path,idx)
        val=(-idx*cfg['rank_penalty'] +f['full_path']*cfg['full_path'] 
          +f['exp_filename']*cfg['exp_filename'] +f['exact_stem']*cfg['exact_stem']
          +min(f['filename_hits'],3)*cfg['filename_hits'] 
          +min(f['dir_hits'],3)*cfg['dir_hits']
          +f['explicit_symbol']*cfg['explicit_symbol'] -f['is_test']*cfg['test_penalty'])
        scores.append((val,-idx,path))
    return max(scores)[2]

def config_choices():
    for penalty in (2.,4.,8.,12.):
      for exact in (0.,3.,6.,12.):
       for fn_hit in (0.,1.,2.,4.):
        for test_penalty in (0.,2.,5.,9.):
         yield dict(rank_penalty=penalty,full_path=20.,exp_filename=12.,exact_stem=exact,
           filename_hits=fn_hit,dir_hits=0.5,explicit_symbol=3.,
           test_penalty=test_penalty)
