import re
from typing import Optional, Tuple

CONCLUSION_PATTERN = re.compile(
    r'(?:'
    r'(?:chọn|ta\s+chọn|nên\s+chọn|hãy\s+chọn)\s*(?:đáp\s+án|phương\s+án)?\s*(?:đúng|chính\s+xác)?\s*(?:là)?\s*[:\s]*([A-D])\b|'
    r'(?:đáp\s+án|phương\s+án)\s*(?:đúng|cần\s+chọn|cần\s+tìm|chính\s+xác)?\s*(?:là)?\s*[:\s]*([A-D])\b|'
    r'(?:vậy|do\s+đó|suy\s+ra|kết\s+luận|tóm\s+lại)\s*[:\s,]*(?:ta\s+)?(?:chọn)?\s*(?:đáp\s+án|phương\s+án)?\s*(?:đúng)?\s*(?:là)?\s*[:\s]*([A-D])\b|'
    r'(?:=>|->)\s*(?:chọn)?\s*(?:đáp\s+án|phương\s+án)?\s*([A-D])\b|'
    r'\(\s*chọn\s*([A-D])\s*\)'
    r')',
    re.IGNORECASE
)

def extract_concluded_letter(text: str) -> Optional[str]:
    """
    Extract the option letter (A, B, C, D) concluded in the explanation text.
    Returns the letter of the last matching conclusion statement.
    """
    if not text:
        return None
    matches = list(CONCLUSION_PATTERN.finditer(text))
    if not matches:
        return None
    last_match = matches[-1]
    for g in last_match.groups():
        if g and g.upper() in ['A', 'B', 'C', 'D']:
            return g.upper()
    return None

def synchronize_mcq_explanation_with_answer(explanation: str, target_answer: str) -> str:
    """
    Ensures that the conclusion inside the explanation matches target_answer (A, B, C, D).
    If a conclusion exists (e.g. 'Chọn đáp án A', 'Do đó chọn B'), updates it to target_answer.
    If no conclusion exists, appends 'Do đó chọn đáp án {target_answer}.'
    Preserves all internal distractor eliminations (e.g. 'Loại A vì...').
    """
    target_answer = (target_answer or "").strip().upper()
    if not target_answer or target_answer not in ['A', 'B', 'C', 'D']:
        return explanation or ""
    if not explanation or not explanation.strip():
        return f"Do đó chọn đáp án {target_answer}."
        
    exp = explanation.strip()
    matches = list(CONCLUSION_PATTERN.finditer(exp))
    
    if matches:
        def repl(match):
            full = match.group(0)
            m_letter = None
            for g in match.groups():
                if g and g.upper() in ['A', 'B', 'C', 'D']:
                    m_letter = g.upper()
                    break
            if m_letter:
                return re.sub(rf'\b{m_letter}\b', target_answer, full, flags=re.IGNORECASE)
            return full

        # Replace conclusion matches to guarantee consistent conclusion throughout
        new_exp = CONCLUSION_PATTERN.sub(repl, exp)
        return new_exp
    else:
        if re.search(r'\b[A-D][\.\s]*$', exp):
            return re.sub(r'\b[A-D]([\.\s]*)$', rf'{target_answer}\g<1>', exp)
        else:
            clean_exp = exp.rstrip(" .;,")
            return f"{clean_exp}. Do đó chọn đáp án {target_answer}."

def sync_tf_sub_explanation(exp: str, old_lbl: str, new_lbl: str) -> str:
    """
    Updates sub-item references in True/False explanations when sub-items are shuffled.
    e.g. 'Ý a) đúng vì...' -> 'Ý c) đúng vì...'
    """
    if not exp or not old_lbl or not new_lbl or old_lbl.lower() == new_lbl.lower():
        return exp or ""
    old_l = old_lbl.lower()
    new_l = new_lbl.lower()
    
    # 1. Replace "Ý a)", "Mệnh đề a)", "Khẳng định a)"
    res = re.sub(rf'(?i)\b(ý|mệnh\s+đề|câu|khẳng\s+định)\s*{old_l}\)', rf'\g<1> {new_l})', exp)
    # 2. Replace "Ý a", "Mệnh đề a", "Khẳng định a"
    res = re.sub(rf'(?i)\b(ý|mệnh\s+đề|câu|khẳng\s+định)\s*{old_l}\b', rf'\g<1> {new_l}', res)
    return res

def reconcile_tf_subitem(is_correct: bool, exp: str) -> Tuple[bool, str]:
    """
    Reconciles any contradiction between is_correct boolean flag and the explanation text.
    If explanation explicitly says statement is false/sai, returns False.
    If explanation explicitly says statement is true/đúng, returns True.
    """
    if not exp:
        return is_correct, exp
    text = exp.strip().lower()
    
    # Match if explanation starts or concludes with 'sai'
    if re.search(r'^(?:mệnh\s+đề\s+(?:này\s+)?|khẳng\s+định\s+(?:này\s+)?|ý\s+[a-d]\s+(?:này\s+)?)?sai\b', text) or \
       re.search(r'(?:do\s+đó|vậy|suy\s+ra|kết\s+luận)\s*[:\s,]*(?:mệnh\s+đề\s+(?:này\s+)?|khẳng\s+định\s+(?:này\s+)?)?sai\b', text):
        if is_correct:
            is_correct = False
    elif re.search(r'^(?:mệnh\s+đề\s+(?:này\s+)?|khẳng\s+định\s+(?:này\s+)?|ý\s+[a-d]\s+(?:này\s+)?)?đúng\b', text) or \
         re.search(r'(?:do\s+đó|vậy|suy\s+ra|kết\s+luận)\s*[:\s,]*(?:mệnh\s+đề\s+(?:này\s+)?|khẳng\s+định\s+(?:này\s+)?)?đúng\b', text):
        if not is_correct:
            is_correct = True
            
    return is_correct, exp
