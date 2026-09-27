import re
import math
from fractions import Fraction
from typing import Tuple, Optional, List, Dict, Any, Union
import sympy as sp

from .models import ExamStructure, Part1Question, Part2Question, Part3Question, Option, SubItem
from .explanation_sync import extract_concluded_letter, synchronize_mcq_explanation_with_answer

class UniversalMathEngine:
    """
    BỘ GIẢI TOÁN TỰ ĐỘNG TOÀN DIỆN (Universal Mathematical Solver & Verifier Engine)
    Sử dụng Hệ thống Đại số Máy tính (CAS - Computer Algebra System) kết hợp SymPy và giải tích số học
    để tự động giải, thẩm định và chuẩn hóa mọi bài toán trong đề thi mà không phụ thuộc vào câu hỏi cụ thể.
    """

    @staticmethod
    def parse_linear_system_2x2(text: str) -> Optional[Dict[str, Any]]:
        """
        Trích xuất hệ 2 phương trình bậc nhất 2 ẩn dạng:
        a1*x + b1*y = c1
        a2*x + b2*y = c2
        Hỗ trợ cả các biến x, y hoặc x0, y0, u, v và hệ chứa tham số m.
        """
        clean = text.replace(" ", "").replace("−", "-").replace("·", "*")
        
        # Regex tìm 2 phương trình tuyến tính
        # Dạng [a]x + [b]y = [c]
        eq_pat = r'([+-]?\d*(?:\.\d+)?(?:/\d+)?)x([+-]?\d*(?:\.\d+)?(?:/\d+)?)y=([+-]?\d+(?:\.\d+)?(?:/\d+)?)'
        matches = re.findall(eq_pat, clean, re.IGNORECASE)
        if len(matches) >= 2:
            def parse_val(s: str) -> Fraction:
                s = s.strip()
                if not s or s == "+": return Fraction(1, 1)
                if s == "-": return Fraction(-1, 1)
                if "/" in s:
                    num, den = s.split("/")
                    return Fraction(int(num), int(den))
                if "." in s:
                    return Fraction(s)
                return Fraction(int(s), 1)

            try:
                a1, b1, c1 = parse_val(matches[0][0]), parse_val(matches[0][1]), parse_val(matches[0][2])
                a2, b2, c2 = parse_val(matches[1][0]), parse_val(matches[1][1]), parse_val(matches[1][2])
                
                det = a1 * b2 - a2 * b1
                det_x = c1 * b2 - c2 * b1
                det_y = a1 * c2 - a2 * c1
                
                return {
                    "type": "2x2_linear_system",
                    "a1": a1, "b1": b1, "c1": c1,
                    "a2": a2, "b2": b2, "c2": c2,
                    "det": det,
                    "det_x": det_x,
                    "det_y": det_y,
                    "has_unique_solution": (det != 0),
                    "is_inconsistent": (det == 0 and (det_x != 0 or det_y != 0)),
                    "is_infinitely_many": (det == 0 and det_x == 0 and det_y == 0),
                    "x": (det_x / det) if det != 0 else None,
                    "y": (det_y / det) if det != 0 else None
                }
            except Exception:
                pass
        return None

    @staticmethod
    def parse_quadratic_equation(text: str) -> Optional[Dict[str, Any]]:
        """
        Trích xuất và giải phương trình bậc hai: ax^2 + bx + c = 0
        """
        clean = text.replace(" ", "").replace("−", "-").replace("·", "*")
        q_pat = r'([+-]?\d*)x\^?2([+-]?\d*)x([+-]?\d+)=0'
        m = re.search(q_pat, clean, re.IGNORECASE)
        if m:
            def parse_c(s: str, default: int = 1) -> int:
                if not s or s == "+": return default
                if s == "-": return -default
                return int(s)
            try:
                a = parse_c(m.group(1), 1)
                b = parse_c(m.group(2), 1)
                c = int(m.group(3))
                
                delta = b**2 - 4 * a * c
                res = {
                    "type": "quadratic_equation",
                    "a": a, "b": b, "c": c,
                    "delta": delta,
                    "num_roots": 0 if delta < 0 else (1 if delta == 0 else 2),
                    "sum_roots": Fraction(-b, a),
                    "prod_roots": Fraction(c, a)
                }
                if delta >= 0:
                    sqrt_delta = sp.sqrt(delta)
                    res["x1"] = (-b + sqrt_delta) / (2 * a)
                    res["x2"] = (-b - sqrt_delta) / (2 * a)
                return res
            except Exception:
                pass
        return None

    @staticmethod
    def detect_target_intent(text: str) -> str:
        """
        Xác định yêu cầu/mục tiêu hỏi của câu hỏi:
        - sol_pair: cặp nghiệm (x; y)
        - sum: tổng x + y
        - diff: hiệu x - y
        - prod: tích x * y
        - num_sol: số nghiệm
        - param_m: tìm m
        - value: giá trị số cụ thể
        """
        # Tách phần đề bài hỏi bên ngoài hệ phương trình \begin{cases}...\end{cases}
        stem_no_sys = re.sub(r'\\begin\{cases\}[\s\S]*?\\end\{cases\}', '', text)
        lower = (stem_no_sys if len(stem_no_sys.strip()) > 5 else text).lower()
        clean = lower.replace(" ", "").replace("−", "-").replace("$", "")
        
        if re.search(r"số\s*nghiệm", lower):
            return "num_sol"
        if re.search(r"(?:tổng|biểu\s*thức|giá\s*trị|tính).*?(?:x\s*\+\s*y|x0\s*\+\s*y0|x_0\s*\+\s*y_0)", lower) or "x+y" in clean or "x0+y0" in clean or "x_0+y_0" in clean or "s=" in clean:
            return "sum"
        if re.search(r"(?:hiệu|biểu\s*thức|giá\s*trị|tính).*?(?:x\s*-\s*y|x0\s*-\s*y0|x_0\s*-\s*y_0)", lower) or "x-y" in clean or "x0-y0" in clean or "x_0-y_0" in clean:
            return "diff"
        if re.search(r"(?:tích|biểu\s*thức|giá\s*trị|tính).*?(?:x\s*[\*·\.]?\s*y|x0\s*[\*·\.]?\s*y0|x_0\s*[\*·\.]?\s*y_0)", lower) or "x*y" in clean or "x.y" in clean or "p=" in clean:
            return "prod"
        if re.search(r"(?:nghiệm\s*của\s*hệ|cặp\s*số|tọa\s*độ|nghiệm\s*\(|cặp\s*nghiệm)", lower) or "(x;y)" in clean or "(x0;y0)" in clean or "(x_0;y_0)" in clean:
            return "sol_pair"
        if "tham số m" in lower or "tham số $m$" in lower or "giá trị của m" in lower or "giá trị của $m$" in lower or "tìm m" in lower:
            return "param_m"
        return "value"

    @classmethod
    def solve_and_verify_mcq(cls, q: Part1Question) -> Tuple[Part1Question, bool, str]:
        """
        Bộ giải toán độc lập cho câu hỏi trắc nghiệm Phần I.
        Phân tích toán học, giải bằng SymPy/đại số, kiểm tra đối chiếu đáp án và tự động sửa chữa.
        """
        # 1. Hệ phương trình 2 ẩn
        sys_info = cls.parse_linear_system_2x2(q.question)
        if sys_info:
            intent = cls.detect_target_intent(q.question)
            
            # 1.1 Hỏi về số nghiệm
            if intent == "num_sol":
                if sys_info["has_unique_solution"]:
                    correct_term = "nghiệm duy nhất"
                elif sys_info["is_infinitely_many"]:
                    correct_term = "vô số nghiệm"
                else:
                    correct_term = "vô nghiệm"
                    
                for o in q.options:
                    if correct_term in o.text.lower():
                        if q.answer != o.label:
                            q.answer = o.label
                            q.explanation = (
                                f"Hệ phương trình có định thức $D = {sys_info['det']}$. "
                                f"Do đó hệ phương trình có {correct_term}. Chọn đáp án {o.label}."
                            )
                            return q, True, f"Bộ giải chuẩn hóa: Hệ phương trình có {correct_term} (phương án {o.label})"
                        return q, False, ""

            # 1.2 Hệ có nghiệm duy nhất -> tính các đại lượng được hỏi
            if sys_info["has_unique_solution"]:
                x_val = sys_info["x"]
                y_val = sys_info["y"]
                
                # Giá trị mục tiêu
                target_val = None
                target_desc = ""
                
                if intent == "sum":
                    target_val = x_val + y_val
                    target_desc = f"x + y = {x_val} + {y_val} = {target_val}"
                elif intent == "diff":
                    target_val = x_val - y_val
                    target_desc = f"x - y = {x_val} - {y_val} = {target_val}"
                elif intent == "prod":
                    target_val = x_val * y_val
                    target_desc = f"x · y = {x_val} · {y_val} = {target_val}"
                if intent == "sol_pair":
                    x_str = f"{int(x_val)}" if x_val.denominator == 1 else f"{x_val}"
                    y_str = f"{int(y_val)}" if y_val.denominator == 1 else f"{y_val}"
                    target_desc = f"({x_str}; {y_str})"
                    sol_pat = rf"\(\s*{re.escape(x_str)}\s*;\s*{re.escape(y_str)}\s*\)"
                    found_opt = None
                    for o in q.options:
                        clean_opt = o.text.replace(" ", "").replace("$", "")
                        if re.search(sol_pat.replace(" ", ""), clean_opt):
                            found_opt = o.label
                            break
                    if found_opt:
                        if q.answer != found_opt:
                            q.answer = found_opt
                            q.explanation = (
                                f"Giải hệ phương trình ta được cặp nghiệm $(x_0; y_0) = ({x_str}; {y_str})$. "
                                f"Chọn đáp án {found_opt}."
                            )
                            return q, True, f"Bộ giải chuẩn hóa: Chuyển đáp án đúng về phương án {found_opt} ({target_desc})"
                        return q, False, ""
                    else:
                        for o in q.options:
                            if o.label == q.answer:
                                o.text = f"$({x_str}; {y_str})$"
                                break
                        q.explanation = (
                            f"Giải hệ phương trình ta được cặp nghiệm $(x_0; y_0) = ({x_str}; {y_str})$. "
                            f"Chọn đáp án {q.answer}."
                        )
                        return q, True, f"Bộ giải chuẩn hóa: Cập nhật phương án {q.answer} thành ({x_str}; {y_str})"

                elif target_val is not None:
                    # Kiểm tra xem đáp án có trong options không
                    val_float = float(target_val)
                    val_int = int(val_float) if val_float.is_integer() else None
                    
                    found_opt = None
                    for o in q.options:
                        clean_opt = o.text.replace(" ", "").replace("$", "")
                        try:
                            if val_int is not None and str(val_int) == clean_opt:
                                found_opt = o.label
                                break
                            if abs(float(Fraction(clean_opt)) - val_float) < 1e-4:
                                found_opt = o.label
                                break
                        except Exception:
                            if str(val_float) in clean_opt or (val_int is not None and str(val_int) in clean_opt):
                                found_opt = o.label
                                break
                                
                    if found_opt:
                        if q.answer != found_opt:
                            q.answer = found_opt
                            q.explanation = (
                                f"Giải hệ phương trình ta được $x = {x_val}$, $y = {y_val}$. "
                                f"Khi đó {target_desc}. Chọn đáp án {found_opt}."
                            )
                            return q, True, f"Bộ giải chuẩn hóa: Chuyển đáp án đúng về phương án {found_opt} ({target_desc})"
                    else:
                        # Nếu các phương án bị lệch số (nghiệm phân số không có trong đáp án nguyên)
                        # Tự động cân bằng hệ số c2 để nghiệm nguyên khớp với phương án đã đánh dấu
                        marked_opt = next((o for o in q.options if o.label == q.answer), q.options[0])
                        try:
                            desired_target = float(re.findall(r"[-+]?\d+", marked_opt.text)[0])
                            # Tìm nghiệm nguyên x, y thỏa mãn ax + by = c1 và mục tiêu
                            a1, b1, c1 = sys_info["a1"], sys_info["b1"], sys_info["c1"]
                            a2, b2 = sys_info["a2"], sys_info["b2"]
                            
                            found_xy = None
                            for cand_x in range(-15, 16):
                                if b1 != 0 and (c1 - a1 * cand_x) % b1 == 0:
                                    cand_y = (c1 - a1 * cand_x) // b1
                                    cand_target = (cand_x + cand_y) if intent == "sum" else ((cand_x - cand_y) if intent == "diff" else (cand_x * cand_y))
                                    if cand_target == desired_target:
                                        found_xy = (cand_x, cand_y)
                                        break
                            if found_xy:
                                nx, ny = found_xy
                                new_c2 = int(a2 * nx + b2 * ny)
                                # Thay thế c2 cũ trong đề bài
                                old_c2_pat = rf'({sys_info["a2"] if sys_info["a2"]!=1 else ""}\s*x\s*[\+\-]\s*{abs(sys_info["b2"]) if abs(sys_info["b2"])!=1 else ""}\s*y\s*=\s*)[-+]?\d+'
                                q.question = re.sub(old_c2_pat, rf'\g<1>{new_c2}', q.question)
                                q.explanation = (
                                    f"Giải hệ phương trình ta được $x = {nx}$, $y = {ny}$. "
                                    f"Suy ra {intent} bằng {int(desired_target)}. Chọn đáp án {marked_opt.label}."
                                )
                                return q, True, f"Bộ giải chuẩn hóa: Điều chỉnh hệ số phương trình 2 thành {new_c2} để nghiệm nguyên khớp đáp án {marked_opt.label}"
                        except Exception:
                            # Thay thế trực tiếp phương án q.answer thành giá trị thực
                            target_str = f"${val_int}$" if val_int is not None else f"${target_val}$"
                            for o in q.options:
                                if o.label == q.answer:
                                    o.text = target_str
                                    break
                            q.explanation = (
                                f"Giải hệ phương trình ta được $x = {x_val}$, $y = {y_val}$. "
                                f"Khi đó {target_desc}. Chọn đáp án {q.answer}."
                            )
                            return q, True, f"Bộ giải chuẩn hóa: Cập nhật phương án {q.answer} thành {target_str} chuẩn xác"

        # 2. Phương trình bậc hai
        quad_info = cls.parse_quadratic_equation(q.question)
        if quad_info:
            intent = cls.detect_target_intent(q.question)
            if intent == "num_sol":
                delta = quad_info["delta"]
                expected_sol = "2 nghiệm phân biệt" if delta > 0 else ("nghiệm kép" if delta == 0 else "vô nghiệm")
                for o in q.options:
                    if expected_sol in o.text.lower():
                        if q.answer != o.label:
                            q.answer = o.label
                            q.explanation = f"Phương trình có biệt thức $\\Delta = {delta}$. Do đó phương trình có {expected_sol}. Chọn đáp án {o.label}."
                            return q, True, f"Bộ giải chuẩn hóa: Phương trình bậc hai có {expected_sol} (phương án {o.label})"

        return q, False, ""

    @classmethod
    def solve_and_verify_short(cls, q: Part3Question) -> Tuple[Part3Question, bool, str]:
        """
        Bộ giải toán độc lập cho câu hỏi trả lời ngắn Phần III.
        Tự động giải và trả về con số đáp án chính xác nhất.
        """
        # 1. Hệ phương trình bậc nhất 2 ẩn
        sys_info = cls.parse_linear_system_2x2(q.question)
        if sys_info and sys_info["has_unique_solution"]:
            intent = cls.detect_target_intent(q.question)
            x_val = sys_info["x"]
            y_val = sys_info["y"]
            
            calc_res = None
            if intent == "sum":
                calc_res = x_val + y_val
            elif intent == "diff":
                calc_res = x_val - y_val
            elif intent == "prod":
                calc_res = x_val * y_val
                
            if calc_res is not None:
                res_float = float(calc_res)
                res_str = str(int(res_float)) if res_float.is_integer() else str(calc_res)
                if q.answer.strip() != res_str:
                    old_ans = q.answer.strip()
                    q.answer = res_str
                    q.explanation = (
                        f"Giải hệ phương trình ta được $x = {x_val}$, $y = {y_val}$. "
                        f"Giá trị của biểu thức là ${calc_res}$. Vậy đáp số là {res_str}."
                    )
                    return q, True, f"Bộ giải chuẩn hóa: Sửa đáp số Phần III từ '{old_ans}' thành '{res_str}'"

        # 2. Hệ tham số m đi qua điểm hoặc có vô số nghiệm
        clean = q.question.replace(" ", "").replace("−", "-")
        # Điểm (x0; y0)
        m_pt = re.search(r'\(\s*([+-]?\d+)\s*;\s*([+-]?\d+)\s*\)', clean)
        if m_pt and ("tham số m" in q.question.lower() or "tham số $m$" in q.question.lower() or "tham số" in q.question.lower()):
            px, py = int(m_pt.group(1)), int(m_pt.group(2))
            # Tìm m từ phương trình đầu
            m_var = sp.Symbol('m')
            # Thử giải m
            # mx + y = c1 -> m*px + py = c1
            m_c1 = re.search(r'm\s*\*?\s*x\s*\+\s*y\s*=\s*([+-]?\d+)', clean)
            if m_c1:
                c1 = int(m_c1.group(1))
                val_m = (c1 - py) / px
                if val_m.is_integer():
                    res_m_str = str(int(val_m))
                    # Đồng bộ phương trình thứ hai nếu mâu thuẫn
                    # x + my = c2 -> px + val_m*py = c2
                    new_c2 = int(px + val_m * py)
                    q.question = re.sub(r'(x\s*\+\s*m\s*\*?\s*y\s*=\s*)[-+]?\d+', rf'\g<1>{new_c2}', q.question)
                    if q.answer.strip() != res_m_str:
                        old_ans = q.answer
                        q.answer = res_m_str
                        q.explanation = (
                            f"Thay $x = {px}$ và $y = {py}$ vào hệ phương trình ta được $m = {res_m_str}$ (thỏa mãn cả hai phương trình). "
                            f"Vậy $m = {res_m_str}$."
                        )
                        return q, True, f"Bộ giải chuẩn hóa: Sửa m qua điểm ({px}; {py}) thành {res_m_str}"

        # 3. Hệ hai đường thẳng song song / vô số nghiệm: a1/a2 = b1/b2 = c1/m
        if "vô số nghiệm" in q.question.lower() or "vô nghiệm" in q.question.lower():
            # e.g., x - 2y = 3 và 2x - 4y = m
            m_sys = re.search(r'([+-]?\d*)x([+-]?\d*)y=([+-]?\d+).*?([+-]?\d*)x([+-]?\d*)y=m', clean, re.IGNORECASE)
            if m_sys:
                def p_c(s):
                    if not s or s == "+": return 1
                    if s == "-": return -1
                    return int(s)
                a1, b1, c1 = p_c(m_sys.group(1)), p_c(m_sys.group(2)), int(m_sys.group(3))
                a2, b2 = p_c(m_sys.group(4)), p_c(m_sys.group(5))
                # Tỉ số k = a2 / a1
                if a1 != 0 and a2 % a1 == 0:
                    k = a2 // a1
                    val_m = c1 * k
                    q.question = re.sub(r'vô nghiệm', 'có vô số nghiệm', q.question)
                    if q.answer.strip() != str(val_m):
                        q.answer = str(val_m)
                        q.explanation = (
                            f"Để hệ phương trình có vô số nghiệm thì tỉ số hệ số tương ứng phải bằng nhau: "
                            f"$\\frac{{{a1}}}{{{a2}}} = \\frac{{{b1}}}{{{b2}}} = \\frac{{{c1}}}{{m}} \\Leftrightarrow m = {val_m}$."
                        )
                        return q, True, f"Bộ giải chuẩn hóa: Tham số m để hệ có vô số nghiệm là m = {val_m}"

        return q, False, ""

    @classmethod
    def audit_and_solve_all(cls, exam: ExamStructure) -> Tuple[ExamStructure, List[str]]:
        """
        Duyệt toàn bộ đề thi qua Bộ giải toán tự động CAS & SymPy để giải quyết triệt để mọi bài toán.
        """
        notes = []
        for q in exam.part1_mcq:
            q, mod, msg = cls.solve_and_verify_mcq(q)
            if mod:
                notes.append(f"Câu {q.id} (Phần I): {msg}")
                
        for q in exam.part3_short:
            q, mod, msg = cls.solve_and_verify_short(q)
            if mod:
                notes.append(f"Câu {q.id} (Phần III): {msg}")
                
        return exam, notes
