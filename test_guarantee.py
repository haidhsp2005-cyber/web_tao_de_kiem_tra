import sys
import json
sys.stdout.reconfigure(encoding='utf-8')

from app.services.ai_generator import (
    find_key,
    normalize_exam_data,
    get_mock_math_exam
)
from app.services.models import ExamStructure

# Simulate an AI output that only returned part1_mcq (because of truncation or omission)
raw_incomplete_ai_output = {
    "title": "ĐỀ KIỂM TRA ĐỊNH KỲ MÔN TOÁN 10",
    "subject": "Toán học",
    "grade": "10",
    "part1_mcq": [
        {
            "id": i,
            "question": f"Câu hỏi trắc nghiệm số {i}",
            "options": [{"label": "A", "text": "A"}, {"label": "B", "text": "B"}, {"label": "C", "text": "C"}, {"label": "D", "text": "D"}],
            "answer": "A",
            "explanation": "Giải thích"
        }
        for i in range(1, 21)
    ]
}

print("Testing incomplete AI output normalization...")
norm = normalize_exam_data(raw_incomplete_ai_output, "Toán học", "10")
print(f"P1 count: {len(norm['part1_mcq'])}")
print(f"P2 count before fill: {len(norm['part2_tf'])}")
print(f"P3 count before fill: {len(norm['part3_short'])}")

# Fill logic
fallback_bank = get_mock_math_exam()
while len(norm["part2_tf"]) < 4:
    idx = len(norm["part2_tf"])
    item = fallback_bank.part2_tf[idx % len(fallback_bank.part2_tf)].model_dump()
    item["id"] = idx + 1
    norm["part2_tf"].append(item)

while len(norm["part3_short"]) < 6:
    idx = len(norm["part3_short"])
    item = fallback_bank.part3_short[idx % len(fallback_bank.part3_short)].model_dump()
    item["id"] = idx + 1
    norm["part3_short"].append(item)

exam_obj = ExamStructure.model_validate(norm)
print(f"P1 count final: {len(exam_obj.part1_mcq)}")
print(f"P2 count final: {len(exam_obj.part2_tf)}")
print(f"P3 count final: {len(exam_obj.part3_short)}")

assert len(exam_obj.part1_mcq) == 20
assert len(exam_obj.part2_tf) == 4
assert len(exam_obj.part3_short) == 6
print("ALL PARTS GUARANTEED SUCCESSFULLY!")
