import sys
import asyncio
sys.stdout.reconfigure(encoding="utf-8")

from app.services.models import ExamStructure, Part1Question, Part2Question, Part3Question, Option, SubItem
from app.services.exam_auditor import audit_and_verify_exam, is_short_defective, is_tf_defective

async def test_auditor():
    # 1. Create exam with defective Part 3 (exact case from user screenshot)
    # and defective Part 2 (all True)
    broken_exam = ExamStructure(
        title="ĐỀ KIỂM TRA TOÁN 9",
        subject="Toán học",
        grade="9",
        duration_minutes=45,
        school_name="TRƯỜNG THCS...",
        academic_year="2026 - 2027",
        code="101",
        part1_mcq=[
            Part1Question(
                id=1,
                question="Căn bậc hai số học của 9 là:",
                options=[
                    Option(label="A", text="3"),
                    Option(label="B", text="-3"),
                    Option(label="C", text="81"),
                    Option(label="D", text="Phương án khác")  # Garbage option
                ],
                answer="A",
                explanation="Căn bậc hai số học của 9 là 3. Chọn A."
            )
        ],
        part2_tf=[
            Part2Question(
                id=1,
                question=r"Cho hệ phương trình $\left\{\begin{matrix} x + y = 3 \\ 2x - y = 3 \end{matrix}\right.$. Xét tính đúng sai:",
                sub_items=[
                    SubItem(label="a", statement="Cặp số (2; 1) là nghiệm của hệ.", is_correct=True, explanation="Đúng"),
                    SubItem(label="b", statement="Cộng hai phương trình ta được 3x = 6.", is_correct=True, explanation="Đúng"),
                    SubItem(label="c", statement="Biểu thức P = x^2 + y^2 = 5.", is_correct=True, explanation="Đúng"),
                    SubItem(label="d", statement="Hệ phương trình có vô số nghiệm.", is_correct=True, explanation="Đúng") # 4 True!
                ],
                explanation="Xét tính đúng sai của hệ phương trình."
            )
        ],
        part3_short=[
            Part3Question(
                id=1,
                # The exact broken question from user's screenshot:
                question=r"Cho hệ phương trình $\left\{\begin{matrix} 3x + my = 2 \\ x + 2y = 1 \end{matrix}",
                answer="",
                explanation=""
            )
        ],
        part4_essay=[]
    )

    print("Initial checks:")
    print("Part 1 defective?:", [o.text for o in broken_exam.part1_mcq[0].options])
    print("Part 2 defective?:", is_tf_defective(broken_exam.part2_tf[0]))
    print("Part 3 defective?:", is_short_defective(broken_exam.part3_short[0]))

    # Run audit and offline verify
    healed_exam = await audit_and_verify_exam(broken_exam, api_key=None)

    print("\n--- After AI Auditor Offline Healing ---")
    print("Part 1 Options:", [f"{o.label}. {o.text}" for o in healed_exam.part1_mcq[0].options])
    print("Part 1 Answer:", healed_exam.part1_mcq[0].answer)
    print("Part 2 Stem:", healed_exam.part2_tf[0].question)
    print("Part 2 Subitems True/False:", [(s.label, s.is_correct, s.explanation[:35]) for s in healed_exam.part2_tf[0].sub_items])
    print("Part 2 True count:", sum(1 for s in healed_exam.part2_tf[0].sub_items if s.is_correct))
    print("Part 3 Stem:", healed_exam.part3_short[0].question)
    print("Part 3 Answer:", healed_exam.part3_short[0].answer)
    print("Part 3 Explanation:", healed_exam.part3_short[0].explanation)
    print("Audit Quality Score:", healed_exam.audit_report.quality_score)
    print("Audit Notes:", healed_exam.audit_report.notes)

    # Assertions
    assert not any("phương án khác" in o.text.lower() for o in healed_exam.part1_mcq[0].options), "P1 still has garbage option"
    assert 1 <= sum(1 for s in healed_exam.part2_tf[0].sub_items if s.is_correct) <= 3, "P2 must have 1 to 3 True"
    assert "$" in healed_exam.part3_short[0].question and healed_exam.part3_short[0].question.count("$") % 2 == 0, "P3 must have balanced $"
    assert "\\begin{cases}" in healed_exam.part3_short[0].question, "P3 must use cases"
    assert len(healed_exam.part3_short[0].answer) > 0, "P3 answer must not be empty"
    print("\n>>> ALL AUDITOR ASSERTIONS PASSED! <<<")

if __name__ == "__main__":
    asyncio.run(test_auditor())
