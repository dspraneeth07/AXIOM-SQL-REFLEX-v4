# architect_api.py
import subprocess
import sys
import json
from pathlib import Path

# Absolute project root (this file lives in repo root)
PROJECT_ROOT = Path(__file__).resolve().parent

def call_llm(model_key: str, prompt: str, max_tokens=256) -> str:
    code = f"""
import sys
sys.path.insert(0, {json.dumps(str(PROJECT_ROOT))})

from llm_runtime import run

print(run(
    model_key={json.dumps(model_key)},
    prompt={json.dumps(prompt)},
    max_tokens={max_tokens}
))
"""

    cmd = [sys.executable, "-c", code]

    return subprocess.check_output(
        cmd,
        cwd=PROJECT_ROOT,
        text=True,
        stderr=subprocess.STDOUT
    )
