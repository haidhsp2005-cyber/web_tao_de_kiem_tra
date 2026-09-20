import re
import json
from typing import List, Optional, Dict, Any
import json_repair

from .models import (
    CognitiveBreakdown,
    TopicRequirements,
    Cv7991TopicItem,
    CognitiveSummary,
    ExamMatrixSpec
)
from .extractor import extract_file_content
from .ai_generator import (
    generate_with_gemini,
    generate_with_openai,
    get_env_api_keys,
    mask_key,
    clean_json_string
)

CV7991_PROMPT = """Bạn là chuyên gia thẩm định và khảo thí giáo dục hàng đầu của Bộ Giáo dục & Đào tạo Việt Nam.
Nhiệm vụ của bạn là đọc hiểu và bóc tách toàn bộ dữ liệu từ tệp MA TRẬN ĐỀ KIỂM TRA ĐỊNH KÌ và/hoặc BẢN ĐẶC TẢ ĐỀ KIỂM TRA ĐỊNH KÌ
theo đúng chuẩn biểu mẫu chính thức tại PHỤ LỤC ban hành kèm theo Công văn số 7991/BGDĐT-GDTrH ngày 17/12/2024 của Bộ GDĐT.

BIỂU MẪU CÔNG VĂN 7991/BGDĐT-GDTrH GỒM 2 BẢNG:
1. BẢNG 1: MA TRẬN ĐỀ KIỂM TRA ĐỊNH KÌ
   - Các cột: TT | Chủ đề/Chương | Nội dung/đơn vị kiến thức | Mức độ đánh giá (chia theo 4 hình thức thi) | Tổng theo mức độ (Biết, Hiểu, Vận dụng) | Tỉ lệ % điểm.
   - 4 hình thức câu hỏi trong bảng:
     + TNKQ Nhiều lựa chọn (Phần I của đề thi): có 3 cột con Biết | Hiểu | Vận dụng
     + TNKQ "Đúng - Sai" (Phần II của đề thi): có 3 cột con Biết | Hiểu | Vận dụng. Mỗi câu gồm 4 ý nhỏ a, b, c, d; trong ô có thể ghi số câu 'n' hoặc '(n)'.
     + TNKQ Trả lời ngắn (Phần III của đề thi): có 3 cột con Biết | Hiểu | Vận dụng.
     + Tự luận (Phần IV của đề thi): có 3 cột con Biết | Hiểu | Vận dụng.
   - Các dòng tổng kết cuối bảng:
     + Tổng số câu (theo từng dạng và từng mức độ).
     + Tổng số điểm: ví dụ 3,0đ (Nhiều lựa chọn) | 2,0đ (Đúng - Sai) | 2,0đ (Trả lời ngắn) | 3,0đ (Tự luận); Tổng điểm: Biết 4,0đ (40%) | Hiểu 3,0đ (30%) | Vận dụng 3,0đ (30%).
     + Tỉ lệ %: 30% | 20% | 20% | 30% theo dạng; 40% | 30% | 30% theo mức độ nhận thức.

2. BẢNG 2: BẢN ĐẶC TẢ ĐỀ KIỂM TRA ĐỊNH KÌ
   - Các cột: TT | Chủ đề/Chương | Nội dung/đơn vị kiến thức | Yêu cầu cần đạt | Số câu hỏi ở các mức độ đánh giá (Nhiều lựa chọn, "Đúng - Sai", Trả lời ngắn, Tự luận).
   - Cột "Yêu cầu cần đạt" có các gạch đầu dòng rất quan trọng:
     + - Biết: ... (Kiến thức nhận biết cơ bản)
     + - Hiểu: ... (Khả năng giải thích, phân biệt, suy luận)
     + - VD: ... (Vận dụng giải quyết bài tập hoặc tình huống thực tế)

HÃY PHÂN TÍCH TÀI LIỆU DƯỚI ĐÂY VÀ TRẢ VỀ DUY NHẤT MỘT CHUỖI JSON HỢP LỆ VỚI CẤU TRÚC:
{
  "title": "MA TRẬN & BẢN ĐẶC TẢ ĐỀ KIỂM TRA ĐỊNH KÌ MÔN...",
  "subject": "Toán học / Vật lý / Hóa học / Sinh học / Tin học / GDQP / Lịch sử / Địa lý / Ngữ văn / Tiếng Anh...",
  "grade": "12" (hoặc "11", "10", "9", "8", "7", "6"),
  "duration_minutes": 50 (số nguyên số phút làm bài, e.g. 45, 50, 90),
  "school_name": "Tên trường hoặc Sở nếu có, hoặc để trống",
  "academic_year": "NĂM HỌC 2026 - 2027",
  "num_part1": 12 (Tổng số câu hỏi TNKQ nhiều lựa chọn),
  "num_part2": 4 (Tổng số câu hỏi TNKQ Đúng - Sai),
  "num_part3": 6 (Tổng số câu hỏi TNKQ Trả lời ngắn),
  "num_essay": 0 (Tổng số câu hỏi Tự luận, nếu không có tự luận thì là 0),
  "total_points": 10.0,
  "scoring_summary": {
    "part1_points": 3.0,
    "part2_points": 2.0,
    "part3_points": 2.0,
    "part4_points": 3.0
  },
  "cognitive_summary": {
    "biet_count": 14,
    "biet_pct": 40.0,
    "hieu_count": 10,
    "hieu_pct": 30.0,
    "vd_count": 8,
    "vd_pct": 30.0
  },
  "topics": [
    {
      "id": 1,
      "topic": "Tên Chủ đề / Chương (Ví dụ: Chủ đề 1: Hàm số và đồ thị)",
      "sub_topic": "Nội dung / đơn vị kiến thức cụ thể (Ví dụ: Tính đơn điệu của hàm số)",
      "requirements": {
        "recognition": "Nội dung sau gạch đầu dòng - Biết: ...",
        "comprehension": "Nội dung sau gạch đầu dòng - Hiểu: ...",
        "application": "Nội dung sau gạch đầu dòng - VD: ..."
      },
      "part1_mcq": {"biet": 2, "hieu": 1, "vd": 0},
      "part2_tf": {"biet": 0, "hieu": 1, "vd": 0},
      "part3_short": {"biet": 0, "hieu": 0, "vd": 1},
      "part4_essay": {"biet": 0, "hieu": 0, "vd": 0},
      "total_questions": 4,
      "points": 1.5
    }
  ]
}

QUY TẮC QUAN TRỌNG:
1. Đọc kỹ số lượng ở từng cột. Nếu ô có ghi '(1)' hoặc '(2)' hoặc '1', '2' thì đó là số câu hỏi.
2. Với các yêu cầu cần đạt (- Biết, - Hiểu, - VD), hãy trích xuất nguyên văn đầy đủ để đưa vào 'requirements'.
3. Nếu tài liệu chỉ có Ma trận (Bảng 1) mà không có Bản đặc tả (Bảng 2), hãy tự động suy luận các yêu cầu cần đạt cốt lõi bám sát chương trình GDPT 2018 cho từng chủ đề.
4. Chỉ trả về chuỗi JSON thuần túy, không bọc trong ```json và không kèm văn bản giải thích.
"""

def detect_subject_from_text(text: str) -> str:
    lower = text.lower()
    if "quốc phòng" in lower or "gdqp" in lower or "quân sự" in lower or "an ninh" in lower:
        return "Giáo dục Quốc phòng & An ninh"
    elif "công nghệ" in lower or "cong nghe" in lower:
        return "Công nghệ"
    elif "tin học" in lower or "tin 10" in lower or "tin 11" in lower or "tin 12" in lower or "python" in lower:
        return "Tin học"
    elif "vật lý" in lower or "vật lí" in lower or "vat li" in lower or "dao động" in lower:
        return "Vật lý"
    elif "hóa học" in lower or "hóa 1" in lower or "hoa hoc" in lower or "este" in lower:
        return "Hóa học"
    elif "sinh học" in lower or "sinh 1" in lower or "di truyền" in lower:
        return "Sinh học"
    elif "lịch sử" in lower or "lich su" in lower:
        return "Lịch sử"
    elif "địa lý" in lower or "địa lí" in lower or "dia ly" in lower:
        return "Địa lý"
    elif "tiếng anh" in lower or "english" in lower:
        return "Tiếng Anh"
    elif "kinh tế" in lower or "gdkt" in lower or "pháp luật" in lower:
        return "Giáo dục kinh tế & Pháp luật"
    elif "ngữ văn" in lower or "văn học" in lower:
        return "Ngữ văn"
    else:
        return "Toán học"

def detect_grade_from_text(text: str) -> str:
    for g in ["12", "11", "10", "9", "8", "7", "6"]:
        re_pattern = rf"(?:lớp|khối|k|khóa)\s*{g}\b|_\b{g}\b|\b{g}\b"
        if re.search(re_pattern, text[:2000], re.IGNORECASE):
            return g
    return "12"

def detect_duration_from_text(text: str) -> int:
    m = re.search(r"(\d+)\s*(?:phút|min|p\b)", text[:2000], re.IGNORECASE)
    if m:
        val = int(m.group(1))
        if 15 <= val <= 180:
            return val
    return 50

def parse_cv7991_heuristic(text: str) -> ExamMatrixSpec:
    """
    Thuật toán Heuristic quét các dòng văn bản và bảng Markdown
    để trích xuất ma trận chuẩn Công văn 7991 khi không có kết nối LLM.
    """
    subject = detect_subject_from_text(text)
    grade = detect_grade_from_text(text)
    duration = detect_duration_from_text(text)
    
    title = f"MA TRẬN & BẢN ĐẶC TẢ ĐỀ KIỂM TRA MÔN {subject.upper()} {grade}"
    
    # Tìm kiếm các dòng bảng chứa Chủ đề
    lines = text.split("\n")
    topics: List[Cv7991TopicItem] = []
    
    current_topic_name = ""
    sub_topic_name = ""
    req_biet = ""
    req_hieu = ""
    req_vd = ""
    
    topic_counter = 1
    num_p1 = 0
    num_p2 = 0
    num_p3 = 0
    num_p4 = 0
    
    total_biet = 0
    total_hieu = 0
    total_vd = 0

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
            
        # Kiểm tra nếu là dòng bảng có dấu |
        if "|" in line:
            parts = [p.strip() for p in line.split("|") if p.strip()]
            if not parts:
                continue
                
            # Kiểm tra dòng tiêu đề hoặc dòng tổng
            first_col_lower = parts[0].lower()
            if "tổng" in first_col_lower or "cộng" in first_col_lower:
                # Quét các số ở dòng tổng
                nums = []
                for p in parts[1:]:
                    found_nums = re.findall(r"\b\d+(?:[.,]\d+)?\b", p)
                    nums.extend(found_nums)
                continue
                
            if "chủ đề" in first_col_lower or "stt" in first_col_lower or "mức độ" in first_col_lower or "tnkq" in first_col_lower:
                continue
                
            # Nhận diện dòng chứa tên Chủ đề
            # Ví dụ: 1 | Chủ đề 1: Este - Lipit | Este | ...
            col_text = " ".join(parts[:3])
            m_topic = re.search(r"(chủ\s*đề\s*\d+[^|]*|chương\s*\d+[^|]*|bài\s*\d+[^|]*)", col_text, re.IGNORECASE)
            if m_topic:
                current_topic_name = m_topic.group(1).strip(" -:;,")
            elif not current_topic_name and len(parts) >= 2 and not parts[0].isdigit():
                current_topic_name = parts[0]
                
            sub_name = parts[1] if len(parts) > 1 and parts[1] != current_topic_name else current_topic_name
            
            # Quét số câu hỏi ở các cột số
            int_candidates = []
            for p in parts:
                # Trích xuất số dạng '2', '(2)', '2.0', v.v.
                # Bỏ qua các chuỗi như "Biết", "Hiểu"
                if p.isdigit():
                    int_candidates.append(int(p))
                else:
                    m_paren = re.search(r"\((\d+)\)", p)
                    if m_paren:
                        int_candidates.append(int(m_paren.group(1)))
                        
            # Nếu dòng có chứa số câu hỏi
            if int_candidates:
                # Phân bổ giả định theo thứ tự các cột của CV 7991:
                # Nhiều lựa chọn (NB, TH, VD) | Đúng - Sai (NB, TH, VD) | Trả lời ngắn (NB, TH, VD) | Tự luận (NB, TH, VD)
                p1_nb = int_candidates[0] if len(int_candidates) > 0 else 0
                p1_th = int_candidates[1] if len(int_candidates) > 1 else 0
                p1_vd = int_candidates[2] if len(int_candidates) > 2 else 0
                
                p2_nb = int_candidates[3] if len(int_candidates) > 3 else 0
                p2_th = int_candidates[4] if len(int_candidates) > 4 else 0
                p2_vd = int_candidates[5] if len(int_candidates) > 5 else 0
                
                p3_nb = int_candidates[6] if len(int_candidates) > 6 else 0
                p3_th = int_candidates[7] if len(int_candidates) > 7 else 0
                p3_vd = int_candidates[8] if len(int_candidates) > 8 else 0
                
                p4_nb = int_candidates[9] if len(int_candidates) > 9 else 0
                p4_th = int_candidates[10] if len(int_candidates) > 10 else 0
                p4_vd = int_candidates[11] if len(int_candidates) > 11 else 0
                
                t_p1 = p1_nb + p1_th + p1_vd
                t_p2 = p2_nb + p2_th + p2_vd
                t_p3 = p3_nb + p3_th + p3_vd
                t_p4 = p4_nb + p4_th + p4_vd
                
                item = Cv7991TopicItem(
                    id=topic_counter,
                    topic=current_topic_name or f"Chủ đề {topic_counter}",
                    sub_topic=sub_name if sub_name != current_topic_name else "",
                    requirements=TopicRequirements(
                        recognition=req_biet or f"Nhận biết kiến thức cốt lõi của {current_topic_name}",
                        comprehension=req_hieu or f"Hiểu và giải thích các tính chất, công thức của {current_topic_name}",
                        application=req_vd or f"Vận dụng giải các bài toán thực tiễn về {current_topic_name}"
                    ),
                    part1_mcq=CognitiveBreakdown(biet=p1_nb, hieu=p1_th, vd=p1_vd),
                    part2_tf=CognitiveBreakdown(biet=p2_nb, hieu=p2_th, vd=p2_vd),
                    part3_short=CognitiveBreakdown(biet=p3_nb, hieu=p3_th, vd=p3_vd),
                    part4_essay=CognitiveBreakdown(biet=p4_nb, hieu=p4_th, vd=p4_vd),
                    total_questions=t_p1 + t_p2 + t_p3 + t_p4,
                    points=round(t_p1 * 0.25 + t_p2 * 1.0 + t_p3 * 0.5 + t_p4 * 1.0, 2)
                )
                topics.append(item)
                topic_counter += 1
                
                num_p1 += t_p1
                num_p2 += t_p2
                num_p3 += t_p3
                num_p4 += t_p4
                
                total_biet += (p1_nb + p2_nb + p3_nb + p4_nb)
                total_hieu += (p1_th + p2_th + p3_th + p4_th)
                total_vd += (p1_vd + p2_vd + p3_vd + p4_vd)
                
                req_biet = ""
                req_hieu = ""
                req_vd = ""
                
        else:
            # Thu thập các dòng Yêu cầu cần đạt
            if "- biết" in line.lower() or "nhận biết:" in line.lower():
                req_biet = line.split(":", 1)[-1].strip() if ":" in line else line
            elif "- hiểu" in line.lower() or "thông hiểu:" in line.lower():
                req_hieu = line.split(":", 1)[-1].strip() if ":" in line else line
            elif "- vd" in line.lower() or "vận dụng:" in line.lower():
                req_vd = line.split(":", 1)[-1].strip() if ":" in line else line
            elif re.match(r"^chủ\s*đề\s*\d+", line, re.IGNORECASE):
                current_topic_name = line.strip(" -:;,")

    # Nếu không bóc tách được các chủ đề từ bảng do định dạng đặc thù,
    # tạo bộ phân bổ chủ đề chuẩn Công văn 7991 theo môn học
    if not topics:
        topics = [
            Cv7991TopicItem(
                id=1,
                topic=f"Chủ đề 1: Kiến thức trọng tâm môn {subject}",
                sub_topic="Lý thuyết và quy luật nền tảng",
                requirements=TopicRequirements(
                    recognition=f"Nhận biết các khái niệm, định nghĩa, công thức cơ bản môn {subject}.",
                    comprehension=f"Hiểu ý nghĩa, phân biệt và liên hệ các hiện tượng/bài toán môn {subject}.",
                    application=f"Vận dụng công thức giải quyết bài toán cơ bản."
                ),
                part1_mcq=CognitiveBreakdown(biet=6, hieu=4, vd=0),
                part2_tf=CognitiveBreakdown(biet=0, hieu=2, vd=0),
                part3_short=CognitiveBreakdown(biet=0, hieu=0, vd=3),
                part4_essay=CognitiveBreakdown(biet=0, hieu=0, vd=0),
                total_questions=15,
                points=5.0
            ),
            Cv7991TopicItem(
                id=2,
                topic=f"Chủ đề 2: Ứng dụng và giải quyết vấn đề môn {subject}",
                sub_topic="Vận dụng thực tiễn và tính toán nâng cao",
                requirements=TopicRequirements(
                    recognition=f"Nhận biết điều kiện áp dụng và phương pháp giải.",
                    comprehension=f"Hiểu và phân tích mô hình bài toán thực tiễn.",
                    application=f"Vận dụng tổng hợp giải quyết tình huống thực tế môn {subject}."
                ),
                part1_mcq=CognitiveBreakdown(biet=6, hieu=4, vd=0),
                part2_tf=CognitiveBreakdown(biet=0, hieu=2, vd=0),
                part3_short=CognitiveBreakdown(biet=0, hieu=0, vd=3),
                part4_essay=CognitiveBreakdown(biet=0, hieu=0, vd=0),
                total_questions=15,
                points=5.0
            )
        ]
        num_part1 = 20
        num_part2 = 4
        num_part3 = 6
        num_essay = 0
        total_biet = 12
        total_hieu = 12
        total_vd = 6
    else:
        # Chuẩn hóa số lượng
        num_part1 = max(num_p1, sum(t.part1_mcq.biet + t.part1_mcq.hieu + t.part1_mcq.vd for t in topics))
        num_part2 = max(num_p2, sum(t.part2_tf.biet + t.part2_tf.hieu + t.part2_tf.vd for t in topics))
        num_part3 = max(num_p3, sum(t.part3_short.biet + t.part3_short.hieu + t.part3_short.vd for t in topics))
        num_essay = max(num_p4, sum(t.part4_essay.biet + t.part4_essay.hieu + t.part4_essay.vd for t in topics))

    # Đảm bảo các giá trị tối thiểu hợp lệ nếu bảng chỉ có tiêu đề
    if num_part1 == 0 and num_part2 == 0 and num_part3 == 0 and num_essay == 0:
        num_part1, num_part2, num_part3, num_essay = 20, 4, 6, 0

    total_q = total_biet + total_hieu + total_vd
    if total_q == 0:
        total_q = num_part1 + num_part2 + num_part3 + num_essay
        total_biet = int(total_q * 0.4)
        total_hieu = int(total_q * 0.3)
        total_vd = total_q - total_biet - total_hieu

    biet_pct = round((total_biet / total_q) * 100, 1) if total_q > 0 else 40.0
    hieu_pct = round((total_hieu / total_q) * 100, 1) if total_q > 0 else 30.0
    vd_pct = round(100.0 - biet_pct - hieu_pct, 1)

    return ExamMatrixSpec(
        title=title,
        subject=subject,
        grade=grade,
        duration_minutes=duration,
        num_part1=num_part1,
        num_part2=num_part2,
        num_part3=num_part3,
        num_essay=num_essay,
        total_points=10.0,
        scoring_summary={
            "part1_points": round(num_part1 * 0.25, 2) if num_part1 > 0 else 0.0,
            "part2_points": round(num_part2 * 1.0, 2) if num_part2 > 0 else 0.0,
            "part3_points": 2.0,
            "part4_points": 3.0 if num_essay > 0 else 0.0
        },
        cognitive_summary=CognitiveSummary(
            biet_count=total_biet,
            biet_pct=biet_pct,
            hieu_count=total_hieu,
            hieu_pct=hieu_pct,
            vd_count=total_vd,
            vd_pct=vd_pct
        ),
        topics=topics,
        raw_markdown_table=text[:5000]
    )

async def analyze_matrix_document(
    file_bytes: Optional[bytes] = None,
    filename: Optional[str] = None,
    raw_text: Optional[str] = None,
    api_keys: Optional[List[str]] = None,
    provider: str = "gemini",
    model_name: str = "auto"
) -> ExamMatrixSpec:
    """
    Phân tích file Word/PDF hoặc chuỗi text ma trận theo chuẩn Công văn 7991/BGDĐT-GDTrH.
    Sử dụng kết hợp LLM thông minh và bộ Heuristic dự phòng.
    """
    # 1. Trích xuất toàn văn và bảng biểu
    extracted_text = ""
    if file_bytes and filename:
        extracted_text = extract_file_content(filename, file_bytes)
    elif raw_text:
        extracted_text = raw_text.strip()
        
    if not extracted_text:
        raise ValueError("Tệp tải lên hoặc nội dung ma trận bị rỗng. Vui lòng kiểm tra lại.")

    # 2. Chuẩn bị danh sách API Keys
    keys = []
    if api_keys:
        keys.extend([k.strip().strip("'\"`") for k in api_keys if k and len(k) > 5])
    if not keys:
        keys.extend(get_env_api_keys(provider))

    # Nếu không có key, dùng ngay bộ Heuristic
    if not keys:
        print("[Matrix Analyzer] Không có API Key, sử dụng bộ Heuristic bóc tách chuẩn Công văn 7991.")
        return parse_cv7991_heuristic(extracted_text)

    # 3. Gọi LLM bóc tách với Schema Công văn 7991
    user_prompt = (
        f"NỘI DUNG TÀI LIỆU MA TRẬN & BẢN ĐẶC TẢ ĐƯỢC TRÍCH XUẤT TỪ TỆP (CẢ BẢNG VÀ ĐOẠN VĂN):\n"
        f"{extracted_text[:40000]}\n\n"
        f"HÃY BÓC TÁCH VÀ TRẢ VỀ DUY NHẤT CHUỖI JSON THEO ĐÚNG CẤU TRÚC ĐÃ YÊU CẦU."
    )
    full_prompt = CV7991_PROMPT + "\n\n" + user_prompt

    raw_json = None
    for attempt_idx, key in enumerate(keys, start=1):
        masked = mask_key(key)
        try:
            if provider == "openai":
                model = model_name or "gpt-4o-mini"
                raw_json = await generate_with_openai(full_prompt, key, model)
            else:
                model = model_name or "auto"
                raw_json = await generate_with_gemini(full_prompt, key, model)
            print(f"[Matrix Analyzer] Đã phân tích ma trận thành công với Key {masked} (Lần thử {attempt_idx})")
            break
        except Exception as e:
            print(f"[Matrix Analyzer] Key {masked} gặp lỗi: {e}. Đang thử key tiếp theo...")
            continue

    if not raw_json:
        print("[Matrix Analyzer] Tất cả API Keys đều lỗi, kích hoạt bộ Heuristic dự phòng.")
        return parse_cv7991_heuristic(extracted_text)

    # 4. Parse JSON kết quả
    cleaned = clean_json_string(raw_json)
    data = None
    try:
        data = json.loads(cleaned)
    except Exception:
        try:
            data = json_repair.loads(cleaned)
        except Exception as e_repair:
            print(f"[Matrix Analyzer] Lỗi parse JSON từ LLM: {e_repair}. Chuyển sang Heuristic.")
            return parse_cv7991_heuristic(extracted_text)

    if not isinstance(data, dict):
        return parse_cv7991_heuristic(extracted_text)

    # 5. Khớp dữ liệu vào ExamMatrixSpec
    try:
        topics_list = []
        raw_topics = data.get("topics", [])
        if isinstance(raw_topics, list):
            for idx, t in enumerate(raw_topics, start=1):
                if not isinstance(t, dict):
                    continue
                reqs = t.get("requirements", {})
                req_obj = TopicRequirements(
                    recognition=str(reqs.get("recognition") or reqs.get("biet") or ""),
                    comprehension=str(reqs.get("comprehension") or reqs.get("hieu") or ""),
                    application=str(reqs.get("application") or reqs.get("vd") or reqs.get("van_dung") or "")
                )
                
                def make_cb(val):
                    if isinstance(val, dict):
                        return CognitiveBreakdown(
                            biet=int(val.get("biet") or val.get("nb") or 0),
                            hieu=int(val.get("hieu") or val.get("th") or 0),
                            vd=int(val.get("vd") or val.get("vdc") or 0)
                        )
                    return CognitiveBreakdown()

                item = Cv7991TopicItem(
                    id=int(t.get("id") or idx),
                    topic=str(t.get("topic") or t.get("chu_de") or f"Chủ đề {idx}"),
                    sub_topic=str(t.get("sub_topic") or t.get("noi_dung") or ""),
                    requirements=req_obj,
                    part1_mcq=make_cb(t.get("part1_mcq")),
                    part2_tf=make_cb(t.get("part2_tf")),
                    part3_short=make_cb(t.get("part3_short")),
                    part4_essay=make_cb(t.get("part4_essay")),
                    total_questions=int(t.get("total_questions") or 0),
                    points=float(t.get("points") or 0.0)
                )
                topics_list.append(item)

        cog_sum = data.get("cognitive_summary", {})
        cog_obj = CognitiveSummary(
            biet_count=int(cog_sum.get("biet_count") or cog_sum.get("nb") or 0),
            biet_pct=float(cog_sum.get("biet_pct") or 40.0),
            hieu_count=int(cog_sum.get("hieu_count") or cog_sum.get("th") or 0),
            hieu_pct=float(cog_sum.get("hieu_pct") or 30.0),
            vd_count=int(cog_sum.get("vd_count") or cog_sum.get("vd") or 0),
            vd_pct=float(cog_sum.get("vd_pct") or 30.0)
        )

        matrix_spec = ExamMatrixSpec(
            title=str(data.get("title") or f"MA TRẬN ĐỀ KIỂM TRA MÔN {data.get('subject', 'TOÁN HỌC')}"),
            subject=str(data.get("subject") or detect_subject_from_text(extracted_text)),
            grade=str(data.get("grade") or detect_grade_from_text(extracted_text)),
            duration_minutes=int(data.get("duration_minutes") or detect_duration_from_text(extracted_text)),
            school_name=str(data.get("school_name") or ""),
            academic_year=str(data.get("academic_year") or "NĂM HỌC 2026 - 2027"),
            num_part1=int(data.get("num_part1") or 12),
            num_part2=int(data.get("num_part2") or 4),
            num_part3=int(data.get("num_part3") or 6),
            num_essay=int(data.get("num_essay") or 0),
            total_points=float(data.get("total_points") or 10.0),
            scoring_summary=data.get("scoring_summary") or {},
            cognitive_summary=cog_obj,
            topics=topics_list,
            raw_markdown_table=extracted_text[:5000]
        )
        return matrix_spec
    except Exception as e_spec:
        print(f"[Matrix Analyzer] Lỗi cấu trúc hóa kết quả LLM: {e_spec}. Chuyển sang Heuristic.")
        return parse_cv7991_heuristic(extracted_text)
