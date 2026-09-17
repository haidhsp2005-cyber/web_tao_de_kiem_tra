import sys
import json
import asyncio

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, ".")

from app.services.ai_generator import (
    robust_repair_latex_in_json,
    heal_truncated_json,
    clean_json_string,
    normalize_exam_data,
    SYSTEM_PROMPT
)
from app.services.models import ExamStructure

def test_latex_repair():
    print("Testing robust_repair_latex_in_json...")
    
    # Test case 1: tricky LaTeX characters that collide with JSON escapes:
    # \beta (\b), \tan (\t), \neq (\n), \rho (\r), \frac (\f), \rightarrow
    raw_ai_text = r"""{
        "title": "Đề thi Toán \beta và \tan",
        "question": "Cho \beta = 0.5 và \tan(x) = 1. Tìm \frac{\sqrt{x}}{2} với x \neq 0 và \rho = 1.",
        "note": "Line 1\nLine 2\tTabbed",
        "arrow": "A \rightarrow B",
        "nested": {
            "val": "Giá trị của \text{pH} là \pm 0.1 và \left( \frac{a}{b} \right)"
        }
    }"""
    repaired = robust_repair_latex_in_json(raw_ai_text)
    print("Repaired JSON:")
    print(repaired)
    parsed = json.loads(repaired)
    assert r"\beta" in parsed["title"]
    assert r"\tan" in parsed["title"]
    assert r"\frac" in parsed["question"]
    assert r"\neq" in parsed["question"]
    assert r"\rho" in parsed["question"]
    assert parsed["note"] == "Line 1\nLine 2\tTabbed"
    print("   -> OK: LaTeX escapes preserved properly without breaking JSON syntax!")

def test_heal_truncated_json():
    print("Testing heal_truncated_json...")
    truncated_1 = r"""{
        "title": "Đề thi",
        "part1_mcq": [
            {"id": 1, "question": "Hàm số nào đồng biến?", "options": [{"label": "A", "text": "y = x"}, {"label": "B", "text": "y = -x"""
    
    healed_1 = heal_truncated_json(truncated_1)
    print("Healed 1:", healed_1)
    parsed_1 = json.loads(healed_1)
    assert parsed_1["title"] == "Đề thi"
    assert len(parsed_1["part1_mcq"]) == 1
    print("   -> OK: Truncated inside string healed cleanly!")

def test_normalize_exam_data():
    print("Testing normalize_exam_data with flexible AI formats...")
    # Test format where options are list of strings, answers are lowercase, etc.
    ai_output = {
        "tieu_de": "Đề thi thử Tốt nghiệp 2025",
        "mon": "Vật lý",
        "lop": "12",
        "part1_mcq": [
            {
                "cau": 1,
                "cau_hoi": "Tần số góc dao động?",
                "lua_chon": ["A. 10 rad/s", "B. 20 rad/s", "C. 30 rad/s", "D. 40 rad/s"],
                "dap_an": "a",
                "loi_giai": "Ta có omega = 10"
            }
        ],
        "part2_tf": [
            {
                "cau": 1,
                "cau_hoi": "Khẳng định về sóng cơ:",
                "y_dung_sai": [
                    {"y": "a", "khang_dinh": "Sóng dọc truyền được trong chất rắn.", "dap_an": "Đúng", "loi_giai": "Đúng"},
                    {"y": "b", "khang_dinh": "Sóng cơ truyền được trong chân không.", "dap_an": "Sai", "loi_giai": "Sai"},
                    {"y": "c", "khang_dinh": "Tốc độ sóng phụ thuộc môi trường.", "dap_an": "Đ", "loi_giai": ""},
                    {"y": "d", "khang_dinh": "Bước sóng tăng khi qua môi trường mới.", "dap_an": "False", "loi_giai": ""}
                ]
            }
        ],
        "part3_short": [
            {
                "cau": 1,
                "cau_hoi": "Tính chu kỳ T (giây)?",
                "dap_so": 0.5,
                "huong_dan_giai": "T = 2pi / omega = 0.5s"
            }
        ]
    }
    normalized = normalize_exam_data(ai_output, "Vật lý", "12")
    exam_obj = ExamStructure.model_validate(normalized)
    assert exam_obj.title == "Đề thi thử Tốt nghiệp 2025"
    assert exam_obj.part1_mcq[0].answer == "A"
    assert exam_obj.part1_mcq[0].options[0].label == "A"
    assert exam_obj.part1_mcq[0].options[0].text == "10 rad/s"
    assert exam_obj.part2_tf[0].sub_items[0].is_correct is True
    assert exam_obj.part2_tf[0].sub_items[1].is_correct is False
    assert exam_obj.part3_short[0].answer == "0.5"
    print("   -> OK: Complex flexible AI structure normalized to standard ExamStructure!")

if __name__ == "__main__":
    test_latex_repair()
    test_heal_truncated_json()
    test_normalize_exam_data()
    print("\nALL AI GENERATOR PIPELINE TESTS PASSED!")
