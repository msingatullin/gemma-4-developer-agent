# AST-Guided Verification Suite: Deterministic Code Slicing and Pre-Flight Validation for Local SWE Agents on Gemma 4

**Author:** Mikhail Singatullin (`msingatullin` / Team `Михаил`)  
**Competition Track:** [Google - The Gemma 4 Developer Agent Paper Track](https://www.kaggle.com/competitions/gemma-4-developer-agent-paper)  
**Primary Award Nomination:** Best New Resource / Best New Application  
**Public Executable Notebook:** [Kaggle Notebook](https://www.kaggle.com/code/msingatullin/ast-guided-loops-verification-for-gemma-4)  
**License:** Apache 2.0  

---

## 1. Abstract & Executive Summary

Deploying autonomous software engineering (SWE) agents with quantized large language models—such as `google/gemma-4-31B-it-qat-w4a16-ct`—on edge-tier single-accelerator developer workstations (1× NVIDIA L4 24GB VRAM) reveals severe operational bottlenecks. Full-file reading across multi-thousand-line modules rapidly inflates prompt context, while unvalidated patches waste valuable container execution time on trivial syntax failures. Furthermore, multi-test failure logs flood context with hundreds of lines of irrelevant environment banners and captured stdout buffers.

This work introduces the **AST-Guided Verification Suite**, an open-source, deterministic evaluation and execution framework engineered specifically for local SWE agents. The suite couples sub-millisecond abstract syntax tree (`ast.NodeVisitor`) symbol indexing, a dual-stage pre-flight syntax and compilation gate (`compile(mode='exec')`), and a multi-failure assertion-preserving traceback compression engine that eliminates captured stdout pollution while strictly retaining diagnostic root causes. Tested on the `ASTVerificationBenchmark` (a curated microbenchmark of 30 representative defect scenarios across FastAPI, Flask, Click, SymPy, Scikit-Learn, and Django with strict ground-truth line and error oracles), the suite achieves an average **44.6% reduction in prompt token consumption on symbol-sliced modules** (reducing targeted context to 36 tokens per extracted method), a **48.4% macro-aggregate volume reduction on traceback logs** while strictly preserving all diagnostic root causes across single- and multi-failure test runs, and intercepts 100% of syntactically invalid patches in under 0.25 milliseconds (80.6 µs mean latency). All benchmark evaluations execute live within the public notebook without external network or GPU dependencies.

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

Under the memory-bound autoregressive decoding regime (operational intensity $I \approx 1$ FLOP/byte), per-token generation latency follows $\tau(T) = \frac{M_{\text{static}} + M_{\text{KV}}(T)}{\text{BW}_{\text{eff}}}$. Expanding context from 8,192 to 24,576 tokens increases generation latency by $+6.36\%$ (from 81.2 to 86.3 ms/token) while shrinking buffer headroom from 4.27 GiB to under 2.94 GiB on single-accelerator setups.

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
2. **Dual-Stage Pre-Flight Compilation Guard:** Catches syntax regressions, top-level return anomalies, and indentation corruptions in under 0.25ms using `compile(mode='exec')` before initiating expensive container test suites.
3. **Multi-Failure Traceback Compression:** Strips hundreds of lines of pytest session banners and captured stdout spam while strictly preserving all individual failing assertion lines (`E ...`) and error signatures across multi-failure test runs.

---

## 4. Empirical Evaluation: Executable Benchmark Suite with Strict Oracles

We evaluated the deterministic components across the `ASTVerificationBenchmark`, a curated microbenchmark of 30 representative defect and context scenarios with strict ground-truth line and error oracles:

| Category | Tasks | Mean CPU Latency (µs) | Strict Oracle Accuracy | Mean Raw Tokens (Est.) | Mean Processed Tokens | Mean Token Reduction |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Code Slicing** | 8 | 429.6 µs | 100.0% (Exact line bounds) | 65.8 | 36.0 | **44.6%** |
| **Syntax Interception** | 10 | 80.6 µs | 100.0% (Syntax catches) | 6.8 | 6.8 | Pre-flight catch |
| **Traceback Compression** | 7 | 240.0 µs | 100.0% (All markers preserved) | 132.6 | 68.4 | **48.4%** (Macro-aggregate) |
| **Valid Clean Patches** | 5 | 165.2 µs | 100.0% (Zero false rejections) | 15.2 | 15.2 | Gate pass |

### Key Takeaways
1. **Zero LLM overhead:** All three operations execute in aggregate under 1.0 ms on a standard CPU.
2. **Context Economy:** Restricts prompt context to precise symbol line boundaries, avoiding prompt pollution.
3. **Multi-Failure Diagnostic Safety:** Preserves root-cause markers across multiple test failures while collapsing captured stdout buffers.
4. **Deterministic Termination:** Enforces strict single-token completion (`Done.`) after test verification.

---

## 5. Artifacts & Open-Source Availability

All artifacts developed for this project are released under the **Apache 2.0** license:
- **Public Executable Notebook:** [msingatullin/ast-guided-loops-verification-for-gemma-4](https://www.kaggle.com/code/msingatullin/ast-guided-loops-verification-for-gemma-4)
- **Open-Source Repository:** [github.com/msingatullin/gemma-4-developer-agent](https://github.com/msingatullin/gemma-4-developer-agent)
- **ADK Specification:** `agent.yaml`
