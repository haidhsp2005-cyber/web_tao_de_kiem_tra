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

QUY TẮC CỐT LÕI VỀ MỨC ĐỘ NHẬN THỨC THEO CÔNG VĂN 7991:
1. CHỈ CÓ 3 MỨC ĐỘ NHẬN THỨC: Nhận biết, Thông hiểu, Vận dụng.
2. TUYỆT ĐỐI KHÔNG CÓ MỨC "VẬN DỤNG CAO". Mức "Vận dụng cao" đã bị bãi bỏ hoàn toàn theo CV 7991. Toàn bộ câu hỏi tự luận, bài tập thực hành, hoặc ý (d) của câu hỏi Đúng - Sai đều thuộc mức "Vận dụng".

BIỂU MẪU CÔNG VĂN 7991/BGDĐT-GDTrH GỒM 2 BẢNG:
1. BẢNG 1: MA TRẬN ĐỀ KIỂM TRA ĐỊNH KÌ
   - Các cột: TT | Chủ đề/Chương | Nội dung/đơn vị kiến thức | Mức độ đánh giá (chia theo 4 hình thức thi) | Tổng theo mức độ (Biết, Hiểu, Vận dụng) | Tỉ lệ % điểm.
   - 4 hình thức câu hỏi trong bảng và các ký hiệu viết tắt giáo viên thường dùng trong ô:
     + TNKQ Nhiều lựa chọn (Phần I của đề thi): cột Biết | Hiểu | Vận dụng. Ký hiệu thường gặp: '1 MC', '2 MC', '1 MCQ', '1 TNKQ' hoặc số nguyên '1', '2'.
     + TNKQ "Đúng - Sai" (Phần II của đề thi): cột Biết | Hiểu | Vận dụng. Ký hiệu thường gặp: '2 YN1(a,b)', '1 YN1(c)', '1 YN1(d)', 'YN2(...)', 'ĐS1(...)'. Mỗi câu hỏi lớn gồm 4 ý lệnh nhỏ a, b, c, d (phân hóa: 2 Biết, 1 Hiểu, 1 Vận dụng).
       * QUY TẮC PHẦN II (ĐÚNG - SAI): 
         - Trường "num_part2" là SỐ CÂU HỎI LỚN (ví dụ YN1, YN2, YN3, YN4 -> num_part2 là 4), KHÔNG PHẢI tổng số lệnh hỏi a,b,c,d (16 lệnh).
         - Trong mảng "topics", CHỈ GÁN part2_tf CHO ĐÚNG BÀI NÀO CÓ KÝ HIỆU YN TRONG MA TRẬN (ví dụ: YN1 ở Bài 1, YN2 ở Bài 4, YN3 ở Bài 5, YN4 ở Bài 9). Các bài khác (như Bài 2, 3, 6, 7, 8) KHÔNG có YN thì BẮT BUỘC gán "part2_tf": {"biet": 0, "hieu": 0, "vd": 0}.
     + TNKQ Trả lời ngắn (Phần III của đề thi): cột Biết | Hiểu | Vận dụng. Ký hiệu thường gặp: '1 TLN', '1 SA' hoặc số nguyên.
       * QUY TẮC: Nếu bảng KHÔNG CÓ cột Trả lời ngắn hoặc ghi 0 câu/ý hoặc để trống, thì BẮT BUỘC "num_part3": 0 và "scoring_summary.part3_points": 0.0. TUYỆT ĐỐI KHÔNG tự ý điền 6 câu.
     + Tự luận (Phần IV của đề thi): cột Biết | Hiểu | Vận dụng. Ký hiệu thường gặp: '1 TL1', '1 TL2', '1 TL'.
       * QUY TẮC TỰ LUẬN CỰC KỲ QUAN TRỌNG:
         - "num_essay" là số câu hỏi tự luận (ví dụ TL1, TL2 -> num_essay là 2) và "scoring_summary.part4_points" là điểm tự luận tương ứng (ví dụ 2.0). Nếu không có, "num_essay": 0 và "part4_points": 0.0.
         - Trong mảng "topics", CHỈ GÁN part4_essay CHO ĐÚNG BÀI NÀO CÓ KÝ HIỆU TL TRONG MA TRẬN (ví dụ: TL1 ở Bài 2 -> Bài 2 có "part4_essay": {"biet": 0, "hieu": 0, "vd": 1}; TL2 ở Bài 8 -> Bài 8 có "part4_essay": {"biet": 0, "hieu": 0, "vd": 1}).
         - TẤT CẢ CÁC BÀI KHÁC (như Bài 1, 3, 4, 5, 6, 7, 9) KHÔNG CÓ KÝ HIỆU TL thì BẮT BUỘC gán "part4_essay": {"biet": 0, "hieu": 0, "vd": 0}. TUYỆT ĐỐI KHÔNG gán tự luận nhầm sang Bài 1 hay bất kỳ bài nào không có TL!
   - Các dòng tổng kết cuối bảng (BẮT BUỘC PHẢI ĐỐI CHIẾU VỚI CÁC DÒNG NÀY):
     + Dòng "Tổng số câu/ý": Ghi tổng số câu hoặc ý lệnh cho từng phần và tổng chung (ví dụ: Nhiều lựa chọn 16 câu, Đúng/Sai 16 ý = 4 câu lớn, Tự luận 2 câu -> Tổng 34 câu/ý).
     + Dòng "Tổng số điểm": Ví dụ Nhiều lựa chọn 4.0đ | Đúng - Sai 4.0đ | Trả lời ngắn 0.0đ | Tự luận 2.0đ -> Tổng điểm 10.0đ.
     + Dòng "Tỉ lệ %": Biết (40%) | Hiểu (30%) | Vận dụng (30%).

2. BẢNG 2: BẢN ĐẶC TẢ ĐỀ KIỂM TRA ĐỊNH KÌ
   - Các cột: TT | Chủ đề/Chương | Nội dung/đơn vị kiến thức | Yêu cầu cần đạt | Mức độ đánh giá (Nhiều lựa chọn, Đúng/Sai, Tự luận, Trả lời ngắn).
   - Cột "Yêu cầu cần đạt" chứa văn bản chi tiết theo từng mức độ nhận thức:
     + - Nhận biết: ... (Kiến thức nhận biết cơ bản)
     + - Thông hiểu: ... (Khả năng giải thích, so sánh, phân biệt)
     + - Vận dụng: ... (Khả năng áp dụng, giải quyết tình huống thực tế, phân tích nguy cơ, viết mã/thuật toán...)
   - BẮT BUỘC TRÍCH XUẤT NGUYÊN VĂN NỘI DUNG YÊU CẦU CẦN ĐẠT CỦA TỪNG BÀI/NỘI DUNG vào trường 'requirements' tương ứng (recognition, comprehension, application).

HÃY PHÂN TÍCH TÀI LIỆU DƯỚI ĐÂY VÀ TRẢ VỀ DUY NHẤT MỘT CHUỖI JSON HỢP LỆ VỚI CẤU TRÚC:
{
  "title": "MA TRẬN & BẢN ĐẶC TẢ ĐỀ KIỂM TRA MÔN TIN HỌC 12 GIỮA KÌ I...",
  "subject": "Tin học" (hoặc Toán học / Vật lý / Hóa học / Sinh học / Lịch sử / Địa lý / GDQP / Tiếng Anh...),
  "grade": "12" (hoặc "11", "10", "9", "8", "7", "6"),
  "duration_minutes": 45 (số nguyên số phút làm bài theo tài liệu),
  "school_name": "Tên trường hoặc Sở nếu có, hoặc để trống",
  "academic_year": "NĂM HỌC 2026 - 2027",
  "num_part1": 16 (Số câu TNKQ nhiều lựa chọn từ dòng tổng kết, ví dụ 16 hoặc 12),
  "num_part2": 4 (Số câu TNKQ Đúng - Sai lớn, mỗi câu 4 ý a,b,c,d; ví dụ 4),
  "num_part3": 0 (Số câu Trả lời ngắn, nếu ma trận không có dạng này thì là 0),
  "num_essay": 2 (Số câu Tự luận, ví dụ 2 hoặc 0 nếu không có),
  "total_points": 10.0,
  "scoring_summary": {
    "part1_points": 4.0,
    "part2_points": 4.0,
    "part3_points": 0.0,
    "part4_points": 2.0
  },
  "cognitive_summary": {
    "biet_count": 16,
    "biet_pct": 40.0,
    "hieu_count": 12,
    "hieu_pct": 30.0,
    "vd_count": 6,
    "vd_pct": 30.0
  },
  "topics": [
    {
      "id": 1,
      "topic": "Chủ đề 1. Máy tính và xã hội tri thức",
      "sub_topic": "1. Làm quen với trí tuệ nhân tạo",
      "requirements": {
        "recognition": "Trình bày được khái niệm AI, các đặc trưng cơ bản.",
        "comprehension": "Hiểu được lợi ích và nêu ví dụ ứng dụng điển hình.",
        "application": "Đánh giá độ tin cậy và vai trò con người trong hệ thống AI."
      },
      "part1_mcq": {"biet": 1, "hieu": 1, "vd": 0},
      "part2_tf": {"biet": 2, "hieu": 1, "vd": 1},
      "part3_short": {"biet": 0, "hieu": 0, "vd": 0},
      "part4_essay": {"biet": 0, "hieu": 0, "vd": 0},
      "total_questions": 6,
      "points": 1.5
    }
  ]
}

QUY TẮC BẮT BUỘC:
1. Đọc kỹ số lượng từ dòng TỔNG SỐ CÂU/Ý và TỔNG SỐ ĐIỂM của tài liệu để điền chính xác num_part1, num_part2, num_part3, num_essay.
2. Với các yêu cầu cần đạt (- Nhận biết, - Thông hiểu, - Vận dụng), hãy trích xuất nguyên văn đầy đủ từ Bản đặc tả để đưa vào 'requirements' của mỗi bài.
3. Nếu tài liệu chỉ có Ma trận (Bảng 1) mà không có Bản đặc tả (Bảng 2), hãy tự động suy luận các yêu cầu cần đạt bám sát chương trình GDPT 2018 cho từng chủ đề.
4. Chỉ trả về chuỗi JSON thuần túy, không bọc trong ```json và không kèm văn bản giải thích.
"""

def detect_subject_from_text(text: str) -> str:
    lower = text.lower()
    
    # 1. Kiểm tra tiêu đề / phần khai báo môn học rõ ràng ở đầu tài liệu
    m_header = re.search(
        r'(?:môn|môn\s*học|phân\s*môn|bài\s*kiểm\s*tra\s*môn|đề\s*(?:thi|kiểm\s*tra)\s*môn?|ma\s*trận.*?môn)\s*[:\-–—]?\s*([^\n\r,\.;]{2,35})',
        text[:1500],
        re.IGNORECASE
    )
    if m_header:
        h = m_header.group(1).lower().strip()
        if any(k in h for k in ['tin học', 'tin', 'informatics', 'lập trình']):
            return 'Tin học'
        if any(k in h for k in ['tiếng anh', 'english', 'ngoại ngữ']):
            return 'Tiếng Anh'
        if any(k in h for k in ['toán học', 'toán', 'giải tích', 'đại số', 'hình học']):
            return 'Toán học'
        if any(k in h for k in ['vật lý', 'vật lí', 'vật li']):
            return 'Vật lý'
        if any(k in h for k in ['hóa học', 'hóa']):
            return 'Hóa học'
        if any(k in h for k in ['sinh học', 'sinh']):
            return 'Sinh học'
        if any(k in h for k in ['quốc phòng', 'gdqp', 'quân sự']):
            return 'Giáo dục Quốc phòng & An ninh'
        if any(k in h for k in ['lịch sử', 'sử']):
            return 'Lịch sử'
        if any(k in h for k in ['địa lý', 'địa lí', 'địa li']):
            return 'Địa lý'
        if any(k in h for k in ['kinh tế', 'pháp luật', 'gdkt', 'gdcd']):
            return 'Giáo dục kinh tế & Pháp luật'
        if any(k in h for k in ['ngữ văn', 'văn học', 'văn']):
            return 'Ngữ văn'
        if any(k in h for k in ['công nghệ']):
            return 'Công nghệ'

    scores = {}

    # --- Tin học ---
    tin_score = 0
    tin_high = [
        'tin học', 'môn tin', 'trí tuệ nhân tạo', 'trí tuệ nhân tạo (ai)', 'machine learning', 
        'học máy', 'deep learning', 'mạng máy tính', 'lập trình', 'thuật toán', 
        'ngôn ngữ lập trình', 'cơ sở dữ liệu', 'csdl', 'hệ quản trị csdl', 'hệ điều hành'
    ]
    tin_med = [
        'python', 'pascal', 'scratch', 'c++', 'bảng tính', 'excel', 'phần mềm', 'phần cứng', 
        'bộ nhớ ram', 'địa chỉ ip', 'an toàn số', 'an toàn mạng', 'an toàn thông tin', 
        'số nhị phân', 'bit', 'byte', 'trình duyệt', 'router', 'switch', 'lan', 'wan', 
        'tường lửa', 'mã độc', 'truy vấn sql', 'khoa học máy tính'
    ]
    for k in tin_high:
        if k in lower:
            tin_score += 10
    for k in tin_med:
        if k in lower:
            tin_score += 5
    if re.search(r'\b(?:ai|agi|lan|wan|cpu|ram|rom|sql|html|css)\b', lower):
        tin_score += 6
    if re.search(r'for\s+\w+\s+in\s+range|def\s+\w+\s*\(|print\s*\(|input\s*\(', text):
        tin_score += 10
    scores['Tin học'] = tin_score

    # --- Tiếng Anh ---
    ta_score = 0
    ta_high = [
        'tiếng anh', 'english', 'ielts', 'toeic', 'toefl', 'pronunciation', 'phonetics', 
        'stress pattern', 'closest in meaning', 'opposite in meaning', 'reading comprehension', 
        'read the following passage', 'sentence transformation', 'word formation', 'cloze test'
    ]
    for k in ta_high:
        if k in lower:
            ta_score += 10
    vocab_pairs = len(re.findall(r'^[a-zA-Z\s\-]+(?:\([a-zA-Z\s\.,]+\))?\s*[:\-=\/]\s*[\w\s]+', text[:3000], re.MULTILINE))
    if vocab_pairs >= 3:
        ta_score += vocab_pairs * 4
    # Chỉ tính mật độ từ tiếng Anh nếu tài liệu không chứa các thuật ngữ Tin học chuyên ngành
    if tin_score < 8:
        common_en_words = {
            'the', 'be', 'to', 'of', 'and', 'in', 'that', 'have', 'for', 'not', 'with', 'you', 
            'this', 'but', 'his', 'from', 'they', 'say', 'her', 'she', 'will', 'one', 'all', 
            'would', 'there', 'their', 'what', 'out', 'about', 'who', 'which', 'when', 'can', 
            'time', 'just', 'into', 'your', 'good', 'some', 'could', 'them', 'other', 'than', 
            'then', 'now', 'only', 'come', 'over', 'also', 'after', 'use', 'two', 'how', 'our', 
            'work', 'well', 'way', 'even', 'new', 'want', 'because', 'any', 'these', 'give', 
            'most', 'advice', 'community', 'police', 'officer', 'garbage', 'collector', 
            'electrician', 'firefighter', 'suburb', 'guess', 'useful', 'lesson', 'unit'
        }
        found_en = [w for w in re.findall(r'[a-zA-Z]{2,}', lower[:2000]) if w in common_en_words]
        if len(found_en) >= 8:
            ta_score += 8
    scores['Tiếng Anh'] = ta_score

    # --- Toán học ---
    toan_score = 0
    toan_words = [
        'toán học', 'hàm số', 'đồ thị', 'phương trình', 'hệ phương trình', 'bất đẳng thức', 
        'đạo hàm', 'tích phân', 'nguyên hàm', 'hình chóp', 'tam giác vuông', 'đường tròn', 
        'vectơ', 'tọa độ oxyz', 'parabol', 'tiệm cận'
    ]
    for k in toan_words:
        if k in lower:
            toan_score += 6
    scores['Toán học'] = toan_score

    # --- Hóa học ---
    hoa_score = 0
    hoa_words = [
        'hóa học', 'phản ứng hóa học', 'dung dịch', 'axit', 'bazơ', 'kim loại', 'phi kim', 
        'este', 'hiđrocacbon', 'khối lượng mol', 'nguyên tử khối', 'đồng phân', 'đồng đẳng'
    ]
    for k in hoa_words:
        if k in lower:
            hoa_score += 6
    scores['Hóa học'] = hoa_score

    # --- Vật lý ---
    ly_score = 0
    ly_words = [
        'vật lý', 'vật lí', 'dao động điều hòa', 'sóng cơ', 'con lắc', 'quang học', 
        'thấu kính', 'điện trở', 'cường độ dòng điện', 'hiệu điện thế', 'vận tốc tức thời'
    ]
    for k in ly_words:
        if k in lower:
            ly_score += 6
    scores['Vật lý'] = ly_score

    # --- Sinh học ---
    sinh_score = 0
    sinh_words = [
        'sinh học', 'di truyền', 'nhiễm sắc thể', 'tế bào', 'đột biến gen', 'quần thể', 
        'quần xã', 'hệ sinh thái', 'alen', 'kiểu gen', 'kiểu hình', 'phiên mã', 'dịch mã'
    ]
    for k in sinh_words:
        if k in lower:
            sinh_score += 6
    scores['Sinh học'] = sinh_score

    # --- Giáo dục Quốc phòng & An ninh ---
    gdqp_score = 0
    gdqp_words = [
        'quốc phòng', 'an ninh', 'gdqp', 'quân đội', 'nghĩa vụ quân sự', 'chiến thuật', 
        'bắn súng', 'sơ cấp cứu', 'bảo vệ tổ quốc', 'ngạch dự bị'
    ]
    for k in gdqp_words:
        if k in lower:
            gdqp_score += 8
    scores['Giáo dục Quốc phòng & An ninh'] = gdqp_score

    # --- Lịch sử ---
    su_score = 0
    su_words = ['lịch sử', 'chiến dịch', 'khởi nghĩa', 'cách mạng', 'kháng chiến', 'triều đại', 'hiệp định']
    for k in su_words:
        if k in lower:
            su_score += 6
    scores['Lịch sử'] = su_score

    # --- Địa lý ---
    dia_score = 0
    dia_words = ['địa lý', 'địa lí', 'địa hình', 'khí hậu', 'sông ngòi', 'thổ nhưỡng', 'vùng kinh tế', 'khoáng sản']
    for k in dia_words:
        if k in lower:
            dia_score += 6
    scores['Địa lý'] = dia_score

    # --- Giáo dục kinh tế & Pháp luật ---
    gdkt_score = 0
    gdkt_words = ['kinh tế & pháp luật', 'kinh tế và pháp luật', 'gdkt', 'gdcd', 'pháp luật', 'hiến pháp', 'lạm phát', 'cung cầu']
    for k in gdkt_words:
        if k in lower:
            gdkt_score += 8
    scores['Giáo dục kinh tế & Pháp luật'] = gdkt_score

    # --- Ngữ văn ---
    van_score = 0
    van_words = ['ngữ văn', 'văn học', 'tác phẩm', 'nhà thơ', 'nhà văn', 'nhân vật', 'nghị luận xã hội', 'nghị luận văn học']
    for k in van_words:
        if k in lower:
            van_score += 6
    scores['Ngữ văn'] = van_score

    # --- Công nghệ ---
    cn_score = 0
    cn_words = ['công nghệ', 'trồng trọt', 'chăn nuôi', 'lâm nghiệp', 'thủy sản', 'cơ khí', 'mạch điện', 'bản vẽ kỹ thuật']
    for k in cn_words:
        if k in lower:
            cn_score += 6
    scores['Công nghệ'] = cn_score

    best_subj, max_s = max(scores.items(), key=lambda x: x[1])
    if max_s > 0:
        return best_subj
    return 'Toán học'

def detect_grade_from_text(text: str) -> str:
    # 1. Ưu tiên tiền tố định danh lớp/khối rõ ràng
    patterns = [
        r'(?:lớp|khối\s*lớp|khối|k|grade|unit)\s*([3-9]|1[0-2])\b',
        r'(?:toán|tin|lý|hóa|sinh|anh|văn|sử|địa|gdqp|công\s*nghệ)\s*([3-9]|1[0-2])\b',
        r'[\s_](?:lop|khoi|k)?([3-9]|1[0-2])[\s_\.]'
    ]
    for pat in patterns:
        m = re.search(pat, text[:2500], re.IGNORECASE)
        if m:
            return m.group(1)
            
    # 2. Suy luận dựa trên chủ đề kiến thức đặc thù lớp 12
    if re.search(r'trí tuệ nhân tạo|machine learning|học máy|đạo hàm|tích phân|nguyên hàm|oxyz|este\s*-\s*lipit', text[:3000], re.IGNORECASE):
        return '12'
        
    return '12'

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
    Hỗ trợ cả bảng số truyền thống và ký hiệu viết tắt (1 MC, 2 YN1(a,b), 1 TL1...).
    """
    subject = detect_subject_from_text(text)
    grade = detect_grade_from_text(text)
    duration = detect_duration_from_text(text)
    
    title = f"MA TRẬN & BẢN ĐẶC TẢ ĐỀ KIỂM TRA MÔN {subject.upper()} {grade}"
    
    lines = text.split("\n")
    
    # 1. Trích xuất yêu cầu cần đạt từ Bảng 2 (Bản đặc tả) nếu có
    # Map từ tên bài/tiểu chủ đề -> TopicRequirements
    requirements_map: Dict[str, TopicRequirements] = {}
    for l in lines:
        if "|" in l and ("nhận biết:" in l.lower() or "thông hiểu:" in l.lower() or "vận dụng:" in l.lower()):
            clean_l = re.sub(r"<[^>]+>", "", l)
            parts = [p.strip() for p in clean_l.split("|") if p.strip()]
            for p in parts:
                if "nhận biết:" in p.lower() or "thông hiểu:" in p.lower() or "vận dụng:" in p.lower():
                    nb = re.search(r"[-*•]?\s*Nhận biết\s*:\s*([^.\n-]+(?:\.[^.\n-]+)*)", p, re.IGNORECASE)
                    th = re.search(r"[-*•]?\s*Thông hiểu\s*:\s*([^.\n-]+(?:\.[^.\n-]+)*)", p, re.IGNORECASE)
                    vd = re.search(r"[-*•]?\s*Vận dụng\s*:\s*([^.\n-]+(?:\.[^.\n-]+)*)", p, re.IGNORECASE)
                    
                    req_nb = nb.group(1).strip() if nb else ""
                    req_th = th.group(1).strip() if th else ""
                    req_vd = vd.group(1).strip() if vd else ""
                    
                    row_key = " ".join(parts[:3]).lower()
                    requirements_map[row_key] = TopicRequirements(
                        recognition=req_nb, comprehension=req_th, application=req_vd
                    )

    # 2. Kiểm tra xem tài liệu có chứa ký hiệu viết tắt (MC, YN, TL, SA) hay không
    has_tokens = bool(re.search(r"\b\d+\s*(?:MC|MCQ|YN|TL)\b", text, re.IGNORECASE))

    # 3. Quét dòng tổng kết cuối bảng (nếu có)
    summary_mc_count = None
    summary_short_count = None
    summary_biet_pct = None
    summary_hieu_pct = None
    summary_vd_pct = None

    for raw_l in lines:
        if "|" not in raw_l:
            continue
        clean_row = re.sub(r"<[^>]+>", "", raw_l)
        parts = [p.strip() for p in clean_row.split("|") if p.strip()]
        if not parts:
            continue
        first_col = parts[0].lower()
        if "tỉ lệ %" in first_col or "tỉ lệ" in first_col:
            pcts = [float(p) for p in re.findall(r"(\d+(?:\.\d+)?)\s*%", clean_row)]
            if len(pcts) >= 3:
                summary_biet_pct, summary_hieu_pct, summary_vd_pct = pcts[0], pcts[1], pcts[2]

    # 4. Quét từng dòng chủ đề trong Bảng 1 (Ma trận)
    topics: List[Cv7991TopicItem] = []
    current_topic_name = ""
    topic_counter = 1
    
    all_mc_count = 0
    all_yn_qids = set()
    all_tl_qids = set()
    all_short_count = 0
    
    total_biet = 0
    total_hieu = 0
    total_vd = 0

    # Flag để chỉ đọc bảng 1 (dừng trước khi sang bảng 2 nếu có)
    in_table_1 = True

    for raw_l in lines:
        clean_l = re.sub(r"<[^>]+>", "", raw_l).strip()
        if not clean_l:
            continue
        if "bản đặc tả" in clean_l.lower():
            in_table_1 = False
            
        if not in_table_1:
            continue
            
        if "|" not in clean_l:
            continue
            
        parts = [p.strip() for p in clean_l.split("|")]
        # Bỏ phần tử rỗng ở 2 đầu
        if parts and not parts[0]:
            parts = parts[1:]
        if parts and not parts[-1]:
            parts = parts[:-1]
        if not parts:
            continue
            
        first_col_lower = parts[0].lower()
        if any(k in first_col_lower for k in ["tổng", "cộng", "tt", "stt", "chủ đề", "mức độ", "trắc nghiệm"]):
            continue
            
        # Tìm tiêu đề Chủ đề lớn
        col_text = " ".join(parts[:3])
        m_top = re.search(r"(chủ\s*đề\s*\d+[^|.\n]*|chương\s*\d+[^|.\n]*|phần\s*\d+[^|.\n]*)", col_text, re.IGNORECASE)
        if m_top:
            current_topic_name = m_top.group(1).strip(" -:;,")
        elif not current_topic_name and len(parts) >= 2 and not parts[0].isdigit():
            current_topic_name = parts[0]
            
        # Tên bài/nội dung
        sub_name = ""
        for p in parts[:3]:
            m_sub = re.search(r"(\d+\.\s*[^|\n]+)", p)
            if m_sub:
                sub_name = m_sub.group(1).strip()
                break
        if not sub_name and len(parts) >= 3 and parts[2] and parts[2] != current_topic_name:
            sub_name = parts[2]
        if not sub_name and len(parts) >= 2 and parts[1] != current_topic_name:
            sub_name = parts[1]

        p1_cb = CognitiveBreakdown()
        p2_cb = CognitiveBreakdown()
        p3_cb = CognitiveBreakdown()
        p4_cb = CognitiveBreakdown()

        if has_tokens:
            # Bóc tách theo Tokens (MC, YN, TL, SA)
            for c_idx, cell in enumerate(parts[3:], start=3):
                # 1. MC (Trắc nghiệm nhiều lựa chọn)
                for m in re.finditer(r"(\d+)\s*(?:MC|MCQ|TNKQ)\b", cell, re.IGNORECASE):
                    cnt = int(m.group(1))
                    all_mc_count += cnt
                    if c_idx == 3:
                        p1_cb.biet += cnt
                        total_biet += cnt
                    elif c_idx == 4:
                        p1_cb.hieu += cnt
                        total_hieu += cnt
                    else:
                        p1_cb.vd += cnt
                        total_vd += cnt
                        
                # 2. YN (Trắc nghiệm Đúng - Sai)
                for m in re.finditer(r"(?:(\d+)\s*)?YN(\d+)(?:\(([^)]+)\))?", cell, re.IGNORECASE):
                    subs = m.group(3) or ""
                    cnt = int(m.group(1)) if m.group(1) else (len(subs.split(',')) if subs else 1)
                    qid = m.group(2)
                    all_yn_qids.add(qid)
                    if "a" in subs or "b" in subs:
                        p2_cb.biet += cnt
                        total_biet += cnt
                    elif "c" in subs:
                        p2_cb.hieu += cnt
                        total_hieu += cnt
                    elif "d" in subs:
                        p2_cb.vd += cnt
                        total_vd += cnt
                    else:
                        if c_idx <= 7:
                            p2_cb.biet += cnt
                            total_biet += cnt
                        elif c_idx == 8:
                            p2_cb.hieu += cnt
                            total_hieu += cnt
                        else:
                            p2_cb.vd += cnt
                            total_vd += cnt
                            
                # 3. TL (Tự luận)
                for m in re.finditer(r"(?:(\d+)\s*)?TL(\d+)?\b", cell, re.IGNORECASE):
                    if "TLN" in cell.upper():
                        continue
                    cnt = int(m.group(1)) if m.group(1) else 1
                    qid = m.group(2) or str(topic_counter)
                    all_tl_qids.add(qid)
                    if c_idx <= 9:
                        p4_cb.biet += cnt
                    elif c_idx == 10:
                        p4_cb.hieu += cnt
                    else:
                        p4_cb.vd += cnt
                    total_vd += cnt
                    
                # 4. TLN (Trả lời ngắn)
                for m in re.finditer(r"(\d+)\s*(?:TLN|SA)\b", cell, re.IGNORECASE):
                    cnt = int(m.group(1))
                    all_short_count += cnt
                    if c_idx <= 10:
                        p3_cb.biet += cnt
                        total_biet += cnt
                    elif c_idx == 11:
                        p3_cb.hieu += cnt
                        total_hieu += cnt
                    else:
                        p3_cb.vd += cnt
                        total_vd += cnt
        else:
            # Bóc tách dạng số truyền thống
            int_candidates = []
            for p in parts[3:]:
                if p.isdigit():
                    int_candidates.append(int(p))
                else:
                    m_paren = re.search(r"\((\d+)\)", p)
                    if m_paren:
                        int_candidates.append(int(m_paren.group(1)))
            if int_candidates:
                p1_nb = int_candidates[0] if len(int_candidates) > 0 else 0
                p1_th = int_candidates[1] if len(int_candidates) > 1 else 0
                p1_vd = int_candidates[2] if len(int_candidates) > 2 else 0
                p1_cb = CognitiveBreakdown(biet=p1_nb, hieu=p1_th, vd=p1_vd)
                all_mc_count += (p1_nb + p1_th + p1_vd)
                
                p2_nb = int_candidates[3] if len(int_candidates) > 3 else 0
                p2_th = int_candidates[4] if len(int_candidates) > 4 else 0
                p2_vd = int_candidates[5] if len(int_candidates) > 5 else 0
                p2_cb = CognitiveBreakdown(biet=p2_nb, hieu=p2_th, vd=p2_vd)
                
                p3_nb = int_candidates[6] if len(int_candidates) > 6 else 0
                p3_th = int_candidates[7] if len(int_candidates) > 7 else 0
                p3_vd = int_candidates[8] if len(int_candidates) > 8 else 0
                p3_cb = CognitiveBreakdown(biet=p3_nb, hieu=p3_th, vd=p3_vd)
                all_short_count += (p3_nb + p3_th + p3_vd)
                
                p4_nb = int_candidates[9] if len(int_candidates) > 9 else 0
                p4_th = int_candidates[10] if len(int_candidates) > 10 else 0
                p4_vd = int_candidates[11] if len(int_candidates) > 11 else 0
                p4_cb = CognitiveBreakdown(biet=p4_nb, hieu=p4_th, vd=p4_vd)
                
                total_biet += (p1_nb + p2_nb + p3_nb + p4_nb)
                total_hieu += (p1_th + p2_th + p3_th + p4_th)
                total_vd += (p1_vd + p2_vd + p3_vd + p4_vd)

        # Gán Yêu cầu cần đạt tương ứng từ Bản đặc tả
        matched_req = None
        for k, v in requirements_map.items():
            if (sub_name and sub_name.lower() in k) or (current_topic_name and current_topic_name.lower() in k):
                matched_req = v
                break
                
        if not matched_req:
            matched_req = TopicRequirements(
                recognition=f"Nhận biết kiến thức cốt lõi về {sub_name or current_topic_name}.",
                comprehension=f"Hiểu và giải thích các nguyên lý, đặc điểm của {sub_name or current_topic_name}.",
                application=f"Vận dụng giải quyết bài toán và tình huống thực tế về {sub_name or current_topic_name}."
            )
            
        t_p1 = p1_cb.biet + p1_cb.hieu + p1_cb.vd
        t_p2 = p2_cb.biet + p2_cb.hieu + p2_cb.vd
        t_p3 = p3_cb.biet + p3_cb.hieu + p3_cb.vd
        t_p4 = p4_cb.biet + p4_cb.hieu + p4_cb.vd
        
        t_item = Cv7991TopicItem(
            id=topic_counter,
            topic=current_topic_name or f"Chủ đề {topic_counter}",
            sub_topic=sub_name if sub_name != current_topic_name else "",
            requirements=matched_req,
            part1_mcq=p1_cb,
            part2_tf=p2_cb,
            part3_short=p3_cb,
            part4_essay=p4_cb,
            total_questions=t_p1 + t_p2 + t_p3 + t_p4,
            points=round(t_p1 * 0.25 + t_p2 * 0.25 + t_p3 * 0.5 + t_p4 * 1.0, 2)
        )
        topics.append(t_item)
        topic_counter += 1

    # Chuẩn hóa tổng số lượng câu hỏi từng phần
    if has_tokens:
        num_part1 = all_mc_count if all_mc_count > 0 else 16
        num_part2 = len(all_yn_qids) if all_yn_qids else 4
        num_part3 = all_short_count
        num_essay = len(all_tl_qids) if all_tl_qids else 0
    else:
        num_part1 = all_mc_count if all_mc_count > 0 else 12
        num_part2 = max(4, sum(t.part2_tf.biet + t.part2_tf.hieu + t.part2_tf.vd for t in topics) // 4 or 4)
        num_part3 = all_short_count
        num_essay = sum(t.part4_essay.biet + t.part4_essay.hieu + t.part4_essay.vd for t in topics)

    # Thang điểm chuẩn hóa
    s1_pts = round(num_part1 * 0.25, 2)
    s2_pts = round(num_part2 * 1.0, 2)
    s4_pts = round(num_essay * 1.0, 2)
    s3_pts = round(max(0.0, 10.0 - s1_pts - s2_pts - s4_pts), 2) if num_part3 > 0 else 0.0

    # Tỉ lệ nhận thức
    total_q = total_biet + total_hieu + total_vd
    if total_q == 0:
        total_q = num_part1 + num_part2 * 4 + num_part3 + num_essay
        total_biet = int(total_q * 0.4)
        total_hieu = int(total_q * 0.3)
        total_vd = total_q - total_biet - total_hieu

    biet_pct = summary_biet_pct or (round((total_biet / total_q) * 100, 1) if total_q > 0 else 40.0)
    hieu_pct = summary_hieu_pct or (round((total_hieu / total_q) * 100, 1) if total_q > 0 else 30.0)
    vd_pct = summary_vd_pct or round(100.0 - biet_pct - hieu_pct, 1)

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
            "part1_points": s1_pts,
            "part2_points": s2_pts,
            "part3_points": s3_pts,
            "part4_points": s4_pts
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

def reconcile_topics_with_matrix_tokens(topics_list: List[Cv7991TopicItem], text: str):
    """
    Đối soát chính xác từng bài/nội dung với ký hiệu YN (Đúng-Sai) và TL (Tự luận) trong văn bản ma trận.
    Đảm bảo 100% không bị lệch vị trí tự luận (như Bài 2, Bài 8) hay Đúng/Sai (Bài 1, 4, 5, 9).
    """
    if not topics_list or not text:
        return
        
    has_tokens = bool(re.search(r"\b(?:MC|YN\d+|TL\d+)\b", text, re.IGNORECASE))
    if not has_tokens:
        return

    lines = [l for l in text.split("\n") if "|" in l and not any(k in l.lower() for k in ["tổng", "cộng", "tỉ lệ %", "tỉ lệ", "bản đặc tả"])]
    
    # 1. Tìm tất cả các dòng có ký hiệu TL (Tự luận) và YN (Đúng/Sai)
    tl_lines = [l for l in lines if re.search(r"\b(?:1\s*)?TL[1-9]?\b", l, re.IGNORECASE) and not re.search(r"\bTLN\b", l, re.IGNORECASE)]
    yn_lines = [l for l in lines if re.search(r"\bYN[1-9]?\b", l, re.IGNORECASE)]
    
    # Reset toàn bộ về 0 trước khi map chính xác
    for t in topics_list:
        t.part4_essay.biet = 0
        t.part4_essay.hieu = 0
        t.part4_essay.vd = 0
        t.part2_tf.biet = 0
        t.part2_tf.hieu = 0
        t.part2_tf.vd = 0

    # 2. Map TL vào đúng topic (Bài 4, Bài 9 hoặc theo TL trong tài liệu)
    for tl_line in tl_lines:
        tl_low = tl_line.lower()
        best_match = None
        for t in topics_list:
            sub = (t.sub_topic or "").strip().lower()
            sub_clean = re.sub(r"^(?:bài\s*\d+[\.\:\-]?\s*|\d+[\.\:\-]\s*)", "", sub).strip()
            if sub and sub in tl_low:
                best_match = t
                break
            if sub_clean and len(sub_clean) > 4 and sub_clean in tl_low:
                best_match = t
                break
        if best_match:
            is_hieu = bool(re.search(r"\|\s*(?:1\s*)?TL[1-9]?\s*\|\s*(?:\||\b\d+\b)", tl_line)) or ("hiểu" in tl_line.lower() and "vận dụng" not in tl_line.lower())
            if is_hieu:
                best_match.part4_essay.hieu = 1
                best_match.part4_essay.vd = 0
            else:
                best_match.part4_essay.vd = 1
                best_match.part4_essay.hieu = 0

    # 3. Map YN vào đúng topic (Bài 1, Bài 4, Bài 5, Bài 9)
    for yn_line in yn_lines:
        yn_low = yn_line.lower()
        best_match = None
        for t in topics_list:
            sub = (t.sub_topic or "").strip().lower()
            sub_clean = re.sub(r"^(?:bài\s*\d+[\.\:\-]?\s*|\d+[\.\:\-]\s*)", "", sub).strip()
            if sub and sub in yn_low:
                best_match = t
                break
            if sub_clean and len(sub_clean) > 4 and sub_clean in yn_low:
                best_match = t
                break
        if best_match:
            best_match.part2_tf.biet = 2
            best_match.part2_tf.hieu = 1
            best_match.part2_tf.vd = 1

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

        # Đối soát và bảo vệ vị trí YN, TL theo các token thực tế trong tài liệu
        reconcile_topics_with_matrix_tokens(topics_list, extracted_text)

        def safe_int_val(val, default):
            if val is None or val == "":
                return default
            try:
                return int(val)
            except Exception:
                return default

        def safe_float_val(val, default):
            if val is None or val == "":
                return default
            try:
                return float(val)
            except Exception:
                return default

        num_part1 = safe_int_val(data.get("num_part1"), 12)
        num_part2 = safe_int_val(data.get("num_part2"), 4)
        num_part3 = safe_int_val(data.get("num_part3"), 0)
        num_essay = safe_int_val(data.get("num_essay"), 0)

        scoring = data.get("scoring_summary") or {}
        s1 = safe_float_val(scoring.get("part1_points"), round(num_part1 * 0.25, 2))
        s2 = safe_float_val(scoring.get("part2_points"), round(num_part2 * 1.0, 2))
        s3 = safe_float_val(scoring.get("part3_points"), round(num_part3 * 0.5, 2) if num_part3 > 0 else 0.0)
        s4 = safe_float_val(scoring.get("part4_points"), round(num_essay * 1.0, 2) if num_essay > 0 else 0.0)

        scoring_dict = {
            "part1_points": s1,
            "part2_points": s2,
            "part3_points": s3,
            "part4_points": s4
        }

        tot_pts = safe_float_val(data.get("total_points"), round(s1 + s2 + s3 + s4, 2))
        if tot_pts <= 0:
            tot_pts = 10.0

        cog_sum = data.get("cognitive_summary", {})
        cog_obj = CognitiveSummary(
            biet_count=safe_int_val(cog_sum.get("biet_count") or cog_sum.get("nb"), 0),
            biet_pct=safe_float_val(cog_sum.get("biet_pct"), 40.0),
            hieu_count=safe_int_val(cog_sum.get("hieu_count") or cog_sum.get("th"), 0),
            hieu_pct=safe_float_val(cog_sum.get("hieu_pct"), 30.0),
            vd_count=safe_int_val(cog_sum.get("vd_count") or cog_sum.get("vd"), 0),
            vd_pct=safe_float_val(cog_sum.get("vd_pct"), 30.0)
        )

        matrix_spec = ExamMatrixSpec(
            title=str(data.get("title") or f"MA TRẬN ĐỀ KIỂM TRA MÔN {data.get('subject', 'TOÁN HỌC')}"),
            subject=str(data.get("subject") or detect_subject_from_text(extracted_text)),
            grade=str(data.get("grade") or detect_grade_from_text(extracted_text)),
            duration_minutes=safe_int_val(data.get("duration_minutes"), detect_duration_from_text(extracted_text)),
            school_name=str(data.get("school_name") or ""),
            academic_year=str(data.get("academic_year") or "NĂM HỌC 2026 - 2027"),
            num_part1=num_part1,
            num_part2=num_part2,
            num_part3=num_part3,
            num_essay=num_essay,
            total_points=tot_pts,
            scoring_summary=scoring_dict,
            cognitive_summary=cog_obj,
            topics=topics_list,
            raw_markdown_table=extracted_text[:5000]
        )
        return matrix_spec
    except Exception as e_spec:
        print(f"[Matrix Analyzer] Lỗi cấu trúc hóa kết quả LLM: {e_spec}. Chuyển sang Heuristic.")
        return parse_cv7991_heuristic(extracted_text)
