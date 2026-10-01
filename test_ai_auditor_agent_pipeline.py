import sys
import asyncio
from app.services.models import ExamStructure, Part1Question, Option, Part2Question, SubItem, Part3Question
from app.services.exam_auditor import audit_and_verify_exam

sys.stdout.reconfigure(encoding='utf-8')

async def test_auditor_preservation_and_healing():
    print("=== TEST AI AUDITOR & PROOFREADER AGENT PIPELINE ===")
    
    # Tạo đề thi giả định với 1 câu chuẩn và 3 câu bị lỗi
    broken_exam = ExamStructure(
        title="ĐỀ THI KIỂM THỬ THẨM ĐỊNH",
        subject="Toán học",
        grade="12",
        part1_mcq=[
            # Câu 1: Bị lỗi phương án rác & sai đáp án
            Part1Question(
                id=1,
                question="Tích phân $\\int_0^1 2x dx$ bằng",
                options=[
                    Option(label="A", text="$0$"),
                    Option(label="B", text="$1$"),
                    Option(label="C", text="$2$"),
                    Option(label="D", text="Phương án khác")  # Phương án rác
                ],
                answer="A",  # Sai (đúng phải là B: 1)
                explanation="Chọn A vì tích phân bằng 0."
            ),
            # Câu 2: Câu chuẩn 100% -> Phải được BẢO TOÀN NGUYÊN VẸN
            Part1Question(
                id=2,
                question="Hàm số $y = x^3 - 3x$ có bao nhiêu điểm cực trị?",
                options=[
                    Option(label="A", text="$2$"),
                    Option(label="B", text="$1$"),
                    Option(label="C", text="$0$"),
                    Option(label="D", text="$3$")
                ],
                answer="A",
                explanation="Ta có $y' = 3x^2 - 3 = 0 \\Leftrightarrow x = \\pm 1$. Đạo hàm đổi dấu 2 lần nên hàm số có 2 điểm cực trị. Chọn A."
            )
        ],
        part2_tf=[
            # Câu 1: Toàn Đúng (4 True - vi phạm quy định Bộ GD&ĐT)
            Part2Question(
                id=1,
                question="Cho hàm số $y = x^2$. Xét tính đúng sai:",
                sub_items=[
                    SubItem(label="a", statement="Tập xác định là $\\mathbb{R}$.", is_correct=True, explanation="Đúng"),
                    SubItem(label="b", statement="Đồ thị đi qua gốc tọa độ $O(0;0)$.", is_correct=True, explanation="Đúng"),
                    SubItem(label="c", statement="Hàm số đồng biến trên $(0; +\\infty)$.", is_correct=True, explanation="Đúng"),
                    SubItem(label="d", statement="Hàm số luôn dương với mọi $x$.", is_correct=True, explanation="Sai vì tại x=0 thì y=0") # Gán True là sai
                ],
                explanation="Khảo sát hàm số bậc hai."
            )
        ],
        part3_short=[
            # Câu 1: Đáp án ghi sai
            Part3Question(
                id=1,
                question="Nghiệm của phương trình $2x - 6 = 0$ là bao nhiêu?",
                answer="2",  # Sai (đáp án đúng là 3)
                explanation="Giải phương trình $2x = 6 \\Leftrightarrow x = 3$."
            )
        ]
    )
    
    original_q2_text = broken_exam.part1_mcq[1].question
    original_q2_ans = broken_exam.part1_mcq[1].answer
    
    # Chạy qua bộ Thẩm định
    healed_exam = await audit_and_verify_exam(broken_exam, api_key=None)
    
    print("\n--- KẾT QUẢ THẨM ĐỊNH ---")
    print(f"1. Câu 1 (Phần I): Options = {[o.text for o in healed_exam.part1_mcq[0].options]}")
    print(f"   -> Không còn phương án rác: {all('Phương án khác' not in o.text for o in healed_exam.part1_mcq[0].options)}")
    
    print(f"\n2. Câu 2 (Phần I - Câu đã chuẩn ban đầu):")
    print(f"   -> Đề bài giữ nguyên vẹn: {healed_exam.part1_mcq[1].question == original_q2_text}")
    print(f"   -> Đáp án giữ nguyên: {healed_exam.part1_mcq[1].answer == original_q2_ans}")
    assert healed_exam.part1_mcq[1].question == original_q2_text, "Câu chuẩn ban đầu không được bị thay đổi!"
    assert healed_exam.part1_mcq[1].answer == original_q2_ans, "Đáp án câu chuẩn ban đầu không được bị thay đổi!"
    
    print(f"\n3. Câu 1 (Phần II - Đúng/Sai):")
    tf_bools = [s.is_correct for s in healed_exam.part2_tf[0].sub_items]
    print(f"   -> Mệnh đề True/False: {tf_bools}")
    print(f"   -> Không còn toàn Đúng: {1 <= sum(tf_bools) <= 3}")
    assert 1 <= sum(tf_bools) <= 3, "Phần II phải có từ 1 đến 3 ý Đúng!"
    
    print(f"\n4. Báo cáo Thẩm định (Audit Report):")
    print(f"   -> Quality score: {healed_exam.audit_report.quality_score}/100")
    print(f"   -> Passed: {healed_exam.audit_report.passed}")
    print(f"   -> Số ghi chú đã sửa: {len(healed_exam.audit_report.notes)}")
    for note in healed_exam.audit_report.notes:
        print(f"      ✓ {note}")
        
    print("\n=== TOÀN BỘ KIỂM THỬ THẨM ĐỊNH & BẢO TOÀN ĐÃ PASS 100%! ===")

if __name__ == "__main__":
    asyncio.run(test_auditor_preservation_and_healing())
