# When Traceback Compression Lies: Verifiable Diagnostics for Gemma 4 SWE Agents

*Falsification-tested, fail-open diagnostics and a reproducible verification resource for local Gemma 4 software agents.*

**Author:** Mikhail Singatullin (`msingatullin` / Team `Михаил`)  
**Competition Track:** [Google - The Gemma 4 Developer Agent Paper Track](https://www.kaggle.com/competitions/gemma-4-developer-agent-paper)  
**Target Track / Category:** Overall Best Paper / Best New Resource & Application  
**Public Executable Notebook:** [Kaggle Notebook](https://www.kaggle.com/code/msingatullin/ast-guided-loops-verification-for-gemma-4)  
**Open-Source Repository:** [github.com/msingatullin/gemma-4-developer-agent](https://github.com/msingatullin/gemma-4-developer-agent)  
**License:** Apache 2.0  

---

## 1. Abstract & Executive Summary

Local SWE agents often shorten pytest logs to reduce context costs. We found that this operation can silently remove failing-assertion evidence **and** cause an integrity certificate to certify the incomplete output. Our Apache-2.0 resource combines a deterministic assertion-aware compressor, an independently checked fail-open guard, versioned certificates, and reproducible tests that require no GPU, credentials, or model calls.

We used **11 authentic failing pytest logs from eight upstream repositories** and 88 synthetic CI/terminal-format perturbations (eight fixed transformations per log). The older ANSI-unaware compressor plus certificate incorrectly accepted **10/88** outputs missing selected evidence. The optional guard preserved the predefined diagnostic/header/summary markers in **88/88** cases and rejected **704/704** deliberate certificate-tampering controls; on the original 11 logs it left outputs byte-identical. Across those logs, B2 retained selected markers on **11/11** versus **2/11** for head35/tail35 while reducing UTF-8 log bytes by **72.01%**. These are bounded marker and software-integrity tests, not proof of semantic equivalence or 88 independent upstream defects.

We also release 150 saved Gemma 4 31B synthetic-task responses and a separate five-authentic-issue pilot. First-pass repair was **1/5 with each of Raw, B2, and tail35**, solving the same issue; B2 used **9.76% fewer API tokens** than Raw. We do **not** claim improved issue solve rate, noninferiority, or overall superiority over other papers. Public source files, hashes, and an executable Kaggle Notebook permit CPU-only verification of the resource.

---

## 2. Introduction: What Is Being Verified?

A local SWE agent must interpret failing tests in a limited context window. Merely cutting logs by line count may remove the assertion and exception details that distinguish a valid fix from an incorrect one. Conventional software integrity checks can also be circular if both the compressor and its validator use the same flawed recognition logic.

Our research question is therefore deliberately narrow: **Can a low-cost resource reduce pytest log volume while independently detecting loss of a defined set of failure evidence, including under unexpected CI formatting?** Our proposed guard uses independent normalization and fails open to the original log on ambiguous input. We evaluate preserved marker multiplicities and compressed bytes separately from language-model repair success. AST slicing and Python `compile()` are conventional companion components, not our claim of standalone novelty. We do not measure GPU runtime acceleration here.

---

## 3. Related Work and Positioning Against Prior Art

Related SWE research:
- [**Agentless** (Xia et al., 2024)](https://arxiv.org/abs/2407.01489): localization, repair, and validation.
- [**SWE-agent** (Yang et al., 2024)](https://arxiv.org/abs/2405.15793): tool-based interactive coding.
- [**RepoCoder** (Zhang et al., 2023)](https://aclanthology.org/2023.emnlp-main.151/): cross-file retrieval and repository context.

**E4B transfer check (distinct module):** On 90 reserved SWE-bench Lite cases, a deterministic file reranker of Maroof's released Gemma E4B candidates achieved File@1 **51/90**, versus **49/90** for the original ordering, with zero additional model calls (exact paired McNemar $p=0.6875$). This non-significant result concerns file localization, **not** traceback compression or SWE issue resolution. [Frozen protocol, code, and paired outcomes](https://github.com/msingatullin/gemma-4-developer-agent/tree/main/paper/peer_head2head).

### Supporting Deterministic Components (Not Individually Novel)

Our suite adds a **deterministic, zero-inference verification layer**:
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

### Additional CPU Ablations and Scope

The original ablation also measured real pytest verbose and short outputs: **62/62** and **55/55** selected items preserved by the original compressor on those fixtures, compared with **14/62** for a 35-line tail cap in the verbose fixture. These cases are distinct from the eleven authentic upstream logs and the adversarial format tests in Section 6.3. CPU microbenchmark timings are not end-to-end agent speedups.

---

## 5. End-to-End Empirical Validation with Real Gemma 4 (31B QAT) Inference and Containerized Execution

To validate whether deterministic traceback compression translates into measurable prompt savings and robust defect resolution without degrading reasoning performance, we conducted a protocol-defined end-to-end empirical study using live model inference and sandboxed test execution. The published frozen artifacts identify the task corpus and evaluation conditions, but we do not treat the early study as independently time-verified preregistration without a matching pre-result commit.

### 5.1 Experimental Protocol and Task Corpus
The benchmark corpus comprises 15 synthetic Python defect reproduction tasks directly modeled after canonical bug patterns in major open-source ecosystems (Flask, Requests, Click, Jinja2, Urllib3, Rich, Pluggy, Marshmallow, Pydantic, Attrs, ItsDangerous, Werkzeug, PyTest). Each task includes a buggy implementation, ground-truth metadata, and an executable pytest test suite.

We tested four trace presentation variants across two configured seed settings ($S \in \{42, 100\}$) with greedy decoding, giving $15 \times 4 \times 2 = 120$ recorded model calls. Repeated seeds are not independent tasks; task ID remains the statistical resampling unit:
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

AST-guided compression reduces the volume of traceback characters fed to Gemma 4 by **56.86%** (2,314 chars down to 998 chars), driving an overall **31.5% reduction in total API tokens** (1,158 down to 793 tokens per inference call).

### 5.3 Diagnostic Accuracy and Post-Hoc Error Taxonomy
Diagnostic reasoning was evaluated across all 120 responses:
- **Defect Localization Pass Rate:** **100.0%** (30/30) across all four variants (`A_raw`, `B_compressed`, `C_tail35`, `D_no_trace`). Gemma 4 accurately localized the canonical defective symbol in 120/120 calls.
- **Pre-Flight Static Syntax Pass Rate:** **100.0%** (30/30) across all variants. Zero syntax errors were introduced by the model.
- **Objective Root Cause Pass Rate:** **90.0%** (27/30) for `A_raw`, **86.7%** (26/30) for `B_compressed`, **93.3%** (28/30) for `C_tail35`, and **86.7%** (26/30) for `D_no_trace`. Paired delta between compressed and raw traces is $\Delta = -3.33\%$ (95% bootstrap CI: $[-10.0\%, 0.0\%]$, permutation $p = 1.0000$).

A post-hoc taxonomy classified 13 diagnostic misclassifications: 3 lexical wording differences, 8 competing-facet prioritizations, and 2 scope overgeneralizations. These exploratory labels do not alter the primary scores; the row-level taxonomy is publicly archived in the linked GitHub experiment results.

### 5.4 Containerized Patch Test Pass Rates and Hypothesis Testing
To measure whether proposed candidate patches actually resolve defects without breaking existing behavior, all 120 generated patches were executed in an isolated, unprivileged container sandbox (`gemma4-eval-sandbox:latest`) configured with `--network none`, `--cap-drop ALL`, `--user 1000:1000`, 512MB RAM, 1.0 CPU core, and read-only host directory mounts.

| Variant | Description | Total Calls | Passed Tests | Pass Rate (%) | Std Error | 95% Bootstrap CI |
|---|---|---|---|---|---|---|
| **`A_raw`** | Native uncompressed traceback | 30 | 30 | **100.0%** | 0.00% | [100.0%, 100.0%] |
| **`B_compressed`** | AST compressor v1 (original planned variant) | 30 | 25 | **83.3%** | 6.80% | [63.3%, 100.0%] |
| **`B2_assertion_aware`** | **AST compressor v2 (Exploratory)** | **30** | **29** | **96.7%** | **3.28%** | **[86.7%, 100.0%]** |
| **`C_tail35`** | Tail 35-line truncation baseline | 30 | 30 | **100.0%** | 0.00% | [100.0%, 100.0%] |
| **`D_no_trace`** | Zero traceback (Exception text only) | 30 | 22 | **73.3%** | 8.07% | [46.7%, 93.3%] |

#### Paired Hypothesis Testing (Task-Clustered Unit):
- `delta_B_minus_A` (`B_compressed` vs `A_raw`): Observed $\Delta = -16.67\%$, 95% Bootstrap CI: $[-36.7\%, 0.0\%]$, permutation $p = 0.2539$.
- `delta_B_minus_C` (`B_compressed` vs `C_tail35`): Observed $\Delta = -16.67\%$, 95% Bootstrap CI: $[-36.7\%, 0.0\%]$, permutation $p = 0.2539$.
- `delta_B_minus_D` (`B_compressed` vs `D_no_trace`): Observed $\Delta = +10.00\%$, 95% Bootstrap CI: $[-6.7\%, +30.0\%]$, permutation $p = 0.5053$.
- `delta_B2_minus_A` (`B2_assertion_aware` vs `A_raw`): Observed $\Delta = -3.33\%$, 95% Bootstrap CI: $[-10.0\%, 0.0\%]$, permutation $p = 1.0000$.
- `delta_B2_minus_B` (`B2_assertion_aware` vs `B_compressed`): Observed $\Delta = +13.33\%$, 95% Bootstrap CI: $[-3.3\%, +33.3\%]$, permutation $p = 0.3768$.

### 5.5 Scientific Rigor and Exploratory B2 Refinement
In paired testing, the observed difference between AST-compressed and raw tracebacks ($\Delta = -16.67\%$, $p = 0.2539$) does not achieve statistical significance at $\alpha = 0.05$. However, **we explicitly caution that failure to reject the null hypothesis ($p \ge 0.05$) does NOT establish proven functional equivalence**.

Detailed inspection of the failure logs revealed the exact operational mechanism: in `task_04` (`requests_socket_error`) and `task_13` (`itsdangerous_expired`), `B_compressed` dropped `with pytest.raises(..., match=...)` context lines because they lacked strict `E ` or `> ` prefixes. Gemma 4 raised the target exception class, but without the exact string enforced by regex match checks. In `task_15` (`pytest_approx_none`), dropping adjacent assertion lines caused the model to handle `None` for only one argument position.

To test whether preserving assertion context repairs this degradation, we executed an exploratory benchmark: **`B2_assertion_aware`** (30 new live calls to Gemma 4 31B across the 15 tasks and two seeds). Crucially, this evaluation is explicitly designated as **post-hoc exploratory** (developed after failure inspection). `B2_assertion_aware` recovered **96.7% Pass Rate** (29/30 passed; tasks 04, 13, and 15 all passed 2/2) while delivering a **39.05% reduction in total API tokens** (706.0 tokens/call vs 1,158.3 for raw), suggesting a useful post-hoc trade-off on synthetic tasks, but not establishing noninferiority to raw traces or generalization to authentic upstream issues.

### 5.6 Authentic Upstream Gemma 4 Pilot (November 11, 2026)
The 150-call study above concerns **synthetic** tasks. Separately, five authentic upstream issues (Flask ×3, Requests ×2) received **15 genuine Gemma 4 31B responses** across A_raw, B2_assertion_aware and C_tail35. Frozen prompt hashes were verified; isolated CPU evaluation completed without harness errors.

| Variant | Resolved | Total API tokens |
| --- | ---: | ---: |
| A_raw | **1/5** | 41,013 |
| B2_assertion_aware | **1/5** | 37,009 |
| C_tail35 | **1/5** | 40,036 |

All variants solved **the same issue**. B2 reduced observed tokens by 9.8%, **without improved resolution**. Four of these five upstream issue IDs (Flask #4045/#4992 and Requests #1963/#2148) were also inspirations for the synthetic corpus; this weakens independence of task selection, though it is not evidence of gold-patch leakage. Five issues cannot establish noninferiority or broad generalization. Later post-hoc patch-application/feedback experiments on these **same issues** reached A=3/5, B2=3/5, C=2/5 under different additional procedures; they are not a new unbiased holdout or evidence that B2 improves repair. [Scope and provenance](https://github.com/msingatullin/gemma-4-developer-agent/blob/main/paper/COMPETITIVE_EVIDENCE_AUDIT_20261111.md). Gold-reference harness controls passed 5/5 RED→GREEN, 155 P2P tests, 12/12 evaluator checks and 39/39 unit tests; these are **not model successes**. [Independent result/provenance](https://github.com/msingatullin/gemma-4-developer-agent/blob/main/paper/STATUS.md). Raw responses remain private.

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
This rejects syntactically malformed source before a test run (38.2 µs mean in our microbenchmark), **not** all unproductive container executions or semantic failures.

### 6.2 Context Window Stability and Attention Mechanics
Hybrid attention makes unnecessary file and traceback text costly. Deterministic slicing and evidence-preserving compression reduce that overhead without additional model inference.

### 6.3 Multi-Format Assertion Preservation
Traceback filtering isolates failing blocks and collapses stdout noise while preserving failure headers, assertion sites (`> assert ...`), assertion details (`E ...`), and multiline diff frames. We tested the unchanged compressor on **11 genuine failing pytest logs from eight repositories**. Three additional cases (Xarray, Pylint, SymPy) were [frozen before this run](https://github.com/msingatullin/gemma-4-developer-agent/blob/main/paper/e2e_gemma_experiment/real_repo_sample/UNSEEN_3REPO_PRECOMMIT_20261111.md) and verified RED→GREEN; two IDs overlapped a parallel pre-registration. On this new holdout, B2 retained all selected diagnostic/header/summary evidence **3/3** against `head35`/`tail35` **0/3**, reducing bytes **82.15%**. Across all 11, B2 retained evidence **11/11** versus **2/11** for each truncation baseline, at **72.01%** byte reduction. This supports diagnostic robustness, **not solve-rate superiority**. [Logs and baselines](https://github.com/msingatullin/gemma-4-developer-agent/tree/main/paper/e2e_gemma_experiment/real_repo_sample). Independent [integrity certificates](https://github.com/msingatullin/gemma-4-developer-agent/tree/main/paper/verification_certificate) verify source/output SHA-256 and exact selected-marker multiplicities: **11/11 certified**, **165/165 adversarial corruptions detected** (software checks, not semantic equivalence).

A subsequent [format-robustness audit](https://github.com/msingatullin/gemma-4-developer-agent/tree/main/paper/robustness_challenge) exposed **10/88 false passes** by the original ANSI-unaware certificate on synthetically recolored real logs. An optional fail-open guard repaired these (**88/88 marker checks; 704/704 tampering controls rejected**) while preserving all 11 original outputs byte-for-byte. It increases raw-log fallback decisions from **23 to 33** across the 88 synthetic cases: safety may reduce compression when formatting is ambiguous. These variants are synthetic, not independent software bugs; the certificate verifies selected markers and consistency, not complete meaning or source authenticity.


---

## 7. Artifacts & Open-Source Availability

### Independent reproduction (Python standard library; CPU-only)

From a clean public checkout, with no model inference or secrets:

```bash
git clone https://github.com/msingatullin/gemma-4-developer-agent.git
cd gemma-4-developer-agent
python3 paper/robustness_challenge/run_chaos_experiment.py
python3 paper/robustness_challenge/validate_robust_guard.py
```

Expected summary: old **78/88** with **10 false certificate PASS**; corrected guard **88/88**, tamper checks **704/704**, original 11 logs byte-identical, **72.01%** saved. The [versioned certificate runner](https://github.com/msingatullin/gemma-4-developer-agent/tree/main/paper/verification_certificate) provides separate **11/11** and **165/165** checks. The authentic Gemma model responses and private CPU-scoring JSONL are not part of the public resource, limiting independent replay of the five-issue pilot.

Open-source **Apache 2.0** artifacts:
- **Public Executable Notebook:** [msingatullin/ast-guided-loops-verification-for-gemma-4](https://www.kaggle.com/code/msingatullin/ast-guided-loops-verification-for-gemma-4)
- **Open-Source Repository:** [github.com/msingatullin/gemma-4-developer-agent](https://github.com/msingatullin/gemma-4-developer-agent)
- **120 Real Model Inferences:** [`paper/e2e_gemma_experiment/real_run_20261108/real_experiment_checkpoint.jsonl`](https://github.com/msingatullin/gemma-4-developer-agent/blob/main/paper/e2e_gemma_experiment/real_run_20261108/real_experiment_checkpoint.jsonl)
- **Exploratory B2 Benchmark (30 calls):** [`paper/e2e_gemma_experiment/real_run_20261108/real_b2_experiment_checkpoint.jsonl`](https://github.com/msingatullin/gemma-4-developer-agent/blob/main/paper/e2e_gemma_experiment/real_run_20261108/real_b2_experiment_checkpoint.jsonl)
- **Containerized Patch Execution Results:** [`paper/e2e_gemma_experiment/real_run_20261108/real_patch_execution_results.jsonl`](https://github.com/msingatullin/gemma-4-developer-agent/blob/main/paper/e2e_gemma_experiment/real_run_20261108/real_patch_execution_results.jsonl)
- **Exploratory B2 Container Results:** [`paper/e2e_gemma_experiment/real_run_20261108/real_b2_patch_execution_results.jsonl`](https://github.com/msingatullin/gemma-4-developer-agent/blob/main/paper/e2e_gemma_experiment/real_run_20261108/real_b2_patch_execution_results.jsonl)
- **Statistical Analysis & Clustered Bootstrap:** [`paper/e2e_gemma_experiment/real_run_20261108/real_patch_execution_analysis.json`](https://github.com/msingatullin/gemma-4-developer-agent/blob/main/paper/e2e_gemma_experiment/real_run_20261108/real_patch_execution_analysis.json)
- **Post-Hoc Diagnostic Error Taxonomy:** [`paper/e2e_gemma_experiment/real_run_20261108/blinded_diagnostic_audit.json`](https://github.com/msingatullin/gemma-4-developer-agent/blob/main/paper/e2e_gemma_experiment/real_run_20261108/blinded_diagnostic_audit.json)
- **License:** Apache 2.0 (`LICENSE` in repository root)
