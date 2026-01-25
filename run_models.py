import os
from pathlib import Path
from llama_cpp import Llama

# Hard-disable all llama.cpp logging (critical on Windows)
os.environ["LLAMA_CPP_LOG_LEVEL"] = "ERROR"

MODELS_DIR = Path("models")

llm_large = Llama(
    model_path=str(MODELS_DIR / "deepseek-coder-6.7b-instruct.Q4_K_M.gguf"),
    n_ctx=2048,
    n_threads=8,
    n_batch=256,
    use_mmap=False,
    use_mlock=False,
    verbose=False
)

llm_medium = Llama(
    model_path=str(MODELS_DIR / "mistral-7b-instruct-v0.2.Q4_K_M.gguf"),
    n_ctx=2048,
    n_threads=8,
    n_batch=256,
    use_mmap=False,
    use_mlock=False,
    verbose=False
)

llm_small = Llama(
    model_path=str(MODELS_DIR / "Phi-3-mini-4k-instruct-q4.gguf"),
    n_ctx=1024,
    n_threads=8,
    n_batch=128,
    use_mmap=False,
    use_mlock=False,
    verbose=False
)

print("✅ All Architect models loaded")

# quick sanity test
out = llm_small("Explain SQL JOIN in one sentence.", max_tokens=50)
print(out["choices"][0]["text"])
