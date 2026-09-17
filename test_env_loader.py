import os
import sys
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8')

# Load .env
load_dotenv(override=True)

gemini_keys = []
# 1. Numbered keys GEMINI_API_KEY_1 .. GEMINI_API_KEY_20
for i in range(1, 30):
    val = os.getenv(f"GEMINI_API_KEY_{i}")
    if val:
        val = val.strip().strip("'\"`")
        if len(val) > 5 and val not in gemini_keys:
            gemini_keys.append(val)

# 2. Comma-separated list GEMINI_API_KEYS
list_val = os.getenv("GEMINI_API_KEYS")
if list_val:
    for k in list_val.split(","):
        k = k.strip().strip("'\"`")
        if len(k) > 5 and k not in gemini_keys:
            gemini_keys.append(k)

# 3. Single GEMINI_API_KEY
single_val = os.getenv("GEMINI_API_KEY")
if single_val:
    single_val = single_val.strip().strip("'\"`")
    if len(single_val) > 5 and single_val not in gemini_keys:
        gemini_keys.append(single_val)

print(f"Total Gemini keys loaded from .env: {len(gemini_keys)}")
for idx, k in enumerate(gemini_keys, 1):
    masked = f"{k[:4]}...{k[-4:]}"
    print(f"  Key {idx}: {masked}")

assert len(gemini_keys) == 5
assert gemini_keys[0].startswith("AQ.A")
assert gemini_keys[4].startswith("AQ.A")
print("TEST ENV LOADER PASSED WITH 100% SUCCESS!")
