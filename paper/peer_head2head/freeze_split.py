#!/usr/bin/env python3
import collections,hashlib,json,pathlib
import pyarrow.parquet as pq
p=pathlib.Path('/opt/kaggle/gemma-paper-kaggle-cli/competitor-audit-20261111/maroofium-repo/results/run_v3.jsonl')
d=pathlib.Path('/opt/kaggle/gemma-paper-kaggle-cli/peer-head2head-maroof-20261111')
rows=[json.loads(s) for s in p.read_text().splitlines() if s.strip()]
rep={r['instance_id']:r for r in rows if r['method']=='repomap_sig'}
dev={r['instance_id'] for r in rows if r['method']=='ours_2stage'}
assert len(rep)==150 and len(dev)==60 and dev<=set(rep)
holdout=set(rep)-dev; assert len(holdout)==90
T=pq.read_table('/opt/kaggle/gemma-paper-kaggle-cli/swebench-lite/test.parquet',columns=['instance_id','problem_statement'])
text={k:v for k,v in zip(T['instance_id'].to_pylist(),T['problem_statement'].to_pylist())}
assert set(rep)<=set(text)
secret_fields=['gold_files','gold_funcs','file_acc1','file_acc3','file_acc5','func_acc1','n_gold_files']
devrows=[];testrows=[]
for name in sorted(rep):
 r=rep[name]
 row={'instance_id':name,'repo':r['repo'],'pred_files':r['pred_files'],'pred_symbol':r['pred_symbol'],
      'problem_statement':text[name],
      'prompt_tokens':r['prompt_tokens'],'gen_tokens':r['gen_tokens'],'ctx_tokens':r['ctx_tokens'],
      'candidate_list_hash':hashlib.sha256(json.dumps(r['pred_files'],sort_keys=True).encode()).hexdigest()}
 assert not any(k in row for k in secret_fields)
 if name in dev:
  row.update(gold_files=r['gold_files'],correct_first=bool(r['file_acc1']))
  devrows.append(row)
 else:testrows.append(row)
(d/'dev60_PRIVATE.json').write_text(json.dumps(devrows,ensure_ascii=False,indent=2)+'\n')
(d/'holdout90_UNLABELED_PRIVATE.json').write_text(json.dumps(testrows,ensure_ascii=False,indent=2)+'\n')
manifest={'experiment_id':'PAPER-HEAD2HEAD-MAROOF-20261111-001',
'prereg_commit':'ed66a5652e560440fa569088430ba1495909c290',
'peer_repo_commit':'b28c4b9790be7ae20ac584385a0cc122d4b5b58b',
'peer_rows_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),
'dev_n':len(devrows),'heldout_n':len(testrows),
'dev_ids_sha256':hashlib.sha256('\n'.join(sorted(dev)).encode()).hexdigest(),
'holdout_ids_sha256':hashlib.sha256('\n'.join(sorted(holdout)).encode()).hexdigest(),
'holdout_unlabeled_sha256':hashlib.sha256((d/'holdout90_UNLABELED_PRIVATE.json').read_bytes()).hexdigest(),
'dev_labeled_sha256':hashlib.sha256((d/'dev60_PRIVATE.json').read_bytes()).hexdigest()}
(d/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps(manifest,indent=2))
print('DEV 1:3')
for r in devrows[:3]:print(r['instance_id'],r['pred_files'],r['gold_files'],'issue prefix',repr(r['problem_statement'][:200]))
