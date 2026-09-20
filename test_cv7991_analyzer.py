import io
import sys
import docx
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

sys.stdout.reconfigure(encoding='utf-8')

from fastapi.testclient import TestClient
from app.main import app
from app.services.extractor import extract_file_content
from app.services.matrix_analyzer import parse_cv7991_heuristic, detect_subject_from_text, detect_grade_from_text, detect_duration_from_text
from app.services.models import ExamMatrixSpec

client = TestClient(app)

def create_sample_cv7991_docx() -> bytes:
    doc = docx.Document()
    
    # Tiêu đề văn bản
    doc.add_heading("BỘ GIÁO DỤC VÀ ĐÀO TẠO", level=1)
    doc.add_paragraph("PHỤ LỤC (Kèm theo Công văn số 7991/BGDĐT-GDTrH ngày 17/12/2024 của Bộ GDĐT)")
    doc.add_heading("1. MA TRẬN ĐỀ KIỂM TRA ĐỊNH KÌ MÔN TOÁN HỌC KHỐI 12", level=2)
    doc.add_paragraph("Thời gian làm bài: 90 phút - Năm học 2026 - 2027")
    
    # Bảng 1: Ma trận đề kiểm tra
    table1 = doc.add_table(rows=4, cols=11)
    headers = [
        "TT", "Chủ đề / Chương", "Nội dung / Đơn vị kiến thức",
        "TNKQ Nhiều lựa chọn (Biết/Hiểu/VD)", "TNKQ Đúng - Sai (Biết/Hiểu/VD)",
        "TNKQ Trả lời ngắn", "Tự luận",
        "Tổng câu Biết", "Tổng câu Hiểu", "Tổng câu VD", "Tỉ lệ %"
    ]
    for col_idx, h in enumerate(headers):
        table1.cell(0, col_idx).text = h
        
    row1 = ["1", "Ứng dụng đạo hàm để khảo sát hàm số", "Tính đơn điệu và cực trị của hàm số", "2 Biết, 1 Hiểu", "1 câu (Hiểu)", "1 câu (VD)", "1 câu (VD)", "2", "2", "2", "30%"]
    for col_idx, val in enumerate(row1):
        table1.cell(1, col_idx).text = val

    row2 = ["2", "Toạ độ trong không gian Oxyz", "Phương trình mặt phẳng và mặt cầu", "2 Biết, 1 Hiểu", "1 câu (Biết)", "1 câu (VD)", "1 câu (VD)", "3", "1", "2", "30%"]
    for col_idx, val in enumerate(row2):
        table1.cell(2, col_idx).text = val

    row_total = ["Tổng số câu", "", "", "12 câu", "4 câu", "6 câu", "2 câu", "14 câu", "10 câu", "8 câu", "100%"]
    for col_idx, val in enumerate(row_total):
        table1.cell(3, col_idx).text = val

    # Bảng 2: Bản đặc tả đề kiểm tra
    doc.add_heading("2. BẢN ĐẶC TẢ ĐỀ KIỂM TRA ĐỊNH KÌ", level=2)
    table2 = doc.add_table(rows=3, cols=6)
    t2_headers = ["TT", "Chủ đề / Chương", "Nội dung / Đơn vị kiến thức", "Yêu cầu cần đạt", "Hình thức câu hỏi", "Số lượng câu"]
    for col_idx, h in enumerate(t2_headers):
        table2.cell(0, col_idx).text = h
        
    t2_row1 = [
        "1", 
        "Ứng dụng đạo hàm", 
        "Tính đơn điệu và cực trị", 
        "- Biết: Nhận biết tính đồng biến, nghịch biến của hàm số thông qua đồ thị hoặc bảng biến thiên.\n- Hiểu: Tìm các khoảng đơn điệu và cực trị của hàm số chứa tham số đơn giản.\n- VD: Vận dụng giải quyết bài toán thực tế về tối ưu hóa chi phí hoặc thể tích.",
        "Phần I: 3 câu | Phần II: 1 câu | Phần III: 1 câu",
        "5"
    ]
    for col_idx, val in enumerate(t2_row1):
        table2.cell(1, col_idx).text = val

    t2_row2 = [
        "2", 
        "Tọa độ không gian Oxyz", 
        "Phương trình mặt phẳng", 
        "- Biết: Viết phương trình mặt phẳng đi qua một điểm và có vectơ pháp tuyến cho trước.\n- Hiểu: Xác định vị trí tương đối giữa hai mặt phẳng.\n- VD: Bài toán khoảng cách từ điểm đến mặt phẳng gắn với hình học thực tế.",
        "Phần I: 3 câu | Phần II: 1 câu | Phần III: 1 câu",
        "5"
    ]
    for col_idx, val in enumerate(t2_row2):
        table2.cell(2, col_idx).text = val

    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()

def run_tests():
    print("=== BẮT ĐẦU BỘ KIỂM THỬ NHẬN DẠNG MA TRẬN THEO CÔNG VĂN 7991 ===")
    
    # 1. Kiểm thử tạo docx và bóc tách bảng
    print("\n1. Kiểm thử trích xuất bảng biểu từ tệp Word docx...")
    docx_bytes = create_sample_cv7991_docx()
    assert len(docx_bytes) > 0, "Docx bytes rỗng!"
    extracted_text = extract_file_content("ma_tran_7991.docx", docx_bytes)
    assert "BẢNG BIỂU / MA TRẬN TRÍCH XUẤT" in extracted_text
    assert "Ứng dụng đạo hàm" in extracted_text
    assert "- Biết: Nhận biết tính đồng biến" in extracted_text
    print(f"   -> Đã trích xuất thành công {len(extracted_text)} ký tự bảng Markdown từ docx.")

    # 2. Kiểm thử Heuristic bóc tách môn, khối, thời gian và chủ đề
    print("\n2. Kiểm thử bộ phân tích Heuristic CV 7991...")
    sub = detect_subject_from_text(extracted_text)
    grade = detect_grade_from_text(extracted_text)
    duration = detect_duration_from_text(extracted_text)
    assert sub == "Toán học", f"Kỳ vọng 'Toán học', nhận được '{sub}'"
    assert grade == "12", f"Kỳ vọng '12', nhận được '{grade}'"
    assert duration == 90, f"Kỳ vọng 90 phút, nhận được {duration}"
    print(f"   -> Nhận diện chính xác: Môn {sub}, Khối {grade}, Thời gian {duration} phút.")

    matrix_spec = parse_cv7991_heuristic(extracted_text)
    assert matrix_spec.subject == "Toán học"
    assert matrix_spec.grade == "12"
    assert matrix_spec.duration_minutes == 90
    assert len(matrix_spec.topics) >= 2, f"Số chủ đề phát hiện: {len(matrix_spec.topics)}"
    assert matrix_spec.num_part1 >= 10, f"Số câu Phần I: {matrix_spec.num_part1}"
    assert matrix_spec.num_part2 >= 2, f"Số câu Phần II: {matrix_spec.num_part2}"
    print(f"   -> Heuristic phát hiện {len(matrix_spec.topics)} chủ đề với yêu cầu cần đạt chi tiết.")
    print(f"   -> Phân bổ số câu: P1={matrix_spec.num_part1}, P2={matrix_spec.num_part2}, P3={matrix_spec.num_part3}, Tự luận={matrix_spec.num_essay}")

    # 3. Kiểm thử API endpoint POST /api/matrix/analyze với tệp docx
    print("\n3. Kiểm thử endpoint POST /api/matrix/analyze tải file Word...")
    response = client.post(
        "/api/matrix/analyze",
        files={"file": ("ma_tran_toan_12_cv7991.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    )
    assert response.status_code == 200, f"Lỗi gọi API: {response.text}"
    res_data = response.json()
    assert res_data["success"] is True
    matrix_res = res_data["matrix"]
    assert matrix_res["subject"] == "Toán học"
    assert matrix_res["grade"] == "12"
    assert len(matrix_res["topics"]) >= 2
    assert "raw_markdown_table" in matrix_res
    print(f"   -> API trả về thành công với môn {matrix_res['subject']}, {len(matrix_res['topics'])} chủ đề.")

    # 4. Kiểm thử API endpoint POST /api/matrix/analyze với văn bản thuần
    print("\n4. Kiểm thử endpoint POST /api/matrix/analyze với raw_text...")
    sample_text = """
    MA TRẬN ĐỀ KIỂM TRA ĐỊNH KÌ HỌC KÌ I MÔN VẬT LÝ KHỐI 12
    Thời gian làm bài: 50 phút
    | TT | Chủ đề | Nhiều lựa chọn | Đúng - Sai | Trả lời ngắn | Tự luận |
    | 1 | Dao động cơ | 6 câu | 2 câu | 2 câu | 0 |
    | 2 | Sóng cơ và sóng âm | 6 câu | 2 câu | 4 câu | 0 |
    """
    response2 = client.post(
        "/api/matrix/analyze",
        data={"raw_text": sample_text}
    )
    assert response2.status_code == 200
    res_data2 = response2.json()
    assert res_data2["success"] is True
    assert res_data2["matrix"]["subject"] == "Vật lý"
    assert res_data2["matrix"]["grade"] == "12"
    assert res_data2["matrix"]["duration_minutes"] == 50
    print("   -> Phân tích qua raw_text chuẩn xác cho môn Vật lý khối 12.")

    # 5. Kiểm thử sinh đề tích hợp ma trận (Mock mode)
    print("\n5. Kiểm thử POST /api/generate với dữ liệu ma trận CV 7991...")
    gen_payload = {
        "mode": "mock",
        "subject": matrix_res["subject"],
        "grade": matrix_res["grade"],
        "duration_minutes": matrix_res["duration_minutes"],
        "num_part1": matrix_res["num_part1"],
        "num_part2": matrix_res["num_part2"],
        "num_part3": matrix_res["num_part3"],
        "num_essay": matrix_res["num_essay"],
        "matrix_spec": matrix_res
    }
    gen_res = client.post("/api/generate", json=gen_payload)
    assert gen_res.status_code == 200
    exam_out = gen_res.json()
    assert len(exam_out["part1_mcq"]) > 0
    assert len(exam_out["part2_tf"]) > 0
    assert len(exam_out["part3_short"]) > 0
    print(f"   -> Sinh đề hoàn chỉnh thành công: {len(exam_out['part1_mcq'])} câu P1, {len(exam_out['part2_tf'])} câu P2, {len(exam_out['part3_short'])} câu P3.")

    print("\n============================================================")
    print("  TOÀN BỘ KIỂM THỬ NHẬN DẠNG MA TRẬN CV 7991 ĐÃ ĐẠT 100% PASS!")
    print("============================================================\n")

if __name__ == "__main__":
    run_tests()
