# AST-Guided Verification Suite: Deterministic Code Slicing and Pre-Flight Validation for Local SWE Agents on Gemma 4

**Author:** Mikhail Singatullin (`msingatullin` / Team `Михаил`)  
**Competition Track:** [Google - The Gemma 4 Developer Agent Paper Track](https://www.kaggle.com/competitions/gemma-4-developer-agent-paper)  
**Primary Award Nomination:** Best New Resource / Best New Application  
**Public Executable Notebook:** [Kaggle Notebook](https://www.kaggle.com/code/msingatullin/ast-guided-loops-verification-for-gemma-4)  
**License:** Apache 2.0  

---

## 1. Abstract & Executive Summary

Deploying autonomous software engineering (SWE) agents with quantized, locally hosted large language models on edge-tier accelerators—such as the competition environment's single NVIDIA L4 (24GB VRAM) running `google/gemma-4-31B-it-qat-w4a16-ct`—reveals severe operational bottlenecks. Full-file reading across multi-thousand-line modules saturates attention memory and inflates prompt context, while unvalidated patches waste valuable container execution time on trivial syntax failures. Furthermore, standard test execution logs flood context with hundreds of lines of irrelevant environment banners.

This work introduces the **AST-Guided Verification Suite**, an open-source, deterministic evaluation and execution framework engineered specifically for local SWE agents. The suite couples sub-millisecond abstract syntax tree (`ast.NodeVisitor`) symbol indexing, a dual-stage pre-flight syntax and compilation gate (`compile(mode='exec')`), and an assertion-preserving traceback compression engine that eliminates captured stdout pollution. Tested on the `ASTVerificationBenchmark` (a curated microbenchmark of 30 representative defect scenarios across FastAPI, Flask, Click, SymPy, Scikit-Learn, and Django), the suite achieves an average **40.7% reduction in prompt token consumption on symbol-sliced modules** (reducing targeted context to under 52 tokens per extracted method), intercepts 100% of syntactically invalid patches in under 0.25 milliseconds (80.6 µs mean latency), and strictly preserves terminal assertion diagnostics across all test failures. All benchmark evaluations execute live within the public notebook without external network or GPU dependencies.

---

## 2. Operating Constraints and Gemma 4 (31B QAT) Attention Mechanics

The official competition container operates under three strict hardware and software boundaries:
- **Host Environment:** 1x NVIDIA L4 (24 GB GDDR6 VRAM, Ada Lovelace architecture, sustained bandwidth $\approx 242$ GB/s), 4 vCPUs, 16 GB RAM, and a hard 12-hour batch execution window.
- **Quantized Model:** `google/gemma-4-31B-it-qat-w4a16-ct` (INT4 pack-quantized weights, group size 32, FP16 activations). Resident model weights occupy $\approx 18.24$ GB VRAM, leaving under 5.76 GB for KV cache expansion and CUDA execution overhead.
- **Architectural Specifications:** Official model configuration inspection reveals:
  * Total transformer layers: $L = 60$.
  * Hybrid attention structure: 50 sliding-window attention layers (sliding window $W = 1024$ tokens, $H_{kv} = 16$ key-value heads, head dimension $d_k = 256$) and 10 full-attention global layers (every 6th layer, $H_{kv,\text{global}} = 4$, $d_{k,\text{global}} = 512$).
  * Query heads: $H_q = 32$.

### Analytical Analysis of KV Cache Growth Across Hybrid Attention Layers

For a context sequence of $T$ tokens stored in FP16 ($2$ bytes/scalar), memory allocation scales differently across the sliding and global attention layers:

1. **Sliding-Window Attention Layers (50 layers):**
   Because sliding layers discard attention history beyond the active window $W = 1024$, their KV footprint saturates:
   $$M_{\text{KV,sliding}}(T) = 50 \times 2 \times H_{kv} \times d_k \times \min(T, 1024) \times 2 = 819,200 \times \min(T, 1024) \text{ bytes}$$
   When $T \ge 1024$, sliding KV memory is strictly capped at $838.86$ MB ($0.781$ GB).

2. **Global Full-Attention Layers (10 layers):**
   The 10 global layers maintain attention across the entire context depth $T$:
   $$M_{\text{KV,global}}(T) = 10 \times 2 \times H_{kv,\text{global}} \times d_{k,\text{global}} \times T \times 2 = 81,920 \times T \text{ bytes} = 80.0 \times T \text{ KB}$$

3. **Total KV Memory Footprint and Roofline Latency:**
   $$M_{\text{KV,total}}(T) = M_{\text{KV,sliding}}(T) + M_{\text{KV,global}}(T)$$
   - At $T = 1,024$ tokens: Total KV $= 0.859$ GB. Total VRAM $= 19.15$ GB ($4.85$ GB safety headroom).
   - At $T = 8,192$ tokens (Deterministic AST bounded scope): Total KV $= 1.406$ GB. Total VRAM $= 19.73$ GB ($4.27$ GB headroom).
   - At $T = 24,576$ tokens (Unconstrained multi-file exploration): Total KV $= 2.656$ GB. Total VRAM $= 21.06$ GB ($2.94$ GB headroom).

Under the memory-bound autoregressive decoding regime (operational intensity $I \approx 1$ FLOP/byte), per-token generation latency follows $\tau(T) = \frac{M_{\text{static}} + M_{\text{KV}}(T)}{\text{BW}_{\text{eff}}}$. Expanding context from 8,192 to 24,576 tokens increases generation latency by $+6.36\%$ (from 81.2 to 86.3 ms/token) while shrinking buffer headroom from 4.27 GB to under 2.94 GB, significantly elevating PagedAttention fragmentation risk in multi-turn sessions.

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
3. **Deterministic Traceback Compression:** Strips hundreds of lines of pytest session banners and captured stdout spam while strictly preserving the failing assertion line and error signature.

---

## 4. Empirical Evaluation: Executable Benchmark Suite

We evaluated the deterministic components across the `ASTVerificationBenchmark`, a curated microbenchmark of 30 representative defect and context scenarios:

| Category | Tasks | Mean CPU Latency (µs) | Accuracy / Catch Rate | Mean Raw Tokens | Mean Processed Tokens | Mean Token Reduction |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Code Slicing** | 8 | 600.2 µs | 100.0% | 86.8 | 51.1 | **40.7%** |
| **Syntax Interception** | 10 | 80.6 µs | 100.0% | 6.8 | 6.8 | Pre-flight catch |
| **Traceback Compression** | 7 | 175.6 µs | 100.0% (Assert preserved) | 118.3 | 47.9 | **59.5%** |
| **Valid Clean Patches** | 5 | 204.3 µs | 100.0% (Zero false rejections) | 15.2 | 15.2 | Gate pass |

### Key Takeaways
1. **Zero LLM overhead:** All three operations execute in aggregate under 1.1 ms on a standard CPU.
2. **Context Economy:** Restricts prompt context to precise symbol line boundaries, avoiding prompt pollution.
3. **Deterministic Termination:** Enforces strict single-token completion (`Done.`) after test verification.

---

## 5. Artifacts & Open-Source Availability

All artifacts developed for this project are released under the **Apache 2.0** license:
- **Public Executable Notebook:** [msingatullin/ast-guided-loops-verification-for-gemma-4](https://www.kaggle.com/code/msingatullin/ast-guided-loops-verification-for-gemma-4)
- **Open-Source Repository:** [github.com/msingatullin/gemma-4-developer-agent](https://github.com/msingatullin/gemma-4-developer-agent)
- **ADK Specification:** `agent.yaml`
