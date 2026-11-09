#!/usr/bin/env python3
"""
Full Benchmark Evaluation of AST + BM25 Locator across SWE-bench Verified tasks.
Measures Recall@1, Recall@3, Recall@5, MRR, latency, and stratified Dev vs Held-Out metrics.
"""

import os
import json
import time
import shutil
import tempfile
import subprocess
from pathlib import Path
from ast_bm25_locator import ASTRepoIndexer, BM25Locator

UPSTREAM_CACHE = Path("/home/mikhail/upstream_repos")
REPO_BARE_MAP = {
    "pallets/flask": UPSTREAM_CACHE / "flask.git",
    "psf/requests": UPSTREAM_CACHE / "requests.git",
    "pytest-dev/pytest": UPSTREAM_CACHE / "pytest.git",
    "pylint-dev/pylint": UPSTREAM_CACHE / "pylint.git",
    "django/django": UPSTREAM_CACHE / "django.git",
    "sympy/sympy": UPSTREAM_CACHE / "sympy.git"
}

MANIFEST_PATH = Path(__file__).resolve().parent / "manifest.json"
RESULTS_PATH = Path(__file__).resolve().parent / "LOCATOR_BENCHMARK_RESULTS.json"


def run_benchmark():
    with open(MANIFEST_PATH) as f:
        manifest = json.load(f)

    tasks = [t for t in manifest["tasks"] if t["repo"] in REPO_BARE_MAP]
    print(f"Running benchmark on {len(tasks)} tasks across {len(REPO_BARE_MAP)} repositories...")

    results = []
    by_repo = {}
    by_split = {"dev": [], "heldout": []}

    # Group by repo to minimize clones
    from collections import defaultdict
    repo_tasks = defaultdict(list)
    for t in tasks:
        repo_tasks[t["repo"]].append(t)

    for repo, t_list in repo_tasks.items():
        bare_repo = REPO_BARE_MAP[repo]
        print(f"\n--- Testing Repository: {repo} ({len(t_list)} tasks) ---")
        workdir = Path(tempfile.mkdtemp(prefix=f"loc_bench_{repo.replace('/', '_')}_"))
        try:
            subprocess.run(["git", "clone", "-q", str(bare_repo), str(workdir)], check=True)
            for t in t_list:
                iid = t["instance_id"]
                split = t["split"]
                base_commit = t["base_commit"]
                gt_files = t["ground_truth_files"]

                # Checkout base commit
                subprocess.run(["git", "checkout", "-q", "-f", base_commit], cwd=workdir, check=True)
                subprocess.run(["git", "clean", "-fdq"], cwd=workdir, check=True)

                t0 = time.time()
                indexer = ASTRepoIndexer(workdir)
                corpus_size, idx_time = indexer.index()
                locator = BM25Locator(indexer)
                q_res = locator.query(t["problem_statement"], top_k_files=10)
                eval_time = time.time() - t0

                top_files = [x["file"] for x in q_res["top_files"]]

                # Calculate rank of first matching GT file
                first_rank = None
                for rank_idx, f in enumerate(top_files, 1):
                    if f in gt_files:
                        first_rank = rank_idx
                        break

                r1 = (first_rank == 1)
                r3 = (first_rank is not None and first_rank <= 3)
                r5 = (first_rank is not None and first_rank <= 5)
                mrr = (1.0 / first_rank) if first_rank is not None else 0.0

                item = {
                    "instance_id": iid,
                    "repo": repo,
                    "split": split,
                    "ground_truth_files": gt_files,
                    "top_3_predictions": top_files[:3],
                    "first_rank": first_rank,
                    "recall_at_1": r1,
                    "recall_at_3": r3,
                    "recall_at_5": r5,
                    "mrr": mrr,
                    "corpus_files": corpus_size,
                    "latency_sec": round(eval_time, 3)
                }
                results.append(item)
                by_split[split].append(item)

                status_mark = "WIN" if r3 else "MISS"
                rank_str = f"Rank {first_rank}" if first_rank else "Not in Top 10"
                print(f"  [{status_mark}] {iid} ({split}) -> {rank_str} in {eval_time:.2f}s | GT: {gt_files}")

        finally:
            shutil.rmtree(workdir, ignore_errors=True)

    # Calculate aggregate metrics
    def summarize(items):
        n = len(items)
        if n == 0:
            return {}
        r1 = sum(1 for x in items if x["recall_at_1"]) / n
        r3 = sum(1 for x in items if x["recall_at_3"]) / n
        r5 = sum(1 for x in items if x["recall_at_5"]) / n
        mrr = sum(x["mrr"] for x in items) / n
        avg_lat = sum(x["latency_sec"] for x in items) / n
        return {
            "count": n,
            "recall_at_1": round(r1, 4),
            "recall_at_3": round(r3, 4),
            "recall_at_5": round(r5, 4),
            "mrr": round(mrr, 4),
            "avg_latency_sec": round(avg_lat, 3)
        }

    summary = {
        "overall": summarize(results),
        "dev_split": summarize(by_split["dev"]),
        "heldout_split": summarize(by_split["heldout"]),
        "by_repo": {r: summarize([x for x in results if x["repo"] == r]) for r in REPO_BARE_MAP}
    }

    full_payload = {
        "summary": summary,
        "tasks": results
    }

    with open(RESULTS_PATH, "w") as f:
        json.dump(full_payload, f, indent=2)

    print("\n================ BENCHMARK SUMMARY ================")
    print(f"Total Tasks Evaluated: {len(results)}")
    print(f"Overall Recall@1: {summary['overall']['recall_at_1']*100:.1f}%")
    print(f"Overall Recall@3: {summary['overall']['recall_at_3']*100:.1f}%")
    print(f"Overall Recall@5: {summary['overall']['recall_at_5']*100:.1f}%")
    print(f"Overall MRR:      {summary['overall']['mrr']:.4f}")
    print(f"Avg Latency:      {summary['overall']['avg_latency_sec']:.2f}s")
    print(f"Dev Recall@3:     {summary['dev_split']['recall_at_3']*100:.1f}% (N={summary['dev_split']['count']})")
    print(f"Heldout Recall@3: {summary['heldout_split']['recall_at_3']*100:.1f}% (N={summary['heldout_split']['count']})")
    print("===================================================\n")
    print("Results saved to:", RESULTS_PATH)


if __name__ == "__main__":
    run_benchmark()
