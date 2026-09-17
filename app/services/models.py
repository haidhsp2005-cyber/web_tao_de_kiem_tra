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

class ExamVariant(BaseModel):
    code: str
    exam: ExamStructure
    part1_answers: Dict[int, str] = Field(default_factory=dict)       # {1: 'A', 2: 'C', ...}
    part2_answers: Dict[int, Dict[str, str]] = Field(default_factory=dict) # {1: {'a': 'Đ', 'b': 'S', ...}}
    part3_answers: Dict[int, str] = Field(default_factory=dict)       # {1: '12', 2: '-4.5', ...}
    part4_answers: Dict[int, str] = Field(default_factory=dict)       # {1: 'Hướng dẫn chấm...'}

class ShuffleRequest(BaseModel):
    exam: ExamStructure
    num_variants: int = 4
    start_code: int = 101
    shuffle_part1_options: bool = True
    shuffle_part2_subitems: bool = True

class ShuffleResponse(BaseModel):
    variants: List[ExamVariant]
    matrix: Dict[str, Any]

class GenerateRequest(BaseModel):
    mode: str = 'prompt'  # prompt, file, mock
    prompt: Optional[str] = None
    subject: str = 'Toán học'
    grade: str = '12'
    topic: Optional[str] = ''
    num_part1: int = 20
    num_part2: int = 4
    num_part3: int = 6
    num_essay: int = 0  # Số câu tự luận (mặc định 0 - nếu là 0 thì không tạo câu tự luận)
    file_content: Optional[str] = None
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
