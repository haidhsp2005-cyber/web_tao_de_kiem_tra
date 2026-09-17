import sys
import json
sys.stdout.reconfigure(encoding='utf-8')

def find_key(d: dict, *candidates: str):
    if not isinstance(d, dict):
        return None
    # 1. Exact match
    for c in candidates:
        if c in d and d[c]:
            return d[c]
    # 2. Case-insensitive and underscore/space-agnostic match
    clean_map = {}
    for k, v in d.items():
        norm_k = k.lower().replace("_", "").replace("-", "").replace(" ", "")
        clean_map[norm_k] = v
        
    for c in candidates:
        norm_c = c.lower().replace("_", "").replace("-", "").replace(" ", "")
        if norm_c in clean_map and clean_map[norm_c]:
            return clean_map[norm_c]
            
    # 3. Substring match
    for k_norm, v in clean_map.items():
        if not v:
            continue
        for c in candidates:
            norm_c = c.lower().replace("_", "").replace("-", "").replace(" ", "")
            if len(norm_c) >= 4 and (norm_c in k_norm or k_norm in norm_c):
                return v
    return None

# Test various AI formats
data1 = {
    "title": "Đề kiểm tra",
    "Part1_MCQ": [{"id": 1}],
    "PHAN_II": [{"id": 1, "sub_items": []}],
    "Phần 3 (Trả lời ngắn)": [{"id": 1, "answer": "5"}]
}

p1 = find_key(data1, "part1_mcq", "part1", "phan1", "mcq")
p2 = find_key(data1, "part2_tf", "part2", "phan2", "phanii", "dungsai", "truefalse")
p3 = find_key(data1, "part3_short", "part3", "phan3", "phaniii", "traloingan", "shortanswer")

print("Test 1 Result:")
print("p1 found:", p1 is not None)
print("p2 found:", p2 is not None)
print("p3 found:", p3 is not None)

assert p1 is not None
assert p2 is not None
assert p3 is not None
print("ALL FIND_KEY TESTS PASSED!")
