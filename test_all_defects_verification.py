import sys
import unittest
from app.services.models import ExamStructure, Part1Question, Part2Question, Part3Question, Option, SubItem
from app.services.math_solver import UniversalMathEngine
from app.services.exam_auditor import auto_heal_math_questions

class TestAllUserDefectsVerification(unittest.TestCase):

    def test_defect_1_two_numbers(self):
        # Phần I - Câu 3: Tổng 59, hai lần số lớn trừ ba lần số bằng 7 (typo thiếu chữ nhỏ, nghiệm lẻ)
        q = Part1Question(
            id=3,
            question="Tìm hai số tự nhiên biết tổng của chúng bằng 59 và hai lần số lớn trừ ba lần số bằng 7.",
            options=[
                Option(label="A", text="35 và 24"),
                Option(label="B", text="36 và 23"),
                Option(label="C", text="37 và 22"),
                Option(label="D", text="38 và 21")
            ],
            answer="D",
            explanation="Giải sai..."
        )
        exam = ExamStructure(
            title="ĐỀ KIỂM TRA TOÁN", subject="Toán học", grade="9",
            duration_minutes=45, code="101",
            part1_mcq=[q], part2_tf=[], part3_short=[]
        )
        healed_exam, notes = auto_heal_math_questions(exam)
        h_q = healed_exam.part1_mcq[0]
        self.assertIn("ba lần số nhỏ bằng", h_q.question)
        self.assertIn("13", h_q.question)
        self.assertEqual(h_q.answer, "D")
        self.assertIn("38", h_q.options[3].text)
        self.assertIn("21", h_q.options[3].text)
        print("[PASS] Defect 1: Two numbers problem healed with integer roots 38 & 21.")

    def test_defect_2_motion(self):
        # Phần I - Câu 4: Một ô tô dự định đi quãng đường 120 km trong thời gian nhất định. Nếu tăng vận tốc thêm 10 km/h thì đến sớm hơn 24 phút.
        # Phương trình: 120/v - 120/(v+10) = 24/60 = 0.4 => v = 50 km/h. AI từng đánh dấu D (40 km/h).
        q = Part1Question(
            id=4,
            question="Một ô tô dự định đi quãng đường 120 km. Nếu vận tốc tăng thêm 10 km/h thì đến sớm 24 phút (2/5 giờ). Tính vận tốc dự định của ô tô.",
            options=[
                Option(label="A", text="30 km/h"),
                Option(label="B", text="45 km/h"),
                Option(label="C", text="50 km/h"),
                Option(label="D", text="40 km/h")
            ],
            answer="D", # AI marked D incorrectly
            explanation="Vận tốc là 40 km/h..."
        )
        exam = ExamStructure(
            title="ĐỀ KIỂM TRA TOÁN", subject="Toán học", grade="9",
            duration_minutes=45, code="101",
            part1_mcq=[q], part2_tf=[], part3_short=[]
        )
        healed_exam, notes = auto_heal_math_questions(exam)
        h_q = healed_exam.part1_mcq[0]
        self.assertEqual(h_q.answer, "C") # Fixed to 50 km/h
        self.assertIn("C", h_q.explanation)
        print("[PASS] Defect 2: Motion problem answer corrected from D to C (50 km/h).")

    def test_defect_3_rectangle_perimeter_100(self):
        # Phần I - Câu 7: Chu vi 100m, giảm dài 2m tăng rộng 3m diện tích tăng 32 m2 (dẫn đến nghiệm lẻ 27.6).
        # Sửa thành 34 m2 để có nghiệm dài 28m, rộng 22m khớp phương án.
        q = Part1Question(
            id=7,
            question="Một mảnh đất hình chữ nhật có chu vi bằng 100 m. Nếu giảm chiều dài đi 2 m và tăng chiều rộng thêm 3 m thì diện tích tăng thêm 32 m^2. Tính chiều dài và chiều rộng.",
            options=[
                Option(label="A", text="30 m và 20 m"),
                Option(label="B", text="26 m và 24 m"),
                Option(label="C", text="25 m và 25 m"),
                Option(label="D", text="28 m và 22 m")
            ],
            answer="D",
            explanation="Chiều dài là 28m..."
        )
        exam = ExamStructure(
            title="ĐỀ KIỂM TRA TOÁN", subject="Toán học", grade="9",
            duration_minutes=45, code="101",
            part1_mcq=[q], part2_tf=[], part3_short=[]
        )
        healed_exam, notes = auto_heal_math_questions(exam)
        h_q = healed_exam.part1_mcq[0]
        self.assertIn("34", h_q.question)
        self.assertEqual(h_q.answer, "D")
        print("[PASS] Defect 3: Rectangle perimeter 100m area increase healed to 34 m2.")

    def test_defect_4_pipes_problem(self):
        # Phần I - Câu 15: Hai vòi nước cùng chảy trong 12/5 giờ thì đầy bể. Nếu vòi 1 chảy trong 2 giờ và vòi 2 chảy trong 3/2 giờ (1.5 giờ) thì được 3/4 bể.
        # Hệ: 1/x + 1/y = 5/12 và 2/x + 1.5/y = 3/4 => x = 4h, y = 6h. Hỏi vòi thứ nhất chảy một mình trong bao lâu?
        # AI từng đánh dấu B (6 giờ - vòi 2). CAS phải sửa thành D (4 giờ - vòi 1).
        q = Part1Question(
            id=15,
            question=r"Hai vòi nước cùng chảy vào một bể không có nước thì sau $\frac{12}{5}$ giờ đầy bể. Nếu vòi thứ nhất chảy trong 2 giờ và vòi thứ hai chảy trong $\frac{3}{2}$ giờ thì được $\frac{3}{4}$ bể. Hỏi vòi thứ nhất chảy một mình trong bao lâu thì đầy bể?",
            options=[
                Option(label="A", text="3 giờ"),
                Option(label="B", text="6 giờ"),
                Option(label="C", text="5 giờ"),
                Option(label="D", text="4 giờ")
            ],
            answer="B", # AI mistook Pipe 2 for Pipe 1
            explanation="Vòi 1 chảy trong 6 giờ..."
        )
        exam = ExamStructure(
            title="ĐỀ KIỂM TRA TOÁN", subject="Toán học", grade="9",
            duration_minutes=45, code="101",
            part1_mcq=[q], part2_tf=[], part3_short=[]
        )
        healed_exam, notes = auto_heal_math_questions(exam)
        h_q = healed_exam.part1_mcq[0]
        self.assertEqual(h_q.answer, "D") # Corrected to 4 hours
        self.assertIn("4", h_q.options[3].text)
        print("[PASS] Defect 4: Water pipes question target verified: Pipe 1 = 4 hours (D).")

    def test_defect_5_quadratic_expression(self):
        # Phần I - Câu 18: Hệ 4x - 3y = 2 và x + 3y = 8 => x=2, y=2 => P = x^2 + y^2 = 8.
        # Phương án gốc của AI không có 8 (chỉ có 25, 6, 13, 10), AI đánh dấu B (6). CAS phải sửa đáp án B thành 8.
        q = Part1Question(
            id=18,
            question=r"Cho hệ phương trình $\begin{cases} 4x - 3y = 2 \\ x + 3y = 8 \end{cases}$ có nghiệm $(x; y)$. Tính giá trị của biểu thức $P = x^2 + y^2$.",
            options=[
                Option(label="A", text="$P = 25$"),
                Option(label="B", text="$P = 6$"),
                Option(label="C", text="$P = 13$"),
                Option(label="D", text="$P = 10$")
            ],
            answer="B",
            explanation="P = 6..."
        )
        exam = ExamStructure(
            title="ĐỀ KIỂM TRA TOÁN", subject="Toán học", grade="9",
            duration_minutes=45, code="101",
            part1_mcq=[q], part2_tf=[], part3_short=[]
        )
        healed_exam, notes = auto_heal_math_questions(exam)
        h_q = healed_exam.part1_mcq[0]
        self.assertIn("8", h_q.options[1].text)
        self.assertEqual(h_q.answer, "B")
        self.assertIn("8", h_q.explanation)
        print("[PASS] Defect 5: Quadratic expression P = x^2 + y^2 = 8 correctly inserted into options and explanation.")

    def test_defect_6_sol_pair_verification(self):
        # Phần I - Câu 20: Hệ 2x + 3y = 7 và x - 3y = 2 => (3; 1/3). AI từng chọn D (3; 1).
        q = Part1Question(
            id=20,
            question=r"Nghiệm của hệ phương trình $\begin{cases} 2x + 3y = 7 \\ x - 3y = 2 \end{cases}$ là cặp số $(x; y)$ bằng",
            options=[
                Option(label="A", text=r"$(1; \frac{5}{3})$"),
                Option(label="B", text=r"$(2; 1)$"),
                Option(label="C", text=r"$(3; \frac{1}{3})$"),
                Option(label="D", text=r"$(3; 1)$")
            ],
            answer="D", # AI selected (3; 1)
            explanation="Chọn (3; 1)..."
        )
        exam = ExamStructure(
            title="ĐỀ KIỂM TRA TOÁN", subject="Toán học", grade="9",
            duration_minutes=45, code="101",
            part1_mcq=[q], part2_tf=[], part3_short=[]
        )
        healed_exam, notes = auto_heal_math_questions(exam)
        h_q = healed_exam.part1_mcq[0]
        self.assertEqual(h_q.answer, "C")
        self.assertIn("C", h_q.explanation)
        print("[PASS] Defect 6: Linear system solution pair corrected from D to C (3; 1/3).")

    def test_defect_7_tf_rectangle_delta(self):
        # Phần II - Câu 1: S = 300 m2, tăng dài 5m, giảm rộng 4m => delta = 1525 không chính phương, mâu thuẫn câu c (chiều dài 20m).
        # Phải sửa giảm rộng 4m thành giảm rộng 3m để delta = 2025 = 45^2 và chiều dài 20m chuẩn xác.
        q = Part2Question(
            id=1,
            question="Một mảnh vườn hình chữ nhật có diện tích 300 m^2. Nếu tăng chiều dài thêm 5 m và giảm chiều rộng đi 4 m thì diện tích không đổi. Xét tính đúng/sai:",
            sub_items=[
                SubItem(label="a", statement="Phương trình thay đổi diện tích...", is_correct=True, explanation=""),
                SubItem(label="b", statement="Phương trình diện tích ban đầu là xy = 300.", is_correct=True, explanation=""),
                SubItem(label="c", statement="Chiều dài của mảnh vườn là 20 m.", is_correct=True, explanation=""),
                SubItem(label="d", statement="Chu vi của mảnh vườn ban đầu là 74 m.", is_correct=False, explanation="")
            ],
            explanation=""
        )
        exam = ExamStructure(
            title="ĐỀ KIỂM TRA TOÁN", subject="Toán học", grade="9",
            duration_minutes=45, code="101",
            part1_mcq=[], part2_tf=[q], part3_short=[]
        )
        healed_exam, notes = auto_heal_math_questions(exam)
        h_q = healed_exam.part2_tf[0]
        self.assertIn("giảm chiều rộng đi 3 m", h_q.question)
        self.assertTrue(h_q.sub_items[2].is_correct)
        self.assertFalse(h_q.sub_items[3].is_correct)
        print("[PASS] Defect 7: TF rectangle delta repaired to perfect square with length 20m.")

    def test_defect_8_short_rectangle(self):
        # Phần III - Câu 1: Chu vi 70m, giảm dài 2m tăng rộng 3m diện tích tăng 40 m2 (ra nghiệm lẻ 23.2).
        # Phải sửa thành tăng 24 m2 để chiều dài là 20m.
        q = Part3Question(
            id=1,
            question="Một khu vườn hình chữ nhật có chu vi bằng 70 m. Nếu giảm chiều dài đi 2 m và tăng chiều rộng lên 3 m thì diện tích tăng thêm 40 mét vuông. Tính chiều dài của khu vườn ban đầu.",
            answer="23.2",
            explanation="Chiều dài là 23.2 m"
        )
        exam = ExamStructure(
            title="ĐỀ KIỂM TRA TOÁN", subject="Toán học", grade="9",
            duration_minutes=45, code="101",
            part1_mcq=[], part2_tf=[], part3_short=[q]
        )
        healed_exam, notes = auto_heal_math_questions(exam)
        h_q = healed_exam.part3_short[0]
        self.assertIn("24", h_q.question)
        self.assertEqual(h_q.answer, "20")
        print("[PASS] Defect 8: Short rectangle problem area increase healed to 24 m2 and length to 20m.")

    def test_defect_9_short_work(self):
        # Phần III - Câu 4: 2 người thợ cùng làm 16 giờ, người 1 làm 3h, người 2 làm 2h được 1/5 công việc (nghiệm 40/3).
        # Phải sửa thành 1/6 công việc để người thứ nhất làm một mình trong 24 giờ.
        q = Part3Question(
            id=4,
            question=r"Hai người thợ cùng làm một công việc trong 16 giờ thì xong. Nếu người thứ nhất làm trong 3 giờ và người thứ hai làm trong 2 giờ thì chỉ hoàn thành được $\frac{1}{5}$ công việc. Hỏi nếu làm một mình thì người thứ nhất hoàn thành công việc trong bao nhiêu giờ?",
            answer="24",
            explanation="Người 1 làm trong 24 giờ."
        )
        exam = ExamStructure(
            title="ĐỀ KIỂM TRA TOÁN", subject="Toán học", grade="9",
            duration_minutes=45, code="101",
            part1_mcq=[], part2_tf=[], part3_short=[q]
        )
        healed_exam, notes = auto_heal_math_questions(exam)
        h_q = healed_exam.part3_short[0]
        self.assertIn(r"\frac{1}{6}", h_q.question)
        self.assertEqual(h_q.answer, "24")
        print("[PASS] Defect 9: Short work problem fraction healed to 1/6 and answer to 24 hours.")

    def test_defect_10_short_two_digit(self):
        # Phần III - Câu 5: Số có 2 chữ số: chữ số hàng chục lớn hơn chữ số hàng đơn vị là 2, đổi chỗ thì nhỏ hơn số ban đầu 18.
        # Đây là đồng nhất thức, vô số số. Phải bổ sung điều kiện tổng bình phương các chữ số bằng 52 để số duy nhất là 64 (tổng chữ số 10).
        q = Part3Question(
            id=5,
            question="Tìm một số tự nhiên có hai chữ số, biết rằng chữ số hàng chục lớn hơn chữ số hàng đơn vị là 2 đơn vị. Nếu viết hai chữ số theo thứ tự ngược lại thì được một số mới nhỏ hơn số ban đầu 18 đơn vị. Tính tổng các chữ số của số đó.",
            answer="10",
            explanation="Số đó là 64..."
        )
        exam = ExamStructure(
            title="ĐỀ KIỂM TRA TOÁN", subject="Toán học", grade="9",
            duration_minutes=45, code="101",
            part1_mcq=[], part2_tf=[], part3_short=[q]
        )
        healed_exam, notes = auto_heal_math_questions(exam)
        h_q = healed_exam.part3_short[0]
        self.assertIn("52", h_q.question)
        self.assertEqual(h_q.answer, "10")
        print("[PASS] Defect 10: Two-digit number underdetermined problem healed with independent quadratic condition.")

    def test_defect_11_team_work(self):
        # Phần I - Câu 16: Hai đội cùng làm 4 ngày xong. Đội 1 làm 2 ngày, đội 2 làm 9 ngày xong. (nghiệm 5.6 ngày không có trong options A. 6, B. 8, C. 10, D. 12)
        # Sửa thành: Đội 2 làm 8 ngày để đội 1 làm một mình trong 6 ngày (khớp A).
        q = Part1Question(
            id=16,
            question="Hai đội công nhân cùng làm một công việc trong 4 ngày thì xong. Nếu đội thứ nhất làm 2 ngày và đội thứ hai làm 9 ngày thì cũng xong công việc đó. Hỏi nếu đội thứ nhất làm một mình thì trong bao lâu xong công việc?",
            options=[
                Option(label="A", text="6 ngày"),
                Option(label="B", text="8 ngày"),
                Option(label="C", text="10 ngày"),
                Option(label="D", text="12 ngày")
            ],
            answer="A", # AI marked A (6 ngày)
            explanation="Đội 1 làm 6 ngày..."
        )
        exam = ExamStructure(
            title="ĐỀ KIỂM TRA TOÁN", subject="Toán học", grade="9",
            duration_minutes=45, code="101",
            part1_mcq=[q], part2_tf=[], part3_short=[]
        )
        healed_exam, notes = auto_heal_math_questions(exam)
        h_q = healed_exam.part1_mcq[0]
        self.assertIn("8 ngày", h_q.question)
        self.assertEqual(h_q.answer, "A")
        print("[PASS] Defect 11: Team work problem adjusted to 8 days for Team 2, root 6 days matches Option A.")

    def test_defect_12_percentage_yield(self):
        # Phần I - Câu 17: Hai lớp 9A và 9B trồng 580 cây. 9A vượt 20%, 9B vượt 15%, tổng được 684 cây.
        # Nghiệm thực tế: 9A = 340 cây (không có trong A. 280, B. 300, C. 320, D. 260. AI chọn B. 300).
        # Nếu AI chọn B (300): 1.2*300 + 1.15*280 = 682 cây.
        q = Part1Question(
            id=17,
            question="Hai lớp 9A và 9B trồng được tổng cộng 580 cây. Trong đợt phát động, lớp 9A trồng vượt mức 20% và lớp 9B trồng vượt mức 15% nên cả hai lớp trồng được 684 cây. Số cây lớp 9A trồng ban đầu là:",
            options=[
                Option(label="A", text="280 cây"),
                Option(label="B", text="300 cây"),
                Option(label="C", text="320 cây"),
                Option(label="D", text="260 cây")
            ],
            answer="B", # AI marked B (300 cây)
            explanation="Số cây lớp 9A là 300..."
        )
        exam = ExamStructure(
            title="ĐỀ KIỂM TRA TOÁN", subject="Toán học", grade="9",
            duration_minutes=45, code="101",
            part1_mcq=[q], part2_tf=[], part3_short=[]
        )
        healed_exam, notes = auto_heal_math_questions(exam)
        h_q = healed_exam.part1_mcq[0]
        self.assertIn("682", h_q.question)
        self.assertEqual(h_q.answer, "B")
        print("[PASS] Defect 12: Percentage yield problem actual total corrected to 682, root 300 trees matches Option B.")

    def test_defect_13_rectangle_100m_length_30(self):
        # Phần I - Câu 18: Chu vi 100m (nửa chu vi p=50m). Tăng dài 3m, tăng rộng 2m, diện tích tăng 160m2 (ra nghiệm âm x = -4!).
        # Phải tự động điều chỉnh 160 -> 126 m2 để chiều dài ban đầu là 30m, chiều rộng là 20m.
        q = Part1Question(
            id=18,
            question="Một khu vườn hình chữ nhật có chu vi bằng 100 m. Nếu tăng chiều dài thêm 3 m và tăng chiều rộng thêm 2 m thì diện tích khu vườn tăng thêm 160 m^2. Chiều dài ban đầu của khu vườn là:",
            options=[
                Option(label="A", text="20 m"),
                Option(label="B", text="30 m"),
                Option(label="C", text="25 m"),
                Option(label="D", text="35 m")
            ],
            answer="B", # chiều dài 30m
            explanation="Chiều dài là 30 m..."
        )
        exam = ExamStructure(
            title="ĐỀ KIỂM TRA TOÁN 9", subject="Toán học", grade="9",
            duration_minutes=45, code="101",
            part1_mcq=[q], part2_tf=[], part3_short=[]
        )
        healed_exam, notes = auto_heal_math_questions(exam)
        h_q = healed_exam.part1_mcq[0]
        self.assertIn("126", h_q.question)
        self.assertEqual(h_q.answer, "B")
        self.assertIn("30", h_q.options[1].text)
        print("[PASS] Defect 13: Rectangle 100m perimeter healed delta S to 126 m2, length 30m matches Option B.")

    def test_defect_14_system_product_scalar_options(self):
        # Phần I - Câu 20: Hệ 2x+y=5 và x+y=3. Hỏi giá trị của x*y.
        # Nghiệm là x=2, y=1 => x*y = 2.
        # Options ban đầu bị hallucinate cặp tọa độ: B. (2; 1).
        # Hệ thống phải nhận diện đúng intent là tích ('prod'), không bị nhầm thành tổng 'x+y' do phương trình chứa x+y=3,
        # và làm sạch option B thành vô hướng 2 (hoặc $2$).
        q = Part1Question(
            id=20,
            question=r"Cho hệ phương trình $\begin{cases} 2x + y = 5 \\ x + y = 3 \end{cases}$. Giá trị của biểu thức $x \cdot y$ là:",
            options=[
                Option(label="A", text="1"),
                Option(label="B", text="(2; 1)"),
                Option(label="C", text="3"),
                Option(label="D", text="6")
            ],
            answer="B",
            explanation="Ta có x=2, y=1 nên x*y = 2."
        )
        exam = ExamStructure(
            title="ĐỀ KIỂM TRA TOÁN 9", subject="Toán học", grade="9",
            duration_minutes=45, code="101",
            part1_mcq=[q], part2_tf=[], part3_short=[]
        )
        healed_exam, notes = auto_heal_math_questions(exam)
        h_q = healed_exam.part1_mcq[0]
        self.assertIn(h_q.options[1].text.strip("$ "), ["2", "2.0"])
        self.assertEqual(h_q.answer, "B")
        print("[PASS] Defect 14: Linear system product intent detected correctly, coordinate option sanitized to scalar 2.")

    def test_defect_15_grade9_boat_motion_no_calculus(self):
        # Phần II - Câu 3: Bài toán ca nô xuôi/ngược dòng lớp 9.
        # Đảm bảo không bị lọt câu hỏi giải tích lớp 12 (f'(x) = 0, f''(x) > 0).
        q = Part2Question(
            id=3,
            question="Một ca nô xuôi dòng từ bến A đến bến B cách nhau 30 km rồi ngược dòng trở lại bến A mất tất cả 5 giờ. Biết vận tốc dòng nước là 3 km/h.",
            sub_items=[
                SubItem(label="a", statement="Vận tốc dòng nước là 3 km/h.", is_correct=True, explanation="Đúng"),
                SubItem(label="b", statement="Thời gian xuôi dòng ít hơn thời gian ngược dòng.", is_correct=True, explanation="Đúng"),
                SubItem(label="c", statement="Vận tốc thực của ca nô là 15 km/h.", is_correct=False, explanation="Sai"),
                SubItem(label="d", statement=r"Nếu $f'(x_0) = 0$ và $f''(x_0) > 0$ thì hàm số đạt cực tiểu tại $x_0$.", is_correct=True, explanation="Lọt kiến thức lớp 12")
            ],
            explanation="Giải phương trình ta được vận tốc thực là 13 km/h..."
        )
        exam = ExamStructure(
            title="ĐỀ KIỂM TRA TOÁN 9", subject="Toán học", grade="9",
            duration_minutes=45, code="101",
            part1_mcq=[], part2_tf=[q], part3_short=[]
        )
        healed_exam, notes = auto_heal_math_questions(exam)
        h_q = healed_exam.part2_tf[0]
        for s in h_q.sub_items:
            self.assertNotIn("f'", s.statement)
            self.assertNotIn("cực tiểu", s.statement)
            self.assertNotIn("tiệm cận", s.statement)
        print("[PASS] Defect 15: Grade 9 boat motion question sanitized, 100% calculus leaks eliminated.")

    def test_defect_16_grade9_diagram_no_cubic(self):
        # Phần III - Câu 6: Tìm hệ số góc của đường thẳng y = ax + b đi qua A(1; 3) và B(2; 5).
        # Không được tự tiện gán đồ thị bậc 3 của lớp 12 khi câu hỏi lớp 9 chỉ nói về đồ thị hàm số bậc nhất.
        from app.services.diagram_generator import enrich_exam_with_diagrams
        q = Part3Question(
            id=6,
            question="Tìm hệ số góc a của đường thẳng (d): y = ax + b biết rằng đồ thị đi qua hai điểm A(1; 3) và B(2; 5).",
            answer="2",
            explanation="a = (5 - 3)/(2 - 1) = 2"
        )
        exam = ExamStructure(
            title="ĐỀ KIỂM TRA TOÁN 9", subject="Toán học", grade="9",
            duration_minutes=45, code="101",
            part1_mcq=[], part2_tf=[], part3_short=[q]
        )
        enrich_exam_with_diagrams(exam)
        self.assertIsNone(getattr(q, "image_base64", None))
        
        healed_exam, notes = auto_heal_math_questions(exam)
        self.assertEqual(healed_exam.part3_short[0].answer, "2")
        print("[PASS] Defect 16: Grade 9 linear graph has no stray cubic diagram, slope a = 2 verified.")

    def test_defect_17_english_vocabulary_detection(self):
        # Kiểm tra nhận diện tài liệu từ vựng tiếng Anh (chứa 'lính cứu hỏa' không được nhầm thành Hóa học)
        from app.services.matrix_analyzer import detect_subject_from_text
        from app.services.ai_generator import get_mock_english_exam
        
        vocab_text = """
        Unit 2: City Life
        Advice: lời khuyên
        Useful advice: lời khuyên có ích
        Community: cộng đồng
        Electrician: thợ điện
        Firefighter: lính cứu hỏa
        Garbage collector: người thu gom rác
        """
        detected = detect_subject_from_text(vocab_text)
        self.assertEqual(detected, "Tiếng Anh")
        self.assertNotEqual(detected, "Hóa học")
        
        # Kiểm tra mock exam Tiếng Anh lớp 9 đạt chuẩn cấu trúc
        english_exam = get_mock_english_exam()
        self.assertEqual(english_exam.subject, "Tiếng Anh")
        self.assertEqual(len(english_exam.part1_mcq), 12)
        self.assertEqual(len(english_exam.part2_tf), 2)
        self.assertEqual(len(english_exam.part2_tf[0].sub_items), 4)
        self.assertEqual(len(english_exam.part3_short), 4)
        print("[PASS] Defect 17: English vocabulary detection & mock exam generation verified.")

    def test_defect_18_grade9_curriculum_boundaries(self):
        # Kiểm tra phát hiện và loại bỏ kiến thức vượt cấp lớp 11-12 (xác suất xạ thủ Bernoulli, khoảng cách hình hộp chữ nhật)
        # khỏi đề kiểm tra Toán lớp 9 (ảnh media_1791083683225)
        import asyncio
        from app.services.exam_auditor import audit_and_verify_exam

        q1 = Part3Question(
            id=1,
            question="Một xạ thủ bắn vào bia 3 phát độc lập. Xác suất bắn trúng mỗi phát là 0.8. Tính xác suất để xạ thủ đó bắn trúng đúng 2 phát (kết quả làm tròn đến hàng phần trăm).",
            answer="0.38",
            explanation="Áp dụng công thức Bernoulli: C(3, 2) * 0.8^2 * 0.2 = 0.384..."
        )
        q2 = Part3Question(
            id=2,
            question="Tìm số tự nhiên lớn hơn trong hai số biết tổng của chúng bằng 100, và nếu lấy số lớn chia cho số bé thì được thương là 3 và dư 4.",
            answer="76",
            explanation="Số lớn là 76."
        )
        q3 = Part3Question(
            id=3,
            question="Trong tam giác ABC vuông tại A có AB = 5 cm, BC = 13 cm. Tính giá trị của biểu thức 5 . tan B.",
            answer="12",
            explanation="5 . tan B = 12."
        )
        q4 = Part3Question(
            id=4,
            question="Cho hình hộp chữ nhật ABCD.A'B'C'D' có AB = 3, AD = 4, AA' = 5. Tính khoảng cách giữa hai đường thẳng AB và C'D'.",
            answer="5",
            explanation="Khoảng cách là 5."
        )
        q5 = Part3Question(
            id=5,
            question=r"Tìm giá trị của tham số m để hệ phương trình \begin{cases} x + y = m \\ 2x - y = 3 \end{cases}",
            answer="",
            explanation=""
        )
        q6 = Part3Question(
            id=6,
            question=r"Giải hệ phương trình \begin{cases} 3x - y = 7 \\ x + y = 5 \end{cases}. Tìm giá trị của x.",
            answer="3",
            explanation="x = 3."
        )

        exam = ExamStructure(
            title="ĐỀ KIỂM TRA TOÁN 9",
            subject="Toán học",
            grade="9",
            part1_mcq=[],
            part2_tf=[],
            part3_short=[q1, q2, q3, q4, q5, q6]
        )

        healed = asyncio.run(audit_and_verify_exam(exam))

        # Câu 1 (xạ thủ) phải được thay thế bằng xác suất bi đỏ lớp 9
        self.assertNotIn("xạ thủ", healed.part3_short[0].question.lower())
        self.assertIn("viên bi", healed.part3_short[0].question.lower())
        self.assertEqual(healed.part3_short[0].answer, "0.35")

        # Câu 2 (tìm số) giữ nguyên chuẩn lớp 9
        self.assertEqual(healed.part3_short[1].answer, "76")

        # Câu 3 (tam giác ABC vuông) giữ nguyên chuẩn lớp 9
        self.assertEqual(healed.part3_short[2].answer, "12")

        # Câu 4 (hình hộp chữ nhật) phải được thay thế bằng hình học lớp 9 (hình trụ)
        self.assertNotIn("hình hộp chữ nhật", healed.part3_short[3].question.lower())
        self.assertIn("hình trụ", healed.part3_short[3].question.lower())
        self.assertEqual(healed.part3_short[3].answer, "80")

        # Câu 5 (câu 5 ban đầu bị cụt) phải được hoàn thiện với m = 3
        self.assertIn("thỏa mãn", healed.part3_short[4].question)
        self.assertEqual(healed.part3_short[4].answer, "3")

        # Câu 6 (giải hệ tìm x) giữ nguyên chuẩn lớp 9
        self.assertEqual(healed.part3_short[5].answer, "3")

        print("[PASS] Defect 18: Grade 9 Math curriculum boundaries verified, 100% Grade 11-12 out-of-scope questions eliminated.")

    def test_defect_19_multigrade_curriculum_enforcement(self):
        import asyncio
        from app.services.exam_auditor import audit_and_verify_exam, is_math_out_of_scope_for_grade

        # 1. Direct out-of-scope detector checks across grades
        # Grade 5 (Primary): Square root & negative numbers forbidden
        bad_g5, r5 = is_math_out_of_scope_for_grade(r"Tính giá trị của căn bậc hai $\sqrt{16}$ và số âm $-5$.", "5")
        self.assertTrue(bad_g5)
        good_g5, _ = is_math_out_of_scope_for_grade("Một hình chữ nhật có chiều dài 15 cm và chiều rộng 8 cm. Tính chu vi.", "5")
        self.assertFalse(good_g5)

        # Grade 6 (THCS): Calculus & Oxyz forbidden
        bad_g6, r6 = is_math_out_of_scope_for_grade(r"Tìm đạo hàm của hàm số $y = x^3 - 3x$ và tiệm cận đứng.", "6")
        self.assertTrue(bad_g6)
        good_g6, _ = is_math_out_of_scope_for_grade("Tìm ước chung lớn nhất của 24 và 36.", "6")
        self.assertFalse(good_g6)

        # Grade 10: Calculus & Oxyz forbidden
        bad_g10, r10 = is_math_out_of_scope_for_grade(r"Tính đạo hàm $y' = 3x^2$ và nguyên hàm $\int x dx$.", "10")
        self.assertTrue(bad_g10)
        good_g10, _ = is_math_out_of_scope_for_grade(r"Trong mặt phẳng $Oxy$, cho hai điểm $A(1; 2)$ và $B(3; 4)$. Tìm tọa độ vectơ $\vec{AB}$.", "10")
        self.assertFalse(good_g10)

        # Grade 11: Integrals & Oxyz forbidden
        bad_g11, r11 = is_math_out_of_scope_for_grade(r"Tính tích phân $\int_0^1 (2x + 1)dx$ trong không gian $Oxyz$.", "11")
        self.assertTrue(bad_g11)
        good_g11, _ = is_math_out_of_scope_for_grade(r"Cho cấp số cộng $(u_n)$ có $u_1 = 3$ và công sai $d = 2$. Tính $u_5$.", "11")
        self.assertFalse(good_g11)

        # Grade 12: Calculus & Integrals are ALLOWED
        bad_g12, _ = is_math_out_of_scope_for_grade(r"Tính tích phân $\int_0^1 (2x + 1)dx$ và tìm tiệm cận ngang.", "12")
        self.assertFalse(bad_g12)

        # 2. End-to-end healing on Grade 10 Exam containing Grade 12 calculus questions
        q_g10_bad = Part1Question(
            id=1,
            question=r"Đường tiệm cận ngang của đồ thị hàm số $y = \frac{2x - 1}{x + 1}$ là đường thẳng nào?",
            options=[
                Option(label="A", text=r"$y = 2$"),
                Option(label="B", text=r"$y = -1$"),
                Option(label="C", text=r"$x = 2$"),
                Option(label="D", text=r"$x = -1$")
            ],
            answer="A",
            explanation="Tiệm cận ngang y = 2."
        )
        exam_g10 = ExamStructure(
            title="ĐỀ KIỂM TRA TOÁN 10",
            subject="Toán học",
            grade="10",
            part1_mcq=[q_g10_bad],
            part2_tf=[],
            part3_short=[]
        )
        healed_g10 = asyncio.run(audit_and_verify_exam(exam_g10))
        # The Grade 12 calculus question should be replaced by a Grade 10 appropriate question
        self.assertNotIn("tiệm cận", healed_g10.part1_mcq[0].question.lower())
        self.assertIn("tập xác định", healed_g10.part1_mcq[0].question.lower()) # Grade 10 domain bank

        print("[PASS] Defect 19: Multi-grade curriculum enforcement verified for Grades 5, 6, 10, 11, and 12.")

    def test_defect_20_mcq_system_distractors_and_deduplication(self):
        # Kiểm tra Phần I - Câu 1 và Câu 6 như phản ánh của người dùng:
        # Câu 1: Tìm nghiệm của hệ phương trình {x + y = 5, 2x - y = 1}
        # Đề gốc bị phương án nhiễu Giải tích 12 ("cực trị", "tiệm cận", "nghịch biến").
        # Hệ thống phải tự động chuẩn hóa các phương án nhiễu thành các cặp số (x; y) chuẩn lớp 9.
        # Câu 6: Trùng lặp nội dung với Câu 1, hệ thống phải tự động phát hiện và thay thế bằng câu hỏi khác.
        import asyncio
        from app.services.exam_auditor import audit_and_verify_exam

        q1 = Part1Question(
            id=1,
            question=r"Tìm nghiệm của hệ phương trình $\begin{cases} x + y = 5 \\ 2x - y = 1 \end{cases}$",
            options=[
                Option(label="A", text="Có đúng một điểm cực trị"),
                Option(label="B", text="Nghịch biến trên khoảng xác định"),
                Option(label="C", text="(2; 3)"),
                Option(label="D", text="Đồ thị có tiệm cận đứng")
            ],
            answer="C",
            explanation="Giải hệ phương trình ta được x = 2, y = 3. Nghiệm là (2; 3)."
        )

        q6 = Part1Question(
            id=6,
            question=r"Nghiệm của hệ phương trình $\begin{cases} x + y = 5 \\ 2x - y = 1 \end{cases}$ là:",
            options=[
                Option(label="A", text="(1; 4)"),
                Option(label="B", text="(3; 2)"),
                Option(label="C", text="(4; 1)"),
                Option(label="D", text="(2; 3)")
            ],
            answer="D",
            explanation="Hệ có nghiệm (2; 3)."
        )

        exam = ExamStructure(
            title="ĐỀ KIỂM TRA TOÁN 9",
            subject="Toán học",
            grade="9",
            part1_mcq=[q1, q6],
            part2_tf=[],
            part3_short=[]
        )

        healed = asyncio.run(audit_and_verify_exam(exam))

        # Kiểm tra Câu 1: Không còn phương án cực trị, tiệm cận, nghịch biến
        h1 = healed.part1_mcq[0]
        for opt in h1.options:
            self.assertNotIn("cực trị", opt.text.lower())
            self.assertNotIn("tiệm cận", opt.text.lower())
            self.assertNotIn("nghịch biến", opt.text.lower())
            # Phương án phải là cặp số
            self.assertIn("(", opt.text)
            self.assertIn(")", opt.text)

        # Kiểm tra Câu 6: Không còn trùng lặp hệ phương trình với Câu 1
        h6 = healed.part1_mcq[1]
        self.assertNotIn("x+y=5", h6.question.replace(" ", "").replace("$", "").lower())
        print("[PASS] Defect 20: MCQ system of equations distractors cleaned of calculus terms, duplicate Question 6 replaced.")

    def test_defect_21_tf_context_mismatch_healing(self):
        # Kiểm tra Phần II - Câu 1, 2, 3 bị lỗi 'râu ông nọ cắm cằm bà kia'
        import asyncio
        from app.services.exam_auditor import audit_and_verify_exam, is_tf_context_mismatched

        # Câu 1: Đề hải đăng nhưng mệnh đề là hệ phương trình vô danh
        q1_tf = Part2Question(
            id=1,
            question="Một người quan sát đứng trên đài quan sát của một ngọn hải đăng cao 40 m so với mực nước biển, nhìn thấy một con tàu chở hàng đang neo đậu ngoài khơi với góc hạ là 30 độ...",
            sub_items=[
                SubItem(label="a", statement="Nếu nhân phương trình thứ nhất với 2 rồi cộng với phương trình thứ hai, ta thu được 5x = 10.", is_correct=True),
                SubItem(label="b", statement="Hệ phương trình đã cho vô nghiệm.", is_correct=False),
                SubItem(label="c", statement="Nghiệm của hệ phương trình là (x; y) = (2; 1).", is_correct=True),
                SubItem(label="d", statement="Hệ phương trình đã cho có nghiệm duy nhất.", is_correct=True)
            ]
        )
        is_bad1, r1 = is_tf_context_mismatched(q1_tf.question, q1_tf.sub_items)
        self.assertTrue(is_bad1)

        # Câu 2: Đề bồn chứa hình trụ nhưng mệnh đề là tam giác vuông lượng giác
        q2_tf = Part2Question(
            id=2,
            question="Một xí nghiệp sản xuất các bồn chứa nước bằng inox hình trụ có nắp đậy kín phục vụ các hộ gia đình. Mỗi bồn chứa có chiều cao h = 2 m và bán kính đáy R = 0,6 m...",
            sub_items=[
                SubItem(label="a", statement="cosB = sinC.", is_correct=True),
                SubItem(label="b", statement="sinB = 12/13.", is_correct=True),
                SubItem(label="c", statement="cotC = 5/12.", is_correct=False),
                SubItem(label="d", statement="Độ dài cạnh huyền BC = 13 cm.", is_correct=True)
            ]
        )
        is_bad2, r2 = is_tf_context_mismatched(q2_tf.question, q2_tf.sub_items)
        self.assertTrue(is_bad2)

        # Câu 3: Đề tính tiền điện nhưng mệnh đề là hằng đẳng thức lượng giác với công thức tan = cos/sin sai
        q3_tf = Part2Question(
            id=3,
            question="Một hộ gia đình sử dụng điện sinh hoạt trong tháng với định mức tính tiền gồm hai bậc: Bậc 1 có đơn giá là x đồng/kWh, Bậc 2 có đơn giá là y đồng/kWh...",
            sub_items=[
                SubItem(label="a", statement=r"$\sin^2\alpha + \cos^2\alpha = 1$", is_correct=True),
                SubItem(label="b", statement=r"$\tan\alpha = \frac{\cos\alpha}{\sin\alpha}$", is_correct=False),
                SubItem(label="c", statement=r"Nếu $\alpha = 45^\circ$ thì $\sin\alpha = \cos\alpha = \frac{\sqrt{2}}{2}$", is_correct=True),
                SubItem(label="d", statement=r"$\tan\alpha \cdot \cot\alpha = 1$", is_correct=True)
            ]
        )
        is_bad3, r3 = is_tf_context_mismatched(q3_tf.question, q3_tf.sub_items)
        self.assertTrue(is_bad3)

        # Chạy kiểm duyệt & phục hồi tự động
        exam = ExamStructure(
            title="ĐỀ KIỂM TRA TOÁN 9",
            subject="Toán học",
            grade="9",
            part1_mcq=[],
            part2_tf=[q1_tf, q2_tf, q3_tf],
            part3_short=[]
        )
        healed = asyncio.run(audit_and_verify_exam(exam))

        # Kiểm tra Câu 1 sau phục hồi: 100% về hải đăng/tàu/ca nô
        h1 = healed.part2_tf[0]
        self.assertIn("hải đăng", h1.question.lower())
        for s in h1.sub_items:
            self.assertNotIn("phương trình thứ nhất", s.statement.lower())
            self.assertNotIn("vô nghiệm", s.statement.lower())
        self.assertTrue(any("hải đăng" in s.statement.lower() or "ca nô" in s.statement.lower() or "khoảng cách" in s.statement.lower() for s in h1.sub_items))

        # Kiểm tra Câu 2 sau phục hồi: 100% về hình trụ/bồn nước/thể tích
        h2 = healed.part2_tf[1]
        for s in h2.sub_items:
            self.assertNotIn("cạnh huyền bc", s.statement.lower())
        self.assertTrue(any("hình trụ" in s.statement.lower() or "bồn" in s.statement.lower() or "thể tích" in s.statement.lower() or "bán kính" in s.statement.lower() for s in h2.sub_items))

        # Kiểm tra Câu 3 sau phục hồi: 100% về tiền điện/kWh/đơn giá
        h3 = healed.part2_tf[2]
        for s in h3.sub_items:
            self.assertNotIn("cos\\alpha", s.statement.lower())
            self.assertNotIn("tan\\alpha", s.statement.lower())
        self.assertTrue(any("kwh" in s.statement.lower() or "tiền" in s.statement.lower() or "đồng" in s.statement.lower() for s in h3.sub_items))

        print("[PASS] Defect 21: TF context mismatches successfully detected and healed into cohesive questions and statements.")

    def test_defect_22_type_safety_int_not_iterable(self):
        # Kiểm tra an toàn kiểu dữ liệu: Nếu dữ liệu AI trả về số nguyên (int) thay vì mảng (list),
        # hàm normalize_exam_data không bao giờ bị văng lỗi 'int' object is not iterable.
        from app.services.ai_generator import normalize_exam_data

        corrupted_data = {
            "title": "ĐỀ KIỂM TRA",
            "subject": "Toán học",
            "grade": "9",
            "part1_mcq": 12,  # int thay vì list!
            "part2_tf": 4,    # int thay vì list!
            "part3_short": 6, # int thay vì list!
            "part4_essay": 0  # int thay vì list!
        }

        # Không được văng ngoại lệ TypeError: 'int' object is not iterable
        res = normalize_exam_data(corrupted_data, default_subject="Toán học", default_grade="9")
        self.assertIsInstance(res["part1_mcq"], list)
        self.assertIsInstance(res["part2_tf"], list)
        self.assertIsInstance(res["part3_short"], list)
        self.assertIsInstance(res["part4_essay"], list)
        print("[PASS] Defect 22: Type safety against non-iterable integers verified.")

    def test_feature_23_matrix_custom_question_counts(self):
        # Kiểm tra tính năng: Tùy chọn số lượng câu hỏi 4 phần khác với ma trận gốc
        # nhưng vẫn giữ nguyên chủ đề và các mức độ nhận thức (Biết - Hiểu - Vận dụng)
        from app.services.models import (
            ExamMatrixSpec, Cv7991TopicItem, CognitiveBreakdown, CognitiveSummary,
            TopicRequirements, GenerateRequest, calculate_exam_scoring
        )
        from app.services.ai_generator import normalize_exam_data

        # 1. Tạo ma trận gốc với cấu hình mặc định (12 câu P1, 4 câu P2, 6 câu P3, 0 câu Tự luận)
        matrix = ExamMatrixSpec(
            title="MA TRẬN ĐỀ KIỂM TRA ĐỊNH KỲ TOÁN 9",
            subject="Toán học",
            grade="9",
            duration_minutes=45,
            num_part1=12,
            num_part2=4,
            num_part3=6,
            num_essay=0,
            cognitive_summary=CognitiveSummary(
                biet_count=10, biet_pct=40.0,
                hieu_count=8, hieu_pct=30.0,
                vd_count=4, vd_pct=30.0
            ),
            topics=[
                Cv7991TopicItem(
                    id=1,
                    topic="Căn bậc hai và căn bậc ba",
                    sub_topic="Tính toán và rút gọn biểu thức chứa căn",
                    requirements=TopicRequirements(
                        recognition="Nhận biết điều kiện xác định của căn thức bậc hai.",
                        comprehension="Thực hiện được các phép tính khai phương, trục căn thức ở mẫu.",
                        application="Vận dụng rút gọn biểu thức chứa căn thức bậc hai."
                    )
                ),
                Cv7991TopicItem(
                    id=2,
                    topic="Hệ hai phương trình bậc nhất hai ẩn",
                    sub_topic="Giải hệ phương trình và bài toán thực tế",
                    requirements=TopicRequirements(
                        recognition="Nhận biết hệ hai phương trình bậc nhất hai ẩn.",
                        comprehension="Giải hệ bằng phương pháp thế hoặc cộng đại số.",
                        application="Giải bài toán thực tế bằng cách lập hệ phương trình."
                    )
                )
            ]
        )

        # 2. Người dùng tùy biến số câu khác hoàn toàn với ma trận gốc:
        # P1 = 16 câu (thay vì 12), P2 = 2 câu (thay vì 4), P3 = 4 câu (thay vì 6), Tự luận = 1 câu (thay vì 0)
        req = GenerateRequest(
            mode="matrix",
            subject="Toán học",
            grade="9",
            num_part1=16,
            num_part2=2,
            num_part3=4,
            num_essay=1,
            matrix_spec=matrix,
            matrix_mode=True
        )

        # 3. Kiểm tra thuật toán phân bổ điểm: Thang điểm 10.0 luôn chuẩn xác
        scoring = calculate_exam_scoring(
            num_p1=req.num_part1,
            num_p2=req.num_part2,
            num_p3=req.num_part3,
            num_p4=req.num_essay
        )
        self.assertEqual(scoring.total_points, 10.0)
        self.assertEqual(scoring.part1_points, 4.0)  # 16 * 0.25 = 4.0
        self.assertEqual(scoring.part2_points, 2.0)  # 2 * 1.0 = 2.0
        self.assertAlmostEqual(scoring.part1_points + scoring.part2_points + scoring.part3_points + scoring.part4_points, 10.0, places=2)

        # 4. Kiểm tra chuẩn hóa đề thi theo số lượng tùy biến
        mock_ai_output = {
            "title": "ĐỀ KIỂM TRA ĐỊNH KỲ TOÁN 9",
            "subject": "Toán học",
            "grade": "9",
            "part1_mcq": [{"id": i, "question": f"Câu hỏi TN {i}", "options": [{"label": "A", "text": "1"}, {"label": "B", "text": "2"}, {"label": "C", "text": "3"}, {"label": "D", "text": "4"}], "answer": "A"} for i in range(1, 17)],
            "part2_tf": [{"id": i, "question": f"Bài toán tình huống {i}", "sub_items": [{"label": "a", "statement": "Mệnh đề 1", "is_correct": True}, {"label": "b", "statement": "Mệnh đề 2", "is_correct": False}, {"label": "c", "statement": "Mệnh đề 3", "is_correct": True}, {"label": "d", "statement": "Mệnh đề 4", "is_correct": False}]} for i in range(1, 3)],
            "part3_short": [{"id": i, "question": f"Câu hỏi ngắn {i}", "answer": str(i)} for i in range(1, 5)],
            "part4_essay": [{"id": 1, "question": "Bài toán thực tế tự luận 1", "points": scoring.part4_points, "explanation": "- Ý 1\n- Ý 2"}]
        }
        normalized = normalize_exam_data(mock_ai_output, default_subject="Toán học", default_grade="9")
        self.assertEqual(len(normalized["part1_mcq"]), 16)
        self.assertEqual(len(normalized["part2_tf"]), 2)
        self.assertEqual(len(normalized["part3_short"]), 4)
        self.assertEqual(len(normalized["part4_essay"]), 1)

        print("[PASS] Defect 23: Custom question counts for matrix generation validated with preserved cognitive levels & 10.0 scale.")

if __name__ == "__main__":
    unittest.main()


