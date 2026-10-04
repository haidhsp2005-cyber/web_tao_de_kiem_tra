import unittest
import re
from app.services.docx_exporter import latex_to_omml, add_formatted_text_with_math
import docx

from app.services.exam_auditor import auto_wrap_and_sanitize_math
from app.services.docx_exporter import latex_to_omml, add_formatted_text_with_math
import docx

class TestMathSanitization(unittest.TestCase):
    def test_cases_from_user_screenshots(self):
        # Image 1, Câu 4: 3\sqrt{3} cm, 2\sqrt{3} cm
        self.assertEqual(auto_wrap_and_sanitize_math("3\\sqrt{3} cm"), "$3\\sqrt{3}$ cm")
        self.assertEqual(auto_wrap_and_sanitize_math("2\\sqrt{3} cm"), "$2\\sqrt{3}$ cm")
        
        # Image 1, Câu 2: m khác 1, m khác 0, m khác -1
        self.assertEqual(auto_wrap_and_sanitize_math("m khác 1"), "$m \\neq 1$")
        self.assertEqual(auto_wrap_and_sanitize_math("m khác 0"), "$m \\neq 0$")
        self.assertEqual(auto_wrap_and_sanitize_math("m khác -1"), "$m \\neq -1$")

        # Image 1, Câu 3: căn 2
        self.assertEqual(auto_wrap_and_sanitize_math("căn 2"), "$\\sqrt{2}$")

        # Image 1, Câu 4: C^ = 30°
        self.assertEqual(auto_wrap_and_sanitize_math("C^ = 30°"), "$\\widehat{C} = 30^\\circ$")

        # Image 2, Câu 1: cosB + cosC = 1.2
        res_cos = auto_wrap_and_sanitize_math("Tổng cosB + cosC = 1.2.")
        self.assertEqual(res_cos, "Tổng $\\cos B + \\cos C = 1.2$.")

        # Image 2, Câu 1: tanC = 0.75
        res_tanC = auto_wrap_and_sanitize_math("Giá trị của tanC = 0.75.")
        self.assertEqual(res_tanC, "Giá trị của $\\tan C = 0.75$.")

        # Image 2, Câu 1: sinB = 0.8
        res_sinB = auto_wrap_and_sanitize_math("Giá trị của sinB = 0.8.")
        self.assertEqual(res_sinB, "Giá trị của $\\sin B = 0.8$.")

        # Multi-clause: sinB = 0.8 và cosB + cosC = 1.2 (without eating 'và')
        res_multi = auto_wrap_and_sanitize_math("sinB = 0.8 và cosB + cosC = 1.2")
        self.assertEqual(res_multi, "$\\sin B = 0.8$ và $\\cos B + \\cos C = 1.2$")

        # Image 2, Câu 2: sin^2\alpha - cos^2\alpha = 1
        res_sin = auto_wrap_and_sanitize_math("a) sin^2\\alpha - cos^2\\alpha = 1.")
        self.assertEqual(res_sin, "a) $\\sin^2\\alpha - \\cos^2\\alpha = 1$.")

        # Image 2, Câu 2: tan\alpha \cdot cot\alpha = 1
        res_tan = auto_wrap_and_sanitize_math("b) tan\\alpha \\cdot cot\\alpha = 1.")
        self.assertEqual(res_tan, "b) $\\tan\\alpha \\cdot \\cot\\alpha = 1$.")

        # Image 2, Câu 2: Cho góc nhọn \alpha bất kỳ
        res_alpha = auto_wrap_and_sanitize_math("Cho góc nhọn \\alpha bất kỳ.")
        self.assertEqual(res_alpha, "Cho góc nhọn $\\alpha$ bất kỳ.")

        # Image 2, Câu 4: { 2x - y = 3 / x + 2y = 4
        res_sys = auto_wrap_and_sanitize_math("Cho hệ phương trình bậc nhất hai ẩn: { 2x - y = 3 / x + 2y = 4. Các phát biểu sau đúng hay sai?")
        self.assertIn("\\begin{cases}", res_sys)

        # Word document formatting test
        doc = docx.Document()
        p = doc.add_paragraph()
        add_formatted_text_with_math(p, "Cạnh bằng 3\\sqrt{3} cm với m khác 1, góc C^ = 30° và sinB = 0.8 và cosB + cosC = 1.2")
        self.assertTrue(len(p.runs) > 0 or len(p._p.xpath('.//*[local-name()="oMath"]')) > 0)

        print("[PASS] All formula sanitizations match expected LaTeX format and docx export succeeds!")

if __name__ == '__main__':
    unittest.main()
