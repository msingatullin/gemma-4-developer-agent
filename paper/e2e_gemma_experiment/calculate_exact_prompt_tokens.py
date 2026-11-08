#!/usr/bin/env python3
"""
Exact Token Length Measurement for 15 Frozen Prompts using Canonical Gemma 4 Tokenizer.
Calculates:
- Exact token count formatted via Gemma 4 canonical chat template (system + user prompt + generation prompt)
- Reserve for generation: exactly 2048 tokens
- Total required context window (input_tokens + 2048)
- Exact SHA256 of prompt file
"""

import json
import hashlib
from pathlib import Path
from transformers import AutoTokenizer

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ARCHIVE_DIR = REPO_ROOT / "paper" / "e2e_gemma_experiment" / "real_repo_sample"
PROMPTS_DIR = ARCHIVE_DIR / "frozen_prompts"
OUTPUT_JSON = ARCHIVE_DIR / "exact_prompt_token_measurements.json"

MODEL_ID = "google/gemma-4-31B-it-qat-w4a16-ct"
GENERATION_RESERVE = 2048

def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def main():
    print(f"[*] Loading Canonical Gemma 4 Tokenizer for {MODEL_ID}...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True)

    prompt_files = sorted(PROMPTS_DIR.glob("*__*.json"))
    assert len(prompt_files) == 15, f"Expected 15 prompt files, found {len(prompt_files)}"

    measurements = []
    max_input_tokens = 0
    max_required_context = 0

    print("\n" + "="*110)
    print(f"{'Task Instance':<22} | {'Variant':<20} | {'Input Tok':<10} | {'Reserve':<8} | {'Req Context':<12} | {'Prompt SHA256'}")
    print("-" * 110)

    for pf in prompt_files:
        raw_text = pf.read_text(encoding="utf-8")
        file_sha = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
        data = json.loads(raw_text)

        iid = data["instance_id"]
        variant = data["variant"]
        sys_prompt = data["system_prompt"]
        usr_prompt = data["user_prompt"]

        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": usr_prompt}
        ]

        # Apply canonical chat template with add_generation_prompt=True
        encoded = tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True, return_dict=True)
        input_tokens = len(encoded["input_ids"])
        required_context = input_tokens + GENERATION_RESERVE

        if input_tokens > max_input_tokens:
            max_input_tokens = input_tokens
        if required_context > max_required_context:
            max_required_context = required_context

        entry = {
            "instance_id": iid,
            "variant": variant,
            "prompt_file": pf.name,
            "prompt_file_sha256": file_sha,
            "user_prompt_sha256": data.get("user_prompt_sha256", sha256_text(usr_prompt)),
            "char_length": len(sys_prompt) + len(usr_prompt),
            "input_tokens": input_tokens,
            "generation_reserve": GENERATION_RESERVE,
            "required_context": required_context
        }
        measurements.append(entry)

        print(f"{iid:<22} | {variant:<20} | {input_tokens:<10} | {GENERATION_RESERVE:<8} | {required_context:<12} | {file_sha[:16]}...")

    print("=" * 110)
    print(f"\n[SUMMARY]")
    print(f"  Maximum Input Tokens:       {max_input_tokens}")
    print(f"  Generation Reserve:         {GENERATION_RESERVE}")
    print(f"  Absolute Maximum Required:  {max_required_context}")

    # Recommended power-of-two or standard vLLM boundary
    # e.g., if max is 9,500 + 2048 = 11,548 -> next safe boundary is 12288 or 16384
    import math
    next_pow2 = 2 ** math.ceil(math.log2(max_required_context))
    print(f"  Recommended max-model-len:  {max_required_context} (or safe round boundary {max(16384, next_pow2)})")

    out_data = {
        "model_id": MODEL_ID,
        "generation_reserve_tokens": GENERATION_RESERVE,
        "max_input_tokens": max_input_tokens,
        "max_required_context": max_required_context,
        "recommended_max_model_len": max(16384, next_pow2),
        "measurements": measurements
    }
    OUTPUT_JSON.write_text(json.dumps(out_data, indent=2), encoding="utf-8")
    print(f"\n[✓] Detailed measurements written to {OUTPUT_JSON.name}")

if __name__ == "__main__":
    main()
