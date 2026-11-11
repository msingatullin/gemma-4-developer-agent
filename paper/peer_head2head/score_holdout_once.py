#!/usr/bin/env python3
"""Pre-registered one-shot 90-issue heldout evaluation, no iterative tuning."""
import collections, hashlib, json, math, pathlib, sys
from reorder_gemma_candidates import rank_predictions
ROOT=pathlib.Path(__file__).resolve().parent
def sha(data):return hashlib.sha256(data).hexdigest()
manifest=json.loads((ROOT/'manifest.json').read_text())
cfgj=json.loads((ROOT/'FROZEN_FINAL_MODEL.json').read_text())
raw=(ROOT/'holdout90_UNLABELED_PRIVATE.json').read_bytes()
assert sha(raw)==manifest['holdout_unlabeled_sha256']==cfgj['holdout_unlabeled_sha256']
cases=json.loads(raw)
assert len(cases)==90
assert len(set(x['instance_id'] for x in cases))==90
assert all(not any(x in r for x in ('gold_files','file_acc1','file_acc3','file_acc5','gold_funcs')) for r in cases)
cfg=cfgj['selected']['cfg']
before={}
for r in cases:
 assert r['pred_files']
 path=rank_predictions(r,cfg)
 assert path in r['pred_files'] and path.endswith('.py')
 before[r['instance_id']]={'baseline':r['pred_files'][0], 'reranked':path,'repo':r['repo'],
      'tokens':r['prompt_tokens']+r['gen_tokens'],'switched':path!=r['pred_files'][0]}
# Freeze exact predictions BEFORE accessing any gold at all.
predictions_bytes=(json.dumps(before,indent=2,sort_keys=True)+'\n').encode()
predfile=ROOT/'holdout90_FROZEN_PREDICTIONS.json'
assert not predfile.exists(),'Prevent accidental second-run silently overwriting results'
predfile.write_bytes(predictions_bytes)
print('PREDICTIONS_FROZEN_BEFORE_GOLD',sha(predictions_bytes),flush=True)
# After prediction freeze, read gold labels from immutable competing release.
peer=pathlib.Path('/opt/kaggle/gemma-paper-kaggle-cli/competitor-audit-20261111/maroofium-repo/results/run_v3.jsonl')
assert sha(peer.read_bytes())==manifest['peer_rows_sha256']
gold={}
for line in peer.read_text().splitlines():
 x=json.loads(line)
 if x['method']=='repomap_sig' and x['instance_id'] in before:
  gold[x['instance_id']]=x
assert len(gold)==len(before)
results=[]
for id,p in sorted(before.items()):
 source=gold[id]
 assert source['pred_files'][0]==p['baseline']
 truth=set(source['gold_files'])
 base_correct=p['baseline'] in truth;post_correct=p['reranked'] in truth
 assert bool(source['file_acc1'])==base_correct
 results.append({'instance_id':id,'repo':p['repo'],'baseline_correct':base_correct,
                 'reranked_correct':post_correct,'switched':p['switched'],
                 'better':(not base_correct and post_correct),
                 'worse':(base_correct and not post_correct)})
b=sum(x['baseline_correct'] for x in results);a=sum(x['reranked_correct'] for x in results)
better=sum(x['better'] for x in results);worse=sum(x['worse'] for x in results);n=better+worse
pval=min(1.,2*sum(math.comb(n,i) for i in range(min(better,worse)+1))/(2**n)) if n else 1.
byrepo=collections.defaultdict(lambda:[0,0,0])
for x in results:
 byrepo[x['repo']][0]+=1
 byrepo[x['repo']][1]+=int(x['baseline_correct'])
 byrepo[x['repo']][2]+=int(x['reranked_correct'])
summary={'experiment_id':'PAPER-HEAD2HEAD-MAROOF-20261111-001',
 'design':'Dev60 selected as published peer ablation ids, 90 reserved complement; zero extra Gemma E4B calls or tokens. Postproc reorders only peer repomap_sig predictions. Development grid and final config published before exactly one heldout evaluation. Not a new model run.',
 'n':len(results),'baseline_correct':b,'reranked_correct':a,'gain_tasks':a-b,
 'baseline_file_at1':b/len(results),'reranked_file_at1':a/len(results),
 'rescued':better,'regressed':worse,
 'exact_mcnemar_two_sided_p_uncorrected':pval,
 'number_switched':sum(x['switched'] for x in results),
 'improved_over_peer':a>b,'passed_preregistered_strong_gate':a-b>=5 and pval<=0.05,
 'predictions_before_gold_sha256':sha(predictions_bytes),
 'by_repository':dict(sorted(byrepo.items())),
 'rows':results,
 'caveats':'Peer published dataset and outputs; split chosen based on peer ablation coverage, not random. The original source paper may have been tuned on all150 cases. No claim about overall judging, model solve rate, or statistically independent fresh tasks.'
}
out=ROOT/'HOLDOUT90_RESULTS.json'
assert not out.exists(),'Never permit rerun to silently overwrite first holdout result'
out.write_text(json.dumps(summary,indent=2)+'\n')
print('ONE_SHOT_HOLDOUT_RESULT',json.dumps({k:v for k,v in summary.items() if k not in ('rows','by_repository')},indent=2),flush=True)
