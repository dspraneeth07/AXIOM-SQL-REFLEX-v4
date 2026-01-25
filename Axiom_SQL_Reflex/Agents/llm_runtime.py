import sys
from pathlib import Path
from llama_cpp import Llama

# 🔒 CRITICAL FIX FOR WINDOWS + JUPYTER
sys.stdout = sys.__stdout__
sys.stderr = sys.__stderr__

MODELS_DIR = Path(__file__).resolve().parent.parent / "models"

def load_llms():
    llm_large = Llama(
        model_path=str(MODELS_DIR / "deepseek-coder-6.7b-instruct.Q4_K_M.gguf"),
        n_ctx=2048,
        n_threads=8,
        n_batch=256,
        use_mmap=False,
        use_mlock=False,
        verbose=True
    )

    llm_medium = Llama(
        model_path=str(MODELS_DIR / "mistral-7b-instruct-v0.2.Q4_K_M.gguf"),
        n_ctx=2048,
        n_threads=8,
        n_batch=256,
        use_mmap=False,
        use_mlock=False,
        verbose=True
    )

    llm_small = Llama(
        model_path=str(MODELS_DIR / "tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf"),
        n_ctx=1024,
        n_threads=8,
        n_batch=128,
        use_mmap=False,
        use_mlock=False,
        verbose=True
    )

    return llm_large, llm_medium, llm_small
