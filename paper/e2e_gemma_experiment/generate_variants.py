#!/usr/bin/env python3
"""
Generate the 4 test failure traceback variants:
- A_raw: Full original pytest output
- B_compressed: AST-guided canonical compressor
- C_tail35: Naive 35-line tail cap
- D_no_trace: Control baseline with no traceback provided
and build the frozen, blinded evaluation prompts without answer-leaking symbols.
"""
import sys
import json
import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
TRACEBACK_EXP_DIR = REPO_ROOT / "paper" / "traceback_experiment"
PAPER_DIR = REPO_ROOT / "paper"
sys.path.insert(0, str(PAPER_DIR))
sys.path.insert(0, str(TRACEBACK_EXP_DIR))

from real_traceback_benchmark import filter_pytest_log, naive_tail_cap
from traceback_compressor import filter_pytest_log_v2

TASKS_DIR = Path(__file__).parent / "tasks"
VARIANTS_DIR = Path(__file__).parent / "variants"
PROMPTS_DIR = Path(__file__).parent / "frozen_prompts"

SYSTEM_PROMPT = """You are an expert autonomous software engineer working with Gemma 4.
Your goal is to inspect the source code and the test failure traceback, determine the exact location and root cause of the defect, and provide the minimal correct code fix for source.py.

Respond strictly in the following format:
DEFECT_LOCATION: <exact function, method, or class name where the defect resides>
ROOT_CAUSE: <a concise 1-3 sentence explanation of the defect and why the test failed>
PROPOSED_CODE:
```python
<complete revised implementation of the target function or file>
```"""

def main():
    VARIANTS_DIR.mkdir(parents=True, exist_ok=True)
    PROMPTS_DIR.mkdir(parents=True, exist_ok=True)
    
    manifest_p = Path(__file__).parent / "task_manifest.json"
    tasks = json.loads(manifest_p.read_text(encoding="utf-8"))
    
    stats = []
    frozen_records = []
    
    print(f"Generating traceback variants for {len(tasks)} tasks...")
    total_raw_chars = 0
    total_comp_chars = 0
    
    for t in tasks:
        tid = t["id"]
        tdir = TASKS_DIR / tid
        source_p = tdir / "source.py"
        test_p = tdir / "test_task.py"
        
        t_var_dir = VARIANTS_DIR / tid
        t_var_dir.mkdir(parents=True, exist_ok=True)
        raw_p = t_var_dir / "variant_A_raw.txt"

        if raw_p.exists():
            raw_output = raw_p.read_text(encoding="utf-8")
        else:
            python_bin = REPO_ROOT / ".venv" / "bin" / "python"
            if not python_bin.exists():
                python_bin = sys.executable
            cmd = [str(python_bin), "-m", "pytest", str(test_p), "-v", "--tb=auto"]
            res = subprocess.run(cmd, cwd=tdir, capture_output=True, text=True)
            raw_output = res.stdout + ("\n" + res.stderr if res.stderr else "")
        
        # Compute variants
        var_a = raw_output
        var_b = filter_pytest_log(raw_output)
        var_b2 = filter_pytest_log_v2(raw_output)
        var_c = naive_tail_cap(raw_output, 35)
        var_d = "No test traceback provided. Locate the defect by analyzing the source code against the specification."
        
        # Track statistics
        total_raw_chars += len(var_a)
        total_comp_chars += len(var_b)
        
        # Save variant text files
        (t_var_dir / "variant_A_raw.txt").write_text(var_a, encoding="utf-8")
        (t_var_dir / "variant_B_compressed.txt").write_text(var_b, encoding="utf-8")
        (t_var_dir / "variant_B2_assertion_aware.txt").write_text(var_b2, encoding="utf-8")
        (t_var_dir / "variant_C_tail35.txt").write_text(var_c, encoding="utf-8")
        (t_var_dir / "variant_D_no_trace.txt").write_text(var_d, encoding="utf-8")
        
        source_code = source_p.read_text(encoding="utf-8")
        
        # Prepare frozen prompts for A, B, B2, C, D (BLINDED: NO TARGET SYMBOL LEAKED)
        variants = [
            ("A_raw", var_a),
            ("B_compressed", var_b),
            ("B2_assertion_aware", var_b2),
            ("C_tail35", var_c),
            ("D_no_trace", var_d)
        ]
        
        for variant_name, trace_text in variants:
            user_prompt = f"""# Task: {t['id']}
## Problem Statement:
{t['issue']}

## Source Code (`source.py`):
```python
{source_code}
```

## Test Failure Traceback ({variant_name}):
```text
{trace_text}
```

Analyze the failure and traceback, identify the exact defect location, explain the root cause, and provide the corrected Python code for source.py.
"""
            prompt_record = {
                "task_id": tid,
                "variant": variant_name,
                "repo_inspiration": t["repo_inspiration"],
                "system_prompt": SYSTEM_PROMPT,
                "user_prompt": user_prompt,
                "prompt_char_len": len(user_prompt),
                "trace_char_len": len(trace_text),
                "trace_line_count": len(trace_text.splitlines())
            }
            frozen_records.append(prompt_record)
            
            p_file = PROMPTS_DIR / f"{tid}__{variant_name}.json"
            p_file.write_text(json.dumps(prompt_record, indent=2), encoding="utf-8")
            
        red_pct = (1 - len(var_b) / len(var_a)) * 100
        row_stat = {
            "task_id": tid,
            "raw_chars": len(var_a),
            "raw_lines": len(var_a.splitlines()),
            "compressed_chars": len(var_b),
            "compressed_lines": len(var_b.splitlines()),
            "tail_chars": len(var_c),
            "tail_lines": len(var_c.splitlines()),
            "reduction_pct": round(red_pct, 2),
            "is_safe_fallback_zero_reduction": len(var_b) == len(var_a)
        }
        stats.append(row_stat)
        print(f"  {tid}: Raw={len(var_a)}c -> Comp={len(var_b)}c ({red_pct:.1f}% reduction), Fallback={row_stat['is_safe_fallback_zero_reduction']}")

    weighted_reduction = (1 - total_comp_chars / total_raw_chars) * 100
    unweighted_reduction = sum(s["reduction_pct"] for s in stats) / len(stats)
    fallback_count = sum(1 for s in stats if s["is_safe_fallback_zero_reduction"])
    compressed_subset = [s["reduction_pct"] for s in stats if not s["is_safe_fallback_zero_reduction"]]
    active_compression_mean = sum(compressed_subset) / len(compressed_subset) if compressed_subset else 0.0
    
    summary_data = {
        "dataset_name": "Synthetic Reproductions Inspired by Open-Source Bugs",
        "provenance_note": "15 self-contained synthetic reproductions inspired by open-source bug patterns. Used for isolated CPU component ablation, distinct from full SWE-bench repo checkouts.",
        "total_tasks": len(tasks),
        "total_prompts": len(frozen_records),
        "variants": ["A_raw", "B_compressed", "C_tail35", "D_no_trace"],
        "metrics": {
            "total_raw_chars": total_raw_chars,
            "total_compressed_chars": total_comp_chars,
            "weighted_reduction_pct": round(weighted_reduction, 2),
            "unweighted_mean_reduction_pct": round(unweighted_reduction, 2),
            "zero_reduction_fallback_tasks_count": fallback_count,
            "zero_reduction_fallback_tasks_pct": round(fallback_count / len(tasks) * 100, 2),
            "active_compression_subset_count": len(compressed_subset),
            "active_compression_mean_reduction_pct": round(active_compression_mean, 2)
        },
        "task_breakdown": stats
    }
    
    summary_p = Path(__file__).parent / "dataset_summary.json"
    summary_p.write_text(json.dumps(summary_data, indent=2), encoding="utf-8")
    
    print(f"\nSummary generated successfully!")
    print(f"  Weighted Reduction: {weighted_reduction:.2f}% (Total chars: {total_raw_chars} -> {total_comp_chars})")
    print(f"  Unweighted Mean Reduction: {unweighted_reduction:.2f}%")
    print(f"  Safe Fallbacks (0% reduction): {fallback_count}/{len(tasks)} ({fallback_count/len(tasks)*100:.1f}%)")
    print(f"  Active Compression Subset (11 tasks): {active_compression_mean:.2f}% mean reduction")
    print(f"  All {len(frozen_records)} frozen blinded prompts saved to {PROMPTS_DIR}")

if __name__ == "__main__":
    main()
