import sys
import json
import json_repair
sys.stdout.reconfigure(encoding='utf-8')

from app.services.ai_generator import robust_repair_latex_in_json

# Test with both internal quotes AND LaTeX:
s = r"""{
    "title": "Đề thi Toán 10",
    "question": "Phương trình bậc hai "ax^2 + bx + c = 0" có \Delta = b^2 - 4ac và \beta = 1. Tìm điều kiện để phương trình có nghiệm x \neq 0.",
    "options": [
        {"label": "A", "text": "Phương án "A" đúng"},
        {"label": "B", "text": "\tan(x) > 0"}
    ]
}"""

# 1. Without repair:
try:
    json.loads(s)
    print("Standard json succeeded")
except Exception as e:
    print(f"Standard json failed: {e}")

# 2. Repair LaTeX first, then json_repair:
repaired_latex = robust_repair_latex_in_json(s)
print("\nAfter robust_repair_latex_in_json:")
try:
    d1 = json.loads(repaired_latex)
    print("Standard json parsed repaired_latex successfully!")
except Exception as e:
    print(f"Standard json on repaired_latex failed: {e}")

# 3. Now try json_repair.loads on repaired_latex:
d2 = json_repair.loads(repaired_latex)
print("\njson_repair.loads on repaired_latex result:")
print(f"title: {d2.get('title')}")
print(f"question: {d2.get('question')}")
print(f"options: {d2.get('options')}")
