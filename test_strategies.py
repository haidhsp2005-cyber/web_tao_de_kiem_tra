import sys
import json
import json_repair
sys.stdout.reconfigure(encoding='utf-8')

from app.services.ai_generator import robust_repair_latex_in_json, clean_json_string

test_cases = [
    # Case 1: The user's exact issue - unescaped quotes in Vietnamese text
    r"""{
        "title": "ĐỀ KIỂM TRA ĐỊNH KỲ MÔN TOÁN 10",
        "part1_mcq": [
            {
                "id": 1,
                "question": "Phương trình nào sau đây là phương trình bậc hai một ẩn "dạng chuẩn"?",
                "options": [
                    {"label": "A", "text": "ax^2 + bx + c = 0 (a \neq 0)"},
                    {"label": "B", "text": "ax + b = 0"}
                ],
                "answer": "A",
                "explanation": "Phương trình bậc hai một ẩn có dạng $ax^2 + bx + c = 0$ với $a \neq 0$."
            }
        ]
    }""",
    # Case 2: Trailing comma, missing brace, unescaped newlines
    r"""{
        "title": "ĐỀ KIỂM TRA",
        "part1_mcq": [
            {
                "id": 1,
                "question": "Cho tam giác ABC có góc A = 60^\circ.
Tính cạnh BC.",
                "options": [
                    {"label": "A", "text": "BC = \sqrt{3}"},
                ],
                "answer": "A",
            },
        ],
    }"""
]

for idx, tc in enumerate(test_cases, 1):
    print(f"\n--- Testing Case {idx} ---")
    cleaned = clean_json_string(tc)
    repaired = robust_repair_latex_in_json(cleaned)
    
    # Try strategy 1: standard json
    parsed = None
    try:
        parsed = json.loads(repaired)
        print("Strategy 1 (json.loads repaired): SUCCESS")
    except Exception as e:
        print(f"Strategy 1 failed: {e}")
        
    # Try strategy 2: json_repair on repaired
    if not parsed:
        try:
            parsed = json_repair.loads(repaired)
            if isinstance(parsed, dict) and parsed:
                print("Strategy 2 (json_repair on repaired): SUCCESS")
        except Exception as e:
            print(f"Strategy 2 failed: {e}")
            
    # Try strategy 3: json_repair on cleaned
    if not parsed:
        try:
            parsed = json_repair.loads(cleaned)
            if isinstance(parsed, dict) and parsed:
                print("Strategy 3 (json_repair on cleaned): SUCCESS")
        except Exception as e:
            print(f"Strategy 3 failed: {e}")
            
    print("Parsed result keys:", parsed.keys() if isinstance(parsed, dict) else type(parsed))
    if isinstance(parsed, dict) and "part1_mcq" in parsed:
        print("Q1 question:", parsed["part1_mcq"][0].get("question"))
        print("Q1 options:", parsed["part1_mcq"][0].get("options"))
