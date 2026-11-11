#!/usr/bin/env python3
import hashlib,json,collections,pathlib
from reorder_gemma_candidates import config_choices,rank_predictions
d=pathlib.Path(__file__).resolve().parent
rows=json.loads((d/'dev60_PRIVATE.json').read_text())
repos=sorted({r['repo'] for r in rows});assert len(rows)==60
ref=sum(r['pred_files'] and r['pred_files'][0] in set(r['gold_files']) for r in rows)
stats=[]
for cfg in config_choices():
 preds=[rank_predictions(r,cfg) for r in rows]
 correct=[p in set(r['gold_files']) for p,r in zip(preds,rows)]
 baseline=[bool(r['correct_first']) for r in rows]
 good=sum(x and not y for x,y in zip(correct,baseline))
 bad=sum(y and not x for x,y in zip(correct,baseline))
 switched=sum(p!=r['pred_files'][0] for p,r in zip(preds,rows))
 folds=collections.defaultdict(lambda:[0,0])
 for r,ok,b in zip(rows,correct,baseline):
  folds[r['repo']][0]+=int(ok);folds[r['repo']][1]+=int(b)
 min_repo_delta=min((a-b for a,b in folds.values()),default=0)
 stats.append({'cfg':cfg,'correct':sum(correct),'vs_baseline':sum(correct)-ref,
             'rescued':good,'lost':bad,'switches':switched,'min_repo_delta':min_repo_delta})
stats.sort(key=lambda x:(x['correct'],x['min_repo_delta'],-x['lost'],-x['switches']),reverse=True)
for v in stats[:8]:print('DEV',v)
eligible=[x for x in stats if x['correct']>=ref+1 and x['lost']<=2]
if not eligible:best={'cfg':{'rank_penalty':1e9,'full_path':0,'exp_filename':0,'exact_stem':0,'filename_hits':0,'dir_hits':0,'explicit_symbol':0,'test_penalty':0},'correct':ref,'vs_baseline':0,'rescued':0,'lost':0,'switches':0}
else: best=sorted(eligible,key=lambda x:(x['correct'],x['min_repo_delta'],-x['lost'],-x['switches']),reverse=True)[0]
out={'experiment_id':'PAPER-HEAD2HEAD-MAROOF-20261111-001','dev_baseline':ref,'dev_n':len(rows),
     'selected':best,'n_configurations':len(stats),'dev_candidates_top8':stats[:8],
     'holdout_unlabeled_sha256':hashlib.sha256((d/'holdout90_UNLABELED_PRIVATE.json').read_bytes()).hexdigest()}
path=d/'FROZEN_FINAL_MODEL.json';path.write_text(json.dumps(out,indent=2)+'\n')
print('FINAL_TUNED_CONFIG',best)
print('FROZEN_MODEL_SHA256',hashlib.sha256(path.read_bytes()).hexdigest())
