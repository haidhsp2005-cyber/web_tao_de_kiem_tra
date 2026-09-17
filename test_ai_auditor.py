import sys
import os
import json

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Ensure app can be imported
sys.path.insert(0, os.path.abspath("."))

from app.services.models import (
    ExamStructure,
    Part1Question,
    Part2Question,
    Part3Question,
    Option,
    SubItem,
    AuditReport
)
from app.services.exam_auditor import (
    is_option_garbage,
    is_mcq_defective,
    heal_mcq_offline,
    audit_and_verify_exam
)
from app.services.ai_generator import (
    normalize_exam_data,
    create_default_audit_report,
    get_mock_math_exam,
    get_mock_physics_exam,
    get_mock_chemistry_exam,
    get_mock_gdqp_exam
)

def test_garbage_detection():
    print("--- 1. Testing Garbage Detection ---")
    garbage_samples = [
        "Phương án khác",
        "không xác định",
        "Giá trị khác",
        "Chưa đủ dữ kiện",
        "Đáp án khác",
        "Tất cả đều sai",
        "Tất cả các đáp án đều đúng",
        "N/A",
        "",
        "..."
    ]
    for g in garbage_samples:
        assert is_option_garbage(g), f"Failed to detect garbage: {g}"
    
    valid_samples = [
        "Năm 1925",
        "1924",
        "Hà Nội",
        "Kim loại kiềm thổ",
        "3.5 m/s",
        "Chiến tranh nhân dân Việt Nam"
    ]
    for v in valid_samples:
        assert not is_option_garbage(v), f"Falsely flagged valid text as garbage: {v}"
    print(" Garbage detection passed!")

async def test_user_screenshot_case():
    print("\n--- 2. Testing User Screenshot Case (Trường Mỹ thuật Đông Dương) ---")
    # Exact case from user image:
    # "Trường Mỹ thuật Đông Dương được thành lập năm nào?"
    # Options had garbage: A. Phương án khác, B. Không xác định, C. Giá trị khác, D. Chưa đủ dữ kiện
    raw_bad_data = {
        "title": "Đề Kiểm Tra Lịch Sử / Mỹ Thuật",
        "subject": "Lịch sử",
        "grade": "12",
        "part_1_mcq": [
            {
                "id": 1,
                "question": "Trường Mỹ thuật Đông Dương được thành lập năm nào?",
                "options": [
                    "Phương án khác",
                    "Không xác định",
                    "Giá trị khác",
                    "Chưa đủ dữ kiện"
                ],
                "correct_answer": "A",
                "explanation": "Trường Cao đẳng Mỹ thuật Đông Dương được thành lập năm 1924."
            }
        ],
        "part_2_true_false": [],
        "part_3_short_answer": []
    }

    # Test normalization
    norm_data = normalize_exam_data(raw_bad_data, default_subject="Lịch sử", default_grade="12")
    exam = ExamStructure.model_validate(norm_data)
    
    # Audit and heal
    audited_exam = await audit_and_verify_exam(exam, api_key=None)

    q = audited_exam.part1_mcq[0]
    print(f"Healed Question: {q.question}")
    print(f"Healed Options: {[o.text for o in q.options]}")
    print(f"Correct Answer: {q.answer}")
    print(f"Explanation: {q.explanation}")
    print(f"Audit Report: {audited_exam.audit_report}")

    # Assertions
    assert len(q.options) == 4, f"Options count should be 4, got {len(q.options)}"
    for opt in q.options:
        assert not is_option_garbage(opt.text), f"Garbage found in healed options: {opt.text}"
    
    # Check that options are plausible years
    assert any("192" in opt.text or "193" in opt.text for opt in q.options), "Options should contain relevant historical years"
    assert audited_exam.audit_report is not None
    assert audited_exam.audit_report.passed is True
    print(" User screenshot case healed successfully!")

async def test_qa_mismatch_correction():
    print("\n--- 3. Testing QA Mismatch Correction ---")
    # Explanation says B, but answer is mistakenly set to A
    exam = ExamStructure(
        title="Đề Kiểm Tra Hóa Học",
        subject="Hóa học",
        grade="11",
        part1_mcq=[
            Part1Question(
                id=1,
                question="Chất nào sau đây là axit clohiđric?",
                options=[
                    Option(label="A", text="H2SO4"),
                    Option(label="B", text="HCl"),
                    Option(label="C", text="HNO3"),
                    Option(label="D", text="NaOH")
                ],
                answer="A",  # Mismatch!
                explanation="Axit clohiđric có công thức phân tử là HCl. Do đó đáp án đúng là B."
            )
        ]
    )

    audited_exam = await audit_and_verify_exam(exam, api_key=None)
    q = audited_exam.part1_mcq[0]
    print(f"Initial answer: A")
    print(f"Audited answer: {q.answer}")
    print(f"Explanation: {q.explanation}")

    assert q.answer == "B", f"Expected answer to be corrected to 'B', got '{q.answer}'"
    print(" QA mismatch correctly aligned!")

def test_mock_exams_integrity():
    print("\n--- 4. Testing Mock Exams Quality ---")
    mock_funcs = [
        ("Toán", get_mock_math_exam),
        ("Vật lý", get_mock_physics_exam),
        ("Hóa học", get_mock_chemistry_exam),
        ("GDQP", get_mock_gdqp_exam)
    ]

    for name, func in mock_funcs:
        exam = func()
        assert exam.audit_report is not None, f"Mock {name} missing audit report!"
        assert exam.audit_report.quality_score == 100, f"Mock {name} quality score is {exam.audit_report.quality_score}!"
        assert exam.audit_report.passed is True
        # Check no garbage in any question
        for q in exam.part1_mcq:
            for opt in q.options:
                assert not is_option_garbage(opt.text), f"Garbage found in mock {name}: {opt.text}"
        print(f" Mock {name}: Quality Score 100%, 0 issues found.")
    print(" All mock exams verified!")

import asyncio

async def main():
    test_garbage_detection()
    await test_user_screenshot_case()
    await test_qa_mismatch_correction()
    test_mock_exams_integrity()
    print("\n==============================================")
    print(" ALL AUDITOR TESTS PASSED WITH 100% ACCURACY! ")
    print("==============================================")

if __name__ == "__main__":
    asyncio.run(main())
