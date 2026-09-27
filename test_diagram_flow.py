import sys
import os
import io

# Fix Windows console encoding
sys.stdout.reconfigure(encoding='utf-8')

from app.services.ai_generator import (
    get_mock_math_exam,
    get_mock_physics_exam,
    get_mock_chemistry_exam,
    get_mock_biology_exam
)
from app.services.shuffler import shuffle_exam
from app.services.docx_exporter import create_exam_document
from app.services.diagram_generator import auto_attach_diagrams_to_exam
from app.services.models import Part1Question, Option, ExamStructure, calculate_exam_scoring

def export_to_bytes(exam, red_answers=False):
    doc = create_exam_document(exam, include_explanations=True, red_answers=red_answers)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()

def test_math_mock():
    print("Testing Math 12 Mock Exam diagrams...")
    exam = get_mock_math_exam()
    q1 = exam.part1_mcq[0]
    q2 = exam.part1_mcq[1]
    q5 = exam.part1_mcq[4]
    
    assert q1.image_base64 is not None and "data:image/png;base64," in q1.image_base64, "Q1 should have variation table"
    assert q2.image_base64 is not None and "data:image/png;base64," in q2.image_base64, "Q2 should have cubic graph"
    assert q5.image_base64 is not None and "data:image/png;base64," in q5.image_base64, "Q5 should have rational graph"
    print(f"  [PASS] Math 12: Q1 len={len(q1.image_base64)}, Q2 len={len(q2.image_base64)}, Q5 len={len(q5.image_base64)}")
    
    # Export to DOCX
    docx_bytes = export_to_bytes(exam, red_answers=True)
    assert len(docx_bytes) > 50000, f"DOCX size too small: {len(docx_bytes)}"
    print(f"  [PASS] Math 12 DOCX exported successfully! Size: {len(docx_bytes):,} bytes")

def test_physics_mock():
    print("Testing Physics Mock Exam diagrams...")
    exam = get_mock_physics_exam()
    q1 = exam.part1_mcq[0]
    q2 = exam.part1_mcq[1]
    
    assert q1.image_base64 is not None and "data:image/png;base64," in q1.image_base64, "Q1 should have oscillation graph"
    assert q2.image_base64 is not None and "data:image/png;base64," in q2.image_base64, "Q2 should have thermodynamic cycle"
    print(f"  [PASS] Physics: Q1 len={len(q1.image_base64)}, Q2 len={len(q2.image_base64)}")
    
    docx_bytes = export_to_bytes(exam, red_answers=True)
    assert len(docx_bytes) > 50000, f"DOCX size too small: {len(docx_bytes)}"
    print(f"  [PASS] Physics DOCX exported successfully! Size: {len(docx_bytes):,} bytes")

def test_chemistry_mock():
    print("Testing Chemistry Mock Exam diagrams...")
    exam = get_mock_chemistry_exam()
    q1 = exam.part1_mcq[0]
    q2 = exam.part1_mcq[1]
    
    assert q1.image_base64 is not None and "data:image/png;base64," in q1.image_base64, "Q1 should have titration graph"
    assert q2.image_base64 is not None and "data:image/png;base64," in q2.image_base64, "Q2 should have precipitation graph"
    print(f"  [PASS] Chemistry: Q1 len={len(q1.image_base64)}, Q2 len={len(q2.image_base64)}")
    
    docx_bytes = export_to_bytes(exam, red_answers=True)
    assert len(docx_bytes) > 50000, f"DOCX size too small: {len(docx_bytes)}"
    print(f"  [PASS] Chemistry DOCX exported successfully! Size: {len(docx_bytes):,} bytes")

def test_biology_mock():
    print("Testing Biology Mock Exam diagrams...")
    exam = get_mock_biology_exam()
    q1 = exam.part1_mcq[0]
    q2 = exam.part1_mcq[1]
    
    assert q1.image_base64 is not None and "data:image/png;base64," in q1.image_base64, "Q1 should have pedigree chart"
    assert q2.image_base64 is not None and "data:image/png;base64," in q2.image_base64, "Q2 should have population curve"
    print(f"  [PASS] Biology: Q1 len={len(q1.image_base64)}, Q2 len={len(q2.image_base64)}")
    
    docx_bytes = export_to_bytes(exam, red_answers=True)
    assert len(docx_bytes) > 50000, f"DOCX size too small: {len(docx_bytes)}"
    print(f"  [PASS] Biology DOCX exported successfully! Size: {len(docx_bytes):,} bytes")

def test_shuffling_preserves_images():
    print("Testing Shuffling with diagrams...")
    exam = get_mock_math_exam()
    variants = shuffle_exam(exam, num_variants=4).variants
    assert len(variants) == 4
    for v in variants:
        img_count = sum(1 for q in v.exam.part1_mcq if q.image_base64)
        assert img_count == 3, f"Variant {v.code} expected 3 images, got {img_count}"
    print(f"  [PASS] All 4 variants preserved exact image attachments!")

def test_auto_attach():
    print("Testing auto_attach_diagrams_to_exam...")
    raw_exam = ExamStructure(
        title="ĐỀ KIỂM TRA ĐỊNH KỲ TOÁN 12",
        subject="Toán học",
        grade="12",
        duration_minutes=50,
        school_name="Trường THPT",
        academic_year="2026-2027",
        code="101",
        part1_mcq=[
            Part1Question(
                id=1,
                question="Cho hàm số có bảng biến thiên như sau. Tìm cực đại của hàm số.",
                options=[Option(label="A", text="1"), Option(label="B", text="2"), Option(label="C", text="3"), Option(label="D", text="4")],
                answer="A",
                explanation="Giải thích"
            ),
            Part1Question(
                id=2,
                question="Cho hàm số bậc bốn trùng phương có đồ thị như hình vẽ bên. Tìm số điểm cực trị.",
                options=[Option(label="A", text="3"), Option(label="B", text="1"), Option(label="C", text="2"), Option(label="D", text="0")],
                answer="A",
                explanation="Giải thích"
            )
        ],
        part2_tf=[],
        part3_short=[],
        part4_essay=[],
        scoring=calculate_exam_scoring(num_p1=2, num_p2=0, num_p3=0, num_p4=0)
    )
    attached = auto_attach_diagrams_to_exam(raw_exam)
    assert attached.part1_mcq[0].image_base64 is not None, "Auto-attached BBT failed"
    assert attached.part1_mcq[1].image_base64 is not None, "Auto-attached Quartic graph failed"
    print("  [PASS] auto_attach_diagrams_to_exam successfully attached diagrams based on question context!")

if __name__ == "__main__":
    test_math_mock()
    test_physics_mock()
    test_chemistry_mock()
    test_biology_mock()
    test_shuffling_preserves_images()
    test_auto_attach()
    print("\nALL DIAGRAM TESTS PASSED 100%!")
