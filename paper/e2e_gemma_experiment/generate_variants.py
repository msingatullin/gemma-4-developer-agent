#!/usr/bin/env python3
"""
Generate the 3 test failure traceback variants (A: Raw, B: AST-Compressed, C: Naive Tail)
for all 15 software tasks, and build the frozen input prompts for Gemma 4 evaluation.
"""
import sys
import json
import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
TRACEBACK_EXP_DIR = REPO_ROOT / "paper" / "traceback_experiment"
sys.path.insert(0, str(TRACEBACK_EXP_DIR))

from real_traceback_benchmark import filter_pytest_log, naive_tail_cap

TASKS_DIR = Path(__file__).parent / "tasks"
VARIANTS_DIR = Path(__file__).parent / "variants"
PROMPTS_DIR = Path(__file__).parent / "frozen_prompts"

SYSTEM_PROMPT = """You are an expert autonomous software engineer working with Gemma 4.
Your goal is to inspect the source code and the test failure traceback, determine the exact root cause of the defect, and provide the minimal correct code fix for source.py.

Respond with:
1. ROOT_CAUSE: A concise 1-3 sentence explanation of the defect and why the test failed.
2. PATCH: The complete revised implementation of the target function/class inside a python markdown code block."""

def main():
    VARIANTS_DIR.mkdir(parents=True, exist_ok=True)
    PROMPTS_DIR.mkdir(parents=True, exist_ok=True)
    
    manifest_p = Path(__file__).parent / "task_manifest.json"
    tasks = json.loads(manifest_p.read_text(encoding="utf-8"))
    
    stats = []
    frozen_records = []
    
    print(f"Generating traceback variants for {len(tasks)} tasks...")
    for t in tasks:
        tid = t["id"]
        tdir = TASKS_DIR / tid
        source_p = tdir / "source.py"
        test_p = tdir / "test_task.py"
        
        # 1. Run pytest to capture raw failing log
        cmd = [sys.executable, "-m", "pytest", str(test_p), "-v", "--tb=auto"]
        res = subprocess.run(cmd, cwd=tdir, capture_output=True, text=True)
        raw_output = res.stdout + ("\n" + res.stderr if res.stderr else "")
        
        # 2. Compute Variant A (Raw)
        var_a = raw_output
        
        # 3. Compute Variant B (AST-Guided Canonical Compressor)
        var_b = filter_pytest_log(raw_output)
        
        # 4. Compute Variant C (Naive 35-line tail cap)
        var_c = naive_tail_cap(raw_output, 35)
        
        # Save variant text files
        t_var_dir = VARIANTS_DIR / tid
        t_var_dir.mkdir(parents=True, exist_ok=True)
        (t_var_dir / "variant_A_raw.txt").write_text(var_a, encoding="utf-8")
        (t_var_dir / "variant_B_compressed.txt").write_text(var_b, encoding="utf-8")
        (t_var_dir / "variant_C_tail35.txt").write_text(var_c, encoding="utf-8")
        
        source_code = source_p.read_text(encoding="utf-8")
        
        # Prepare frozen prompts for A, B, C
        for variant_name, trace_text in [("A_raw", var_a), ("B_compressed", var_b), ("C_tail35", var_c)]:
            user_prompt = f"""# Task: {t['id']} ({t['repo']})
## Issue Description:
{t['issue']}

## Source Code (`source.py`):
```python
{source_code}
```

## Test Failure Traceback ({variant_name}):
```text
{trace_text}
```

Analyze the failure, identify the root cause in `{t['target_symbol']}`, and provide the corrected implementation.
"""
            prompt_record = {
                "task_id": tid,
                "variant": variant_name,
                "repo": t["repo"],
                "target_symbol": t["target_symbol"],
                "expected_exception": t["expected_exception"],
                "root_cause_gold": t["root_cause"],
                "system_prompt": SYSTEM_PROMPT,
                "user_prompt": user_prompt,
                "prompt_char_len": len(user_prompt),
                "trace_char_len": len(trace_text),
                "trace_line_count": len(trace_text.splitlines())
            }
            frozen_records.append(prompt_record)
            
            p_file = PROMPTS_DIR / f"{tid}__{variant_name}.json"
            p_file.write_text(json.dumps(prompt_record, indent=2), encoding="utf-8")
            
        row_stat = {
            "task_id": tid,
            "raw_chars": len(var_a),
            "raw_lines": len(var_a.splitlines()),
            "compressed_chars": len(var_b),
            "compressed_lines": len(var_b.splitlines()),
            "tail_chars": len(var_c),
            "tail_lines": len(var_c.splitlines()),
            "compression_ratio": (1 - len(var_b) / len(var_a)) * 100
        }
        stats.append(row_stat)
        print(f"  {tid}: Raw={len(var_a)}c -> Comp={len(var_b)}c (-{row_stat['compression_ratio']:.1f}%), Tail={len(var_c)}c")
        
    summary_p = Path(__file__).parent / "dataset_summary.json"
    summary_p.write_text(json.dumps({
        "total_tasks": len(tasks),
        "total_prompts": len(frozen_records),
        "variants": ["A_raw", "B_compressed", "C_tail35"],
        "task_stats": stats
    }, indent=2), encoding="utf-8")
    
    print(f"\nAll 45 frozen evaluation prompts generated and saved to {PROMPTS_DIR}!")
    print(f"Summary saved to {summary_p}")

if __name__ == "__main__":
    main()
