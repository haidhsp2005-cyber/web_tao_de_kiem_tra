import sys
import unittest
from app.services.models import Part1Question, Option
from app.services.exam_auditor import heal_cubic_graph_mcq, heal_quartic_graph_mcq, heal_rational_graph_mcq

sys.stdout.reconfigure(encoding='utf-8')

class TestGraphMCQHealing(unittest.TestCase):
    def test_case_1_cubic_graph_intercept_healed(self):
        """
        Câu 3 (Người dùng phản ánh):
        Đồ thị trong hình đi qua điểm (0; 2) trên trục tung, đạt cực đại tại (-1; 4) và cực tiểu tại (1; 0).
        Hàm số chính xác phải là y = x^3 - 3x + 2.
        Tuy nhiên cả 4 đáp án A, B, C, D đều có hệ số tự do là +1 hoặc -1.
        -> Hệ thống phải tự động chuẩn hóa đáp án thành y = x^3 - 3x + 2 khớp 100%.
        """
        q = Part1Question(
            id=3,
            question="Đường cong trong hình vẽ bên là đồ thị của hàm số nào dưới đây?",
            options=[
                Option(label="A", text="$y = x^3 - 3x + 1$"),
                Option(label="B", text="$y = -x^3 + 3x + 1$"),
                Option(label="C", text="$y = x^3 - 3x - 1$"),
                Option(label="D", text="$y = -x^3 + 3x - 1$")
            ],
            answer="A",
            explanation="Chọn A."
        )
        
        healed_q, mod, msg = heal_cubic_graph_mcq(q)
        self.assertTrue(mod, "Hàm kiểm định đồ thị bậc ba phải kích hoạt sửa lỗi!")
        self.assertIn("x^3 - 3x + 2", healed_q.options[0].text, "Phương án A phải được sửa thành y = x^3 - 3x + 2")
        self.assertEqual(healed_q.answer, "A")
        self.assertIn("(-1; 4)", healed_q.explanation)
        self.assertIn("(1; 0)", healed_q.explanation)
        self.assertIn("(0; 2)", healed_q.explanation)
        print(f"[PASS] Case 1 (Cubic): {msg}")

    def test_case_2_quartic_graph_formula_healed(self):
        """
        Câu 8 (Người dùng phản ánh):
        Đồ thị hàm bậc bốn trùng phương có cực đại tại (0; -1) và cực tiểu tại (±1; -2).
        Hàm số chính xác phải là y = x^4 - 2x^2 - 1.
        Không có đáp án nào khớp (Đáp án A là x^4 + 2x^2 - 1; Đáp án C là x^4 - 2x^2 + 1).
        -> Hệ thống phải tự động chuẩn hóa đáp án thành y = x^4 - 2x^2 - 1 khớp 100%.
        """
        q = Part1Question(
            id=8,
            question="Đường cong trong hình vẽ bên là đồ thị của hàm số bậc bốn trùng phương nào dưới đây?",
            options=[
                Option(label="A", text="$y = x^4 + 2x^2 - 1$"),
                Option(label="B", text="$y = -x^4 + 2x^2 - 1$"),
                Option(label="C", text="$y = x^4 - 2x^2 + 1$"),
                Option(label="D", text="$y = x^4 + 2x^2 + 1$")
            ],
            answer="A",
            explanation="Chọn A."
        )
        
        healed_q, mod, msg = heal_quartic_graph_mcq(q)
        self.assertTrue(mod, "Hàm kiểm định đồ thị trùng phương phải kích hoạt sửa lỗi!")
        self.assertIn("x^4 - 2x^2 - 1", healed_q.options[0].text, "Phương án A phải được sửa thành y = x^4 - 2x^2 - 1")
        self.assertEqual(healed_q.answer, "A")
        self.assertIn("(0; -1)", healed_q.explanation)
        print(f"[PASS] Case 2 (Quartic): {msg}")

    def test_case_3_rational_graph_sign_typo_healed(self):
        """
        Câu 9 (Người dùng phản ánh):
        Đồ thị hàm phân thức có tiệm cận ngang y=2, tiệm cận đứng x=1 và cắt trục hoành tại x = -0.5 (âm).
        Hàm số chính xác phải là y = (2x+1)/(x-1).
        Phương án A ghi y = (2x-1)/(x-1) (cắt trục hoành tại x = 0.5 dương) là lỗi đánh máy về dấu.
        -> Hệ thống phải tự động sửa lỗi dấu trừ thành dấu cộng thành y = (2x+1)/(x-1) khớp 100%.
        """
        q = Part1Question(
            id=9,
            question="Cho hàm số phân thức hữu tỉ có đồ thị như hình vẽ bên. Đồ thị trong hình là của hàm số nào?",
            options=[
                Option(label="A", text="$y = \\frac{2x-1}{x-1}$"),  # Lỗi dấu trừ ở tử số
                Option(label="B", text="$y = \\frac{x+1}{x-1}$"),
                Option(label="C", text="$y = \\frac{2x+1}{x+1}$"),
                Option(label="D", text="$y = \\frac{x-2}{x-1}$")
            ],
            answer="A",
            explanation="Chọn A."
        )
        
        healed_q, mod, msg = heal_rational_graph_mcq(q)
        self.assertTrue(mod, "Hàm kiểm định đồ thị phân thức phải kích hoạt sửa lỗi!")
        self.assertIn("2x+1", healed_q.options[0].text, "Phương án A phải được sửa dấu thành 2x+1")
        self.assertIn("x-1", healed_q.options[0].text)
        self.assertEqual(healed_q.answer, "A")
        self.assertIn("-0.5", healed_q.explanation)
        print(f"[PASS] Case 3 (Rational): {msg}")

if __name__ == "__main__":
    unittest.main()
