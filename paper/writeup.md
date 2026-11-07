# AST-Guided Verification Suite: Deterministic Code Slicing and Pre-Flight Validation for Local SWE Agents on Gemma 4

**Author:** Mikhail Singatullin (`msingatullin` / Team `Михаил`)  
**Competition Track:** [Google - The Gemma 4 Developer Agent Paper Track](https://www.kaggle.com/competitions/gemma-4-developer-agent-paper)  
**Target Track / Category:** Overall Best Paper / Best New Resource & Application  
**Public Executable Notebook:** [Kaggle Notebook](https://www.kaggle.com/code/msingatullin/ast-guided-loops-verification-for-gemma-4)  
**License:** Apache 2.0  

---

## 1. Abstract & Executive Summary

Deploying autonomous software engineering (SWE) agents with quantized large language models—such as `google/gemma-4-31B-it-qat-w4a16-ct`—on edge developer workstations (1× NVIDIA L4 24GB VRAM) exposes severe operational bottlenecks. Full-file reading across multi-thousand-line modules inflates prompt context, while unvalidated patches waste execution time on syntax failures. Furthermore, multi-test failure logs flood context with environment banners and captured stdout buffers.

This work introduces the **AST-Guided Verification Suite**, an open-source, deterministic evaluation and execution framework engineered for local SWE agents. The suite couples sub-millisecond abstract syntax tree (`ast.NodeVisitor`) symbol indexing, a native pre-flight syntax gate (`compile(mode='exec')`), and a multi-format assertion-preserving traceback compression engine that eliminates stdout pollution while strictly retaining diagnostic root causes across standard pytest formats (`--tb=auto`, `--tb=long`, `--tb=short`), native tracebacks (`--tb=native`), and standalone Python exceptions. Evaluated on the `ASTVerificationBenchmark` (31 curated defect scenarios across FastAPI, Flask, Click, SymPy, Scikit-Learn, Django, and PyTest with ground-truth line, exception, and line-anchored multiline assertion oracles), the suite achieves an average **44.6% reduction in prompt token consumption on symbol-sliced modules** (65.8 to 36.0 estimated tokens per method), a **30.6% corpus-level volume reduction on traceback logs** (892 to 619 estimated tokens) while strictly preserving 100% of diagnostic root causes, line pointers, and multiline assertion details, and intercepts 100% of syntactically invalid patches in under 0.1 milliseconds (38.2 µs cloud / 58.0 µs local mean latency). All reported token consumption metrics are heuristic estimates computed via integer division `len(text) // 4` (matching BPE subword approximations). The microbenchmark evaluates deterministic components in isolation using strict executable oracles, establishing empirical foundations for autonomous SWE agent integration without external network or GPU dependencies.

---

## 2. Operating Constraints and Gemma 4 (31B QAT) Attention Mechanics

### Hardware Environments: Official Competition Runner vs. Edge Developer Deployments
- **Official Competition Cluster:** 4 × NVIDIA L4 GPUs (96 GB GDDR6 total) with Tensor Parallelism (TP=4), distributing model weights and KV cache across four accelerators.
- **Edge Developer Workstations:** Single accelerator (1 × NVIDIA L4 24GB or local workstation GPU) without multi-GPU orchestration. Memory headroom is strictly constrained, making deterministic context management imperative.

### Architectural Specifications of `google/gemma-4-31B-it-qat-w4a16-ct`:
- **Weights:** INT4 pack-quantized weights (group size 32, FP16 activations), occupying $\approx 18.24$ GiB VRAM.
- **Total Transformer Layers:** $L = 60$.
- **Hybrid Attention:** 50 sliding-window attention layers (sliding window $W = 1024$ tokens, $H_{kv} = 16$ key-value heads, head dimension $d_k = 256$) and 10 full-attention global layers (every 6th layer, $H_{kv,\text{global}} = 4$, $d_{k,\text{global}} = 512$).
- **Query Heads:** $H_q = 32$.

### Analytical Analysis of KV Cache Growth Across Hybrid Attention Layers

The KV cache memory footprints and Roofline decoding latencies in this section are analytical calculations based on theoretical memory bandwidth ($242.0 \times 10^9$ bytes/sec for NVIDIA L4) and INT4/FP16 cache layout under stated resident-memory assumptions; they are not empirical GPU runtime measurements and do not establish the actual memory headroom or token latency of a live serving runtime.

For a context sequence of $T$ tokens stored in FP16 ($2$ bytes/scalar), memory allocation scales across sliding and global layers:

1. **Sliding-Window Attention Layers (50 layers):**
   Sliding layers discard attention history beyond the active window $W = 1024$:
   $$M_{\text{KV,sliding}}(T) = 50 \times 2 \times H_{kv} \times d_k \times \min(T, 1024) \times 2 = 819,200 \times \min(T, 1024) \text{ bytes}$$
   When $T \ge 1024$, sliding KV memory saturates at $838,860,800$ bytes $\approx 0.839$ GB ($0.781$ GiB).

2. **Global Full-Attention Layers (10 layers):**
   The 10 global layers maintain attention across full depth $T$:
   $$M_{\text{KV,global}}(T) = 10 \times 2 \times H_{kv,\text{global}} \times d_{k,\text{global}} \times T \times 2 = 81,920 \times T \text{ bytes} = 80.0 \times T \text{ KB}$$

3. **Total KV Memory Footprint and Single-L4 Roofline Latency:**
   $$M_{\text{KV,total}}(T) = M_{\text{KV,sliding}}(T) + M_{\text{KV,global}}(T)$$
   - At $T = 1,024$ tokens: Total KV $= 0.859$ GiB. Total VRAM $= 19.15$ GiB ($4.85$ GiB headroom on 1× L4).
   - At $T = 8,192$ tokens (Deterministic AST scope): Total KV $= 1.406$ GiB. Total VRAM $= 19.73$ GiB ($4.27$ GiB headroom).
   - At $T = 24,576$ tokens (Unconstrained file exploration): Total KV $= 2.656$ GiB. Total VRAM $= 21.06$ GiB ($2.94$ GiB headroom).

Under the memory-bound autoregressive decoding regime ($I \approx 1$ FLOP/byte), per-token generation latency follows:
$$\tau(T) = \frac{(M_{\text{static}} + M_{\text{KV}}(T)) \times 1024^3}{\text{BW}_{\text{eff}} \times 10^9} \times 1000$$
At bandwidth $242.0 \times 10^9$ bytes/sec, modeled latency is **87.2 ms/token at 8,192 tokens** versus **92.7 ms/token at 24,576 tokens** ($+6.36\%$ latency growth), while shrinking buffer headroom from 4.27 GiB to 2.94 GiB on single-accelerator setups.

---

## 3. Related Work and Positioning Against Prior Art

Autonomous SWE agents have advanced rapidly across benchmarks like SWE-bench:

- **Hierarchical Inspection and Repair (`Agentless`):**
  Xia et al. (2024) proposed a three-phase pipeline: localization $\rightarrow$ patch repair $\rightarrow$ patch validation. However, `Agentless` relies on multiple high-temperature LLM queries against frontier commercial models (GPT-4o, Claude 3.5 Sonnet) and multi-step file search heuristics. In an edge environment with zero external API access and an INT4 quantized local model, running multiple LLM filtering steps introduces fatal inference latency.

- **Iterative ReAct Loops (`SWE-agent`):**
  Yang et al. (2024) introduced Agent-Computer Interfaces (ACI) with commands like `search_file` and `scroll_down`. While effective with large context windows, these interfaces prompt local quantized models to perform continuous conversational reading, saturating context with redundant file bodies.

- **Code Graphs and Semantic Retrieval (`RepoCoder`):**
  Zhang et al. (2023) used cross-file semantic similarity and RAG for repository context. Building full repository code graphs on runtime containers requires heavy AST parsing and vector indexing libraries that frequently timeout during test suite execution.

### Architectural Novelty: The Deterministic Zero-Inference Stance

In contrast to prior art, this suite introduces a **zero-inference, deterministic verification layer**:
1. **Zero LLM Overhead for Localization:** Symbol discovery relies entirely on Python's built-in `ast` visitor, extracting precise function and class line ranges in sub-millisecond latency without consuming model generation tokens.
2. **Native Pre-Flight Compilation Gate:** Catches syntax regressions, top-level return anomalies, and indentation corruptions in under 0.1 ms using Python's standard `compile(mode='exec')` before initiating container test suites.
3. **Multi-Format Traceback Compression:** Strips hundreds of lines of pytest session banners and captured stdout spam while strictly preserving all individual failing assertion lines (`E ...`), line pointers, and multiline exception messages across standard pytest (`--tb=auto`, `--tb=long`, `--tb=short`), native tracebacks (`--tb=native`), and standalone Python exceptions.

---

## 4. Deterministic Component Evaluation: Executable Benchmark with Hardened Oracles

We evaluated the deterministic components across the `ASTVerificationBenchmark`, a curated microbenchmark of 31 representative defect scenarios with ground-truth line, exception, and multiline assertion oracles enforced by executable assertions:

| Category | Tasks | Mean Cloud CPU Latency (v16, µs) | Strict Oracle Accuracy | Mean Raw Tokens (Est.) | Mean Processed Tokens | Mean Token Reduction |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Code Slicing** | 8 | 235.8 µs | 100.0% (Exact bounds & content) | 65.8 | 36.0 | **44.6%** |
| **Syntax Interception** | 10 | 38.2 µs | 100.0% (Syntax catches) | 6.8 | 6.8 | Pre-flight catch (100%) |
| **Traceback Compression** | 8 | 159.3 µs | 100.0% (All details preserved) | 111.5 | 77.4 | **30.6%** (Corpus aggregate) |
| **Valid Clean Patches** | 5 | 70.2 µs | 100.0% (Zero false rejections) | 15.2 | 15.2 | Gate pass (100%) |

*Note on Token Estimation:* All token quantities reported above are heuristic estimates computed via integer division `len(text) // 4` (matching standard BPE subword approximations); they are not exact Gemma tokenizer outputs.

### Component Ablation Study and Comparison Against Naive Baselines

To evaluate the isolated and synergistic contributions of each verification layer, we conducted an ablation study comparing the framework against standard naive SWE agent patterns:

| Configuration / Mode | Symbol Context Reduction | Traceback Volume Reduction | Syntax Errors Caught Pre-Flight | Diagnostic Assertion Retention | Deterministic Verification Latency (CPU) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Baseline 0: Naive SWE Agent** (Full file read, raw pytest logs, no pre-flight gate) | 0.0% (65.8 tok/fn) | 0.0% (892 tok corpus) | 0% (Escapes to test runner) | 100% (Uncompressed raw) | N/A (No verification layer; passes raw files/logs to test runner) |
| **Ablation 1: AST Slicing Alone** (`ast.NodeVisitor` symbol extraction) | **44.6%** (36.0 tok/fn) | 0.0% (892 tok corpus) | 0% (Escapes to test runner) | 100% (Uncompressed raw) | 235.8 µs |
| **Ablation 2: Syntax Gate Alone** (`compile(mode='exec')` pre-flight) | 0.0% (65.8 tok/fn) | 0.0% (892 tok corpus) | **100%** (38.2 µs catch) | 100% (Uncompressed raw) | 38.2 µs |
| **Ablation 3: Traceback Compression Alone** (Multiline assertion parser) | 0.0% (65.8 tok/fn) | **30.6%** (619 tok corpus) | 0% (Escapes to test runner) | **100%** (Zero diagnostic loss) | 159.3 µs |
| **Full AST-Guided Verification Suite** (All deterministic components active) | **44.6%** | **30.6%** | **100%** | **100%** | **3.893 ms** (All 31 benchmark tasks) |

### Empirical Traceback Validation on Real Pytest Execution Logs

To evaluate the compressor on unmocked execution logs, we benchmarked real test runs executed with `pytest 8.4.2` (`Python 3.12.3`). Crucially, these test runs were generated by executing a purpose-built fixture test suite designed to evaluate compressor failure modes under heavy diagnostic load. The suite collects 8 test items yielding 7 distinct failures and 1 passing control across diverse failure typologies (120 lines of verbose stdout buffer noise, 32-frame multiline assertion diffs, parametrized test instances, and distinct exception types: `AssertionError`, `ValueError`, `KeyError`), rather than organic defect logs from external repositories.

We benchmarked the canonical compressor implementation (`filter_pytest_log`, matching the public Kaggle notebook v16 cell 7):

| Pytest Log Format / Configuration | Raw Volume (Chars / Est. Tokens) | Compressed Volume (Chars / Est. Tokens) | Prompt Volume Reduction | Diagnostic Retention (Categorized) | Processing Latency (CPU) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Standard Verbose (`-v`, `--tb=auto`)** | 21,557 chars / 5,389 tok | **6,068 chars / 1,517 tok** | **71.9%** (72.8% lines) | **100.0%** (62/62 items) | 5.91 ms ± 0.13 ms |
| **Short Traceback (`--tb=short`)** | 18,086 chars / 4,521 tok | **4,509 chars / 1,127 tok** | **75.1%** (75.5% lines) | **100.0%** (55/55 items) | 4.49 ms ± 0.03 ms |
| **Long Traceback (`--tb=long`)** | 20,810 chars / 5,202 tok | **6,068 chars / 1,517 tok** | **70.8%** (72.2% lines) | **100.0%** (62/62 items) | 6.03 ms ± 0.20 ms |
| **Native Traceback (`--tb=native`)** | 40,884 chars / 10,221 tok | 40,884 chars / 10,221 tok | Untruncated safe fallback | **100.0%** (55/55 items) | 0.05 ms ± 0.00 ms |
| **Baseline 1: Naive Tail-Cap (35 lines)** | 21,557 chars / 5,389 tok | 1,873 chars / 468 tok | 91.3% (Heuristic cutoff) | **22.6%** (Drops 48/62 items) | 0.09 ms ± 0.00 ms |
| **Baseline 2: Naive E-Lines Only** | 21,557 chars / 5,389 tok | 2,897 chars / 724 tok | 86.6% (Strips headers/sites) | **62.9%** (Drops 23/62 items) | 0.28 ms ± 0.01 ms |

#### Diagnostic Category Breakdown and Latency Trade-Off

The categorized evaluation reveals the failure modes of naive compressors: **Naive Tail-Capping (35 lines)** achieves 91.3% reduction in 0.09 ms but drops 48 of 62 diagnostic items (retaining only 22.6% overall: 1/7 headers, 1/7 source sites, 0/32 multiline frames, 3/7 root causes) because stdout buffers displace earlier failures. **Naive E-Lines Only** strips all headers, summaries, source sites, and parametrized IDs (0/7 each, 62.9% overall retention) and fails entirely on native tracebacks. In contrast, the **AST-Guided Suite** executes in 4.5–6.0 ms on CPU (<0.1% of a single LLM turn), achieving 71.9% reduction while preserving 100% of all 62 diagnostic items across all categories. On native tracebacks, it activates an untruncated lossless fallback in 0.05 ms. All 8 negative control tests confirm that dropping any diagnostic item causes immediate hard `AssertionError` rejection in the verification oracle.

### Hardened Oracles and Methodological Rigor
1. **Slicing Oracle:** Validates bounds, non-emptiness, target symbol ID, and normalized source lines; empty slices fail.
2. **Line-Anchored Traceback Oracle:** Requires line-anchored regex matching for all intermediate assertion lines, preventing substring false passes.
3. **Multi-Format Safe Fallback:** Supports standard, short, long, native, and standalone Python tracebacks, falling back untruncated if block parsing is ambiguous.
4. **Sub-Millisecond Execution:** Deterministic components execute in 3.893 ms on Kaggle cloud CPU for all 31 benchmark tasks combined.
5. **Certified Test Gate:** Hard assertions (`assert len(failed_cases) == 0`) certify benchmark execution in the public notebook.

---

## 5. SWE Agent Integration Architecture & Operational Design Principles

The microbenchmark in Section 4 evaluates deterministic CPU-based components in isolation; multi-turn agent evaluations with live Gemma model inference remain prospective future work. Here we outline the integration architecture for embedding these verified components into an autonomous agent loop.

### 5.1 Native Pre-Flight Compiler Gate
When a candidate Python module contains a syntax error, a pre-flight compiler gate rejects it before the project test command is dispatched. The gate invokes Python's standard `compile(patch_code, '<candidate_patch>', 'exec')`, intercepting patches in under 0.1 ms (38.2 µs cloud / 58.0 µs local mean latency; 38.176 µs verified on Kaggle cloud v16) and returning actionable diagnostic feedback directly to the model.

### 5.2 Context Window Stability and Attention Mechanics
The quantized `gemma-4-31B-it-qat-w4a16-ct` architecture utilizes hybrid attention (50 sliding-window layers with $W = 1024$ tokens, 10 full-attention layers). Unconstrained file reading rapidly expands context depth, causing early instructions to slide outside the active window and degrading attention focus. AST-guided symbol slicing (`ast_indexer`) targets function and class definitions (44.6% mean prompt token reduction), while traceback compression achieves 30.6% corpus volume reduction. Because full agent sessions accumulate multi-turn dialog history, their empirical impact on multi-turn attention stability and overall agent solve rate remains to be established in future end-to-end model evaluations.

### 5.3 Multi-Format Lossless Diagnostic Retention
To prevent accidental suppression of critical diagnostic clues across multiline assertion diffs, parametrized suites, and native exceptions, the AST-guided traceback filter employs block-aware parsing. It isolates failing test blocks, collapses captured stdout noise, and strictly preserves all failure headers, source code lines (`> assert ...`), assertion lines (`E ...`), and independent test failure blocks within parametrized suites.

### 5.4 Deterministic Loop Termination
Autonomous agents frequently suffer from conversational over-generation upon task completion. The agent system prompt instructs concise single-sentence completion upon resolving all failing tests, and the integration harness enforces termination via deterministic test exit-code inspection, halting the loop immediately upon test suite pass.

### 5.5 Production ADK Specification
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

## 6. Artifacts & Open-Source Availability

All artifacts developed for this project are released under the open-source **Apache 2.0** license:
- **Public Executable Notebook:** [msingatullin/ast-guided-loops-verification-for-gemma-4](https://www.kaggle.com/code/msingatullin/ast-guided-loops-verification-for-gemma-4)
- **Open-Source Repository:** [github.com/msingatullin/gemma-4-developer-agent](https://github.com/msingatullin/gemma-4-developer-agent)
- **License:** Apache 2.0 (`LICENSE` file in repository root)
- **Production ADK Specification:** `agent.yaml`
