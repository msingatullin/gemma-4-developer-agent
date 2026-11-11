#!/usr/bin/env python3
"""Descriptive uncertainty after frozen 90-task one-shot evaluation, no tuning."""
import collections,random,statistics,json,pathlib,hashlib
p=pathlib.Path(__file__).resolve().parent
d=json.loads((p/'HOLDOUT90_RESULTS.json').read_text())
rows=d['rows']
assert len(rows)==90
rng=random.Random(20261111)
effects=[int(x['reranked_correct'])-int(x['baseline_correct']) for x in rows]
draws=[]
for _ in range(25000):
    draws.append(sum(rng.choices(effects,k=len(effects)))/len(effects))
draws.sort()
byrepo=collections.defaultdict(list)
for r in rows:byrepo[r['repo']].append(int(r['reranked_correct'])-int(r['baseline_correct']))
all_repos=sorted(byrepo)
cluster_draws=[]
for _ in range(25000):
    sampled=rng.choices(all_repos,k=len(all_repos))
    values=[x for repo in sampled for x in byrepo[repo]]
    cluster_draws.append(sum(values)/len(values))
cluster_draws.sort()
def q(v,x):return v[min(len(v)-1,round((len(v)-1)*x))]
s={'n':90,'different_repositories':len(byrepo),
'paired_diff_pp':round(100*sum(effects)/len(effects),4),
'bootstrap_95_ci_pp':[round(100*q(draws,0.025),3),round(100*q(draws,0.975),3)],
'repo_cluster_bootstrap_95_ci_pp':[round(100*q(cluster_draws,0.025),3),round(100*q(cluster_draws,0.975),3)],
'rescued':sum(x==1 for x in effects),'regressed':sum(x==-1 for x in effects),
'statistic':d['exact_mcnemar_two_sided_p_uncorrected'],
'methodology':'25,000 paired-task bootstrap and 25,000 repo-cluster bootstrap, fixed seed 20261111. Observational 90 tasks from 150 released peer rows, no new Gemma inference. The intervals are exploratory and may not account for competitor model-development leakage.'}
(p/'UNCERTAINTY_HOLDOUT90.json').write_text(json.dumps(s,indent=2)+'\n')
print(json.dumps(s,indent=2))
