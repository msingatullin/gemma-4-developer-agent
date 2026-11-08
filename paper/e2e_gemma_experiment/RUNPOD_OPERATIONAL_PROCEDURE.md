# RunPod GPU Deployment and Safe Execution Protocol

This document specifies the exact, step-by-step operational procedure for conducting a single bounded, controlled GPU evaluation run with Gemma 4 (`google/gemma-4-31B-it-qat-w4a16-ct`).

## 1. Hardware Selection and VRAM/OOM Engineering Analysis

- **Target GPU:** NVIDIA RTX A6000 (48 GB VRAM, Ampere architecture).
- **RunPod Pricing:** ~$0.59 / hour (Community Cloud) or ~$0.79 / hour (Secure Cloud).
- **Static Weight Headroom:**
  Gemma 4 31B QAT W4A16 weighs ~19.8 GB. On a 48 GB GPU, nominal static headroom is ~28 GB.
- **Critical OOM Warning & Memory Non-Guarantee:**
  A 48 GB VRAM capacity does NOT guarantee immunity from Out-of-Memory (OOM) crashes.
  1. Under context windows up to 4,096 tokens with completion length up to 1,536 tokens, dynamic KV-cache expansion consumes significant memory.
  2. PyTorch memory allocator fragmentation during repeated requests can trigger CUDA OOM.
  3. Pre-allocated CUDA graphs in vLLM can cause transient spikes during initialization.
- **Strict Mitigations Enforced in Runner:**
  - Sequential single-prompt inference: `batch_size = 1`.
  - vLLM eager execution flag: `--enforce-eager` (eliminates CUDA graph memory spikes).
  - VRAM utilization ceiling: `--gpu-memory-utilization 0.90`.
  - Watchdog hook: Automatic pod termination on HTTP 500 / OOM errors.

## 2. Hard Spending Limits and Financial Safeguards

- **Budget Hard Cap:** $2.00 USD.
- **Inference Scope:** 120 calls total (15 tasks x 4 variants x 2 random seeds).
- **Time Estimate:** ~20-25 seconds per call = ~40-45 minutes active inference.
- **Expected Cost:** ~$0.45 USD.
- **Lifetime Watchdog:** The pod must be terminated within 60 minutes of launch regardless of run status.

## 3. Safe Execution Architecture: `collect_only` Mode

- **Zero Host Code Execution:**
  During the GPU run, `run_e2e_inference.py` runs strictly in `collect_only` mode (the default).
  It records model responses, token counts, latencies, finish reasons, and evaluates diagnostic text strings (`DEFECT_LOCATION`, `ROOT_CAUSE`).
  It **NEVER** executes model-generated candidate code on the GPU instance or on the host machine containing secrets or API tokens.
- **Offline Post-Processing:**
  Any future test suite execution of model patches must occur in an isolated, network-disabled ephemeral container without cloud credentials.

## 4. Operational Step-by-Step Runbook

### Step 1: Pre-Run Financial Gate
Verify that account balance is at least $5.00 USD and note the initial balance:
```bash
python paper/e2e_gemma_experiment/runpod_lifecycle.py --check-balance
```

### Step 2: Launch RunPod Instance
Deploy an on-demand pod with the following configuration:
- Image: `vllm/vllm-openai:v0.6.3`
- GPU: 1x NVIDIA RTX A6000 (48 GB)
- Container Disk: 60 GB
- Ports: `8000/http`
- Container Start Command:
```bash
vllm serve google/gemma-4-31B-it-qat-w4a16-ct \
  --port 8000 \
  --max-model-len 4096 \
  --gpu-memory-utilization 0.90 \
  --enforce-eager \
  --dtype bfloat16
```

### Step 3: Wait for vLLM Readiness
Poll the health endpoint until HTTP 200 is returned:
```bash
curl -s http://<POD_IP>:8000/v1/models
```

### Step 4: Run 1-Prompt Pre-Flight Smoke Test
Before executing any benchmark prompts, run the single-prompt smoke test:
```bash
python paper/e2e_gemma_experiment/runpod_lifecycle.py \
  --smoke-test http://<POD_IP>:8000 \
  --model google/gemma-4-31B-it-qat-w4a16-ct
```
Criteria for PASS:
- HTTP 200 received within 30s.
- `finish_reason == "stop"`.
- Non-empty response.
If the smoke test fails, immediately terminate the pod and abort.

### Step 5: Execute 120-Call Benchmark in `collect_only` Mode
Execute the full balanced Latin-Square benchmark:
```bash
python paper/e2e_gemma_experiment/run_e2e_inference.py \
  --endpoint http://<POD_IP>:8000 \
  --model google/gemma-4-31B-it-qat-w4a16-ct \
  --seeds 42,100
```
Features:
- Incremental checkpointing per call to `experiment_checkpoint.jsonl`.
- Resilient retry (up to 3 attempts with exponential backoff).
- Truncation tracking (`finish_reason == "length"`).

### Step 6: Verified Pod Termination and Billing Cease
Immediately upon completion of call 120 (or upon any unrecoverable error):
```bash
python paper/e2e_gemma_experiment/runpod_lifecycle.py --terminate-pod <POD_ID>
```
The script polls RunPod GraphQL API until status is confirmed `TERMINATED` or deleted, and confirms that compute billing accumulation has halted.

### Step 7: Verification and Statistical Analysis
Verify completeness (120 unique records, zero duplicates, zero missing cells) and review paired statistical analysis in `paired_statistical_analysis.json`.
