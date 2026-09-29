# Research Paper & Kaggle Writeup Outline: Gemma 4 Developer Agent

**Title:** AST-Guided Navigation and Deterministic Verification Loops for Local SWE Agents with Gemma 4  
**Target Tracks:**
- Main: [Gemma 4 Developer Agent](https://www.kaggle.com/competitions/gemma-4-developer-agent)
- Paper: [Gemma 4 Developer Agent Paper Track](https://www.kaggle.com/competitions/gemma-4-developer-agent-paper) ($35,000 Prize Pool)
**Target Award Category:** Best New Resource / Application ($10,000) or Overall Best Paper ($15,000)

---

## 1. Abstract
- Emerging open-weight LLMs like `gemma-4-31b-it-qat-w4a16-ct` enable local, private software engineering automation.
- However, naive single-turn or monolithic agent loops struggle with context rot, hallucinated APIs, and unverified regression bugs in large repositories.
- We introduce a dual-agent architecture with:
  1. AST-guided symbol extraction and code-graph navigation to minimize context consumption.
  2. A deterministic Test-Time Verification Loop that automatically reproduces bugs before synthesis and verifies patches against regressions before submission.
- Our framework achieves a significant boost in resolved issues compared to baseline zero-shot prompting while remaining within consumer/offline hardware constraints.

---

## 2. Motivation & Problem Statement
- **Context Rot & Token Budgeting:** Reading full source files overwhelms the model's effective reasoning window.
- **Surgical vs Destructive Edits:** LLM agents often inadvertently reformat code or delete adjacent logic.
- **The Ground Truth Gap:** Why agents without execution feedback fail: an edit that "looks correct" often introduces silent runtime failures.

---

## 3. Architecture & Methodology
- **Agent Specification (`agent.yaml`):** Declarative orchestration model.
- **Code Graph & AST Skills:**
  - Semantic neighbor querying (`get_code_neighbors`, `get_code_subgraph`).
  - AST-level symbol extraction to identify candidate modification targets without full-file ingestion.
- **Verification Harness:**
  - Automated test isolation (`pytest -k ... --tb=short`).
  - Clean error signature extraction for localized model feedback.

---

## 4. Empirical Evaluation & Benchmarks
- Benchmark dataset: `tasks.jsonl` (SWE-bench tasks like `fastapi`, `flask`, `scikit-learn`).
- Metrics:
  - Resolution Rate (% of issues resolved with passing `test_patch`).
  - Context Efficiency (average tokens consumed per bug resolution).
  - First-time Success vs Multi-turn Correction Rate.
- A/B Comparisons:
  - Baseline Gemma 4 (Monolithic prompt + raw file reads)
  - Gemma 4 + AST Navigation
  - Gemma 4 + AST Navigation + Deterministic Verification Loop

---

## 5. Discussion, Limitations & Future Work
- Quantitative limitations of 4-bit quantization under complex multi-file refactoring.
- Future work: Training task-specific LoRA adapters for repo-level patch synthesis.

---

## 6. Reproducibility & Open Source Artifacts
- Permissive Apache 2.0 release of all prompts, skills, evaluation scripts, and writeup assets.
