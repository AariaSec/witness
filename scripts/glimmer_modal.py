"""
Muse Glimmer on Modal — OpenAI-compatible inference for the witness analyst pass.

Serves `meta-models/Muse-Glimmer-30B-GGUF` (Apache-2.0, GGUF ~16.8 GB) via llama.cpp's
OpenAI-compatible server on a single 24 GB A10G — a self-deployed GPU (partner-hosted on Modal) as evidence for the
hackathon's $10K Best-Build-on-Meta-Open-Weights bonus. The 16.8 GB GGUF fits an A10G
with room for context; no quantization spike needed (vs bf16 ~60 GB which would force
an A100-80GB).

DEPLOY
    pip install modal
    modal setup                      # one-time auth (uses your Modal account + $100 credit)
    modal deploy glimmer_modal.py    # prints the public base URL

USE (witness reads it from WITNESS_GLIMMER_URL; or any OpenAI client)
    base_url = "https://<your-modal-app>.modal.run/v1"
    model    = "glimmer"             # alias we register; the real file is the GGUF below
    # POST {base_url}/chat/completions  (no API key needed unless you add one)

COST GUARD
    - A10G ≈ $1.10/hr on Modal; scaledown_window keeps it warm 3 min then stops.
    - max_containers=1 so a runaway can't fan out. Well inside the $40 GPU cap.

VERIFY-ID RULE (your plan): confirm the exact GGUF filename returns 200 before the demo.
    huggingface-cli download meta-models/Muse-Glimmer-30B --include "*.gguf" --local-dir /tmp/g
If the repo id or filename differ in your environment, change MODEL_REPO / GGUF_GLOB below.
"""

import modal

MODEL_REPO = "meta-models/Muse-Glimmer-30B-GGUF"   # verify this id returns 200 before deploying
GGUF_GLOB = "Muse-Glimmer-30B-KQuant-17GB-Q4_K_M.gguf"  # proven-loadable quant (XL dynamic needs newer llama.cpp)
MINUTES = 60

app = modal.App("aariasec-glimmer")

# ---- image: llama.cpp server (OpenAI-compatible) + HF downloader -----------------
# Muse Glimmer needs llama.cpp build b10353+ (muse-glimmer arch merged 2026-08-10,
# PR ggml-org/llama.cpp#26841). llama-cpp-python 0.3.2 predates it → "unknown model
# architecture: 'muse-glimmer'". 0.3.36 (2026-10-01) bundles a new-enough llama.cpp;
# install the prebuilt cu124 CUDA wheel so all layers offload to the A10G.
image = (
    modal.Image.from_registry(
        "nvidia/cuda:12.4.1-runtime-ubuntu22.04", add_python="3.11"
    )
    .apt_install("curl", "libgomp1")
    .pip_install("huggingface_hub[hf_transfer]==0.26.2")
    .pip_install(
        "llama-cpp-python[server]==0.3.36",
        extra_index_url="https://abetlen.github.io/llama-cpp-python/whl/cu124",
    )
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "1"})
)

# cache the weights across cold starts so we download the 16.8 GB GGUF once
weights = modal.Volume.from_name("glimmer-weights", create_if_missing=True)
WEIGHTS_DIR = "/weights"


@app.function(image=image, volumes={WEIGHTS_DIR: weights}, timeout=60 * MINUTES)
def download():
    """Download the Glimmer GGUF into the shared volume (run once)."""
    import glob
    import os

    from huggingface_hub import snapshot_download

    snapshot_download(
        repo_id=MODEL_REPO,
        local_dir=WEIGHTS_DIR,
        allow_patterns=[GGUF_GLOB],
    )
    weights.commit()
    found = sorted(glob.glob(os.path.join(WEIGHTS_DIR, "**", "*.gguf"), recursive=True))
    print("GGUF files:", found)
    assert found, "no .gguf found — check MODEL_REPO / GGUF_GLOB"
    return found[0]


@app.function(
    image=image,
    gpu="A10G",                 # 24 GB — fits the 16.8 GB GGUF; cheaper than L40S
    volumes={WEIGHTS_DIR: weights},
    timeout=60 * MINUTES,
    scaledown_window=180,       # stop 3 min after idle — cost guard
    max_containers=1,           # never fan out
)
@modal.concurrent(max_inputs=8)
@modal.web_server(port=8000, startup_timeout=20 * MINUTES)
def serve():
    """llama.cpp OpenAI-compatible server on the Glimmer GGUF."""
    import glob
    import os
    import subprocess

    # Prefer the exact pinned GGUF (the volume may also hold an earlier quant).
    pinned = os.path.join(WEIGHTS_DIR, GGUF_GLOB)
    if os.path.exists(pinned):
        model_path = pinned
    else:
        gguf = sorted(glob.glob(os.path.join(WEIGHTS_DIR, "**", "*.gguf"), recursive=True))
        if not gguf:
            raise RuntimeError("weights not downloaded — run `modal run glimmer_modal.py::download` first")
        model_path = gguf[0]
    # -ngl 999: offload all layers to GPU; --host 0.0.0.0 so Modal can proxy it.
    cmd = [
        "python", "-m", "llama_cpp.server",
        "--model", model_path,
        "--model_alias", "glimmer",
        "--host", "0.0.0.0", "--port", "8000",
        "--n_gpu_layers", "999",
        "--n_ctx", "8192",
    ]
    subprocess.Popen(" ".join(cmd), shell=True)


@app.local_entrypoint()
def main():
    """`modal run glimmer_modal.py` → download the weights, then print deploy hint."""
    path = download.remote()
    print(f"Downloaded: {path}")
    print("Now: modal deploy glimmer_modal.py   (then POST to <url>/v1/chat/completions)")
