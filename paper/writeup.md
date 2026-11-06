# AST-Guided Verification Suite: Deterministic Code Slicing and Pre-Flight Validation for Local SWE Agents on Gemma 4

**Author:** Mikhail Singatullin (`msingatullin` / Team `Михаил`)  
**Competition Track:** [Google - The Gemma 4 Developer Agent Paper Track](https://www.kaggle.com/competitions/gemma-4-developer-agent-paper)  
**Primary Award Nomination:** Overall Best Paper ($15,000) (Secondary Nominations: Best New Resource / Best New Application)  
**Public Executable Notebook:** [Kaggle Notebook](https://www.kaggle.com/code/msingatullin/ast-guided-loops-verification-for-gemma-4)  
**License:** Apache 2.0  

---

## 1. Abstract & Executive Summary

Deploying autonomous software engineering (SWE) agents with quantized large language models—such as `google/gemma-4-31B-it-qat-w4a16-ct`—on edge-tier single-accelerator developer workstations (1× NVIDIA L4 24GB VRAM) reveals severe operational bottlenecks. Full-file reading across multi-thousand-line modules rapidly inflates prompt context, while unvalidated patches waste valuable container execution time on trivial syntax failures. Furthermore, multi-test failure logs flood context with hundreds of lines of irrelevant environment banners and captured stdout buffers.

This work introduces the **AST-Guided Verification Suite**, an open-source, deterministic evaluation and execution framework engineered specifically for local SWE agents. The suite couples sub-millisecond abstract syntax tree (`ast.NodeVisitor`) symbol indexing, a native pre-flight syntax and compilation gate (`compile(mode='exec')`), and a multi-format, multi-failure assertion-preserving traceback compression engine that eliminates captured stdout pollution while strictly retaining diagnostic root causes across standard pytest formats (`--tb=auto`, `--tb=long`, `--tb=short`), native tracebacks (`--tb=native`), and standalone Python exception traces. Tested on the `ASTVerificationBenchmark` (a curated microbenchmark of 31 representative defect and diagnostic scenarios across FastAPI, Flask, Click, SymPy, Scikit-Learn, Django, and PyTest with strict ground-truth line, exception, and line-anchored multiline assertion oracles verified by hard executable assertions), the suite achieves an average **44.6% reduction in prompt token consumption on symbol-sliced modules** (reducing targeted context from 65.8 to 36.0 estimated tokens per extracted method), a **30.6% corpus-level volume reduction on traceback logs** (892 to 619 estimated tokens; 30.3% mean per-log reduction) while strictly preserving 100% of diagnostic root causes, line pointers, and multiline assertion details across single- and multi-failure parametrized test runs, and intercepts 100% of syntactically invalid patches in under 0.1 milliseconds (47.2 µs cloud / 58.5 µs local mean latency). The microbenchmark evaluates the deterministic components in isolation using strict ground-truth oracles verified by hard executable assertions, providing empirical foundations for autonomous SWE agent integration without external network or GPU dependencies.

---

## 2. Operating Constraints and Gemma 4 (31B QAT) Attention Mechanics

### Hardware Environments: Official Competition Runner vs. Edge Developer Deployments
- **Official Competition Cluster:** As specified in `HARNESS_README.md` §3.1, the official evaluation environment operates on **4 × NVIDIA L4 GPUs (96 GB GDDR6 total) with Tensor Parallelism (TP=4)**, distributing model weights and KV cache across four accelerators.
- **Edge Developer Workstation Deployment:** Individual researchers, private on-premise developers, and local continuous integration (CI) runners frequently operate on a **single edge accelerator (1 × NVIDIA L4 24GB or local workstation GPU)** without multi-GPU tensor-parallel orchestration. In this single-accelerator setting, memory headroom is strictly limited, making deterministic context management imperative.

### Architectural Specifications of `google/gemma-4-31B-it-qat-w4a16-ct`:
- **Weights:** INT4 pack-quantized weights (group size 32, FP16 activations), occupying $\approx 18.24$ GiB VRAM.
- **Total Transformer Layers:** $L = 60$.
- **Hybrid Attention:** 50 sliding-window attention layers (sliding window $W = 1024$ tokens, $H_{kv} = 16$ key-value heads, head dimension $d_k = 256$) and 10 full-attention global layers (every 6th layer, $H_{kv,\text{global}} = 4$, $d_{k,\text{global}} = 512$).
- **Query Heads:** $H_q = 32$.

### Analytical Analysis of KV Cache Growth Across Hybrid Attention Layers

The memory and latency values below are analytical estimates under the stated cache-layout, storage-precision, resident-memory and bandwidth assumptions. They are not GPU measurements and do not establish the actual memory headroom or token latency of a serving runtime.

For a context sequence of $T$ tokens stored in FP16 ($2$ bytes/scalar), memory allocation scales differently across sliding and global layers:

1. **Sliding-Window Attention Layers (50 layers):**
   Because sliding layers discard attention history beyond the active window $W = 1024$, their KV footprint saturates:
   $$M_{\text{KV,sliding}}(T) = 50 \times 2 \times H_{kv} \times d_k \times \min(T, 1024) \times 2 = 819,200 \times \min(T, 1024) \text{ bytes}$$
   When $T \ge 1024$, sliding KV memory is strictly capped at $838,860,800$ bytes $\approx 0.839$ GB ($0.781$ GiB).

2. **Global Full-Attention Layers (10 layers):**
   The 10 global layers maintain attention across the entire context depth $T$:
   $$M_{\text{KV,global}}(T) = 10 \times 2 \times H_{kv,\text{global}} \times d_{k,\text{global}} \times T \times 2 = 81,920 \times T \text{ bytes} = 80.0 \times T \text{ KB}$$

3. **Total KV Memory Footprint and Single-L4 Roofline Latency:**
   $$M_{\text{KV,total}}(T) = M_{\text{KV,sliding}}(T) + M_{\text{KV,global}}(T)$$
   - At $T = 1,024$ tokens: Total KV $= 0.859$ GiB. Total VRAM $= 19.15$ GiB ($4.85$ GiB safety headroom on 1× L4).
   - At $T = 8,192$ tokens (Deterministic AST bounded scope): Total KV $= 1.406$ GiB. Total VRAM $= 19.73$ GiB ($4.27$ GiB headroom).
   - At $T = 24,576$ tokens (Unconstrained multi-file exploration): Total KV $= 2.656$ GiB. Total VRAM $= 21.06$ GiB ($2.94$ GiB headroom).

Under the memory-bound autoregressive decoding regime (operational intensity $I \approx 1$ FLOP/byte), per-token generation latency follows:
$$\tau(T) = \frac{(M_{\text{static}} + M_{\text{KV}}(T)) \times 1024^3}{\text{BW}_{\text{eff}} \times 10^9} \times 1000$$
Converting binary GiB to bytes and decimal memory bandwidth ($242.0 \times 10^9$ bytes/sec) yields a modeled per-token generation latency of **87.2 ms/token at 8,192 tokens** versus **92.7 ms/token at 24,576 tokens** ($+6.36\%$ latency growth), while shrinking buffer headroom from 4.27 GiB to under 2.94 GiB on single-accelerator setups.

---

## 3. Related Work and Positioning Against Prior Art

Autonomous software engineering agents have advanced rapidly across benchmark evaluations such as SWE-bench:

- **Hierarchical Inspection and Repair (`Agentless`):**
  Xia et al. (2024) demonstrated that complex multi-agent architectures often overcomplicate problem-solving, proposing a streamlined three-phase pipeline: localization $\rightarrow$ patch repair $\rightarrow$ patch validation. However, `Agentless` relies on multiple high-temperature LLM queries against frontier commercial models (GPT-4o, Claude 3.5 Sonnet) and multi-step file search heuristics. In an edge competition environment with zero external API access and an INT4 quantized local model, running multiple LLM-based filtering steps introduces fatal inference latency.

- **Iterative ReAct Loops (`SWE-agent`):**
  Yang et al. (2024) introduced dedicated Agent-Computer Interfaces (ACI) with file navigation commands (`search_file`, `scroll_down`). While effective with unconstrained context windows, these interfaces prompt local quantized models to perform continuous conversational reading, saturating context with redundant file bodies.

- **Code Graphs and Semantic Retrieval (`RepoCoder`):**
  Zhang et al. (2023) utilized cross-file semantic similarity and retrieval-augmented generation (RAG) for repository context. Building full repository code graphs on runtime containers requires heavy AST parsing and vector indexing libraries that frequently timeout during test suite execution.

### Architectural Novelty: The Deterministic Zero-Inference Stance

In contrast to prior art, this suite introduces a **zero-inference, deterministic verification layer**:
1. **Zero LLM Overhead for Localization:** Symbol discovery relies entirely on Python's built-in `ast` visitor, extracting precise function and class line ranges in sub-millisecond latency without consuming model generation tokens.
2. **Native Pre-Flight Compilation Gate:** Catches syntax regressions, top-level return anomalies, and indentation corruptions in under 0.1 ms using Python's standard `compile(mode='exec')` before initiating expensive container test suites.
3. **Multi-Format Traceback Compression:** Strips hundreds of lines of pytest session banners and captured stdout spam while strictly preserving all individual failing assertion lines (`E ...`), line pointers, and multiline exception messages across standard pytest (`--tb=auto`, `--tb=long`, `--tb=short`), native tracebacks (`--tb=native`), and standalone Python exception traces.

---

## 4. Deterministic Component Evaluation: Executable Benchmark with Hardened Oracles

We evaluated the deterministic components across the `ASTVerificationBenchmark`, a curated microbenchmark of 31 representative defect and context scenarios with strict ground-truth line, exception, and multiline assertion oracles enforced by executable assertions:

| Category | Tasks | Mean Cloud CPU Latency (v13, µs) | Strict Oracle Accuracy | Mean Raw Tokens (Est.) | Mean Processed Tokens | Mean Token Reduction |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Code Slicing** | 8 | 302.6 µs | 100.0% (Exact bounds & content) | 65.8 | 36.0 | **44.6%** |
| **Syntax Interception** | 10 | 47.2 µs | 100.0% (Syntax catches) | 6.8 | 6.8 | Pre-flight catch (100%) |
| **Traceback Compression** | 8 | 74.5 µs | 100.0% (All details preserved) | 111.5 | 77.4 | **30.6%** (Corpus aggregate) |
| **Valid Clean Patches** | 5 | 93.9 µs | 100.0% (Zero false rejections) | 15.2 | 15.2 | Gate pass (100%) |

### Hardened Oracles and Methodological Rigor
1. **Slicing Oracle Hardening:** In addition to validating expected start and end line coordinates (`s_line == expected_start and e_line == expected_end`), the oracle validates that the extracted slice is non-empty, contains the target symbol identifier, and matches the expected source lines (modulo normalized whitespace). Fault-injection tests confirming that empty slices with correct coordinates fail the oracle are verified in the test suite.
2. **Line-Anchored Traceback Oracle:** In addition to verifying primary failure markers and `FAILED` summary lines, multiline exception fixtures (such as `TRC-08`) require that all 30 intermediate assertion detail lines (`detail-0` through `detail-29`) and boundary markers match via line-anchored regex patterns. This prevents substring false passes (such as `detail-1` matching inside `detail-10`) and ensures that the loss of any single diagnostic line triggers immediate oracle rejection.
3. **Multi-Format Support & Safe Fallback:** The compressor supports standard pytest formats (`--tb=auto`, `--tb=long`, `--tb=short`), native tracebacks (`--tb=native`), standalone Python tracebacks, and provides an untruncated safe fallback that returns filtered logs without arbitrary line limits if a log cannot be partitioned into recognized failure blocks, ensuring zero loss of terminal exception diagnostics.
4. **Sub-Millisecond Execution:** All four verification categories execute in aggregate under 6.1 ms on CPU for all 31 tasks combined (3.96 ms on Kaggle cloud CPU in v13).
5. **Certified Test Gate:** The benchmark execution is permanently certified in the public notebook via an active hard assertion (`assert len(failed_cases) == 0`) that terminates execution with an exception if any ground-truth oracle fails.

---

## 5. SWE Agent Integration Architecture & Operational Design Principles

The microbenchmark in Section 4 evaluates the deterministic CPU-based components in isolation. Full end-to-end multi-turn agent evaluations with live Gemma model inference remain prospective future work. In this section, we present the integration architecture and design principles for embedding these verified components into an autonomous agent loop.

### 5.1 Native Pre-Flight Compiler Gate
When a candidate Python module contains a syntax error, a pre-flight compiler gate can reject it before the project test command is dispatched. Potentially avoided work includes sandbox invocation, test-runner startup and handling the resulting test traceback. These costs are unmeasured in this study; no numerical container or test-runner timing is claimed. A persistent sandbox may incur no per-attempt container startup cost. The net effect, including model correction turns, must be measured in the paired E2E study.

The native pre-flight compiler gate invokes Python's compilation pipeline (`compile(patch_code, '<candidate_patch>', 'exec')`) before any sandbox command is dispatched. If syntax or indentation anomalies exist, the gate intercepts the patch in under 0.1 ms (47.2 µs cloud / 58.5 µs local mean latency) and returns an actionable diagnostic feedback message directly to the model. The intended benefit is avoiding test execution on syntactically invalid modules; the effect on total latency, token use and task resolution has not been measured.

### 5.2 Context Window Stability and Attention Mechanics
The quantized `gemma-4-31B-it-qat-w4a16-ct` architecture utilizes hybrid attention, comprising 50 sliding-window layers with an effective window of $W = 1024$ tokens and 10 full-attention layers. Unconstrained file navigation—where agents read complete multi-thousand-line modules—rapidly expands context depth. In sliding-window attention layers, this expansion causes the earliest instructions and task definitions to slide outside the active window, degrading attention focus and causing reasoning drift.

Deploying AST-guided symbol slicing (`ast_indexer`) targets function and class definitions (yielding 44.6% mean prompt token reduction on benchmark symbols). Combined with traceback compression (30.6% corpus volume reduction), these tools are designed to substantially mitigate context inflation. However, because full agent sessions accumulate multi-turn dialog history and symbol slicing does not impose a global token ceiling, their empirical impact on multi-turn attention stability, memory fragmentation, and overall agent solve rate remains to be established in future end-to-end model evaluations.

### 5.3 Multi-Format Lossless Diagnostic Retention
A primary hazard in log compression is the accidental suppression of critical diagnostic clues. In real pytest environments, test failures frequently produce:
- Multiline exception messages spanning dozens of assertion details.
- Parametrized tests where multiple distinct input fixtures fail with different root causes.
- Plugin-level or framework configuration errors (`plugins: ...`).
- Formats without `E ` prefixes, such as Python's native traceback mode (`--tb=native`) and standalone Python exceptions.

The AST-guided traceback filter employs block-aware parsing. It isolates failing test blocks, collapses captured stdout noise, and strictly preserves:
1. Every failing test header and file location (`.py:line: Error` or `File "...", line ..., in ...`).
2. The failing source code line (`> assert ...`).
3. Every single diagnostic assertion line prefixed with `E ` or `E\t` in standard pytest modes, and the full exception block in native traceback mode.
4. All independent test failure blocks within parametrized suites.
5. Untruncated logs for unrecognized formats without arbitrary line caps.

### 5.4 Deterministic Loop Termination
Autonomous agents frequently suffer from conversational over-generation—continuing to explain, apologize, or query after a task has been successfully solved. The agent system prompt instructs concise single-sentence completion upon resolving all failing tests, and the integration harness can enforce termination via deterministic test exit-code inspection, halting the loop immediately upon test suite pass.

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
