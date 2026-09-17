import sys
import os
import io
import asyncio
import json

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.abspath("."))

from app.services.models import (
    ExamStructure,
    Part1Question,
    Part2Question,
    Part3Question,
    Part4EssayQuestion,
    Option,
    SubItem,
    GenerateRequest
)
from app.services.ai_generator import normalize_exam_data
from app.services.shuffler import shuffle_exam
from app.services.docx_exporter import create_exam_document
from app.services.exam_auditor import audit_and_verify_exam

def extract_docx_text(doc) -> str:
    full_text = []
    for p in doc.paragraphs:
        full_text.append(p.text)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    full_text.append(p.text)
    return "\n".join(full_text)

async def test_num_essay_zero():
    print("--- 1. Testing num_essay == 0 (Strict Omission) ---")
    raw_data_with_unwanted_essay = {
        "title": "Đề Kiểm Tra Toán 12",
        "subject": "Toán học",
        "grade": "12",
        "part1_mcq": [
            {
                "id": 1,
                "question": "Tính đạo hàm của hàm số $y = x^2$.",
                "options": [
                    {"label": "A", "text": "$y' = 2x$"},
                    {"label": "B", "text": "$y' = x$"},
                    {"label": "C", "text": "$y' = x^2$"},
                    {"label": "D", "text": "$y' = 2$"}
                ],
                "answer": "A",
                "explanation": "Ta có $(x^2)' = 2x$. Do đó chọn đáp án A."
            }
        ],
        "part2_tf": [],
        "part3_short": [],
        "part4_essay": [
            {
                "id": 1,
                "question": "Giải phương trình lượng giác sau: $\\sin x = 1$.",
                "points": 2.0,
                "answer": "$x = \\frac{\\pi}{2} + k2\\pi$",
                "explanation": "Phương trình có nghiệm là $x = \\pi/2 + k2\\pi, k \\in \\mathbb{Z}$."
            }
        ]
    }

    norm = normalize_exam_data(raw_data_with_unwanted_essay, "Toán học", "12")
    
    # Simulate user choosing num_essay = 0
    req = GenerateRequest(
        subject="Toán học",
        grade="12",
        num_part1=1,
        num_part2=0,
        num_part3=0,
        num_essay=0
    )

    if req.num_essay == 0:
        norm["part4_essay"] = []
    if req.num_part2 == 0:
        norm["part2_tf"] = []
    if req.num_part3 == 0:
        norm["part3_short"] = []

    exam = ExamStructure.model_validate(norm)
    audited = await audit_and_verify_exam(exam)

    # Assertions on exam structure
    assert len(audited.part4_essay) == 0, f"Expected 0 essay questions, got {len(audited.part4_essay)}"
    assert audited.audit_report.total_questions == 1, f"Expected total_questions = 1, got {audited.audit_report.total_questions}"

    # Test Shuffler with num_essay = 0
    shuffled = shuffle_exam(audited, num_variants=2, start_code=101)
    for v in shuffled.variants:
        assert len(v.exam.part4_essay) == 0, "Variant should have 0 essay questions"
        assert len(v.part4_answers) == 0, "Variant part4_answers should be empty"
    assert "part4" not in shuffled.matrix, "Matrix should not have part4 when num_essay == 0"

    # Test DOCX Export with num_essay = 0
    doc = create_exam_document(audited, variant_code="101")
    doc_text = extract_docx_text(doc)
    assert "PHẦN IV" not in doc_text, "DOCX should NOT contain 'PHẦN IV' when num_essay == 0!"
    assert "TỰ LUẬN" not in doc_text, "DOCX should NOT contain 'TỰ LUẬN' when num_essay == 0!"
    print(" num_essay == 0 successfully verified: 0 questions, 0 headers in docx, 0 matrix rows!")

async def test_num_essay_positive():
    print("\n--- 2. Testing num_essay == 2 (Essay Section Included) ---")
    raw_data_with_essay = {
        "title": "Đề Kiểm Tra Toán 12 Có Tự Luận",
        "subject": "Toán học",
        "grade": "12",
        "part1_mcq": [
            {
                "id": 1,
                "question": "Tính đạo hàm $y = x^2$.",
                "options": [
                    {"label": "A", "text": "$2x$"},
                    {"label": "B", "text": "$x$"},
                    {"label": "C", "text": "$x^2$"},
                    {"label": "D", "text": "$2$"}
                ],
                "answer": "A",
                "explanation": "Chọn A."
            }
        ],
        "part2_tf": [],
        "part3_short": [],
        "part4_essay": [
            {
                "id": 1,
                "question": "Tìm giá trị lớn nhất và nhỏ nhất của hàm số $f(x) = x^3 - 3x$ trên $[-2, 2]$.",
                "points": 1.5,
                "answer": "GTLN là 2, GTNN là -2",
                "explanation": "- Bước 1 (0.5đ): Tính $f'(x) = 3x^2 - 3 = 0 \\Leftrightarrow x = \\pm 1$.\n- Bước 2 (0.5đ): Tính $f(-2)=-2, f(-1)=2, f(1)=-2, f(2)=2$.\n- Bước 3 (0.5đ): Kết luận $\\max = 2, \\min = -2$."
            },
            {
                "id": 2,
                "question": "Trong không gian $Oxyz$, viết phương trình mặt phẳng $(P)$ đi qua $A(1,0,0)$ và có vecto pháp tuyến $\\vec{n}=(1,2,3)$.",
                "points": 1.0,
                "answer": "$x + 2y + 3z - 1 = 0$",
                "explanation": "- Bước 1 (0.5đ): Dạng phương trình $1(x-1) + 2(y-0) + 3(z-0) = 0$.\n- Bước 2 (0.5đ): Thu gọn được $x + 2y + 3z - 1 = 0$."
            }
        ]
    }

    norm = normalize_exam_data(raw_data_with_essay, "Toán học", "12")
    exam = ExamStructure.model_validate(norm)
    audited = await audit_and_verify_exam(exam)

    # Assertions
    assert len(audited.part4_essay) == 2, f"Expected 2 essay questions, got {len(audited.part4_essay)}"
    assert audited.audit_report.total_questions == 3, f"Expected total_questions = 3, got {audited.audit_report.total_questions}"
    assert any("tự luận" in n.lower() for n in audited.audit_report.notes), "Audit notes should mention essay"

    # Test Shuffler
    shuffled = shuffle_exam(audited, num_variants=2, start_code=101)
    for v in shuffled.variants:
        assert len(v.exam.part4_essay) == 2, "Variant should have 2 essay questions"
        assert len(v.part4_answers) == 2, "Variant part4_answers should contain 2 entries"
    assert "part4" in shuffled.matrix, "Matrix should contain part4"

    # Test DOCX Export
    doc = create_exam_document(audited, variant_code="101")
    doc_text = extract_docx_text(doc)
    assert "PHẦN IV" in doc_text and "CÂU HỎI TỰ LUẬN" in doc_text, "DOCX must contain PHẦN IV CÂU HỎI TỰ LUẬN!"
    assert "HƯỚNG DẪN CHẤM" in doc_text and "TỰ LUẬN" in doc_text, "DOCX must contain Essay Rubric!"
    assert "điểm" in doc_text, "DOCX must display points"
    print(" num_essay == 2 successfully verified: 2 questions, rubric in docx, matrix populated!")

async def main():
    await test_num_essay_zero()
    await test_num_essay_positive()
    print("\n=======================================================")
    print(" ALL ESSAY OPTION & OMISSION TESTS PASSED WITH 100%!  ")
    print("=======================================================")

if __name__ == "__main__":
    asyncio.run(main())
