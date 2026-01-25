from pathlib import Path
import json

SPIDER_DEV = Path("data/spider/dev.json")

print("Exists:", SPIDER_DEV.exists())

with open(SPIDER_DEV, "r", encoding="utf-8") as f:
    data = json.load(f)

print("Samples:", len(data))
