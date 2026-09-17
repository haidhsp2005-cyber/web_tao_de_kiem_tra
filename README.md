# EduExam AI 2026 - Hệ Thống Tạo & Trộn Đề Kiểm Tra Chuẩn Bộ GD&ĐT 2026 - 2027

Hệ thống web chuyên nghiệp hỗ trợ giáo viên và học sinh:
- **Tạo đề kiểm tra đa môn học** (Toán, Vật lý, Hóa học, Sinh học, Tiếng Anh, Lịch sử, Địa lý, GDQP, Tin học, Công nghệ...).
- **Nguồn dữ liệu linh hoạt**:
  1. Tải lên tệp Word (`.docx`) hoặc PDF (`.pdf`) - tự động trích xuất nội dung.
  2. Tự động sinh từ câu lệnh Prompt (theo chuyên đề, ma trận mức độ nhận thức).
  3. Thử nghiệm tức thì với ngân hàng đề mẫu môn Toán, Vật lý, Hóa học, GDQP không cần API Key.
- **Cấu trúc chuẩn định dạng Bộ GD&ĐT năm học 2026 - 2027**:
  - **Phần I**: Câu trắc nghiệm nhiều phương án lựa chọn (A, B, C, D).
  - **Phần II**: Câu trắc nghiệm Đúng / Sai (mỗi câu 4 lệnh con a, b, c, d).
  - **Phần III**: Câu trắc nghiệm Trả lời ngắn.
  - **Phần IV**: Câu hỏi Tự luận (tùy chọn số câu linh hoạt từ 0 đến 10 câu).
- **Trộn đề thi thông minh**:
  - Tùy chỉnh số lượng đề (1, 2, 4, 8, 12, 24 mã đề...) và mã đề bắt đầu (101, 102...).
  - Tự động hoán vị thứ tự câu hỏi và phương án A-B-C-D, hoán vị các ý con a-b-c-d.
  - Tự động đồng bộ và sinh ma trận đáp án so sánh đầy đủ cả Phần I, Phần II và Phần III giữa các mã đề.
- **Xử lý công thức Toán học, Vật lý, Hóa học bản xứ (Native Word Equation OMML)**:
  - Tự động chuyển đổi công thức LaTeX sang định dạng Word OMML nguyên bản (không phải ảnh, chỉnh sửa trực tiếp được trong Microsoft Word với font Cambria Math / Times New Roman).
- **Xuất bản file Word (.docx) chuyên nghiệp gồm 3 phần rõ ràng**:
  1. Đề kiểm tra (Header trường, thời gian, bảng điền thông tin học sinh).
  2. Bảng đáp án (Ma trận đáp án đối chiếu nhanh cho giáo viên chấm thi).
  3. Hướng dẫn giải chi tiết (Từng bước giải thích cặn kẽ).
- **Tùy chọn tải về**:
  - Tải file Word từng mã đề riêng biệt.
  - Tải file Word Tổng hợp (Đề + Ma trận đáp án các mã + Lời giải chi tiết).
  - Tải file nén ZIP chứa tất cả các file Word.

## Hướng dẫn sử dụng
1. Mở thư mục dự án: `C:\Users\Admin\.gemini\antigravity\scratch\exam-generator-web`
2. Nhấp đúp vào file `run.bat` (hoặc chạy lệnh `python main.py` trong terminal).
3. Mở trình duyệt tại địa chỉ: `http://localhost:8888`.
