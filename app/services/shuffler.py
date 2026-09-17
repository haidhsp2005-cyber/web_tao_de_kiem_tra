import random
import copy
from typing import List, Dict, Any
from .models import ExamStructure, ExamVariant, Option, Part1Question, Part2Question, Part3Question, Part4EssayQuestion, ShuffleResponse, calculate_exam_scoring
from .explanation_sync import synchronize_mcq_explanation_with_answer, sync_tf_sub_explanation

def shuffle_exam(
    exam: ExamStructure,
    num_variants: int = 4,
    start_code: int = 101,
    shuffle_part1_options: bool = True,
    shuffle_part2_subitems: bool = True
) -> ShuffleResponse:
    """
    Shuffles an exam into multiple variants with distinct test codes.
    Maintains 100% accuracy of answer keys and explanations.
    """
    variants: List[ExamVariant] = []
    
    for i in range(num_variants):
        code = str(start_code + i)
        rng = random.Random(f"{exam.title}_{code}_{i}")
        
        # Deep copy to ensure independence
        v_exam = copy.deepcopy(exam)
        v_exam.code = code
        if v_exam.scoring is None:
            p4_pts = sum(q.points for q in (v_exam.part4_essay or []))
            v_exam.scoring = calculate_exam_scoring(
                num_p1=len(v_exam.part1_mcq),
                num_p2=len(v_exam.part2_tf),
                num_p3=len(v_exam.part3_short),
                num_p4=len(v_exam.part4_essay or []),
                p4_points_total=p4_pts
            )
        
        # ---------------------------------------------------------
        # 1. Shuffle Part 1 (MCQs)
        # ---------------------------------------------------------
        shuffled_p1: List[Part1Question] = copy.deepcopy(exam.part1_mcq)
        if len(shuffled_p1) > 1:
            rng.shuffle(shuffled_p1)
            
        p1_answers: Dict[int, str] = {}
        for new_idx, q in enumerate(shuffled_p1, start=1):
            q.id = new_idx
            original_answer_label = q.answer.strip().upper()
            
            # Find the original correct option text
            correct_option_text = None
            for opt in q.options:
                if opt.label.strip().upper() == original_answer_label:
                    correct_option_text = opt.text
                    break
            
            # Strictly enforce exactly 4 options (A, B, C, D)
            if len(q.options) > 4:
                correct_idx = -1
                for o_i, opt in enumerate(q.options):
                    if opt.label.strip().upper() == original_answer_label:
                        correct_idx = o_i
                        break
                if correct_idx >= 4:
                    q.options[3] = q.options[correct_idx]
                q.options = q.options[:4]
                for o_i, opt in enumerate(q.options):
                    opt.label = ["A", "B", "C", "D"][o_i]
            
            if shuffle_part1_options and len(q.options) > 1:
                # Shuffle options list (strictly 4 options)
                opts_to_shuffle = copy.deepcopy(q.options[:4])
                rng.shuffle(opts_to_shuffle)
                
                # Re-assign labels A, B, C, D strictly
                labels = ["A", "B", "C", "D"]
                new_options: List[Option] = []
                new_answer_label = "A"
                
                for opt_i, opt in enumerate(opts_to_shuffle):
                    lbl = labels[opt_i]
                    new_opt = Option(label=lbl, text=opt.text)
                    new_options.append(new_opt)
                    
                    # If this was the correct option, update new answer
                    if correct_option_text is not None and opt.text == correct_option_text:
                        new_answer_label = lbl
                
                q.options = new_options
                q.answer = new_answer_label
            
            # Synchronize explanation conclusion with the final answer of this variant
            q.explanation = synchronize_mcq_explanation_with_answer(q.explanation, q.answer)
            p1_answers[new_idx] = q.answer
        
        v_exam.part1_mcq = shuffled_p1
        
        # ---------------------------------------------------------
        # 2. Shuffle Part 2 (True / False)
        # ---------------------------------------------------------
        shuffled_p2: List[Part2Question] = copy.deepcopy(exam.part2_tf)
        if len(shuffled_p2) > 1:
            rng.shuffle(shuffled_p2)
            
        p2_answers: Dict[int, Dict[str, str]] = {}
        for new_idx, q in enumerate(shuffled_p2, start=1):
            q.id = new_idx
            
            if shuffle_part2_subitems and len(q.sub_items) > 1:
                subs_to_shuffle = copy.deepcopy(q.sub_items)
                rng.shuffle(subs_to_shuffle)
                
                sub_labels = ["a", "b", "c", "d"]
                new_subs = []
                for s_i, sub in enumerate(subs_to_shuffle):
                    old_sub_lbl = sub.label
                    lbl = sub_labels[s_i] if s_i < len(sub_labels) else str(s_i + 1)
                    sub.label = lbl
                    # Sync sub.explanation if it references the old label (e.g. "Ý a) đúng...")
                    sub.explanation = sync_tf_sub_explanation(sub.explanation, old_sub_lbl, lbl)
                    new_subs.append(sub)
                q.sub_items = new_subs
            
            # Record answer: 'Đ' or 'S'
            p2_answers[new_idx] = {
                s.label: ('Đ' if s.is_correct else 'S') for s in q.sub_items
            }
        
        v_exam.part2_tf = shuffled_p2
        
        # ---------------------------------------------------------
        # 3. Shuffle Part 3 (Short Answer)
        # ---------------------------------------------------------
        shuffled_p3: List[Part3Question] = copy.deepcopy(exam.part3_short)
        if len(shuffled_p3) > 1:
            rng.shuffle(shuffled_p3)
            
        p3_answers: Dict[int, str] = {}
        for new_idx, q in enumerate(shuffled_p3, start=1):
            q.id = new_idx
            p3_answers[new_idx] = q.answer
        
        v_exam.part3_short = shuffled_p3

        # ---------------------------------------------------------
        # 4. Part 4 (Essay / Tự luận)
        # ---------------------------------------------------------
        p4_answers: Dict[int, str] = {}
        if exam.part4_essay:
            shuffled_p4: List[Part4EssayQuestion] = copy.deepcopy(exam.part4_essay)
            for new_idx, q in enumerate(shuffled_p4, start=1):
                q.id = new_idx
                p4_answers[new_idx] = q.answer or (q.explanation[:50] + "..." if q.explanation else "Xem hướng dẫn chấm")
            v_exam.part4_essay = shuffled_p4
        else:
            v_exam.part4_essay = []
        
        # Create Variant
        variant = ExamVariant(
            code=code,
            exam=v_exam,
            part1_answers=p1_answers,
            part2_answers=p2_answers,
            part3_answers=p3_answers,
            part4_answers=p4_answers
        )
        variants.append(variant)
    
    # -------------------------------------------------------------
    # Build Master Grading Matrix
    # -------------------------------------------------------------
    matrix = {
        "codes": [v.code for v in variants],
        "part1": {},
        "part2": {},
        "part3": {}
    }
    
    # Part 1 matrix: row = question idx, cols = variants
    if exam.part1_mcq:
        num_mcq = len(exam.part1_mcq)
        for q_idx in range(1, num_mcq + 1):
            matrix["part1"][q_idx] = {
                v.code: v.part1_answers.get(q_idx, "-") for v in variants
            }
            
    # Part 2 matrix
    if exam.part2_tf:
        num_tf = len(exam.part2_tf)
        for q_idx in range(1, num_tf + 1):
            matrix["part2"][q_idx] = {
                v.code: v.part2_answers.get(q_idx, {}) for v in variants
            }
        
        # Flattened rows for direct table rendering on Web UI & reports:
        # e.g. [{"label": "Câu 1a", "q_idx": 1, "sub": "a", "answers": {"101": "Đ", "102": "S", ...}}]
        part2_rows = []
        for q_idx in range(1, num_tf + 1):
            for sub_lbl in ["a", "b", "c", "d"]:
                part2_rows.append({
                    "label": f"Câu {q_idx}{sub_lbl}",
                    "q_idx": q_idx,
                    "sub": sub_lbl,
                    "answers": {
                        v.code: v.part2_answers.get(q_idx, {}).get(sub_lbl, "-") for v in variants
                    }
                })
        matrix["part2_rows"] = part2_rows
            
    # Part 3 matrix
    if exam.part3_short:
        num_short = len(exam.part3_short)
        for q_idx in range(1, num_short + 1):
            matrix["part3"][q_idx] = {
                v.code: v.part3_answers.get(q_idx, "-") for v in variants
            }
        
        part3_rows = []
        for q_idx in range(1, num_short + 1):
            part3_rows.append({
                "label": f"Câu {q_idx}",
                "q_idx": q_idx,
                "answers": {
                    v.code: v.part3_answers.get(q_idx, "-") for v in variants
                }
            })
        matrix["part3_rows"] = part3_rows

    # Part 4 matrix
    if exam.part4_essay:
        matrix["part4"] = {}
        num_essay = len(exam.part4_essay)
        for q_idx in range(1, num_essay + 1):
            matrix["part4"][q_idx] = {
                v.code: v.part4_answers.get(q_idx, "-") for v in variants
            }
            
    return ShuffleResponse(variants=variants, matrix=matrix)
