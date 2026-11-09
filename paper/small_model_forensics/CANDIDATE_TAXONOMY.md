# Architectural Taxonomy & Disambiguation: Small Model Track

Date of Audit: 2026-11-09
Repository: `msingatullin/gemma-4-developer-agent`
Target: Kaggle Small Model Development Prize ($10,000)

---

## 1. Executive Summary & Forensic Disambiguation

Previous reports conflated two distinct candidate implementations under the ambiguous name `v17`:
- Candidate A: `v17-grep-only` (v15 system prompt with quoted recursive pathspec `git grep`).
- Candidate B: `v17-AST-BM25` (external lexical + AST repository indexer and ranker).

Furthermore, empirical localization results from `LOCATOR_BENCHMARK_RESULTS.json` (Recall@3 = 59.52% on 42 tasks) were previously misquoted in text as 81%. This document strictly establishes the formal taxonomy, cryptographic file hashes, verified metrics, and execution contracts for all historical baselines and active candidates.

---

## 2. Comprehensive Candidate Matrix

| Feature / Metric | Baseline v15 | Baseline v16 | Candidate `v17-grep-only` | Candidate `v17-AST-BM25` |
|---|---|---|---|---|
| **Kaggle Status** | Submitted (Ref 58073369) | Submitted (Ref 58126337) | Candidate (Unsubmitted) | Candidate (Unsubmitted) |
| **Public LB Score** | **0.06** | **0.05** | Not Submitted | Not Submitted |
| **Model** | Gemma 4 E4B QAT W4A16 | Gemma 4 E4B QAT W4A16 | Gemma 4 E4B QAT W4A16 | Gemma 4 E4B QAT W4A16 |
| **Max Output Tokens** | 8192 | 4096 (Truncated) | 8192 (Exact v15) | 8192 (Exact v15) |
| **Thinking Budget** | 4096 | 4096 | 4096 (Exact v15) | 4096 (Exact v15) |
| **Temperature / Top-p**| 0.2 / 0.95 | 0.2 / 0.95 | 0.2 / 0.95 (Exact v15) | 0.2 / 0.95 (Exact v15) |
| **Tool Call Budget** | 32 calls, 6 min | 36 calls, 6 min | 32 calls, 6 min (Exact v15) | 32 calls, 6 min (Exact v15) |
| **Localization Method** | Unquoted `git grep *.py` | Refined literal `git grep` | Quoted `git grep "*.py"` | Deterministic AST + BM25 locator |
| **Localization Recall@3**| 33.3% (Subdir Blind) | ~45.0% | Eliminates bash expansion bug | **59.52% (25/42 tasks)** |
| **External Files Req.** | None | None | None | `ast_bm25_locator.py` |
| **Delivery Mechanism** | Pure bash in `run_command` | Pure bash in `run_command` | Pure bash in `run_command` | Self-contained bash heredoc to `/tmp` |
| **Workspace Pollution** | 0 bytes (`clean`) | 0 bytes (`clean`) | 0 bytes (`clean`) | 0 bytes (`clean`) |
| **Real E4B Inference** | Verified on Kaggle LB | Verified on Kaggle LB | BLOCKED — REAL INFERENCE NOT EXECUTED | BLOCKED — REAL INFERENCE NOT EXECUTED |

---

## 3. Cryptographic Hashes & File Manifest

### Baseline v15 (Submitted Ref 58073369)
- Directory: `v15_small_model/`
- Archive SHA-256: `f812377537d941a9d7308a0d0e153a7e1362ba5b8832e66520a3b8916e9ca63a`
- `prompts/system.md` SHA-256: `0e8b54ef2ab231040686bbdf25fe20be0651aa823904497bcc7e6b9dc1ed7f89`
- `configs/sampling.yaml` SHA-256: `b39199dcd617e4cd6ae67efb1ccd5f08198780d0aca629d043e95a4aa264702c`

### Baseline v16 (Submitted Ref 58126337)
- Directory: `v16_small_model/`
- Archive SHA-256: `b6c470a38d4eb60a529b1f716e3d5a28b3f74b80f8197080549f1c3ee9c92a7c`
- `prompts/system.md` SHA-256: `5772f8e41858ff838070a2a30918e805bdacf9a8214df25c98cf03a04e1c8551`
- `configs/sampling.yaml` SHA-256: `6d5389a7b35f61caffce32acb66d51ddc4d7b27fe70fd9bccf08f9c99b8f7b09`

### Candidate 1: `v17-grep-only`
- Directory: `candidates/v17_grep_only/`
- `prompts/system.md` SHA-256: `ee5135961a45c632db3535d5aec0549f10a3fec89e591935816eabc04c5e6acf`
- `configs/sampling.yaml` SHA-256: `b39199dcd617e4cd6ae67efb1ccd5f08198780d0aca629d043e95a4aa264702c`
- Core Modification:
  Fixes the bash expansion flaw of v15 by strictly quoting `"*.py"`:
  `git grep -n -i "SPECIFIC_TOKEN" -- "*.py" ':!tests/*' ':!docs/*' ':!examples/*' | head -20`
  Requires zero helper scripts and leaves zero trace outside `/workspace`.

### Candidate 2: `v17-AST-BM25`
- Directory: `candidates/v17_ast_bm25/`
- `prompts/system.md` SHA-256: `b6f28306434b65b93f6852162e19d63cd5fe83a1ebf7766eee94dd2cf79b06fd`
- `configs/sampling.yaml` SHA-256: `b39199dcd617e4cd6ae67efb1ccd5f08198780d0aca629d043e95a4aa264702c`
- `paper/small_model_benchmark/ast_bm25_locator.py` SHA-256: `2b7330768b97d2836e5200216dc83d4bb4e357ae1cb315e985fe66b8fb9e1966`
- Core Modification:
  In-sandbox deterministic AST symbol indexing + BM25 lexical ranking across repository files.
  Verified Empirical Recall: Recall@1 = 47.62%, Recall@3 = 59.52%, Recall@5 = 64.29%, MRR = 0.5459 across 42 SWE-bench tasks.

---

## 4. Contractual Differences in Delivery

1. `v17-grep-only` is completely transparent to the Kaggle Container A / Container B evaluation harness. It uses only standard tools (`run_command`, `read_file`, `edit_file`) and native git commands present in all Unix environments.
2. `v17-AST-BM25` requires the execution script `ast_bm25_locator.py` in `/tmp`. In an unmodified container, this file does not pre-exist. The delivery must happen either via bash heredoc/base64 delivery through `run_command`, or pre-staging by the competition harness.
3. Neither candidate is allowed to be claimed as having solved tasks with real Gemma 4 E4B until real neural weights are evaluated on dedicated GPU hardware.
