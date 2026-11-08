# AST-Guided Verification Suite: Deterministic Code Slicing, Pre-Flight Validation, and Traceback Compression for Local SWE Agents on Gemma 4

**Author:** Mikhail Singatullin (`msingatullin` / Team `Михаил`)  
**Competition Track:** [Google - The Gemma 4 Developer Agent Paper Track](https://www.kaggle.com/competitions/gemma-4-developer-agent-paper)  
**Target Track / Category:** Overall Best Paper / Best New Resource & Application  
**Public Executable Notebook:** [Kaggle Notebook](https://www.kaggle.com/code/msingatullin/ast-guided-loops-verification-for-gemma-4)  
**Open-Source Repository:** [github.com/msingatullin/gemma-4-developer-agent](https://github.com/msingatullin/gemma-4-developer-agent)  
**License:** Apache 2.0  

---

## 1. Abstract & Executive Summary

Deploying autonomous software engineering (SWE) agents with quantized large language models—specifically `google/gemma-4-31B-it-qat-w4a16-ct`—on edge developer workstations (1× NVIDIA L4 or RTX GPU with 24–48GB VRAM) exposes severe operational bottlenecks. Full-file reading across multi-thousand-line modules inflates prompt context, while unvalidated candidate patches waste expensive execution cycles on trivial syntax regressions. Furthermore, multi-test execution logs inundate model context with environment banners and captured stdout buffers, crowding out critical fault localization signals.

This work introduces the **AST-Guided Verification Suite**, an open-source, deterministic evaluation and execution framework engineered for local SWE agents. The suite couples sub-millisecond abstract syntax tree (`ast.NodeVisitor`) symbol indexing, a native pre-flight compilation gate (`compile(mode='exec')`), and a multi-format assertion-preserving traceback compression engine that eliminates stdout pollution while strictly retaining diagnostic root causes across standard pytest formats, native tracebacks, and standalone exceptions.

Beyond isolated microbenchmarks, this work presents an **end-to-end empirical study comprising 120 live inference calls to real quantized Gemma 4 31B (`google/gemma-4-31B-it-qat-w4a16-ct`)** across 15 synthetic defect reproduction tasks and two random seeds. Compared to native raw tracebacks, our AST-guided compression delivers a **31.5% reduction in total prompt tokens** (1,158 to 793 tokens per task call) and a **56.86% reduction in traceback characters** (2,314 to 998 characters), while preserving 100% localization accuracy and 86.7% objective diagnostic accuracy (versus 90.0% for raw traces, $\Delta = -3.33\%$, 95% bootstrap CI: $[-10.0\%, 0.0\%]$, permutation $p = 1.0000$). 

Furthermore, we evaluate all 120 candidate patches in an isolated, unprivileged container sandbox (`--network none`, `--cap-drop ALL`, 512MB RAM, read-only mounts). The measured **Patch Test Pass Rate** was **100.0%** (30/30) for native raw traces (`A_raw`), **83.3%** (25/30) for AST-compressed traces (`B_compressed`), **100.0%** (30/30) for 35-line tail truncation (`C_tail35`), and **73.3%** (22/30) for zero traceback (`D_no_trace`). In paired hypothesis testing, the observed difference between compressed and raw traces ($\Delta_{B-A} = -16.67\%$, 95% CI: $[-36.7\%, 0.0\%]$, permutation $p = 0.2539$) does not achieve statistical significance at $\alpha = 0.05$. In accordance with scientific rigor, we emphasize that failure to reject the null hypothesis cannot be interpreted as proven functional equivalence, and we provide a detailed failure taxonomy illustrating engineering trade-offs between context compression and patch precision.

---

## 2. Operating Constraints and Gemma 4 (31B QAT) Attention Mechanics

### Hardware Environments: Competition Cluster vs. Edge Deployments
- **Official Competition Cluster:** 4 × NVIDIA L4 GPUs (96 GB GDDR6 total) with Tensor Parallelism (TP=4), distributing model weights and KV cache across four accelerators.
- **Edge Developer Deployments:** Single accelerator (1 × NVIDIA L4 24GB or local workstation GPU) without multi-GPU orchestration. Memory headroom is strictly constrained, making deterministic context management imperative.

### Architectural Specifications of `google/gemma-4-31B-it-qat-w4a16-ct`:
- **Weights:** INT4 pack-quantized weights (group size 32, FP16 activations), occupying $\approx 18.24$ GiB VRAM.
- **Total Layers:** $L = 60$.
- **Hybrid Attention:** 50 sliding-window layers (window $W = 1024$ tokens, $H_{kv} = 16$, head dimension $d_k = 256$) and 10 full-attention global layers (every 6th layer, $H_{kv,\text{global}} = 4$, $d_{k,\text{global}} = 512$).
- **Query Heads:** $H_q = 32$.

### Analytical KV Cache Growth Across Hybrid Attention Layers

The KV cache memory footprints and Roofline decoding latencies below are analytical calculations based on theoretical memory bandwidth ($242.0 \times 10^9$ bytes/sec for NVIDIA L4) and INT4/FP16 cache layout under stated resident-memory assumptions; they are not empirical GPU runtime measurements.

For context sequence $T$ in FP16 ($2$ bytes/scalar), memory allocation scales across sliding and global layers:
1. **Sliding Layers (50 layers):** $M_{\text{KV,sliding}}(T) = 50 \times 2 \times 16 \times 256 \times \min(T, 1024) \times 2 = 819,200 \times \min(T, 1024) \text{ bytes}$. Saturates at $0.781$ GiB when $T \ge 1024$.
2. **Global Layers (10 layers):** $M_{\text{KV,global}}(T) = 10 \times 2 \times 4 \times 512 \times T \times 2 = 80.0 \times T \text{ KB}$.
3. **Total Footprint and Modeled Latency:**
   - At $T = 1,024$: Total KV $= 0.859$ GiB; Total VRAM $= 19.15$ GiB ($4.85$ GiB headroom on 1× L4).
   - At $T = 8,192$ (AST scope): Total KV $= 1.406$ GiB; Total VRAM $= 19.73$ GiB ($4.27$ GiB headroom).
   - At $T = 24,576$ (Unconstrained): Total KV $= 2.656$ GiB; Total VRAM $= 21.06$ GiB ($2.94$ GiB headroom).

Under memory-bound decoding ($I \approx 1$ FLOP/byte), modeled per-token latency is **87.2 ms/token at 8,192 tokens** versus **92.7 ms/token at 24,576 tokens** ($+6.36\%$ latency growth), while shrinking headroom from 4.27 GiB to 2.94 GiB on single-accelerator setups.

---

## 3. Related Work and Positioning Against Prior Art

Autonomous SWE agents have advanced rapidly across benchmarks like SWE-bench:
- **Hierarchical Inspection (`Agentless`):** Xia et al. (2024) proposed localization $\rightarrow$ patch repair $\rightarrow$ validation. However, `Agentless` relies on high-temperature LLM queries against frontier models (GPT-4o, Claude 3.5 Sonnet) and multi-step file search heuristics, introducing fatal latency on quantized local models.
- **Iterative ReAct Loops (`SWE-agent`):** Yang et al. (2024) introduced Agent-Computer Interfaces (ACI). While effective with large context windows, these interfaces prompt local quantized models to perform continuous conversational reading, saturating context with redundant file bodies.
- **Code Graphs (`RepoCoder`):** Zhang et al. (2023) used cross-file semantic similarity and RAG. Full repository code graphs incur heavy indexing overhead unsuited for lightweight execution loops.

### Architectural Novelty: The Deterministic Zero-Inference Stance

In contrast to prior art, this suite introduces a **zero-inference, deterministic verification layer**:
1. **Zero LLM Overhead for Localization:** Symbol discovery relies on Python's built-in `ast` visitor, extracting precise function and class line ranges in sub-millisecond latency without consuming model generation tokens.
2. **Native Pre-Flight Compilation Gate:** Catches syntax regressions, top-level return anomalies, and indentation corruptions in under 0.1 ms using Python's standard `compile(mode='exec')` before initiating container test suites.
3. **Multi-Format Traceback Compression:** Strips hundreds of lines of pytest session banners and captured stdout spam while strictly preserving failing assertion lines (`E ...`), line pointers, and multiline exception messages across standard pytest (`--tb=auto`, `--tb=long`, `--tb=short`), native tracebacks (`--tb=native`), and standalone Python exceptions.

---

## 4. Deterministic Component Evaluation: Executable Benchmark with Hardened Oracles

We evaluated deterministic components across the `ASTVerificationBenchmark`, a curated microbenchmark of 31 representative defect scenarios with ground-truth line, exception, and multiline assertion oracles enforced by executable assertions:

| Category | Tasks | Mean CPU Latency (µs) | Strict Oracle Accuracy | Mean Raw Tokens (Est.) | Mean Processed Tokens | Mean Token Reduction |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Code Slicing** | 8 | 235.8 µs | 100.0% (Exact bounds) | 65.8 | 36.0 | **44.6%** |
| **Syntax Interception** | 10 | 38.2 µs | 100.0% (Syntax catches) | 6.8 | 6.8 | Pre-flight catch (100%) |
| **Traceback Compression** | 8 | 159.3 µs | 100.0% (Details preserved) | 111.5 | 77.4 | **30.6%** (Corpus aggregate) |
| **Valid Clean Patches** | 5 | 70.2 µs | 100.0% (Zero false reject) | 15.2 | 15.2 | Gate pass (100%) |

*Note on Token Estimation:* Reported token quantities are heuristic estimates via integer division `len(text) // 4` (matching BPE subword approximations).

### Component Ablation and Real Pytest Traceback Validation

We benchmarked the components against naive agent baselines and unmocked pytest execution logs (`pytest 8.4.2`, `Python 3.12.3`) across diverse failure typologies (120 lines of stdout noise, 32-frame multiline assertion diffs, parametrized suites, distinct exception types):

| Configuration / Mode | Volume Reduction (%) | Diagnostic Retention (%) | Syntax Errors Caught Pre-Flight | Processing Latency (CPU) |
| :--- | :---: | :---: | :---: | :---: |
| **Baseline 0: Naive SWE Agent** (Raw files, raw logs) | 0.0% (Baseline) | 100.0% (Uncompressed raw) | 0% (Escapes to runner) | N/A (Direct pass-through) |
| **Ablation 1: AST Slicing Alone** (`ast.NodeVisitor`) | **44.6%** (Code context) | 100.0% (Uncompressed raw) | 0% (Escapes to runner) | 235.8 µs |
| **Ablation 2: Syntax Gate Alone** (`compile(mode='exec')`) | 0.0% (Code context) | 100.0% (Uncompressed raw) | **100.0%** (Pre-flight) | 38.2 µs |
| **Ablation 3: Traceback Compression Alone** | **30.6%** (Microbenchmark) | **100.0%** (Zero diagnostic loss) | 0% (Escapes to runner) | 159.3 µs |
| **Real Pytest Verbose (`-v`, `--tb=auto`)** | **71.9%** (6,068 vs 21,557 ch) | **100.0%** (62/62 items preserved) | N/A | 5.93 ms ± 0.08 ms |
| **Real Pytest Short (`--tb=short`)** | **75.1%** (4,509 vs 18,104 ch) | **100.0%** (55/55 items preserved) | N/A | 4.65 ms ± 0.06 ms |
| **Baseline: Naive Tail-Cap (35 lines)** | 91.3% (Heuristic cutoff) | **22.6%** (Drops 48/62 items) | N/A | 0.08 ms ± 0.00 ms |
| **Baseline: Naive E-Lines Only** | 86.6% (Strips headers/sites) | **62.9%** (Drops 23/62 items) | N/A | 0.25 ms ± 0.00 ms |
| **Full AST Suite (All Components Active)** | **44.6% code / 71.9% trace** | **100.0% diagnostic retention** | **100.0% pre-flight catch** | **3.893 ms** (31 tasks combined) |

---

## 5. End-to-End Empirical Validation with Real Gemma 4 (31B QAT) Inference and Containerized Execution

To validate whether deterministic traceback compression translates into measurable prompt savings and robust defect resolution without degrading reasoning performance, we conducted a pre-registered end-to-end empirical study using live model inference and sandboxed test execution.

### 5.1 Experimental Protocol and Task Corpus
The benchmark corpus comprises 15 synthetic Python defect reproduction tasks directly modeled after canonical bug patterns in major open-source ecosystems (Flask, Requests, Click, Jinja2, Urllib3, Rich, Pluggy, Marshmallow, Pydantic, Attrs, ItsDangerous, Werkzeug, PyTest). Each task includes a buggy implementation, ground-truth metadata, and an executable pytest test suite.

We tested four trace presentation variants across two independent random seeds ($S \in \{42, 100\}$), producing exactly $15 \times 4 \times 2 = 120$ unique model calls:
1. `A_raw`: Native, uncompressed traceback containing all session banners and captured stdout noise.
2. `B_compressed`: Our AST-guided compressed traceback, eliminating stdout noise while preserving failure headers, assertion sites, and multiline error lines.
3. `C_tail35`: Naive tail-truncation baseline retaining only the final 35 lines of the log.
4. `D_no_trace`: Complete ablation of the traceback, providing only the final exception name and message.

All 120 calls were executed against `google/gemma-4-31B-it-qat-w4a16-ct` hosted on an isolated cloud instance (NVIDIA RTX A6000 48GB VRAM) via vLLM with eager attention kernels, greedy decoding (temperature 0.0, top_p 0.95), and strict completeness verification prohibiting zero-substitution.

### 5.2 Token and Traceback Volume Reduction
Across the 120 live inference calls, our AST-guided compressor dramatically reduced prompt volume:

| Variant | Total Calls | Mean Prompt Chars | Mean Trace Chars | Trace Reduction (%) | Mean Tokens Used | Total Token Reduction (%) | Mean Latency (s) |
|---|---|---|---|---|---|---|---|
| **`A_raw`** | 30 | 3,124 | 2,314 | 0.0% (Baseline) | 1,158 | 0.0% (Baseline) | 10.33 s |
| **`B_compressed`** | 30 | 1,807 | 998 | **56.86%** | 793 | **31.52%** | 9.89 s |
| **`C_tail35`** | 30 | 2,584 | 1,775 | 23.29% | 1,001 | 13.56% | 10.01 s |
| **`D_no_trace`** | 30 | 910 | 101 | 95.64% | 537 | 53.63% | 9.97 s |

AST-guided compression reduces the volume of traceback characters fed to Gemma 4 by **56.86%** (2,314 chars down to 998 chars), driving an overall **31.5% reduction in total prompt tokens** (1,158 down to 793 tokens per inference call).

### 5.3 Diagnostic Accuracy and Blinded Failure Audit
Diagnostic reasoning was evaluated across all 120 responses:
- **Defect Localization Pass Rate:** **100.0%** (30/30) across all four variants (`A_raw`, `B_compressed`, `C_tail35`, `D_no_trace`). Gemma 4 accurately localized the canonical defective symbol in 120/120 calls.
- **Pre-Flight Static Syntax Pass Rate:** **100.0%** (30/30) across all variants. Zero syntax errors were introduced by the model.
- **Objective Root Cause Pass Rate:** **90.0%** (27/30) for `A_raw`, **86.7%** (26/30) for `B_compressed`, **93.3%** (28/30) for `C_tail35`, and **86.7%** (26/30) for `D_no_trace`. Paired delta between compressed and raw traces is $\Delta = -3.33\%$ (95% bootstrap CI: $[-10.0\%, 0.0\%]$, permutation $p = 1.0000$).

To investigate the 13 automated diagnostic failures, we conducted a blinded independent qualitative audit in which variant identities (A/B/C/D) were concealed from the reviewer. The original pre-registered rubric results were retained strictly unchanged as primary truth. The blinded audit revealed:
- **Zero Hallucinations (0/13):** The model never fabricated non-existent classes, phantom modules, or imaginary tracebacks.
- **Inflection Mismatches (3/13, 23.1%):** In task 07 (`urllib3`) and task 15 (`pytest`), the model diagnosed the exact failure mechanism, but used morphological inflections (participle "preserving" vs infinitive "preserve"; verb "subtract" vs noun "subtraction") that failed pre-registered literal substring filters.
- **Competing Facet Diagnoses (8/13, 61.5%):** In task 09 (`pluggy`), all variants across both seeds correctly localized `HookCaller.execute` and identified hook ordering bugs, but prioritized the `tryfirst` FIFO/LIFO ordering specification rather than the `trylast` appending rule.
- **Generalization Over-Extensions (2/13, 15.4%):** In task 07, variants under seed 100 correctly identified manual '+' replacement flaws, but over-generalized to full URL unquoting.

### 5.4 Containerized Patch Test Pass Rates and Hypothesis Testing
To measure whether proposed candidate patches actually resolve defects without breaking existing behavior, all 120 generated patches were executed in an isolated, unprivileged container sandbox (`gemma4-eval-sandbox:latest`) configured with `--network none`, `--cap-drop ALL`, `--user 1000:1000`, 512MB RAM, 1.0 CPU core, and read-only host directory mounts.

| Variant | Description | Total Calls | Passed Tests | Pass Rate (%) | Std Error | 95% Bootstrap CI |
|---|---|---|---|---|---|---|
| **`A_raw`** | Native uncompressed traceback | 30 | 30 | **100.0%** | 0.00% | [100.0%, 100.0%] |
| **`B_compressed`** | AST-guided compressed traceback (Ours) | 30 | 25 | **83.3%** | 6.80% | [63.3%, 100.0%] |
| **`C_tail35`** | Tail 35-line truncation baseline | 30 | 30 | **100.0%** | 0.00% | [100.0%, 100.0%] |
| **`D_no_trace`** | Zero traceback (Exception text only) | 30 | 22 | **73.3%** | 8.07% | [46.7%, 93.3%] |

#### Paired Hypothesis Testing (Task-Clustered Unit):
- `delta_B_minus_A` (`B_compressed` vs `A_raw`): Observed $\Delta = -16.67\%$, 95% Bootstrap CI: $[-36.7\%, 0.0\%]$, permutation $p = 0.2539$.
- `delta_B_minus_C` (`B_compressed` vs `C_tail35`): Observed $\Delta = -16.67\%$, 95% Bootstrap CI: $[-36.7\%, 0.0\%]$, permutation $p = 0.2539$.
- `delta_B_minus_D` (`B_compressed` vs `D_no_trace`): Observed $\Delta = +10.00\%$, 95% Bootstrap CI: $[-6.7\%, +30.0\%]$, permutation $p = 0.5053$.

### 5.5 Scientific Rigor and Equivalence Caveat
In paired hypothesis testing, the observed difference between AST-compressed and raw tracebacks ($\Delta = -16.67\%$, $p = 0.2539$) does not achieve statistical significance at the standard $\alpha = 0.05$ threshold. However, **we explicitly caution that failure to reject the null hypothesis ($p \ge 0.05$) does NOT establish proven functional equivalence**. 

Inspection of the failure taxonomy explains this nuance: in two specific tasks (task 04 `requests_socket_error` and task 13 `itsdangerous_expired`), removing intermediate socket framing and timestamp wrapper frames deprived the quantized 31B model of contextual clues needed to structure exception chaining (`from err`), causing `B_compressed` to fail assertion checks that `A_raw` and `C_tail35` passed. Conversely, completely eliminating tracebacks (`D_no_trace`) caused pass rates to drop to 73.3% (failing 8 calls across 4 tasks). This demonstrates that while AST compression achieves significant token savings (31.5%) and preserves diagnostic localization (100%), aggressive traceback stripping involves a genuine engineering trade-off for complex exception hierarchies.

### 5.6 Synthetic Tasks vs. Upstream Real Repository Archive
The primary 15 tasks evaluated in this study are synthetic reproductions modeled on real bug patterns. To support future open-ended benchmarks, the repository maintains an isolated upstream real repository archive (`real_repo_sample/`) containing 5 unmodified multi-file tasks from historical Git commits in `pallets/flask`, `psf/requests`, `pallets/click`, `pallets/jinja`, and `urllib3/urllib3`. These real-world tasks serve as a prospective benchmark reserved for multi-turn evaluations.

---

## 6. SWE Agent Integration Architecture & Operational Design Principles

The empirical findings from Section 5 inform the production integration architecture for local SWE agents.

### 6.1 Native Pre-Flight Compiler Gate
Before executing test commands in container environments, candidate patches pass through the pre-flight compiler gate:
```python
def check_preflight_syntax(patch_code: str) -> tuple[bool, str]:
    if not patch_code:
        return False, "Empty code patch"
    try:
        compile(patch_code, "<candidate_patch>", "exec")
        return True, ""
    except SyntaxError as e:
        return False, f"SyntaxError at line {e.lineno}: {e.msg}"
```
This intercepts malformed patches in under 0.1 ms (38.2 µs cloud mean latency), completely preventing wasted container executions.

### 6.2 Context Window Stability and Attention Mechanics
Under hybrid attention (50 sliding-window layers with $W = 1024$ tokens, 10 full-attention layers), uncontrolled file reading and noisy logs quickly exhaust the active attention window. By deploying AST symbol slicing (44.6% context reduction) and traceback compression (31.5% token reduction), agent conversations maintain critical early instructions within active attention without cache thrashing.

### 6.3 Multi-Format Assertion Preservation
Traceback filtering isolates failing blocks and collapses stdout noise while strictly preserving failure headers, assertion sites (`> assert ...`), assertion details (`E ...`), and multiline diff frames across standard, short, long, native, and standalone tracebacks.

### 6.4 Production ADK Specification
The complete system is formalized as a Google Agent Development Kit (ADK) specification in `agent.yaml`:
```yaml
name: gemma4_ast_verified_agent
model: gemma-4-31b-it-qat-w4a16-ct
description: Deterministic AST-verified autonomous software engineering agent.
instruction: !include prompts/system.md
generate_content_config:
  temperature: 0.1
  top_p: 0.95
  max_output_tokens: 2048
tools:
  - run_command
  - read_file
  - edit_file
  - write_file
  - submit_patch
max_tool_calls: 24
max_turns: 36
session_timeout_seconds: 300
```

---

## 7. Artifacts & Open-Source Availability

All artifacts developed for this project are permanently archived and released under the open-source **Apache 2.0** license:
- **Public Executable Notebook:** [msingatullin/ast-guided-loops-verification-for-gemma-4](https://www.kaggle.com/code/msingatullin/ast-guided-loops-verification-for-gemma-4)
- **Open-Source Repository:** [github.com/msingatullin/gemma-4-developer-agent](https://github.com/msingatullin/gemma-4-developer-agent)
- **120 Real Model Inferences:** `paper/e2e_gemma_experiment/real_run_20261108/real_experiment_checkpoint.jsonl`
- **Containerized Patch Execution Results:** `paper/e2e_gemma_experiment/real_run_20261108/real_patch_execution_results.jsonl`
- **Statistical Analysis & Clustered Bootstrap:** `paper/e2e_gemma_experiment/real_run_20261108/real_patch_execution_analysis.json`
- **Blinded Qualitative Audit:** `paper/e2e_gemma_experiment/real_run_20261108/blinded_diagnostic_audit.json`
- **License:** Apache 2.0 (`LICENSE` in repository root)
