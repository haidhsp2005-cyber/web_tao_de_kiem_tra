import re
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class Option(BaseModel):
    label: str  # A, B, C, D
    text: str

class Part1Question(BaseModel):
    id: int
    question: str
    options: List[Option]
    answer: str  # A, B, C, or D
    explanation: Optional[str] = ''

class SubItem(BaseModel):
    label: str  # a, b, c, d
    statement: str
    is_correct: bool  # True: Dung, False: Sai
    explanation: Optional[str] = ''

class Part2Question(BaseModel):
    id: int
    question: str
    sub_items: List[SubItem]
    explanation: Optional[str] = ''

class Part3Question(BaseModel):
    id: int
    question: str
    answer: str  # Short text or numerical answer e.g. '12.5', '3'
    explanation: Optional[str] = ''

class Part4EssayQuestion(BaseModel):
    id: int
    question: str
    points: Optional[float] = 1.0  # Điểm số của câu tự luận
    answer: Optional[str] = ''     # Tóm tắt đáp án / kết quả then chốt
    explanation: Optional[str] = '' # Hướng dẫn chấm chi tiết & biểu điểm

class AuditReport(BaseModel):
    passed: bool = True
    quality_score: int = 100
    total_questions: int = 0
    issues_found: int = 0
    issues_repaired: int = 0
    notes: List[str] = Field(default_factory=list)

class ExamScoring(BaseModel):
    total_points: float = 10.0
    part1_points: float = 0.0
    part1_per_q: float = 0.0
    part2_points: float = 0.0
    part2_per_q: float = 0.0
    part3_points: float = 0.0
    part3_per_q: float = 0.0
    part4_points: float = 0.0
    part4_per_q: float = 0.0

def calculate_exam_scoring(
    num_p1: int,
    num_p2: int,
    num_p3: int,
    num_p4: int = 0,
    p4_points_total: Optional[float] = None
) -> ExamScoring:
    """
    Quy tắc tính toán điểm số theo yêu cầu:
    - Phần I (Trắc nghiệm khách quan): Không đổi, mỗi câu luôn là 0,25 điểm.
    - Phần II (Trắc nghiệm Đúng / Sai): Không đổi, mỗi câu luôn là 1,0 điểm
      (Đúng 1 ý: 0,1đ; đúng 2 ý: 0,25đ; đúng 3 ý: 0,5đ; đúng 4 ý: 1,0đ).
    - Phần III (Trả lời ngắn) & Phần IV (Tự luận): Điều chỉnh theo hai phần trên
      để tổng điểm toàn bài luôn đạt chính xác 10,0 điểm.
    """
    # 1. Phần I: Cố định 0.25 điểm / câu
    if num_p1 > 0:
        s1 = round(num_p1 * 0.25, 2)
        p1_per_q = 0.25
    else:
        s1 = 0.0
        p1_per_q = 0.0

    # 2. Phần II: Cố định 1.0 điểm / câu
    if num_p2 > 0:
        s2 = round(num_p2 * 1.0, 2)
        p2_per_q = 1.0
    else:
        s2 = 0.0
        p2_per_q = 0.0

    fixed_12 = round(s1 + s2, 2)
    remaining = round(max(0.0, 10.0 - fixed_12), 2)

    # 3. Phần III (Trả lời ngắn) và Phần IV (Tự luận) điều chỉnh theo hai phần trên
    s3, s4 = 0.0, 0.0
    p3_per_q, p4_per_q = 0.0, 0.0

    if num_p3 == 0 and num_p4 == 0:
        # Không có cả Phần III và Phần IV
        if num_p1 > 0 and num_p2 == 0 and num_p1 == 40:
            s1 = 10.0
            p1_per_q = 0.25
    elif num_p3 > 0 and num_p4 == 0:
        # Chỉ có Phần III, nhận toàn bộ số điểm còn lại
        s3 = remaining
        p3_per_q = round(s3 / num_p3, 2) if num_p3 > 0 else 0.0
    elif num_p3 == 0 and num_p4 > 0:
        # Chỉ có Phần IV (Tự luận), nhận toàn bộ số điểm còn lại
        s4 = remaining
        p4_per_q = round(s4 / num_p4, 2) if num_p4 > 0 else 0.0
    else:
        # Có cả Phần III và Phần IV cùng chia sẻ số điểm còn lại
        if p4_points_total is not None and p4_points_total > 0:
            s4 = min(round(p4_points_total, 2), max(0.5, remaining - 0.25 * num_p3))
        else:
            w3 = num_p3 * 1.0
            w4 = num_p4 * 4.0
            s4 = round((remaining * w4) / (w3 + w4), 1)
            if s4 >= remaining:
                s4 = round(remaining - 0.5, 1) if remaining >= 1.0 else round(remaining / 2, 1)
            if s4 <= 0:
                s4 = 0.5 if remaining >= 1.0 else round(remaining / 2, 1)

        s3 = round(remaining - s4, 2)
        p3_per_q = round(s3 / num_p3, 2) if num_p3 > 0 else 0.0
        p4_per_q = round(s4 / num_p4, 2) if num_p4 > 0 else 0.0

    # Đảm bảo tổng chính xác 10.0 điểm
    tot = round(s1 + s2 + s3 + s4, 2)
    diff = round(10.0 - tot, 2)
    if diff != 0:
        # Ưu tiên bù trừ vào Phần III hoặc Phần IV để giữ nguyên Phần I (0.25) và Phần II (1.0)
        if s3 > 0:
            s3 = round(s3 + diff, 2)
            p3_per_q = round(s3 / num_p3, 2) if num_p3 > 0 else 0.0
        elif s4 > 0:
            s4 = round(s4 + diff, 2)
            p4_per_q = round(s4 / num_p4, 2) if num_p4 > 0 else 0.0
        elif s2 > 0:
            s2 = round(s2 + diff, 2)
        elif s1 > 0:
            s1 = round(s1 + diff, 2)

    return ExamScoring(
        total_points=10.0,
        part1_points=round(s1, 2),
        part1_per_q=p1_per_q,
        part2_points=round(s2, 2),
        part2_per_q=p2_per_q,
        part3_points=round(s3, 2),
        part3_per_q=p3_per_q,
        part4_points=round(s4, 2),
        part4_per_q=p4_per_q
    )

def clean_essay_explanation(text: str) -> str:
    """
    Chuẩn hóa lời giải/hướng dẫn chấm câu tự luận:
    - Loại bỏ tiền tố các bước ('Bước 1:', 'Bước 2 (0.5đ):', '(0.5đ):', v.v.)
    - Loại bỏ điểm số con từng phần ở cuối dòng (ví dụ '... (0.5đ)') để tránh gây hiểu lầm cộng dồn sai tổng điểm.
    - Định dạng lại thành các gạch đầu dòng '- ' mạch lạc cho các ý chính.
    """
    if not text:
        return ""
    lines = str(text).split("\n")
    cleaned_lines = []
    
    points_regex = r'(?:[\(\[]\s*\d+(?:[.,]\d+)?\s*(?:đ|điểm|pt|pts)?\s*[\)\]]|\d+(?:[.,]\d+)?\s*(?:đ|điểm))'
    step_word = r'(?:bước|giai\s*đoạn)\s*\d+'

    prefix_pattern = re.compile(
        r'^\s*(?:[-*+•]|\d+[\.)])?\s*'
        r'(?:'
            rf'{step_word}\s*(?:{points_regex})?'
            r'|'
            rf'{points_regex}\s*(?:{step_word})?'
            r'|'
            rf'{points_regex}'
            r'|'
            rf'{step_word}'
        r')\s*[:.-]*\s*',
        re.IGNORECASE
    )
    trailing_point_pattern = re.compile(
        r'\s*[\(\[]\s*\d+(?:[.,]\d+)?\s*(?:đ|điểm|pt|pts)?\s*[\)\]]\s*$',
        re.IGNORECASE
    )
    
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        subbed = prefix_pattern.sub('', stripped).strip()
        subbed = trailing_point_pattern.sub('', subbed).strip()
        subbed = re.sub(r'^\s*[-*+•]\s*', '', subbed).strip()
        if subbed:
            if subbed[0].isalpha():
                subbed = subbed[0].upper() + subbed[1:]
            cleaned_lines.append(f"- {subbed}")
            
    return "\n".join(cleaned_lines) if cleaned_lines else text

def sync_part4_essay_points(part4_essay: List[Any], total_p4: float) -> List[Any]:
    """
    Đồng bộ và phân bổ lại điểm từng câu tự luận (q.points) sao cho:
    1. Tổng điểm của tất cả các câu con luôn luôn BẰNG CHÍNH XÁC điểm của Phần IV (total_p4).
    2. Lời giải/hướng dẫn chấm được làm sạch, bỏ chia điểm từng bước, chỉ gạch đầu dòng các ý chính.
    """
    if not part4_essay:
        return part4_essay

    # Chuẩn hóa lời giải/hướng dẫn chấm: bỏ bước và điểm con, chỉ giữ gạch đầu dòng
    for q in part4_essay:
        if isinstance(q, dict):
            if q.get("explanation"):
                q["explanation"] = clean_essay_explanation(q["explanation"])
        else:
            if getattr(q, "explanation", None):
                q.explanation = clean_essay_explanation(q.explanation)

    if total_p4 is None or total_p4 <= 0:
        return part4_essay
        
    n = len(part4_essay)
    if n == 1:
        pt = round(float(total_p4), 2)
        if isinstance(part4_essay[0], dict):
            part4_essay[0]["points"] = pt
        else:
            part4_essay[0].points = pt
        return part4_essay

    raw_points = []
    for q in part4_essay:
        pts = q.get("points", 1.0) if isinstance(q, dict) else getattr(q, "points", 1.0)
        try:
            val = float(pts) if pts and float(pts) > 0 else 1.0
        except (ValueError, TypeError):
            val = 1.0
        raw_points.append(val)
    
    all_equal = len(set(raw_points)) <= 1
    
    if all_equal:
        base = round(total_p4 / n, 2)
        allocated = [base] * n
    else:
        sum_raw = sum(raw_points)
        allocated = [round((pts / sum_raw) * total_p4, 2) for pts in raw_points]
    
    diff = round(total_p4 - sum(allocated), 2)
    if diff != 0:
        allocated[-1] = round(allocated[-1] + diff, 2)
        
    for i, q in enumerate(part4_essay):
        if isinstance(q, dict):
            q["points"] = allocated[i]
        else:
            q.points = allocated[i]

    return part4_essay

class ExamStructure(BaseModel):
    title: str = 'ĐỀ KIỂM TRA ĐỊNH KỲ'
    subject: str = 'Toán học'
    grade: str = '12'
    duration_minutes: int = 50
    school_name: str = 'SỞ GD&ĐT ... - TRƯỜNG THPT ...'
    academic_year: str = 'NĂM HỌC 2026 - 2027'
    code: str = '101'
    part1_mcq: List[Part1Question] = Field(default_factory=list)
    part2_tf: List[Part2Question] = Field(default_factory=list)
    part3_short: List[Part3Question] = Field(default_factory=list)
    part4_essay: List[Part4EssayQuestion] = Field(default_factory=list)
    audit_report: Optional[AuditReport] = None
    scoring: Optional[ExamScoring] = None

    def model_post_init(self, __context: Any) -> None:
        if self.scoring is None and (self.part1_mcq or self.part2_tf or self.part3_short or self.part4_essay):
            self.scoring = calculate_exam_scoring(
                num_p1=len(self.part1_mcq),
                num_p2=len(self.part2_tf),
                num_p3=len(self.part3_short),
                num_p4=len(self.part4_essay)
            )
        if self.scoring and self.part4_essay:
            sync_part4_essay_points(self.part4_essay, self.scoring.part4_points)

class ExamVariant(BaseModel):
    code: str
    exam: ExamStructure
    part1_answers: Dict[int, str] = Field(default_factory=dict)       # {1: 'A', 2: 'C', ...}
    part2_answers: Dict[int, Dict[str, str]] = Field(default_factory=dict) # {1: {'a': 'Đ', 'b': 'S', ...}}
    part3_answers: Dict[int, str] = Field(default_factory=dict)       # {1: '12', 2: '-4.5', ...}
    part4_answers: Dict[int, str] = Field(default_factory=dict)       # {1: 'Hướng dẫn chấm...'}

    def model_post_init(self, __context: Any) -> None:
        if self.exam and self.exam.scoring and self.exam.part4_essay:
            sync_part4_essay_points(self.exam.part4_essay, self.exam.scoring.part4_points)

class ShuffleRequest(BaseModel):
    exam: ExamStructure
    num_variants: int = 4
    start_code: int = 101
    shuffle_part1_options: bool = True
    shuffle_part2_subitems: bool = True

class ShuffleResponse(BaseModel):
    variants: List[ExamVariant]
    matrix: Dict[str, Any]

class CognitiveBreakdown(BaseModel):
    biet: int = 0
    hieu: int = 0
    vd: int = 0

class TopicRequirements(BaseModel):
    recognition: Optional[str] = ''   # - Biết: ...
    comprehension: Optional[str] = '' # - Hiểu: ...
    application: Optional[str] = ''   # - VD: ...

class Cv7991TopicItem(BaseModel):
    id: int = 1
    topic: str                        # Chủ đề / Chương
    sub_topic: Optional[str] = ''     # Nội dung / đơn vị kiến thức
    requirements: Optional[TopicRequirements] = None
    part1_mcq: CognitiveBreakdown = Field(default_factory=CognitiveBreakdown)     # Nhiều lựa chọn
    part2_tf: CognitiveBreakdown = Field(default_factory=CognitiveBreakdown)      # Đúng - Sai
    part3_short: CognitiveBreakdown = Field(default_factory=CognitiveBreakdown)   # Trả lời ngắn
    part4_essay: CognitiveBreakdown = Field(default_factory=CognitiveBreakdown)   # Tự luận
    total_questions: int = 0
    points: float = 0.0

class CognitiveSummary(BaseModel):
    biet_count: int = 0
    biet_pct: float = 40.0
    hieu_count: int = 0
    hieu_pct: float = 30.0
    vd_count: int = 0
    vd_pct: float = 30.0

class ExamMatrixSpec(BaseModel):
    title: str = 'MA TRẬN & BẢN ĐẶC TẢ ĐỀ KIỂM TRA ĐỊNH KÌ'
    subject: str = 'Toán học'
    grade: str = '12'
    duration_minutes: int = 50
    school_name: Optional[str] = 'SỞ GD&ĐT ... - TRƯỜNG THPT ...'
    academic_year: Optional[str] = 'NĂM HỌC 2026 - 2027'
    num_part1: int = 12
    num_part2: int = 4
    num_part3: int = 6
    num_essay: int = 0
    total_points: float = 10.0
    scoring_summary: Optional[Dict[str, float]] = None
    cognitive_summary: CognitiveSummary = Field(default_factory=CognitiveSummary)
    topics: List[Cv7991TopicItem] = Field(default_factory=list)
    raw_markdown_table: Optional[str] = ''

class MatrixAnalyzeResponse(BaseModel):
    success: bool = True
    message: str = ''
    matrix: ExamMatrixSpec

class GenerateRequest(BaseModel):
    mode: str = 'prompt'  # prompt, file, mock, matrix
    prompt: Optional[str] = None
    subject: str = 'Toán học'
    grade: str = '12'
    topic: Optional[str] = ''
    num_part1: int = 20
    num_part2: int = 4
    num_part3: int = 6
    num_essay: int = 0  # Số câu tự luận (mặc định 0 - nếu là 0 thì không tạo câu tự luận)
    file_content: Optional[str] = None
    matrix_spec: Optional[ExamMatrixSpec] = None
    matrix_mode: bool = False
    api_provider: str = 'gemini'  # gemini, openai, mock
    api_key: Optional[str] = None
    api_keys: Optional[List[str]] = Field(default_factory=list)
    model_name: Optional[str] = None

class ExportDocxRequest(BaseModel):
    exam: ExamStructure
    variant_code: Optional[str] = None
    all_variants: Optional[List[ExamVariant]] = None
    include_answers: bool = True
    include_explanations: bool = True
    red_answers: bool = False

