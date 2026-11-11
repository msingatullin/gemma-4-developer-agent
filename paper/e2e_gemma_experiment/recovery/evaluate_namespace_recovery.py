#!/usr/bin/env python3
"""Post-hoc namespace-binding recovery on 15 previously obtained Gemma responses.

Re-evaluates changed candidates in the original immutable Docker harness.
No new inference or gold patch access for candidate production.
"""
import argparse,hashlib,json,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
sys.path.insert(0,str(HERE.parent))
from namespace_binding_recovery import recover_import_bindings
from evaluate_real_repo_patches import TASKS_MAP,evaluate_patch_on_task

def main():
  ap=argparse.ArgumentParser()
  ap.add_argument('responses',type=Path)
  ap.add_argument('prior_score',type=Path)
  ap.add_argument('full_response_prior',type=Path)
  ap.add_argument('--report-dir',type=Path,required=True)
  args=ap.parse_args()
  args.report_dir.mkdir(parents=True,exist_ok=True)
  rows=[json.loads(s) for s in args.responses.read_text().splitlines() if s.strip()]
  prior={(r['instance_id'],r['variant']):r for r in (json.loads(s) for s in args.prior_score.read_text().splitlines() if s.strip())}
  full=json.loads(args.full_response_prior.read_text())
  interim={(r['instance_id'],r['variant']):r for r in full['rows']}
  expected={(name,variant) for name in TASKS_MAP for variant in ('A_raw','B2_assertion_aware','C_tail35')}
  assert len(rows)==15 and {(r['instance_id'],r['variant']) for r in rows}==expected
  evidence=[]
  for idx,row in enumerate(rows):
    instance_id,variant=row['instance_id'],row['variant']
    spec=TASKS_MAP[instance_id]
    base=subprocess.check_output(['git',f"--git-dir={spec['repo_bare']}",'show',f"{spec['base_commit']}:{spec['target_file']}"],text=True)
    candidate,meta=recover_import_bindings(
        row['response_text'],base,spec['target_file'],spec['base_commit'],str(spec['repo_bare']))
    before=prior[(instance_id,variant)]['verdict']
    previously=interim[(instance_id,variant)]
    if meta['transformed']:
      # This path is always evaluated fresh; do not trust offline text matching.
      r=evaluate_patch_on_task(instance_id,candidate,run_id='namespace%02d'%idx)
      after=r['verdict']
      judge='fresh_immutable_Docker'
    else:
      after=previously['verdict']
      judge='previously_verified_full_response_or_original'
    line={'instance_id':instance_id,'variant':variant,'original_verdict':before,
          'recovered_verdict':after,'transformation':meta.get('reason'),
          'added_imports':meta.get('added_imports',[]),
          'source_model_response_sha256':hashlib.sha256(row['response_text'].encode()).hexdigest(),
          'new_transform':meta['transformed'],'verification':judge,
          'f2p_pass':r.get('f2p_pass') if meta['transformed'] else previously.get('f2p_pass'),
          'p2p_pass':r.get('p2p_pass') if meta['transformed'] else previously.get('p2p_pass')}
    evidence.append(line)
    print('CASE',instance_id,variant,before,'->',after,judge,flush=True)
  summary={v:{'before':sum(x['original_verdict']=='RESOLVED' for x in evidence if x['variant']==v),
              'after':sum(x['recovered_verdict']=='RESOLVED' for x in evidence if x['variant']==v),
              'n':5}
           for v in ('A_raw','B2_assertion_aware','C_tail35')}
  assert summary['A_raw']['after']>=2 and summary['B2_assertion_aware']['after']>=2
  assert all(x['recovered_verdict']!='HARNESS_ERROR' for x in evidence)
  outfile=args.report_dir/'namespace_recovery_sanitized_report_20261111.json'
  outfile.write_text(json.dumps({'experiment_id':'PAPER-REAL5-POSTHOC-NAMESPACE-20261111-002',
    'scope':'Exploratory post-hoc reuse of exact original 15 real Gemma4 responses. New namespace binding inference learned after inspecting feedback on same cases; never claim held-out model quality or independent generalization.',
    'original_corpus_sha256':hashlib.sha256(args.responses.read_bytes()).hexdigest(),
    'summary':summary,'rows':evidence},indent=2)+'\n')
  print('FINAL_SUMMARY',json.dumps(summary),flush=True)
  print('REPORT',outfile,flush=True)

if __name__=='__main__':
  main()

