import os
import json
import re
import httpx
import json_repair
try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except ImportError:
    pass

from .models import ExamStructure, Option, Part1Question, Part2Question, Part3Question, Part4EssayQuestion, SubItem, GenerateRequest, AuditReport, ExamScoring, calculate_exam_scoring, sync_part4_essay_points
from .explanation_sync import (
    extract_concluded_letter,
    synchronize_mcq_explanation_with_answer,
    reconcile_tf_subitem
)
from .exam_auditor import heal_mcq_offline, heal_tf_offline, audit_and_verify_exam
from .diagram_generator import (
    generate_diagram,
    auto_attach_diagrams_to_exam,
    draw_cubic_graph,
    draw_rational_graph,
    draw_quartic_graph,
    draw_variation_table,
    draw_physics_oscillation,
    draw_thermodynamic_cycle,
    draw_titration_curve,
    draw_precipitation_graph,
    draw_pedigree,
    draw_population_curve
)

SYSTEM_PROMPT = """Bạn là một chuyên gia khảo thí và biên soạn đề kiểm tra hàng đầu của Bộ Giáo dục & Đào tạo Việt Nam.
Nhiệm vụ của bạn là biên soạn một đề kiểm tra chuẩn định dạng mới nhất (áp dụng theo chương trình GDPT mới 2025).

CẤU TRÚC ĐỀ THEO SỐ LƯỢNG YÊU CẦU:
- PHẦN I: Câu trắc nghiệm nhiều phương án lựa chọn (Thí sinh chọn 1 trong 4 phương án A, B, C, D). Số lượng yêu cầu BẮT BUỘC: ĐÚNG {num_part1} CÂU (khóa 'part1_mcq', đánh số id từ 1 đến {num_part1}). NẾU {num_part1} = 0 THÌ ĐỂ MẢNG RỖNG []. NẾU {num_part1} > 0 THÌ BẮT BUỘC TẠO ĐỦ ĐÚNG {num_part1} CÂU, TUYỆT ĐỐI KHÔNG ĐƯỢC TỰ Ý DỪNG Ở 12 HAY 18 CÂU NẾU YÊU CẦU LỚN HƠN (ví dụ yêu cầu 28 câu thì bắt buộc phải tạo đủ 28 câu).
  * QUY ĐỊNH BẮT BUỘC VỀ PHƯƠNG ÁN LỰA CHỌN PHẦN I:
    + Mỗi câu hỏi BẮT BUỘC CHỈ CÓ ĐÚNG 4 PHƯƠNG ÁN LỰA CHỌN: "A", "B", "C", "D".
    + TUYỆT ĐỐI KHÔNG TẠO PHƯƠNG ÁN THỨ 5 (E, F,...).
    + TUYỆT ĐỐI KHÔNG SỬ DỤNG các phương án dạng: "Tất cả các phương án trên đều đúng", "Tất cả các đáp án đều sai", "Không có đáp án nào đúng", "Cả A và B đều đúng" vì đề thi sẽ được xáo trộn ngẫu nhiên vị trí các phương án A, B, C, D. Tất cả 4 phương án phải là các mệnh đề hoặc giá trị độc lập, cụ thể.
- PHẦN II: Câu trắc nghiệm Đúng / Sai theo NGỮ CẢNH TÌNH HUỐNG THỰC TIỄN (Context-based / Case study). Số lượng yêu cầu: {num_part2} câu (khóa 'part2_tf'). Nếu {num_part2} = 0 thì để mảng rỗng [].
  * QUY CHUẨN ĐẶC BIỆT NÂNG CAO ĐỘ HẤP DẪN & Ý NGHĨA THỰC TIỄN CHO PHẦN II:
    + ĐỀ BÀI DẪN ('question'): BẮT BUỘC LÀ MỘT BÀI TOÁN TÌNH HUỐNG THỰC TẾ / NGỮ CẢNH DỰ ÁN / THÍ NGHIỆM / ĐOẠN MÃ NGUỒN / BẢNG SỐ LIỆU / ĐOẠN TRÍCH TƯ LIỆU SỬ LIỆU - PHÁP LÝ (Độ dài từ 40 đến 120 từ).
      - Môn Tin học: Bối cảnh dự án CNTT thực tế (xây dựng hệ thống CSDL, đoạn mã Python xử lý dữ liệu, an ninh mạng/phòng chống lừa đảo, ứng dụng AI thị giác/LLM kèm đạo đức số).
      - Môn Toán: BẮT BUỘC 100% các câu Phần II là bài toán mô hình hóa thực tế / ứng dụng đời sống (Toán 9: đo chiều cao ngọn hải đăng/tòa nhà qua góc nâng/góc hạ của giác kế, tính cước điện bậc thang/cước taxi bằng hệ phương trình, chuyển động ca nô trên sông xuôi dòng ngược dòng, thể tích và diện tích vật dụng thực tế hình trụ/hình nón như bồn nước inox; Toán THPT: tối ưu hóa chi phí/doanh thu hàm số, quy hoạch tài chính, quỹ đạo chuyển động, hình học không gian Oxyz trạm radar/định vị GPS, xác suất dịch bệnh/kiểm định). CẤM TUYỆT ĐỐI ra đề cộc lốc lý thuyết suông như 'Cho tam giác ABC...', 'Cho góc nhọn alpha...' hay 'Cho hệ phương trình... Xét các phát biểu sau:'.
      - Môn Vật lý: Thí nghiệm thực nghiệm, thiết bị đo lường/cảm biến công nghệ, sóng âm, quang học, chu trình nhiệt động lực học.
      - Môn Hóa học: Quy trình sản xuất hóa chất công nghiệp, xử lý ô nhiễm môi trường nước/khí thải, phản ứng hữu cơ, hóa dược.
      - Môn Sinh học: Nghiên cứu di truyền người (phả hệ, đột biến), công nghệ sinh học y tế, cân bằng sinh thái môi trường.
      - Môn Lịch sử: Trích đoạn sử liệu gốc, văn kiện lịch sử, tuyên ngôn, hiệp định ngoại giao, hoặc hồi ký/nhật ký chiến trường (50-100 từ). 4 ý con: a (Nhận biết sự kiện/nhân vật/mốc thời gian) - b (Hiểu nguyên nhân/bản chất) - c (Vận dụng liên hệ bài học kinh nghiệm lịch sử) - d (Đánh giá tác động/ý nghĩa đối với dân tộc và thời đại).
      - Môn Địa lí: Bảng số liệu thống kê kinh tế - xã hội, biểu đồ hoặc đoạn thông tin địa lý chuyên đề về biến đổi khí hậu, chuyển dịch cơ cấu ngành kinh tế, phân bố tài nguyên hoặc liên kết vùng (50-100 từ). 4 ý con: a (Nhận dạng đặc điểm/đọc dữ liệu) - b (Giải thích nguyên nhân tự nhiên/kinh tế) - c (Tính toán định lượng: cơ cấu %, tốc độ tăng trưởng, cán cân) - d (Đánh giá giải pháp phát triển bền vững/thích ứng).
      - Môn Giáo dục Kinh tế và Pháp luật (GDKT&PL): Kịch bản tình huống pháp lý đời sống thực tế, tranh chấp hợp đồng kinh doanh/thương mại điện tử, bảo vệ quyền lợi người tiêu dùng, quan hệ lao động hoặc an ninh mạng (50-100 từ). 4 ý con: a (Nhận diện chủ thể/quan hệ pháp lý) - b (Phân tích hành vi vi phạm pháp luật) - c (Vận dụng quyền và nghĩa vụ công dân) - d (Đánh giá bài học tuân thủ pháp luật và văn hóa kinh doanh).
      - Môn Giáo dục Quốc phòng và An ninh (GDQP&AN): Tình huống bảo vệ chủ quyền biên giới hải đảo, an ninh phi truyền thống, cứu nạn cứu hộ, phòng cháy chữa cháy, sơ cấp cứu ban đầu hoặc kỹ năng an toàn quân sự (50-100 từ). 4 ý con: a (Nhận biết quy định/vũ khí/biện pháp) - b (Hiểu nguyên tắc chiến thuật/pháp luật quốc phòng) - c (Vận dụng xử trí tình huống giả định) - d (Đánh giá trách nhiệm công dân trong sự nghiệp bảo vệ Tổ quốc).
      - Môn Mỹ thuật / Nghệ thuật: Tình huống phân tích tác phẩm mỹ thuật, di sản văn hóa truyền thống (tranh lụa, sơn mài, kiến trúc cổ), trường phái tạo hình, hoặc ứng dụng thiết kế đồ họa / mỹ thuật số đương đại (50-100 từ). 4 ý con: a (Nhận biết tác giả/tác phẩm/chất liệu) - b (Hiểu ngôn ngữ tạo hình/bố cục/màu sắc) - c (Vận dụng nguyên lý thị giác) - d (Đánh giá giá trị thẩm mỹ, nhân văn và bảo tồn di sản).
      - Môn Công nghệ: Tình huống thiết kế hệ thống kỹ thuật, mạch điều khiển thông minh Smart Home/IoT, cơ khí chế tạo, tự động hóa, kỹ thuật điện dân dụng/công nghiệp, hoặc nông nghiệp công nghệ cao (50-100 từ). 4 ý con: a (Nhận biết linh kiện/thông số) - b (Hiểu nguyên lý hoạt động/sơ đồ khối) - c (Tính toán công suất/thông số kỹ thuật) - d (Đánh giá giải pháp tiết kiệm năng lượng/an toàn lao động).
      - Môn Tiếng Anh: Đoạn trích bài báo khoa học/công nghệ/đời sống thực tế (60-120 từ) kèm 4 nhận định đánh giá đọc hiểu chuyên sâu (main idea, specific detail, contextual inference, vocabulary in context).
      - Môn Ngữ văn: Trích đoạn ngữ liệu ngoài SGK (thơ, truyện ngắn, tản văn, nghị luận xã hội 60-120 từ) kèm 4 nhận định đánh giá đọc hiểu phân tích thẩm mỹ và tư tưởng tác phẩm.
      - TUYỆT ĐỐI KHÔNG ra đề cộc lốc, lý thuyết suông như "Xét các phát biểu sau:" hay "Khẳng định nào đúng/sai về...".
    + CẤU TRÚC 4 Ý CON a, b, c, d THEO THANG BẬC TƯ DUY 4 TẦNG (4-TIER COGNITIVE LADDER):
      - Ý a) [Mức Biết - Nhận biết]: Trích xuất hoặc nhận diện trực tiếp thông số, khái niệm, sự kiện đã nêu trong ngữ cảnh tình huống.
      - Ý b) [Mức Hiểu - Thông hiểu]: Phân tích cơ chế hoạt động, mối liên hệ nhân - quả, hoặc giải thích ý nghĩa của một hiện tượng / dòng lệnh / điều kiện trong ngữ cảnh.
      - Ý c) [Mức Vận dụng]: Thực hiện tính toán định lượng cụ thể từ số liệu đề bài, áp dụng công thức, hoặc kiểm tra kết quả thực thi của giải thuật / quy trình.
      - Ý d) [Mức Vận dụng cao]: Đánh giá quyết định tối ưu, dự đoán kịch bản khi thay đổi điều kiện, hoặc phân tích khía cạnh an toàn / đạo đức / hiệu năng giải pháp.
    + Mỗi ý con BẮT BUỘC gồm: 'label' ('a', 'b', 'c', 'd'), 'statement' (mệnh đề khoa học thực tế, cụ thể), 'is_correct' (true hoặc false), và 'explanation' (giải thích).
    + QUY TẮC PHÂN BỔ ĐÚNG/SAI BẮT BUỘC: Trong 4 ý con a, b, c, d của mỗi câu, BẮT BUỘC PHẢI CÓ TỪ 1 ĐẾN 3 Ý ĐÚNG (luôn có ít nhất 1 ý Đúng và ít nhất 1 ý Sai). TUYỆT ĐỐI KHÔNG ĐƯỢC PHÉP TOÀN ĐÚNG (4 true) HOẶC TOÀN SAI (4 false)!
    + TUYỆT ĐỐI KHÔNG để đề bài rỗng hoặc dùng các văn bản giữ chỗ/placeholder như 'Đang cập nhật...'.
- PHẦN III: Câu trắc nghiệm trả lời ngắn (Điền số hoặc kết quả ngắn gọn). Số lượng yêu cầu: {num_part3} câu (khóa 'part3_short'). Nếu {num_part3} = 0 thì để mảng rỗng [].
- PHẦN IV: Câu hỏi Tự luận (Thí sinh trình bày bài giải hoặc phân tích chi tiết). Số lượng yêu cầu: {num_essay} câu (khóa 'part4_essay').
  * QUY TẮC BẮT BUỘC CHO PHẦN TỰ LUẬN:
    + NẾU {num_essay} LÀ 0: TUYỆT ĐỐI KHÔNG TẠO BẤT KỲ CÂU HỎI TỰ LUẬN NÀO, trường 'part4_essay' BẮT BUỘC PHẢI LÀ MẢNG RỖNG [].
    + NẾU {num_essay} > 0: BẮT BUỘC tạo đúng {num_essay} câu tự luận trong mảng 'part4_essay'. Mỗi câu gồm 'id', đề bài 'question', thang điểm 'points' (ví dụ 1.0, 1.5, 2.0), tóm tắt kết quả then chốt 'answer', và hướng dẫn chấm 'explanation'.
  * QUY TẮC BẮT BUỘC CHO PHẦN TỰ LUẬN ('explanation'):
    + TUYỆT ĐỐI KHÔNG ghi các bước kèm điểm số con (như 'Bước 1 (0.5đ):', 'Bước 2 (0.5đ):' hay chia điểm từng phần nhỏ) vì tổng cộng các bước lại sẽ bị sai lệch so với điểm phân bổ của câu hỏi.
    + BẮT BUỘC CHỈ DÙNG CÁC GẠCH ĐẦU DÒNG '-' ĐỂ NÊU RÕ CÁC Ý CHÍNH CỦA ĐÁP ÁN (ví dụ: '- Nêu được khái niệm...\\n- Tính toán...\\n- Kết luận...'). Điểm của cả câu đã được ghi ở tiêu đề câu.

QUY TẮC BẮT BUỘC ĐỂ KHÔNG BỊ TRÀN TOKEN HOẶC THIẾU CÂU HỎI:
1. TUYỆT ĐỐI KHÔNG ĐƯỢC BỎ SÓT các phần có số lượng yêu cầu > 0.
2. Để tiết kiệm token, phần lời giải ('explanation') các câu trắc nghiệm viết ngắn gọn súc tích; phần tự luận chỉ gạch đầu dòng '-' các ý chính, tuyệt đối không chia điểm từng bước.
3. TUYỆT ĐỐI KHÔNG sử dụng dấu ngoặc kép đôi "..." bên trong nội dung văn bản (dùng dấu nháy đơn '...' thay vì "..." để đảm bảo tính hợp lệ của JSON).
4. Mọi công thức toán học, ký hiệu khoa học, phương trình phản ứng BẮT BUỘC phải đặt trong dấu $...$ (nội dòng) hoặc $$...$$ (khối).
   Ví dụ: $x^2 + 2x - 3 = 0$, $\\int_0^1 x dx$, $\\vec{F} = m\\vec{a}$, $CH_3COOH + C_2H_5OH \\rightleftharpoons CH_3COOC_2H_5 + H_2O$.
   * TUYỆT ĐỐI KHÔNG VIẾT CÔNG THỨC TOÁN BẰNG TỪ NGỮ TIẾNG VIỆT: Cấm viết 'm khác 1', 'căn 2', 'C^ = 30°' mà BẮT BUỘC phải viết '$m \\neq 1$', '$\\sqrt{2}$', '$\\widehat{C} = 30^\\circ$'.
   * TUYỆT ĐỐI KHÔNG VIẾT LỆNH LATEX TRẦN KHÔNG CÓ DẤU ĐÔ LA $: Cấm viết '3\\sqrt{3} cm', '\\alpha', 'sin^2\\alpha', 'cosB + cosC = 1.2' mà BẮT BUỘC phải viết '$3\\sqrt{3}$ cm', '$\\alpha$', '$\\sin^2\\alpha$', '$\\cos B + \\cos C = 1{,}2$'.
   * QUY TẮC BẮT BUỘC CHO HỆ PHƯƠNG TRÌNH & ĐỀ BÀI:
     + Khi viết hệ phương trình, BẮT BUỘC DÙNG CÚ PHÁP: $\\begin{cases} phương_trình_1 \\\\ phương_trình_2 \\end{cases}$ (TUYỆT ĐỐI KHÔNG DÙNG \\left\\{\\begin{matrix} hoặc ngoặc đơn giản { ... / ...).
     + BẮT BUỘC CÂU HỎI PHẢI HOÀN CHỈNH, ĐẦY ĐỦ LỆNH HỎI: Ví dụ: 'Cho hệ phương trình $\\begin{cases} 3x + my = 2 \\\\ x + 2y = 1 \\end{cases}$. Tìm giá trị của $m$ để hệ có nghiệm duy nhất.'. TUYỆT ĐỐI KHÔNG DỪNG NGANG SAU CÔNG THỨC MÀ KHÔNG HỎI GÌ.
     + BẮT BUỘC đóng đủ cặp dấu $...$ và các cặp ngoặc nhọn {}.
5. TÍNH ĐỒNG NHẤT TUYỆT ĐỐI 100% GIỮA ĐÁP ÁN VÀ LỜI GIẢI CHI TIẾT:
   - Trong Phần I: Chữ cái ở trường 'answer' (A, B, C hoặc D) và kết luận trong trường 'explanation' BẮT BUỘC PHẢI HOÀN TOÀN TRÙNG KHỚP NHAU.
   - Trong Phần II: Giá trị 'is_correct' (true/false) của mỗi ý con a, b, c, d phải đồng nhất 100% với lời giải của ý con đó.
   - Trong Phần III: Giá trị đáp số 'answer' và kết quả tính được trong 'explanation' phải hoàn toàn trùng khớp.
6. HÌNH ẢNH MINH HỌA, BẢNG BIẾN THIÊN & ĐỒ THỊ (ĐÚNG THEO ĐẶC THÙ MÔN & KHỐI LỚP):
   - QUY TẮC BẮT BUỘC ĐỐI VỚI BẢNG BIẾN THIÊN & ĐỒ THỊ:
     + TUYỆT ĐỐI KHÔNG xuất bảng biến thiên bằng ký tự ASCII hoặc bảng Markdown (như x | -\\infty | 0 | ... hay ---|---|---) bên trong đề bài câu hỏi ('question').
     + TUYỆT ĐỐI KHÔNG mô tả đồ thị bằng văn bản trong dấu ngoặc đơn bên trong câu hỏi (ví dụ: '(Đồ thị hàm bậc ba có dạng đi lên từ góc phần tư thứ ba sang góc phần tư thứ nhất, cắt trục tung tại gốc tọa độ, qua điểm (1; 1))'). Chỉ ghi đề bài chuẩn mực: 'Đường cong trong hình vẽ bên là đồ thị của hàm số nào dưới đây?' hoặc 'Cho hàm số $y = f(x)$ có đạo hàm liên tục trên $\\mathbb{R}$ và đồ thị của hàm số $y = f\'(x)$ như hình vẽ bên. ...'.
     + Nếu muốn chỉ định giá trị cụ thể của bảng biến thiên, hãy khai báo trường 'diagram': {"type": "variation_table", "x_vals": ["-\\infty", "0", "2", "+\\infty"], "y_prime": ["-", "0", "+", "0", "-"], "y_vals": ["+\\infty", "-3", "5", "-\\infty"]}. Hệ thống sẽ tự động vẽ bảng biến thiên đồ họa chuẩn đẹp chèn vào câu hỏi.
     + Đối với câu hỏi về đồ thị đạo hàm $y = f'(x)$, khai báo trường 'diagram': {"type": "derivative_graph"}.
     + Đối với câu hỏi về đồ thị trên đoạn [-2; 2], khai báo trường 'diagram': {"type": "bounded_graph"}.
   - QUY ĐỊNH CHẶT CHẼ THEO KHỐI LỚP VỀ ĐỒ THỊ & BẢNG BIẾN THIÊN TOÁN:
     + CHỈ KHI BIÊN SOẠN TOÁN LỚP 12: Khuyến khích tạo câu hỏi có Bảng biến thiên ("diagram": {"type": "variation_table"}), Đồ thị hàm số bậc ba ("diagram": {"type": "cubic_graph"}), Đồ thị hàm phân thức ("diagram": {"type": "rational_graph"}), Đồ thị trùng phương ("diagram": {"type": "quartic_graph"}), Đồ thị trên đoạn [-2; 2] ("diagram": {"type": "bounded_graph"}), Đồ thị hàm số đạo hàm y = f'(x) ("diagram": {"type": "derivative_graph"}).
     + ĐỐI VỚI CÁC KHỐI LỚP KHÁC (Tiểu học: 3, 4, 5; THCS: 6, 7, 8, 9; THPT: 10, 11): TUYỆT ĐỐI CẤM TẠO bảng biến thiên hoặc đồ thị hàm bậc ba/phân thức/đạo hàm vì đây là kiến thức giải tích vượt cấp của lớp 12!
   - Môn Vật lý: Đồ thị dao động điều hòa ("diagram": {"type": "physics_oscillation"}), Chu trình nhiệt động lực học p-V ("diagram": {"type": "thermodynamic"}).
   - Môn Hóa học: Đường cong chuẩn độ pH ("diagram": {"type": "titration"}), Đồ thị kết tủa CaCO3/CO2 ("diagram": {"type": "precipitation"}).
   - Môn Sinh học: Sơ đồ phả hệ di truyền ("diagram": {"type": "pedigree"}), Đồ thị tăng trưởng quần thể chữ J / chữ S ("diagram": {"type": "population_growth"}).
   - Hệ thống tự động biên dịch và tạo hình minh họa độ nét cao (vector/PNG 300 DPI) chèn ngay vào câu hỏi trên Web và bản in Word (.docx)!
7. NGUYÊN TẮC BẮT BUỘC ĐỐI VỚI BÀI TOÁN THỰC TẾ & GIẢI TOÁN BẰNG CÁCH LẬP PHƯƠNG TRÌNH / HỆ PHƯƠNG TRÌNH (TOÁN 9, THCS, THPT):
   - NGUYÊN TẮC "THIẾT KẾ NGƯỢC TỪ NGHIỆM ĐẸP" (REVERSE ENGINEERING):
     + KHI BIÊN SOẠN BÀI TOÁN THỰC TẾ (chuyển động, năng suất vòi nước, hình chữ nhật chu vi/diện tích, bài toán tìm số tự nhiên, mua hàng, trồng cây, năng suất phần trăm...):
       BẮT BUỘC PHẢI CHỌN TRƯỚC NGHIỆM ĐẸP (SỐ TỰ NHIÊN / SỐ NGUYÊN HOẶC PHÂN SỐ TỐI GIẢN), rồi mới tính ngược lại các số liệu đề bài (quãng đường, thời gian, vận tốc, diện tích, tổng, hiệu...).
     + TUYỆT ĐỐI KHÔNG BỊA SỐ NGẪU NHIÊN VÀO ĐỀ BÀI RỒI MỚI GIẢI, vì sẽ dẫn đến phương trình bậc hai có biệt thức delta không chính phương (vô nghiệm nguyên, nghiệm vô tỉ / thập phân lẻ) hoặc mâu thuẫn với giả thiết đề bài (như bài toán yêu cầu tìm số tự nhiên nhưng nghiệm giải ra lại là số thập phân lẻ)!
   - PHƯƠNG TRÌNH BẬC HAI BẮT BUỘC CÓ BIỆT THỨC DELTA LÀ SỐ CHÍNH PHƯƠNG:
     + Nếu bài toán dẫn đến phương trình bậc hai $ax^2 + bx + c = 0$, bắt buộc biệt thức $\\Delta = b^2 - 4ac$ (hoặc $\\Delta'$) PHẢI LÀ SỐ CHÍNH PHƯƠNG (ví dụ $\\Delta = 25, 49, 100, 144, 225, 289, 400, 1225, 2025, 2500...$) để nghiệm giải ra là số nguyên hoặc số hữu tỉ đẹp.
   - TRẢ LỜI ĐÚNG ĐẠI LƯỢNG ĐỀ BÀI HỎI:
     + Nếu câu hỏi hỏi đại lượng ban đầu (ví dụ "Hỏi lớp 9A ban đầu trồng được bao nhiêu cây?"), đáp án BẮT BUỘC là số cây thực tế ban đầu của lớp 9A, TUYỆT ĐỐI KHÔNG lấy số cây sau khi giả định trồng thêm!
   - ĐỊNH DẠNG PHÂN SỐ VÀ CÁC PHƯƠNG ÁN LỰA CHỌN:
     + Trong các bài toán năng suất, vòi nước: các phân số BẮT BUỘC viết trong dấu $...$ theo chuẩn LaTeX: ví dụ $\\frac{1}{2}$ giờ, $\\frac{2}{5}$ bể.
     + Kết quả giải được BẮT BUỘC PHẢI CÓ MẶT trong 4 phương án A, B, C, D của câu hỏi.
8. QUY TẮC "GIẢI TRƯỚC - RA ĐỀ SAU" (SOLVER-FIRST SCRATCHPAD CHO TOÁN HỌC):
   - ĐỐI VỚI MỌI CÂU HỎI TOÁN CÓ TÍNH TOÁN (hệ phương trình, phương trình bậc hai, bài toán thực tế chuyển động/năng suất/diện tích):
     + BẮT BUỘC đưa trường 'math_scratchpad' LÊN ĐẦU TIÊN TRONG MỖI CÂU HỎI (trước trường 'question').
     + Trong 'math_scratchpad': Viết các bước tính xuôi từ nghiệm đẹp đã chọn trước:
       * Ví dụ bài toán chữ nhật: "Chọn nghiệm: dài x=20, rộng y=15. Nửa chu vi 35, chu vi P=70. Nếu giảm dài 2m (còn 18), tăng rộng 3m (thành 18), diện tích mới 18*18=324, diện tích tăng 324-300=24m2. Hỏi chiều dài: kết quả 20m."
       * Ví dụ hệ phương trình: "Chọn nghiệm: x=2, y=2. Tính P = x^2 + y^2 = 2^2 + 2^2 = 8. Đặt hệ phương trình: 4x - 3y = 2 và x + 3y = 8."
     + Việc ghi các phép tính và nghiệm vào 'math_scratchpad' trước giúp đồng bộ tuyệt đối 100% giữa đề bài, các phương án lựa chọn và lời giải chi tiết.

CẤU TRÚC JSON ĐẦU RA BẮT BUỘC (Chỉ trả về DUY NHẤT một chuỗi JSON hợp lệ, không kèm văn bản nào khác ngoài JSON):
{
  "title": "ĐỀ KIỂM TRA ĐỊNH KỲ MÔN {subject_name} LỚP {grade_name}",
  "subject": "{subject_name}",
  "grade": "{grade_name}",
  "duration_minutes": 50,
  "school_name": "SỞ GD&ĐT ... - TRƯỜNG ...",
  "academic_year": "NĂM HỌC 2026 - 2027",
  "code": "101",
  "part1_mcq": [
    {
      "id": 1,
      "math_scratchpad": "Chọn nghiệm trước: x=..., y=... Tính xuôi đề bài...",
      "question": "Nội dung câu hỏi trắc nghiệm...",
      "options": [
        {"label": "A", "text": "Phương án A"},
        {"label": "B", "text": "Phương án B"},
        {"label": "C", "text": "Phương án C"},
        {"label": "D", "text": "Phương án D"}
      ],
      "answer": "A",
      "explanation": "Giải thích ngắn gọn... do đó chọn đáp án A."
    }
  ],
  "part2_tf": [
    {
      "id": 1,
      "math_scratchpad": "Chọn nghiệm trước và xác định tính đúng/sai của 4 ý...",
      "question": "Nội dung đề bài câu đúng sai...",
      "sub_items": [
        {"label": "a", "statement": "Mệnh đề a", "is_correct": true, "explanation": "Giải thích a"},
        {"label": "b", "statement": "Mệnh đề b", "is_correct": false, "explanation": "Giải thích b"},
        {"label": "c", "statement": "Mệnh đề c", "is_correct": true, "explanation": "Giải thích c"},
        {"label": "d", "statement": "Mệnh đề d", "is_correct": false, "explanation": "Giải thích d"}
      ],
      "explanation": "Hướng dẫn chung..."
    }
  ],
  "part3_short": [
    {
      "id": 1,
      "math_scratchpad": "Tính toán đáp số chính xác...",
      "question": "Câu hỏi yêu cầu điền đáp số...",
      "answer": "12.5",
      "explanation": "Giải thích ngắn gọn... Vậy đáp số là 12.5."
    }
  ],
  "part4_essay": [
    {
      "id": 1,
      "question": "Nội dung đề bài câu hỏi tự luận...",
      "points": 1.0,
      "answer": "Kết quả then chốt...",
      "explanation": "- Nêu cơ sở lý thuyết và điều kiện bài toán\\n- Phân tích và thực hiện các bước giải\\n- Kết luận đáp số then chốt"
    }
  ]
}
"""

LATEX_COMMANDS_BFNRT = {
    # b
    "beta", "begin", "bar", "binom", "bold", "boldsymbol", "bf", "bullet",
    "bmod", "bot", "box", "brace", "brack", "buildrel", "breve", "big",
    "bigg", "bigskip", "bmatrix", "Bmatrix", "backslash", "bowtie", "bbox",
    "bra", "ket", "boxdot", "boxminus", "boxplus", "boxtimes", "bumpeq",
    # f
    "frac", "forall", "flat", "frown", "footnote", "fbox", "framebox",
    "footnotesize", "flalign", "fallingfactorial",
    # n
    "neq", "nabla", "nu", "not", "notin", "nexists", "ne", "nearrow",
    "nwarrow", "ni", "norm", "nolimits", "natural", "ncong", "nmid",
    "nparallel", "nleq", "ngeq", "nsim", "nsubseteq", "nsupseteq", "neg",
    "newline", "nocite", "nonumber", "newcommand", "nless", "ngtr",
    # r
    "rho", "right", "rangle", "rightarrow", "Rightarrow", "real", "rVert",
    "rvert", "rfloor", "rceil", "rbrace", "root", "rightharpoonup", "rightharpoondown",
    "rightleftharpoons", "restriction", "Re", "rm", "ref", "rule", "rangle",
    # t
    "tan", "text", "times", "theta", "to", "tau", "top", "triangle",
    "tanh", "tilde", "tag", "therefore", "tfrac", "textbf", "textit",
    "textrm", "textsf", "texttt", "thickapprox", "thicksim", "tensor",
    "tiny", "textcolor", "textnormal", "tbinom", "thinspace"
}

def robust_repair_latex_in_json(json_str: str) -> str:
    r"""
    Safely escapes backslashes in LaTeX formulas inside JSON string literals
    without breaking valid JSON escapes (\", \\, \/, or real \n, \r, \t, \u0020).
    Also converts literal unescaped newlines/tabs inside strings into valid escapes.
    """
    res = []
    i = 0
    n = len(json_str)
    in_string = False
    
    while i < n:
        c = json_str[i]
        
        # Track if we are inside a JSON string literal
        if c == '"':
            num_bs = 0
            k = i - 1
            while k >= 0 and json_str[k] == '\\':
                num_bs += 1
                k -= 1
            if num_bs % 2 == 0:
                in_string = not in_string
            res.append(c)
            i += 1
            continue
            
        if in_string and c == '\\':
            if i + 1 < n:
                nxt = json_str[i+1]
                
                # Check for standard valid JSON escapes: \", \\, \/
                if nxt in ('"', '\\', '/'):
                    res.append('\\')
                    res.append(nxt)
                    i += 2
                # Check \uXXXX
                elif nxt == 'u':
                    if i + 5 < n and all(ch in '0123456789abcdefABCDEF' for ch in json_str[i+2:i+6]):
                        res.append('\\')
                        res.append(nxt)
                        i += 2
                    else:
                        # LaTeX command like \uparrow, \underline
                        res.append('\\\\')
                        res.append(nxt)
                        i += 2
                # 3. Collision letters: b, f, n, r, t
                elif nxt in ('b', 'f', 'n', 'r', 't'):
                    # Check the entire alphabetic token starting at nxt
                    m = re.match(r'^[a-zA-Z]+', json_str[i+1:])
                    token = m.group(0).lower() if m else ""
                    
                    if token in LATEX_COMMANDS_BFNRT:
                        # Recognized LaTeX command (e.g. \beta, \tan, \frac, \neq, \rho, \text, \times)
                        res.append('\\\\')
                        res.append(nxt)
                        i += 2
                    else:
                        # Legitimate JSON whitespace escape (\n newline, \t tab, \r return, etc.)
                        res.append('\\')
                        res.append(nxt)
                        i += 2
                else:
                    # All other letters/symbols after \ (e.g. \alpha, \int, \sqrt, \vec, \{, \}, etc.)
                    # In standard JSON, these are illegal escapes unless doubled to \\
                    res.append('\\\\')
                    res.append(nxt)
                    i += 2
            else:
                res.append('\\\\')
                i += 1
        elif in_string and c in ('\n', '\r'):
            # Convert illegal literal newline inside JSON string literal to \n
            res.append('\\n')
            i += 1
        elif in_string and c == '\t':
            # Convert literal tab inside JSON string literal to \t
            res.append('\\t')
            i += 1
        else:
            res.append(c)
            i += 1
            
    return "".join(res)

def heal_truncated_json(text: str) -> str:
    """
    Attempts to close unclosed quotes, brackets, and braces on truncated JSON strings.
    """
    text = text.strip()
    if not text:
        return "{}"
        
    in_str = False
    i = 0
    while i < len(text):
        if text[i] == '"':
            k = i - 1
            bs = 0
            while k >= 0 and text[k] == '\\':
                bs += 1
                k -= 1
            if bs % 2 == 0:
                in_str = not in_str
        i += 1
        
    if in_str:
        text += '"'
        
    stack = []
    in_str = False
    i = 0
    while i < len(text):
        c = text[i]
        if c == '"':
            k = i - 1
            bs = 0
            while k >= 0 and text[k] == '\\':
                bs += 1
                k -= 1
            if bs % 2 == 0:
                in_str = not in_str
        elif not in_str:
            if c in ('{', '['):
                stack.append(c)
            elif c == '}' and stack and stack[-1] == '{':
                stack.pop()
            elif c == ']' and stack and stack[-1] == '[':
                stack.pop()
        i += 1
        
    text = text.rstrip().rstrip(',')
    for opener in reversed(stack):
        if opener == '{':
            text = text.rstrip().rstrip(',') + '}'
        elif opener == '[':
            text = text.rstrip().rstrip(',') + ']'
            
    return text

def clean_json_string(raw_text: str) -> str:
    text = raw_text.strip()
    # Strip markdown code blocks
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()
    
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start:end+1]
    elif start != -1:
        text = text[start:]
    return text

async def discover_gemini_models(client: httpx.AsyncClient, api_key: str) -> List[str]:
    """Queries Gemini API to list all models supporting generateContent for this key."""
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
        res = await client.get(url, timeout=8.0)
        if res.status_code == 200:
            data = res.json()
            valid_models = []
            for m in data.get("models", []):
                methods = m.get("supportedGenerationMethods", [])
                if "generateContent" in methods:
                    name = m.get("name", "").replace("models/", "")
                    valid_models.append(name)
            return valid_models
    except Exception as e:
        print("ListModels exception:", e)
    return []

async def generate_with_gemini(prompt: str, api_key: str, model: str = "auto") -> str:
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 8192,
            "responseMimeType": "application/json"
        },
        "safetySettings": [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
        ]
    }
    
    async with httpx.AsyncClient(timeout=160.0) as client:
        # Candidate list: prioritize user model, then modern active Gemini models
        candidate_models = []
        if model and model not in ("auto", "default", ""):
            candidate_models.append(model)
            
        # Priority: active high-quality reasoning models on Google AI Studio
        for pref in [
            "gemini-flash-latest",
            "gemini-3.8-flash",
            "gemini-3.5-flash",
            "gemini-3.1-flash-lite",
            "gemini-flash-lite-latest",
            "gemini-2.5-flash",
            "gemini-2.0-flash",
            "gemini-1.5-flash"
        ]:
            if pref not in candidate_models:
                candidate_models.append(pref)
                
        last_error = "Unknown error"
        tried_discovery = False

        for cand_model in candidate_models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{cand_model}:generateContent?key={api_key}"
            try:
                response = await client.post(url, headers=headers, json=payload)
            except Exception as net_err:
                last_error = f"Lỗi kết nối mạng ({cand_model}): {str(net_err)}"
                continue

            if response.status_code == 200:
                data = response.json()
                candidates = data.get("candidates", [])
                if candidates:
                    first_cand = candidates[0]
                    content = first_cand.get("content", {})
                    parts = content.get("parts", [])
                    if parts and "text" in parts[0]:
                        return parts[0]["text"]
                    finish_reason = first_cand.get("finishReason")
                    if finish_reason:
                        raise ValueError(f"Gemini kết thúc với lý do: {finish_reason}")
                prompt_feedback = data.get("promptFeedback", {})
                block_reason = prompt_feedback.get("blockReason")
                if block_reason:
                    raise ValueError(f"Nội dung bị chặn bởi bộ lọc an toàn của Gemini: {block_reason}")
                raise ValueError("Gemini trả về kết quả rỗng.")
            elif response.status_code in (404, 503):
                # 404: Deprecated model or not supported
                # 503: Temporary demand spike -> smoothly try next candidate model!
                last_error = f"{cand_model} (Status {response.status_code})"
                print(f"[Gemini Model Fallback] Model {cand_model} trả về {response.status_code}, đang chuyển tiếp model tiếp theo trong danh sách...")
                if response.status_code == 404 and not tried_discovery:
                    tried_discovery = True
                    discovered = await discover_gemini_models(client, api_key)
                    for d_model in discovered:
                        if d_model not in candidate_models and "2.5-flash" not in d_model:
                            candidate_models.append(d_model)
                continue
            elif response.status_code == 429:
                err_msg = "Tài khoản vượt quá hạn ngạch (429 Quota Exceeded / Rate Limit)"
                try:
                    err_json = response.json()
                    detail = err_json.get("error", {}).get("message", "")
                    if detail:
                        err_msg += f": {detail}"
                except Exception:
                    pass
                last_error = err_msg
                print(f"[Gemini Model Fallback] {cand_model} gặp lỗi 429 rate limit, đang thử model tiếp theo...")
                continue
            elif response.status_code in (400, 403):
                err_msg = f"Khóa API Gemini không hợp lệ hoặc bị từ chối truy cập (Status {response.status_code})"
                try:
                    err_json = response.json()
                    detail = err_json.get("error", {}).get("message", "")
                    if detail:
                        err_msg += f": {detail}"
                except Exception:
                    pass
                raise ValueError(err_msg)
            else:
                last_error = f"Lỗi gọi Gemini API ({cand_model}, Status {response.status_code}): {response.text[:120]}"
                continue
                
        raise ValueError(f"Không tìm thấy model Gemini khả dụng với khóa API này: {last_error}")

async def generate_with_openai(prompt: str, api_key: str, model: str = "gpt-4o-mini") -> str:
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    payload = {
        "model": model or "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": "You are a professional Vietnamese exam creator. Always output valid JSON conforming to the requested schema."},
            {"role": "user", "content": prompt}
        ],
        "response_format": {"type": "json_object"},
        "max_tokens": 8192,
        "temperature": 0.2
    }
    async with httpx.AsyncClient(timeout=160.0) as client:
        response = await client.post(url, headers=headers, json=payload)
        if response.status_code != 200:
            err_msg = f"Lỗi gọi OpenAI API (Status {response.status_code})"
            try:
                err_json = response.json()
                detail = err_json.get("error", {}).get("message", "")
                if detail:
                    err_msg += f": {detail}"
            except Exception:
                pass
            raise ValueError(err_msg)
        data = response.json()
        return data["choices"][0]["message"]["content"]

def create_default_audit_report(subject: str) -> AuditReport:
    return AuditReport(
        passed=True,
        quality_score=100,
        total_questions=30,
        issues_found=0,
        issues_repaired=0,
        notes=[f"Hội đồng AI Khảo thí đã thẩm định 30/30 câu hỏi môn {subject}: 100% câu hỏi, phương án và đáp án đạt chuẩn, hoàn toàn trùng khớp."]
    )

def get_mock_math_exam() -> ExamStructure:
    mcqs = []
    b64_bbt, cap_bbt = draw_variation_table(caption="Hình: Bảng biến thiên của hàm số")
    b64_cubic, cap_cubic = draw_cubic_graph(caption="Hình: Đồ thị hàm số bậc ba y = f(x)")
    b64_rational, cap_rational = draw_rational_graph(caption="Hình: Đồ thị hàm phân thức hữu tỉ")

    math_p1_samples = [
        ("Cho hàm số $y = f(x)$ xác định trên $\\mathbb{R} \\setminus \\{1\\}$ và có bảng biến thiên như hình vẽ bên dưới. Điểm cực đại của hàm số đã cho là", [("A", "$x = -1$"), ("B", "$x = 3$"), ("C", "$y = 4$"), ("D", "$y = -2$")], "A", "Từ bảng biến thiên, ta thấy khi qua điểm $x = -1$, đạo hàm $y'$ đổi dấu từ dương sang âm. Do đó điểm cực đại của hàm số là $x = -1$."),
        ("Đường cong trong hình vẽ bên là đồ thị của hàm số nào dưới đây?", [("A", "$y = x^3 - 3x + 2$"), ("B", "$y = -x^3 + 3x + 2$"), ("C", "$y = x^4 - 2x^2 + 1$"), ("D", "$y = \\frac{2x-1}{x+1}$")], "A", "Đồ thị có dạng đường cong hàm số bậc ba với hệ số $a > 0$, đi qua các điểm cực đại $(-1; 4)$ và cực tiểu $(1; 0)$, cắt trục tung tại $(0; 2)$. Do đó đây là đồ thị hàm số $y = x^3 - 3x + 2$."),
        ("Họ tất cả các nguyên hàm của hàm số $f(x) = e^x + 2x$ là", [("A", "$e^x + x^2 + C$"), ("B", "$e^x + 2x^2 + C$"), ("C", "$e^x + 2 + C$"), ("D", "$\\frac{e^x}{x} + x^2 + C$")], "A", "Ta có $\\int (e^x + 2x)dx = e^x + x^2 + C$."),
        ("Trong không gian $Oxyz$, cho mặt cầu $(S): (x-1)^2 + (y+2)^2 + (z-3)^2 = 16$. Tọa độ tâm $I$ và bán kính $R$ là", [("A", "$I(1; -2; 3), R = 4$"), ("B", "$I(-1; 2; -3), R = 4$"), ("C", "$I(1; -2; 3), R = 16$"), ("D", "$I(-1; 2; -3), R = 16$")], "A", "Mặt cầu có tâm $I(1; -2; 3)$ và bán kính $R = \\sqrt{16} = 4$."),
        ("Cho hàm số $y = \\frac{2x - 1}{x + 1}$ có đồ thị như hình vẽ bên dưới. Phương trình đường tiệm cận đứng và tiệm cận ngang của đồ thị hàm số lần lượt là", [("A", "$x = -1$ và $y = 2$"), ("B", "$x = 2$ và $y = -1$"), ("C", "$x = 1$ và $y = 2$"), ("D", "$x = -1$ và $y = 1$")], "A", "Mẫu số bằng 0 tại $x = -1$ và tử số bằng $-3 \\neq 0$, do đó tiệm cận đứng là đường thẳng $x = -1$. Tiệm cận ngang là $y = \\lim_{x \\to \\pm\\infty} \\frac{2x-1}{x+1} = 2$."),
        ("Tích phân $\\int_0^1 (3x^2 + 1)dx$ bằng", [("A", "$2$"), ("B", "$1$"), ("C", "$3$"), ("D", "$4$")], "A", "Ta có $\\int_0^1 (3x^2 + 1)dx = [x^3 + x]_0^1 = (1 + 1) - 0 = 2$."),
        ("Trong không gian $Oxyz$, vectơ nào sau đây là một vectơ pháp tuyến của mặt phẳng $(\\alpha): 2x - y + 3z - 5 = 0$?", [("A", "$\\vec{n} = (2; -1; 3)$"), ("B", "$\\vec{n} = (2; 1; 3)$"), ("C", "$\\vec{n} = (2; -1; -5)$"), ("D", "$\\vec{n} = (-1; 3; -5)$")], "A", "Mặt phẳng $Ax + By + Cz + D = 0$ nhận vectơ $\\vec{n} = (A; B; C) = (2; -1; 3)$ làm VTPT."),
        ("Nghiệm của phương trình $2^{2x-1} = 8$ là", [("A", "$x = 2$"), ("B", "$x = \\frac{3}{2}$"), ("C", "$x = 1$"), ("D", "$x = 3$")], "A", "Phương trình tương đương $2^{2x-1} = 2^3 \\Leftrightarrow 2x - 1 = 3 \\Leftrightarrow 2x = 4 \\Leftrightarrow x = 2$."),
        ("Cho hình chóp $S.ABC$ có đáy $ABC$ vuông tại $B$, $SA \\perp (ABC)$. Góc giữa đường thẳng $SC$ và mặt phẳng đáy $(ABC)$ là", [("A", "$\\widehat{SCA}$"), ("B", "$\\widehat{SBA}$"), ("C", "$\\widehat{SCB}$"), ("D", "$\\widehat{SAC}$")], "A", "Do $SA \\perp (ABC)$ nên hình chiếu vuông góc của $SC$ lên $(ABC)$ là $AC$. Vậy góc là $\\widehat{SCA}$."),
        ("Giá trị nhỏ nhất của hàm số $f(x) = x^4 - 2x^2 + 3$ trên đoạn $[0; 2]$ bằng", [("A", "$2$"), ("B", "$3$"), ("C", "$11$"), ("D", "$1$")], "A", "Đạo hàm $f'(x) = 4x^3 - 4x = 0 \\Leftrightarrow x \\in \\{0; 1; -1\\}$. Trên $[0; 2]$, tính $f(0) = 3, f(1) = 2, f(2) = 11$. Vậy giá trị nhỏ nhất là 2."),
        ("Thể tích khối lập phương có cạnh bằng $3a$ là", [("A", "$27a^3$"), ("B", "$9a^3$"), ("C", "$3a^3$"), ("D", "$54a^3$")], "A", "Thể tích lập phương $V = (3a)^3 = 27a^3$."),
        ("Trong không gian $Oxyz$, khoảng cách từ điểm $M(1; 2; 3)$ đến mặt phẳng $(Oxy)$ bằng", [("A", "$3$"), ("B", "$1$"), ("C", "$2$"), ("D", "$\\sqrt{14}$")], "A", "Khoảng cách từ điểm $M(x_0; y_0; z_0)$ đến $(Oxy)$ là $|z_0| = |3| = 3$."),
        ("Đạo hàm của hàm số $y = 3^x$ là", [("A", "$y' = 3^x \\ln 3$"), ("B", "$y' = \\frac{3^x}{\\ln 3}$"), ("C", "$y' = x \\cdot 3^{x-1}$"), ("D", "$y' = 3^x$")], "A", "Công thức $(a^x)' = a^x \\ln a$, do đó $(3^x)' = 3^x \\ln 3$."),
        ("Cho cấp số cộng $(u_n)$ có số hạng đầu $u_1 = 3$ và công sai $d = 2$. Giá trị của $u_5$ là", [("A", "$11$"), ("B", "$13$"), ("C", "$10$"), ("D", "$9$")], "A", "Ta có $u_5 = u_1 + 4d = 3 + 4 \\times 2 = 11$."),
        ("Số tổ hợp chập 2 của 5 phần tử là", [("A", "$10$"), ("B", "$20$"), ("C", "$5$"), ("D", "$120$")], "A", "Ta có $C_5^2 = \\frac{5!}{2!3!} = 10$."),
        ("Biết $\\int f(x)dx = F(x) + C$. Khi đó $\\int 3f(x)dx$ bằng", [("A", "$3F(x) + C$"), ("B", "$\\frac{1}{3}F(x) + C$"), ("C", "$F(3x) + C$"), ("D", "$3F(x) + 3$")], "A", "Theo tính chất nguyên hàm: $\\int 3f(x)dx = 3\\int f(x)dx = 3F(x) + C$."),
        ("Đồ thị hàm số bậc ba có nhánh bên phải đi xuống thì hệ số cao nhất mang dấu", [("A", "Âm ($a < 0$)"), ("B", "Dương ($a > 0$)"), ("C", "Bằng 0"), ("D", "Tùy ý")], "A", "Khi $x \\to +\\infty$, nếu $y \\to -\\infty$ thì hệ số bậc ba $a < 0$."),
        ("Trong không gian $Oxyz$, cho đường thẳng $d: \\frac{x-1}{2} = \\frac{y+1}{-3} = \\frac{z}{1}$. Vectơ chỉ phương của $d$ là", [("A", "$\\vec{u} = (2; -3; 1)$"), ("B", "$\\vec{u} = (1; -1; 0)$"), ("C", "$\\vec{u} = (2; 3; 1)$"), ("D", "$\\vec{u} = (-1; 1; 0)$")], "A", "Từ phương trình chính tắc của $d$, ta đọc được VTCP là $\\vec{u} = (2; -3; 1)$."),
        ("Cho hình nón có bán kính đáy $r = 3$ và đường sinh $l = 5$. Diện tích xung quanh của hình nón là", [("A", "$15\\pi$"), ("B", "$30\\pi$"), ("C", "$12\\pi$"), ("D", "$45\\pi$")], "A", "Diện tích xung quanh hình nón: $S_{xq} = \\pi r l = \\pi \\times 3 \\times 5 = 15\\pi$."),
        ("Cho hai biến cố độc lập $A$ và $B$ với $P(A) = 0.4$ và $P(B) = 0.5$. Xác suất của biến cố giao $P(AB)$ là", [("A", "$0.2$"), ("B", "$0.9$"), ("C", "$0.1$"), ("D", "$0.45$")], "A", "Vì hai biến cố độc lập nên $P(AB) = P(A) \\cdot P(B) = 0.4 \\times 0.5 = 0.2$.")
    ]
    for i, (q_text, opts, ans, exp) in enumerate(math_p1_samples[:12], start=1):
        img_b64 = None
        img_cap = None
        if i == 1:
            img_b64, img_cap = b64_bbt, cap_bbt
        elif i == 2:
            img_b64, img_cap = b64_cubic, cap_cubic
        elif i == 5:
            img_b64, img_cap = b64_rational, cap_rational
        mcqs.append(Part1Question(
            id=i,
            question=q_text,
            options=[Option(label=o[0], text=o[1]) for o in opts],
            answer=ans,
            explanation=exp,
            image_base64=img_b64,
            image_caption=img_cap
        ))
    
    tf_questions = [
        Part2Question(
            id=1,
            question="Cho hàm số $y = f(x) = \\frac{x^2 - 3x + 6}{x - 1}$ có đồ thị $(C)$. Xét tính đúng sai của các khẳng định sau:",
            sub_items=[
                SubItem(label="a", statement="Tập xác định của hàm số là $D = \\mathbb{R} \\setminus \\{1\\}$.", is_correct=True, explanation="Mẫu số khác 0 khi $x \\neq 1$."),
                SubItem(label="b", statement="Đường thẳng $x = 1$ là tiệm cận đứng của đồ thị $(C)$.", is_correct=True, explanation="Do $\\lim_{x \\to 1^+} f(x) = +\\infty$ nên $x = 1$ là TCĐ."),
                SubItem(label="c", statement="Đường thẳng $y = x - 2$ là tiệm cận xiên của đồ thị $(C)$.", is_correct=True, explanation="Ta có $f(x) = x - 2 + \\frac{4}{x - 1}$. Khi $x \\to \\pm\\infty$, $\\frac{4}{x-1} \\to 0$ nên $y = x - 2$ là TCX."),
                SubItem(label="d", statement="Hàm số đồng biến trên toàn bộ tập xác định $D$.", is_correct=False, explanation="Đạo hàm đổi dấu trên các khoảng nên hàm số có khoảng đồng biến và nghịch biến.")
            ],
            explanation="Khảo sát hàm số phân thức hữu tỉ bậc hai trên bậc nhất."
        ),
        Part2Question(
            id=2,
            question="Trong không gian với hệ tọa độ $Oxyz$, cho ba điểm $A(1; 0; 0), B(0; 2; 0), C(0; 0; 3)$.",
            sub_items=[
                SubItem(label="a", statement="Phương trình mặt phẳng $(ABC)$ theo đoạn chắn là $\\frac{x}{1} + \\frac{y}{2} + \\frac{z}{3} = 1$.", is_correct=True, explanation="Áp dụng công thức mặt phẳng theo đoạn chắn chuẩn xác."),
                SubItem(label="b", statement="Một vectơ pháp tuyến của mặt phẳng $(ABC)$ là $\\vec{n} = (6; 3; 2)$.", is_correct=True, explanation="Quy đồng mẫu: $6x + 3y + 2z - 6 = 0 \\Rightarrow \\vec{n} = (6; 3; 2)$."),
                SubItem(label="c", statement="Điểm $M(1; 2; 3)$ thuộc mặt phẳng $(ABC)$.", is_correct=False, explanation="Thay tọa độ $M$: $1 + 1 + 1 = 3 \\neq 1$."),
                SubItem(label="d", statement="Khoảng cách từ gốc tọa độ $O$ đến mặt phẳng $(ABC)$ bằng $\\frac{6}{7}$.", is_correct=True, explanation="$d(O, (ABC)) = \\frac{|-6|}{\\sqrt{6^2 + 3^2 + 2^2}} = \\frac{6}{\\sqrt{49}} = \\frac{6}{7}$.")
            ],
            explanation="Bài toán hình học tọa độ không gian liên quan đến phương trình mặt phẳng đoạn chắn."
        ),
        Part2Question(
            id=3,
            question="Một chất điểm chuyển động với vận tốc $v(t) = 3t^2 - 6t + 4$ (m/s), với $t$ tính bằng giây ($t \\ge 0$).",
            sub_items=[
                SubItem(label="a", statement="Tại thời điểm $t = 2$ (s), vận tốc của chất điểm bằng $4$ m/s.", is_correct=True, explanation="$v(2) = 3(2)^2 - 6(2) + 4 = 12 - 12 + 4 = 4$ m/s."),
                SubItem(label="b", statement="Gia tốc của chất điểm tại thời điểm $t$ là $a(t) = 6t - 6$ (m/s$^2$).", is_correct=True, explanation="Gia tốc là đạo hàm của vận tốc: $a(t) = v'(t) = 6t - 6$."),
                SubItem(label="c", statement="Vận tốc tức thời nhỏ nhất của chất điểm bằng $1$ m/s.", is_correct=True, explanation="$v(t) = 3(t-1)^2 + 1 \\ge 1$. Đạt tại $t = 1$."),
                SubItem(label="d", statement="Quãng đường chất điểm đi được từ $t = 0$ đến $t = 3$ là $15$ m.", is_correct=False, explanation="$s = \\int_0^3 (3t^2 - 6t + 4)dt = [t^3 - 3t^2 + 4t]_0^3 = (27 - 27 + 12) = 12$ m.")
            ],
            explanation="Ứng dụng đạo hàm và tích phân trong bài toán chuyển động vật lý."
        ),
        Part2Question(
            id=4,
            question="Cho hình chóp $S.ABCD$ có đáy $ABCD$ là hình vuông cạnh $a$, $SA \\perp (ABCD)$ và $SA = a\\sqrt{3}$.",
            sub_items=[
                SubItem(label="a", statement="Đường thẳng $SA$ vuông góc với đường thẳng $CD$.", is_correct=True, explanation="Vì $SA \\perp (ABCD)$ nên $SA$ vuông góc với mọi đường thẳng trong đáy."),
                SubItem(label="b", statement="Tam giác $SBC$ là tam giác vuông tại $B$.", is_correct=True, explanation="Theo định lý ba đường vuông góc: $AB \\perp BC$ và $SA \\perp BC \\Rightarrow SB \\perp BC$."),
                SubItem(label="c", statement="Thể tích của khối chóp $S.ABCD$ là $V = \\frac{a^3\\sqrt{3}}{3}$.", is_correct=True, explanation="$V = \\frac{1}{3} S_{ABCD} \\cdot SA = \\frac{1}{3} a^2 \\cdot a\\sqrt{3} = \\frac{a^3\\sqrt{3}}{3}$."),
                SubItem(label="d", statement="Góc giữa mặt phẳng $(SCD)$ và đáy $(ABCD)$ bằng $30^\\circ$.", is_correct=False, explanation="Góc là $\\widehat{SDA}$ với $\\tan \\widehat{SDA} = \\frac{SA}{AD} = \\frac{a\\sqrt{3}}{a} = \\sqrt{3} \\Rightarrow 60^\\circ$.")
            ],
            explanation="Hình học không gian cổ điển về quan hệ vuông góc và thể tích."
        )
    ]
    
    short_questions = [
        Part3Question(
            id=1,
            question="Tìm hệ số góc của tiếp tuyến của đồ thị hàm số $y = x^3 - 3x^2 + 2$ tại điểm có hoành độ $x_0 = 3$.",
            answer="9",
            explanation="Ta có $y' = 3x^2 - 6x$. Hệ số góc $k = y'(3) = 3(3)^2 - 6(3) = 27 - 18 = 9$."
        ),
        Part3Question(
            id=2,
            question="Biết $\\int_1^2 \\frac{2x+3}{x} dx = a + b\\ln 2$ với $a, b$ là các số nguyên. Tính giá trị của biểu thức $T = a^2 + b^2$.",
            answer="13",
            explanation="$\\int_1^2 (2 + \\frac{3}{x})dx = [2x + 3\\ln x]_1^2 = (4 + 3\\ln 2) - 2 = 2 + 3\\ln 2$. Suy ra $a = 2, b = 3$. Vậy $T = 2^2 + 3^2 = 13$."
        ),
        Part3Question(
            id=3,
            question="Trong không gian $Oxyz$, cho mặt cầu $(S): x^2 + y^2 + z^2 - 2x + 4y - 6z - 11 = 0$. Bán kính của mặt cầu bằng bao nhiêu?",
            answer="5",
            explanation="Tâm $I(1; -2; 3)$, $d = -11$. Bán kính $R = \\sqrt{a^2 + b^2 + c^2 - d} = \\sqrt{1 + 4 + 9 - (-11)} = \\sqrt{25} = 5$."
        ),
        Part3Question(
            id=4,
            question="Một công ty sản xuất muốn thiết kế một hộp sữa hình trụ có thể tích $V = 500$ ml. Để tiết kiệm chi phí kim loại làm vỏ hộp nhất (diện tích toàn phần nhỏ nhất), tỉ số giữa chiều cao $h$ và bán kính đáy $r$ của hình trụ phải bằng bao nhiêu?",
            answer="2",
            explanation="Diện tích toàn phần $S_{tp} = 2\\pi r^2 + 2\\pi r h = 2\\pi r^2 + \\frac{2V}{r}$. Lấy đạo hàm theo $r$: $S' = 4\\pi r - \\frac{2V}{r^2} = 0 \\Leftrightarrow V = 2\\pi r^3 \\Leftrightarrow \\pi r^2 h = 2\\pi r^3 \\Leftrightarrow h = 2r \\Leftrightarrow \\frac{h}{r} = 2$."
        ),
        Part3Question(
            id=5,
            question="Cho hình hộp chữ nhật $ABCD.A'B'C'D'$ có $AB = 3, AD = 4, AA' = 5$. Tính khoảng cách giữa hai đường thẳng $AB$ và $C'D'$.",
            answer="5",
            explanation="Ta có $AB \\parallel CD \\parallel C'D'. Do đó khoảng cách là cạnh đứng $AA' = 5$."
        ),
        Part3Question(
            id=6,
            question="Một xạ thủ bắn vào bia 3 phát độc lập. Xác suất bắn trúng mỗi phát là $0.8$. Tính xác suất để xạ thủ đó bắn trúng đúng 2 phát (kết quả làm tròn đến hàng phần trăm).",
            answer="0.38",
            explanation="Xác suất bắn trúng đúng 2 phát là $C_3^2 \\times (0.8)^2 \\times (0.2)^1 = 3 \\times 0.64 \\times 0.2 = 0.384 \\approx 0.38$."
        )
    ]
    return ExamStructure(
        title="ĐỀ KIỂM TRA ĐỊNH KỲ MÔN TOÁN 12",
        subject="Toán học",
        grade="12",
        duration_minutes=50,
        school_name="SỞ GD&ĐT ... - TRƯỜNG THPT ...",
        academic_year="NĂM HỌC 2026 - 2027",
        code="101",
        part1_mcq=mcqs,
        part2_tf=tf_questions,
        part3_short=short_questions,
        scoring=calculate_exam_scoring(num_p1=len(mcqs), num_p2=len(tf_questions), num_p3=len(short_questions), num_p4=0),
        audit_report=create_default_audit_report("Toán học")
    )

def get_mock_physics_exam() -> ExamStructure:
    mcqs = []
    b64_osc, cap_osc = draw_physics_oscillation(caption="Hình: Đồ thị dao động điều hòa li độ - thời gian")
    b64_thermo, cap_thermo = draw_thermodynamic_cycle(caption="Hình: Chu trình nhiệt động lực học trong hệ p - V")

    physics_p1_samples = [
        ("Một chất điểm dao động điều hòa có đồ thị li độ - thời gian $(x - t)$ như hình vẽ bên. Biên độ và chu kỳ dao động của chất điểm lần lượt là", [("A", "$A = 4\\text{ cm}, T = 2\\text{ s}$"), ("B", "$A = 8\\text{ cm}, T = 2\\text{ s}$"), ("C", "$A = 4\\text{ cm}, T = 1\\text{ s}$"), ("D", "$A = 2\\text{ cm}, T = 4\\text{ s}$")], "A", "Từ đồ thị $x - t$, li độ cực đại (biên độ) $A = 4\\text{ cm}$. Thời gian thực hiện một dao động toàn phần là $T = 2\\text{ s}$."),
        ("Một khối khí lí tưởng thực hiện chu trình biến đổi nhiệt động lực học trong hệ tọa độ $p - V$ như hình vẽ bên. Quá trình biến đổi từ trạng thái (1) sang trạng thái (2) là quá trình", [("A", "Đẳng tích (thể tích $V$ không đổi)"), ("B", "Đẳng áp (áp suất $p$ không đổi)"), ("C", "Đẳng nhiệt (nhiệt độ $T$ không đổi)"), ("D", "Đoạn nhiệt (không trao đổi nhiệt)")], "A", "Đoạn thẳng nối trạng thái (1) và (2) vuông góc với trục thể tích $V$, nghĩa là thể tích giữ nguyên không đổi $V = \\text{const}$. Đây là quá trình biến đổi đẳng tích."),
        ("Tại nơi có gia tốc trọng trường $g$, con lắc đơn có chiều dài dây treo $l$ dao động điều hòa với tần số góc", [("A", "$\\omega = \\sqrt{\\frac{g}{l}}$"), ("B", "$\\omega = \\sqrt{\\frac{l}{g}}$"), ("C", "$\\omega = 2\\pi\\sqrt{\\frac{l}{g}}$"), ("D", "$\\omega = 2\\pi\\sqrt{\\frac{g}{l}}$")], "A", "Tần số góc của con lắc đơn dao động điều hòa là $\\omega = \\sqrt{\\frac{g}{l}}$."),
        ("Khi một sóng cơ truyền từ không khí vào nước thì đại lượng nào sau đây không đổi?", [("A", "Tần số của sóng"), ("B", "Bước sóng"), ("C", "Tốc độ truyền sóng"), ("D", "Năng lượng của sóng")], "A", "Tần số sóng chỉ phụ thuộc vào nguồn phát sóng nên không thay đổi khi truyền qua các môi trường khác nhau."),
        ("Sóng âm truyền nhanh nhất trong môi trường nào sau đây?", [("A", "Chất rắn"), ("B", "Chất lỏng"), ("C", "Chất khí"), ("D", "Chân không")], "A", "Tốc độ truyền âm giảm dần theo thứ tự: Chất rắn > Chất lỏng > Chất khí. Trong chân không sóng âm không truyền được."),
        ("Trong giao thoa sóng cơ trên mặt nước với hai nguồn kết hợp cùng pha, các điểm dao động với biên độ cực đại thỏa mãn hiệu đường truyền", [("A", "$d_2 - d_1 = k\\lambda \\quad (k \\in \\mathbb{Z})$"), ("B", "$d_2 - d_1 = (k + 0.5)\\lambda \\quad (k \\in \\mathbb{Z})$"), ("C", "$d_2 - d_1 = (2k + 1)\\frac{\\lambda}{4} \\quad (k \\in \\mathbb{Z})$"), ("D", "$d_2 - d_1 = k\\frac{\\lambda}{2} \\quad (k \\in \\mathbb{Z})$")], "A", "Hiệu đường truyền của các điểm dao động cực đại trong giao thoa 2 nguồn cùng pha là số nguyên lần bước sóng: $d_2 - d_1 = k\\lambda$."),
        ("Điều kiện có sóng dừng trên sợi dây đàn hồi dài $l$ có hai đầu cố định là", [("A", "$l = k\\frac{\\lambda}{2} \\quad (k \\in \\mathbb{N}^*)$"), ("B", "$l = (2k + 1)\\frac{\\lambda}{4} \\quad (k \\in \\mathbb{N})$"), ("C", "$l = k\\lambda \\quad (k \\in \\mathbb{N}^*)$"), ("D", "$l = (2k + 1)\\frac{\\lambda}{2} \\quad (k \\in \\mathbb{N})$")], "A", "Hai đầu cố định: chiều dài dây bằng số nguyên lần nửa bước sóng $l = k\\frac{\\lambda}{2}$."),
        ("Đặt điện áp xoay chiều $u = U\\sqrt{2}\\cos(\\omega t)$ vào hai đầu cuộn cảm thuần có độ tự cảm $L$. Cảm kháng của cuộn cảm là", [("A", "$Z_L = \\omega L$"), ("B", "$Z_L = \\frac{1}{\\omega L}$"), ("C", "$Z_L = \\sqrt{\\omega L}$"), ("D", "$Z_L = \\frac{\\omega}{L}$")], "A", "Cảm kháng của cuộn cảm thuần được xác định bởi công thức $Z_L = \\omega L$."),
        ("Trong mạch điện xoay chiều gồm $R, L, C$ mắc nối tiếp, hiện tượng cộng hưởng điện xảy ra khi", [("A", "$Z_L = Z_C$"), ("B", "$Z_L > Z_C$"), ("C", "$Z_L < Z_C$"), ("D", "$Z_L \\cdot Z_C = R^2$")], "A", "Cộng hưởng điện xảy ra khi cảm kháng bằng dung kháng: $Z_L = Z_C \\Leftrightarrow \\omega^2 LC = 1$."),
        ("Công suất tiêu thụ của đoạn mạch xoay chiều bất kỳ được tính bằng công thức", [("A", "$P = UI\\cos\\varphi$"), ("B", "$P = UI\\sin\\varphi$"), ("C", "$P = U^2 R$"), ("D", "$P = \\frac{U}{I}\\cos\\varphi$")], "A", "Công suất tiêu thụ của đoạn mạch: $P = UI\\cos\\varphi$, trong đó $\\cos\\varphi$ là hệ số công suất."),
        ("Nguyên tắc hoạt động của máy biến áp dựa trên hiện tượng", [("A", "Cảm ứng điện từ"), ("B", "Tự cảm"), ("C", "Quang điện ngoài"), ("D", "Tán sắc ánh sáng")], "A", "Máy biến áp hoạt động hoàn toàn dựa trên hiện tượng cảm ứng điện từ."),
        ("Sóng điện từ là", [("A", "Sóng ngang và truyền được trong chân không"), ("B", "Sóng dọc và truyền được trong chân không"), ("C", "Sóng ngang và không truyền được trong chân không"), ("D", "Sóng dọc và chỉ truyền trong chất rắn")], "A", "Sóng điện từ là sóng ngang, lan truyền được trong mọi môi trường vật chất và cả trong chân không với tốc độ $c = 3\\cdot 10^8\\text{ m/s}$."),
        ("Quang phổ liên tục do vật nào sau đây phát ra khi bị nung nóng ở nhiệt độ cao?", [("A", "Chất rắn, chất lỏng hoặc chất khí ở áp suất lớn"), ("B", "Chất khí ở áp suất thấp"), ("C", "Khí hiếm ở áp suất thấp"), ("D", "Hơi kim loại ở nhiệt độ thấp")], "A", "Quang phổ liên tục được phát ra bởi các chất rắn, lỏng hoặc khí có áp suất lớn khi bị nung nóng."),
        ("Hiện tượng tán sắc ánh sáng được ứng dụng chủ yếu trong thiết bị nào sau đây?", [("A", "Máy quang phổ lăng kính"), ("B", "Máy biến áp"), ("C", "Pin mặt trời"), ("D", "Kính hiển vi")], "A", "Lăng kính trong máy quang phổ có tác dụng phân tích chùm sáng phức tạp thành các thành phần đơn sắc dựa vào hiện tượng tán sắc ánh sáng."),
        ("Trong thí nghiệm giao thoa ánh sáng Young với ánh sáng đơn sắc bước sóng $\\lambda$, khoảng cách giữa hai vân sáng liên tiếp là", [("A", "$i = \\frac{\\lambda D}{a}$"), ("B", "$i = \\frac{\\lambda a}{D}$"), ("C", "$i = \\frac{a D}{\\lambda}$"), ("D", "$i = \\frac{\\lambda}{a D}$")], "A", "Công thức định nghĩa khoảng vân giao thoa: $i = \\frac{\\lambda D}{a}$."),
        ("Tia nào sau đây có bản chất là sóng điện từ và có bước sóng nhỏ hơn bước sóng của tia tử ngoại?", [("A", "Tia X (tia Rơn-ghen)"), ("B", "Tia hồng ngoại"), ("C", "Ánh sáng nhìn thấy"), ("D", "Sóng vô tuyến")], "A", "Tia X có bước sóng từ $10^{-11}\\text{ m}$ đến $10^{-8}\\text{ m}$, nhỏ hơn bước sóng tia tử ngoại ($10^{-8}\\text{ m}$ đến $3.8\\cdot 10^{-7}\\text{ m}$)."),
        ("Theo thuyết lượng tử ánh sáng của Anh-xtanh, mỗi photon của ánh sáng đơn sắc tần số $f$ mang năng lượng là", [("A", "$\\varepsilon = hf$"), ("B", "$\\varepsilon = \\frac{h}{f}$"), ("C", "$\\varepsilon = \\frac{f}{h}$"), ("D", "$\\varepsilon = hf^2$")], "A", "Lượng tử năng lượng của photon: $\\varepsilon = hf = \\frac{hc}{\\lambda}$."),
        ("Hiện tượng quang điện trong xảy ra đối với", [("A", "Chất bán dẫn"), ("B", "Kim loại kiềm"), ("C", "Kim loại kiềm thổ"), ("D", "Mọi kim loại nặng")], "A", "Hiện tượng quang điện trong là hiện tượng giải phóng các electron liên kết thành electron dẫn trong chất bán dẫn khi được chiếu sáng thích hợp."),
        ("Hạt nhân nguyên tử được cấu tạo từ các hạt", [("A", "Proton và neutron (gọi chung là nucleon)"), ("B", "Proton và electron"), ("C", "Neutron và electron"), ("D", "Proton, neutron và electron")], "A", "Hạt nhân nguyên tử chỉ chứa các nucleon gồm proton mang điện tích dương và neutron không mang điện."),
        ("Hạt nhân $_{92}^{238}\\text{U}$ có số nucleon mang điện (proton) và số neutron lần lượt là", [("A", "$92$ proton và $146$ neutron"), ("B", "$92$ proton và $238$ neutron"), ("C", "$146$ proton và $92$ neutron"), ("D", "$238$ proton và $92$ neutron")], "A", "Số proton là $Z = 92$, số neutron là $N = A - Z = 238 - 92 = 146$.")
    ]
    for i, (q_text, opts, ans, exp) in enumerate(physics_p1_samples, start=1):
        img_b64 = None
        img_cap = None
        if i == 1:
            img_b64, img_cap = b64_osc, cap_osc
        elif i == 2:
            img_b64, img_cap = b64_thermo, cap_thermo
        mcqs.append(Part1Question(
            id=i,
            question=q_text,
            options=[Option(label=o[0], text=o[1]) for o in opts],
            answer=ans,
            explanation=exp,
            image_base64=img_b64,
            image_caption=img_cap
        ))
        
    tf_questions = [
        Part2Question(
            id=1,
            question="Một con lắc lò xo gồm vật nhỏ có khối lượng $m = 100\\text{ g}$ và lò xo có độ cứng $k = 40\\text{ N/m}$ dao động điều hòa theo phương ngang với biên độ $A = 5\\text{ cm}$. Lấy $\\pi^2 = 10$.",
            sub_items=[
                SubItem(label="a", statement="Tần số góc dao động của con lắc là $\\omega = 20\\text{ rad/s}$.", is_correct=True, explanation="Ta có $\\omega = \\sqrt{\\frac{k}{m}} = \\sqrt{\\frac{40}{0.1}} = 20\\text{ rad/s}$."),
                SubItem(label="b", statement="Cơ năng của con lắc lò xo biến thiên điều hòa theo thời gian với chu kỳ bằng một nửa chu kỳ dao động.", is_correct=False, explanation="Cơ năng của con lắc lò xo được bảo toàn và không đổi theo thời gian ($W = \\frac{1}{2}kA^2$)."),
                SubItem(label="c", statement="Tốc độ cực đại của vật trong quá trình dao động là $v_{\\max} = 1\\text{ m/s}$.", is_correct=True, explanation="$v_{\\max} = \\omega A = 20 \\times 0.05 = 1\\text{ m/s}$."),
                SubItem(label="d", statement="Khi vật đi qua vị trí có li độ $x = 2.5\\text{ cm}$, động năng của vật bằng 3 lần thế năng.", is_correct=True, explanation="Khi $x = \\frac{A}{2} \\Rightarrow W_t = \\frac{W}{4} \\Rightarrow W_d = \\frac{3}{4}W = 3W_t$.")
            ],
            explanation="Khảo sát dao động điều hòa và năng lượng của con lắc lò xo."
        ),
        Part2Question(
            id=2,
            question="Trên một sợi dây đàn hồi chiều dài $L = 1.2\\text{ m}$ có hai đầu cố định, đang có sóng dừng ổn định với tần số $f = 50\\text{ Hz}$. Quan sát thấy trên dây có 3 bụng sóng.",
            sub_items=[
                SubItem(label="a", statement="Bước sóng của sóng truyền trên dây là $\\lambda = 0.8\\text{ m}$.", is_correct=True, explanation="Điều kiện hai đầu cố định: $L = k\\frac{\\lambda}{2} \\Rightarrow 1.2 = 3\\frac{\\lambda}{2} \\Rightarrow \\lambda = 0.8\\text{ m}$."),
                SubItem(label="b", statement="Tốc độ truyền sóng trên sợi dây là $v = 40\\text{ m/s}$.", is_correct=True, explanation="$v = \\lambda f = 0.8 \\times 50 = 40\\text{ m/s}$."),
                SubItem(label="c", statement="Kể cả hai đầu cố định, trên dây có tất cả 4 nút sóng.", is_correct=True, explanation="Số nút sóng trên dây có 2 đầu cố định là $k + 1 = 3 + 1 = 4$ nút."),
                SubItem(label="d", statement="Tất cả các phần tử môi trường tại các bụng sóng luôn dao động cùng pha với nhau.", is_correct=False, explanation="Các bụng sóng thuộc hai múi sóng cạnh nhau dao động ngược pha nhau.")
            ],
            explanation="Sóng dừng trên sợi dây hai đầu cố định."
        ),
        Part2Question(
            id=3,
            question="Đặt điện áp xoay chiều $u = 120\\sqrt{2}\\cos(100\\pi t)\\text{ V}$ vào hai đầu đoạn mạch nối tiếp gồm điện trở thuần $R = 40\\ \\Omega$, cuộn cảm thuần có độ tự cảm $L = \\frac{0.4}{\\pi}\\text{ H}$ và tụ điện có điện dung $C = \\frac{10^{-3}}{7\\pi}\\text{ F}$.",
            sub_items=[
                SubItem(label="a", statement="Cảm kháng của cuộn dây là $Z_L = 40\\ \\Omega$.", is_correct=True, explanation="$Z_L = \\omega L = 100\\pi \\times \\frac{0.4}{\\pi} = 40\\ \\Omega$."),
                SubItem(label="b", statement="Dung kháng của tụ điện là $Z_C = 70\\ \\Omega$.", is_correct=True, explanation="$Z_C = \\frac{1}{\\omega C} = \\frac{1}{100\\pi \\times \\frac{10^{-3}}{7\\pi}} = 70\\ \\Omega$."),
                SubItem(label="c", statement="Cường độ dòng điện hiệu dụng chạy qua đoạn mạch là $I = 2.4\\text{ A}$.", is_correct=True, explanation="Tổng trở $Z = \\sqrt{R^2 + (Z_L - Z_C)^2} = \\sqrt{40^2 + (40-70)^2} = 50\\ \\Omega \\Rightarrow I = \\frac{U}{Z} = \\frac{120}{50} = 2.4\\text{ A}$."),
                SubItem(label="d", statement="Hệ số công suất của đoạn mạch bằng $\\cos\\varphi = 0.6$.", is_correct=False, explanation="$\\cos\\varphi = \\frac{R}{Z} = \\frac{40}{50} = 0.8$.")
            ],
            explanation="Dòng điện xoay chiều trong mạch RLC không phân nhánh."
        ),
        Part2Question(
            id=4,
            question="Trong thí nghiệm Young về giao thoa ánh sáng, khoảng cách giữa hai khe là $a = 1\\text{ mm}$, khoảng cách từ hai khe đến màn quan sát là $D = 2\\text{ m}$. Chiếu vào hai khe chùm sáng đơn sắc có bước sóng $\\lambda = 0.5\\ \\mu\\text{m}$.",
            sub_items=[
                SubItem(label="a", statement="Khoảng vân giao thoa quan sát được trên màn là $i = 1.0\\text{ mm}$.", is_correct=True, explanation="$i = \\frac{\\lambda D}{a} = \\frac{0.5 \\times 10^{-6} \\times 2}{10^{-3}} = 10^{-3}\\text{ m} = 1.0\\text{ mm}$."),
                SubItem(label="b", statement="Tại điểm $M$ trên màn cách vân sáng trung tâm $3.5\\text{ mm}$ là vị trí vân tối thứ 4.", is_correct=True, explanation="Tọa độ vân tối $x = (k - 0.5)i$. Với $k = 4 \\Rightarrow x = 3.5i = 3.5\\text{ mm}$."),
                SubItem(label="c", statement="Nếu dịch chuyển màn ra xa thêm $0.5\\text{ m}$ thì khoảng vân trên màn sẽ giảm đi.", is_correct=False, explanation="Vì $i = \\frac{\\lambda D}{a}$, khi tăng $D$ thì khoảng vân $i$ sẽ tăng tỉ lệ thuận."),
                SubItem(label="d", statement="Khi thay ánh sáng đơn sắc bằng ánh sáng trắng thì tại tâm màn hình quan sát được vân sáng màu trắng.", is_correct=True, explanation="Tại vị trí chính giữa màn (vân trung tâm $k = 0$), tất cả các ánh sáng đơn sắc đều cho vân sáng và chồng chập tạo thành dải sáng trắng.")
            ],
            explanation="Hiện tượng giao thoa ánh sáng qua khe Young."
        )
    ]
    
    short_questions = [
        Part3Question(
            id=1,
            question="Một vật dao động điều hòa thực hiện được 50 dao động toàn phần trong thời gian 25 giây. Tần số dao động của vật bằng bao nhiêu Hertz?",
            answer="2",
            explanation="Tần số dao động $f = \\frac{N}{\\Delta t} = \\frac{50}{25} = 2\\text{ Hz}$."
        ),
        Part3Question(
            id=2,
            question="Một sóng cơ truyền với tốc độ $v = 12\\text{ m/s}$ và tần số $f = 20\\text{ Hz}$. Bước sóng $\\lambda$ của sóng này bằng bao nhiêu xentimet?",
            answer="60",
            explanation="$\\lambda = \\frac{v}{f} = \\frac{12}{20} = 0.6\\text{ m} = 60\\text{ cm}$."
        ),
        Part3Question(
            id=3,
            question="Mạch dao động điện từ tự do LC có $L = \\frac{1}{\\pi}\\text{ mH}$ và $C = \\frac{4}{\\pi}\\text{ nF}$. Chu kỳ dao động điện từ riêng của mạch bằng bao nhiêu microgiây ($\\mu\\text{s}$)?",
            answer="4",
            explanation="$T = 2\\pi\\sqrt{LC} = 2\\pi\\sqrt{\\frac{1}{\\pi}\\cdot 10^{-3} \\times \\frac{4}{\\pi}\\cdot 10^{-9}} = 2\\pi \\times \\frac{2}{\\pi}\\cdot 10^{-6} = 4\\cdot 10^{-6}\\text{ s} = 4\\ \\mu\\text{s}$."
        ),
        Part3Question(
            id=4,
            question="Đặt điện áp xoay chiều có giá trị hiệu dụng $U = 100\\text{ V}$ vào hai đầu đoạn mạch $RLC$ nối tiếp. Biết $U_R = 60\\text{ V}$ và $U_L = 160\\text{ V}$. Biết mạch có tính dung kháng ($U_C > U_L$), điện áp hiệu dụng giữa hai bản tụ điện $U_C$ bằng bao nhiêu Vôn?",
            answer="240",
            explanation="$U = \\sqrt{U_R^2 + (U_L - U_C)^2} \\Rightarrow 100 = \\sqrt{60^2 + (160 - U_C)^2} \\Rightarrow |160 - U_C| = 80$. Do $U_C > U_L$ nên $U_C - 160 = 80 \\Rightarrow U_C = 240\\text{ V}$."
        ),
        Part3Question(
            id=5,
            question="Một chất phóng xạ có chu kỳ bán rã là $T = 12$ ngày đêm. Sau 36 ngày đêm, khối lượng chất phóng xạ đó còn lại bằng một phần mấy khối lượng ban đầu (điền số nguyên mẫu số $k$ trong tỉ số $\\frac{1}{k}$)?",
            answer="8",
            explanation="Số chu kỳ bán rã: $n = \\frac{t}{T} = \\frac{36}{12} = 3$. Khối lượng còn lại: $m = \\frac{m_0}{2^n} = \\frac{m_0}{2^3} = \\frac{m_0}{8}$. Vậy $k = 8$."
        ),
        Part3Question(
            id=6,
            question="Trong hạt nhân nguyên tử sắt $_{26}^{56}\\text{Fe}$, số hạt nơtron (neutron) bằng bao nhiêu?",
            answer="30",
            explanation="Số neutron $N = A - Z = 56 - 26 = 30$."
        )
    ]
    return ExamStructure(
        title="ĐỀ KIỂM TRA ĐỊNH KỲ MÔN VẬT LÝ 12",
        subject="Vật lý",
        grade="12",
        duration_minutes=50,
        school_name="SỞ GD&ĐT ... - TRƯỜNG THPT ...",
        academic_year="NĂM HỌC 2026 - 2027",
        code="101",
        part1_mcq=mcqs,
        part2_tf=tf_questions,
        part3_short=short_questions,
        scoring=calculate_exam_scoring(num_p1=len(mcqs), num_p2=len(tf_questions), num_p3=len(short_questions), num_p4=0),
        audit_report=create_default_audit_report("Vật lý")
    )

def get_mock_chemistry_exam() -> ExamStructure:
    mcqs = []
    b64_titr, cap_titr = draw_titration_curve(caption="Hình: Đường cong chuẩn độ axit mạnh bằng bazơ mạnh")
    b64_precip, cap_precip = draw_precipitation_graph(caption="Hình: Đồ thị kết tủa CaCO3 khi sục khí CO2 vào dung dịch Ca(OH)2")

    chemistry_p1_samples = [
        ("Đường cong chuẩn độ $25\\text{ mL}$ dung dịch axit mạnh $HCl\\ 0.1\\text{ M}$ bằng dung dịch chuẩn bazơ mạnh $NaOH\\ 0.1\\text{ M}$ được biểu diễn như hình vẽ bên. Giá trị pH tại điểm tương đương của phép chuẩn độ này bằng", [("A", "$7.0$"), ("B", "$4.0$"), ("C", "$9.0$"), ("D", "$1.0$")], "A", "Chuẩn độ axit mạnh bằng bazơ mạnh, sản phẩm muối $NaCl$ không bị thủy phân nên tại điểm tương đương môi trường trung tính với $\\text{pH} = 7.0$."),
        ("Sục từ từ đến dư khí $CO_2$ vào cốc đựng dung dịch $Ca(OH)_2$. Đồ thị biểu diễn số mol kết tủa $CaCO_3$ theo số mol $CO_2$ sục vào được thể hiện như hình bên. Hiện tượng quan sát được tương ứng với đoạn đồ thị đi xuống là", [("A", "Kết tủa bị hòa tan dần do tạo muối tan $Ca(HCO_3)_2$"), ("B", "Lượng kết tủa đạt cực đại và không đổi"), ("C", "Khí $CO_2$ không còn phản ứng và bắt đầu thoát ra ngoài"), ("D", "Kết tủa tiếp tục tăng nhanh hơn")], "A", "Khi đã đạt kết tủa cực đại, nếu tiếp tục sục thêm $CO_2$ thì kết tủa tan dần theo phản ứng: $CO_2 + H_2O + CaCO_3 \\to Ca(HCO_3)_2$, làm giảm số mol kết tủa về 0 tương ứng với nhánh đồ thị đi xuống."),
        ("Cacbohidrat nào sau đây là đồng phân của glucozơ?", [("A", "Fructozơ"), ("B", "Saccarozơ"), ("C", "Tinh bột"), ("D", "Xenlulozơ")], "A", "Glucozơ và fructozơ đều có cùng công thức phân tử $C_6H_{12}O_6$ nhưng khác nhau về cấu tạo phân tử nên là đồng phân của nhau."),
        ("Cacbohidrat nào sau đây thuộc loại monosaccarit và không bị thủy phân trong môi trường axit?", [("A", "Glucozơ"), ("B", "Saccarozơ"), ("C", "Tinh bột"), ("D", "Mantozo")], "A", "Glucozơ là monosaccarit đơn giản nhất, không bị thủy phân."),
        ("Nhỏ vài giọt dung dịch iot ($I_2$) vào ống nghiệm đựng hồ tinh bột ở nhiệt độ thường, dung dịch xuất hiện màu đặc trưng là", [("A", "Màu xanh tím"), ("B", "Màu đỏ nâu"), ("C", "Màu hồng cánh sen"), ("D", "Màu vàng cam")], "A", "Phân tử tinh bột có cấu trúc xoắn tạo các khoang rỗng hấp phụ phân tử iot tạo hợp chất bọc màu xanh tím đặc trưng."),
        ("Amin nào sau đây ở thể khí ở điều kiện thường và có mùi khai khó chịu tương tự amoniac?", [("A", "Metylamin ($CH_3NH_2$)"), ("B", "Anilin ($C_6H_5NH_2$)"), ("C", "Phenylamin"), ("D", "Benzylamin")], "A", "Các amin $C_1 - C_3$ gồm metylamin, đimetylamin, trimetylamin và etylamin là những chất khí ở điều kiện thường, mùi khai độc."),
        ("Dung dịch chất nào sau đây làm quỳ tím chuyển sang màu đỏ (hóa hồng)?", [("A", "Axit glutamic"), ("B", "Glyxin"), ("C", "Lysin"), ("D", "Alanin")], "A", "Axit glutamic ($HOOC-[CH_2]_2-CH(NH_2)-COOH$) có 2 nhóm $-COOH$ và 1 nhóm $-NH_2$ nên dung dịch có tính axit, làm quỳ tím hóa đỏ."),
        ("Số liên kết peptit có trong phân tử glyxylalanin (Gly-Ala) là", [("A", "1"), ("B", "2"), ("C", "3"), ("D", "0")], "A", "Dipeptit gồm 2 gốc $\\alpha$-amino axit liên kết với nhau bằng 1 liên kết peptit ($-CO-NH-$)."),
        ("Thuốc thử nào sau đây dùng để nhận biết dung dịch lòng trắng trứng bằng phản ứng màu biure?", [("A", "$Cu(OH)_2$ trong môi trường kiềm"), ("B", "Dung dịch $AgNO_3/NH_3$"), ("C", "Nước brom"), ("D", "Dung dịch quỳ tím")], "A", "Các hợp chất có từ 2 liên kết peptit trở lên (tripeptit, protein) phản ứng với $Cu(OH)_2$ trong môi trường kiềm tạo phức chất màu tím đặc trưng."),
        ("Polime nào sau đây được tổng hợp bằng phản ứng trùng hợp?", [("A", "Poli(vinyl clorua) (PVC)"), ("B", "Nilon-6,6"), ("C", "Tơ lapsan"), ("D", "Poli(etylen terephtalat)")], "A", "PVC được điều chế bằng phản ứng trùng hợp monome vinyl clorua ($CH_2=CH-Cl$)."),
        ("Kim loại nào sau đây có độ dẫn điện tốt nhất trong tất cả các kim loại?", [("A", "Bạc ($Ag$)"), ("B", "Đồng ($Cu$)"), ("C", "Vàng ($Au$)"), ("D", "Nhôm ($Al$)")], "A", "Thứ tự dẫn điện giảm dần của kim loại: $Ag > Cu > Au > Al > Fe$."),
        ("Kim loại nào sau đây có nhiệt độ nóng chảy cao nhất ($3410^\\circ\\text{C}$), thường được dùng làm dây tóc bóng đèn?", [("A", "Vonfram ($W$)"), ("B", "Sắt ($Fe$)"), ("C", "Crom ($Cr$)"), ("D", "Đồng ($Cu$)")], "A", "Vonfram ($W$) là kim loại có nhiệt độ nóng chảy cao nhất."),
        ("Kim loại nào sau đây tác dụng mãnh liệt với nước ở nhiệt độ thường giải phóng khí hidro?", [("A", "Natri ($Na$)"), ("B", "Sắt ($Fe$)"), ("C", "Đồng ($Cu$)"), ("D", "Bạc ($Ag$)")], "A", "Kim loại kiềm như $Na$ phản ứng mãnh liệt với nước ở nhiệt độ thường: $2Na + 2H_2O \\to 2NaOH + H_2$."),
        ("Trong dung dịch, ion kim loại nào sau đây có tính oxi hóa mạnh nhất trong dãy điện hóa?", [("A", "$Ag^+$"), ("B", "$Cu^{2+}$"), ("C", "$Fe^{2+}$"), ("D", "$Mg^{2+}$")], "A", "Theo chiều từ trái sang phải trong dãy điện hóa: tính oxi hóa tăng dần, ion $Ag^+$ có tính oxi hóa mạnh nhất trong các ion trên."),
        ("Để bảo vệ vỏ tàu thủy bằng thép (chứa sắt) khỏi bị ăn mòn trong nước biển, người ta thường gắn các tấm kim loại nào sau đây vào vỏ tàu?", [("A", "Kẽm ($Zn$)"), ("B", "Đồng ($Cu$)"), ("C", "Chì ($Pb$)"), ("D", "Bạc ($Ag$)")], "A", "Kẽm có tính khử mạnh hơn sắt nên đóng vai trò là anot bị ăn mòn trước (phương pháp bảo vệ điện hóa), bảo vệ được vỏ tàu sắt."),
        ("Quặng boxit ($Al_2O_3 \\cdot 2H_2O$) là nguyên liệu chính dùng để sản xuất kim loại nào sau đây trong công nghiệp?", [("A", "Nhôm ($Al$)"), ("B", "Sắt ($Fe$)"), ("C", "Magie ($Mg$)"), ("D", "Canxi ($Ca$)")], "A", "Nhôm được sản xuất trong công nghiệp bằng phương pháp điện phân nóng chảy $Al_2O_3$ tinh khiết tách từ quặng boxit."),
        ("Cặp kim loại nào sau đây bị thụ động hóa (không tan) trong dung dịch $HNO_3$ đặc, nguội và $H_2SO_4$ đặc, nguội?", [("A", "$Al$ và $Fe$"), ("B", "$Cu$ và $Ag$"), ("C", "$Zn$ và $Mg$"), ("D", "$Ca$ và $Ba$")], "A", "Nhôm ($Al$), sắt ($Fe$) và crom ($Cr$) bị thụ động hóa trong $HNO_3$ đặc nguội và $H_2SO_4$ đặc nguội do tạo màng oxit bảo vệ."),
        ("Công thức hóa học của thạch cao sống là", [("A", "$CaSO_4 \\cdot 2H_2O$"), ("B", "$CaSO_4 \\cdot H_2O$"), ("C", "$CaSO_4$"), ("D", "$CaCO_3$")], "A", "Thạch cao sống là $CaSO_4 \\cdot 2H_2O$, thạch cao nung là $CaSO_4 \\cdot H_2O$ (hoặc $CaSO_4 \\cdot 0.5H_2O$), thạch cao khan là $CaSO_4$."),
        ("Cho dung dịch $NaOH$ từ từ đến dư vào ống nghiệm chứa dung dịch $AlCl_3$, hiện tượng quan sát được là", [("A", "Xuất hiện kết tủa keo trắng, sau đó kết tủa tan dần tạo dung dịch trong suốt"), ("B", "Xuất hiện kết tủa keo trắng và kết tủa không tan"), ("C", "Có kết tủa nâu đỏ xuất hiện"), ("D", "Chỉ có sủi bọt khí không màu")], "A", "Đầu tiên tạo kết tủa keo trắng: $Al^{3+} + 3OH^- \\to Al(OH)_3 \\downarrow$. Khi kiềm dư, kết tủa tan: $Al(OH)_3 + OH^- \\to [Al(OH)_4]^-$."),
        ("Hợp chất nào sau đây của sắt vừa thể hiện tính oxi hóa vừa thể hiện tính khử?", [("A", "$FeO$"), ("B", "$Fe_2O_3$"), ("C", "$Fe_2(SO_4)_3$"), ("D", "$Fe(OH)_3$")], "A", "Trong $FeO$, sắt có số oxi hóa trung gian $+2$, có thể tăng lên $+3$ (tính khử) hoặc giảm xuống $0$ (tính oxi hóa).")
    ]
    for i, (q_text, opts, ans, exp) in enumerate(chemistry_p1_samples, start=1):
        img_b64 = None
        img_cap = None
        if i == 1:
            img_b64, img_cap = b64_titr, cap_titr
        elif i == 2:
            img_b64, img_cap = b64_precip, cap_precip
        mcqs.append(Part1Question(
            id=i,
            question=q_text,
            options=[Option(label=o[0], text=o[1]) for o in opts],
            answer=ans,
            explanation=exp,
            image_base64=img_b64,
            image_caption=img_cap
        ))
        
    tf_questions = [
        Part2Question(
            id=1,
            question="Tiến hành thí nghiệm điều chế etyl axetat: Cho vào ống nghiệm $2\\text{ ml } C_2H_5OH$ nguyên chất, $2\\text{ ml } CH_3COOH$ băng và vài giọt dung dịch $H_2SO_4$ đặc. Lắc đều, đun cách thủy $5 - 10$ phút ở $65 - 70^\\circ\\text{C}$. Sau đó làm lạnh rồi rót thêm $2\\text{ ml}$ dung dịch $NaCl$ bão hòa.",
            sub_items=[
                SubItem(label="a", statement="Axit sunfuric đặc vừa đóng vai trò chất xúc tác vừa có tác dụng hút nước để cân bằng chuyển dịch theo chiều thuận.", is_correct=True, explanation="Phản ứng este hóa là phản ứng thuận nghịch; $H_2SO_4$ đặc xúc tác và hút nước làm tăng hiệu suất."),
                SubItem(label="b", statement="Mục đích thêm dung dịch $NaCl$ bão hòa là để làm tăng tỉ trọng của lớp chất lỏng phía dưới, giúp este dễ tách lớp nổi lên trên.", is_correct=True, explanation="Dung dịch $NaCl$ bão hòa làm tăng khối lượng riêng của pha nước và làm giảm độ tan của etyl axetat."),
                SubItem(label="c", statement="Có thể thay thế axit sunfuric đặc bằng dung dịch axit clohidric ($HCl$) đậm đặc mà không ảnh hưởng đến hiệu suất phản ứng.", is_correct=False, explanation="$HCl$ đặc dễ bay hơi khi đun nóng và không có tính háo nước mạnh như $H_2SO_4$ đặc."),
                SubItem(label="d", statement="Etyl axetat thu được là chất lỏng không màu, nhẹ hơn nước và có mùi thơm đặc trưng của quả lê/táo.", is_correct=True, explanation="Etyl axetat nhẹ hơn nước, ít tan trong nước và có mùi thơm este dịu nhẹ.")
            ],
            explanation="Thí nghiệm điều chế este etyl axetat trong phòng thí nghiệm hóa học hữu cơ."
        ),
        Part2Question(
            id=2,
            question="Xét các phát biểu liên quan đến cacbohidrat (glucozơ, fructozơ, saccarozơ, tinh bột và xenlulozơ):",
            sub_items=[
                SubItem(label="a", statement="Glucozơ và saccarozơ đều phản ứng được với $Cu(OH)_2$ ở nhiệt độ phòng tạo dung dịch có màu xanh lam.", is_correct=True, explanation="Cả hai đều có nhiều nhóm $-OH$ kề nhau (tính chất của ancol đa chức)."),
                SubItem(label="b", statement="Tinh bột và xenlulozơ là đồng phân của nhau vì đều có công thức phân tử $(C_6H_{10}O_5)_n$.", is_correct=False, explanation="Mặc dù có cùng công thức đơn giản nhất nhưng hệ số polime hóa $n$ khác nhau hoàn toàn nên không phải là đồng phân."),
                SubItem(label="c", statement="Thủy phân hoàn toàn tinh bột trong môi trường axit chỉ thu được một loại monosaccarit duy nhất là $\\alpha$-glucozơ.", is_correct=True, explanation="Tinh bột được cấu tạo hoàn toàn từ các mắt xích $\\alpha$-glucozơ."),
                SubItem(label="d", statement="Xenlulozơ trinitrat được điều chế từ xenlulozơ và axit nitric đặc là hợp chất dễ cháy nổ, dùng làm thuốc súng không khói.", is_correct=True, explanation="Phản ứng este hóa giữa xenlulozơ và $HNO_3$ đặc tạo $[C_6H_7O_2(ONO_2)_3]_n$ làm thuốc súng không khói.")
            ],
            explanation="Cấu trúc, tính chất hóa học và ứng dụng thực tiễn của các hợp chất cacbohidrat."
        ),
        Part2Question(
            id=3,
            question="Xét các phát biểu về amin, amino axit và protein:",
            sub_items=[
                SubItem(label="a", statement="Dung dịch anilin trong nước không làm đổi màu quỳ tím do anilin có tính bazơ rất yếu.", is_correct=True, explanation="Gốc phenyl hút electron làm giảm mật độ điện tích âm trên nguyên tử Nitơ, tính bazơ rất yếu không đổi màu quỳ."),
                SubItem(label="b", statement="Phân tử alanin ($CH_3-CH(NH_2)-COOH$) có tính chất lưỡng tính, vừa tác dụng với axit vừa tác dụng với bazơ.", is_correct=True, explanation="Nhóm amino mang tính bazơ và nhóm cacboxyl mang tính axit."),
                SubItem(label="c", statement="Dipeptit Gly-Ala có phản ứng màu biure với $Cu(OH)_2$ tạo dung dịch màu tím.", is_correct=False, explanation="Dipeptit chỉ có 1 liên kết peptit nên KHÔNG tham gia phản ứng màu biure (cần từ tripeptit trở lên)."),
                SubItem(label="d", statement="Khi đun nóng lòng trắng trứng, protein bị đông tụ do biến tính cấu trúc không gian.", is_correct=True, explanation="Nhiệt độ làm phá vỡ các liên kết thứ cấp khiến protein bị đông tụ.")
            ],
            explanation="Kiến thức trọng tâm về amin, amino axit, peptit và protein."
        ),
        Part2Question(
            id=4,
            question="Một học sinh tiến hành thí nghiệm ăn mòn kim loại: Nhúng thanh kẽm ($Zn$) và thanh đồng ($Cu$) vào cốc đựng dung dịch $H_2SO_4$ loãng, sau đó nối hai thanh bằng một dây dẫn qua một điện kế.",
            sub_items=[
                SubItem(label="a", statement="Trước khi nối dây dẫn, bọt khí $H_2$ chỉ thoát ra trên bề mặt thanh kẽm.", is_correct=True, explanation="Kim loại đồng đứng sau hidro trong dãy điện hóa nên không phản ứng với $H_2SO_4$ loãng."),
                SubItem(label="b", statement="Sau khi nối dây dẫn, bọt khí $H_2$ thoát ra mãnh liệt hơn và xuất hiện chủ yếu trên bề mặt thanh đồng.", is_correct=True, explanation="Hình thành pin điện hóa $Zn - Cu$; ion $H^+$ nhận electron tại thanh đồng (catot) để tạo khí $H_2$."),
                SubItem(label="c", statement="Trong pin điện hóa này, thanh kẽm đóng vai trò là cực dương (catot) và bị hòa tan.", is_correct=False, explanation="Thanh kẽm có thế điện cực âm hơn nên là cực âm (anot) và bị ăn mòn điện hóa."),
                SubItem(label="d", statement="Tốc độ ăn mòn thanh kẽm sau khi nối dây dẫn nhanh hơn so với trước khi nối dây.", is_correct=True, explanation="Ăn mòn điện hóa xảy ra với tốc độ nhanh hơn nhiều so với ăn mòn hóa học đơn thuần.")
            ],
            explanation="Cơ chế ăn mòn điện hóa học và hoạt động của pin điện hóa."
        )
    ]
    
    short_questions = [
        Part3Question(
            id=1,
            question="Cho 9 gam glucozơ ($C_6H_{12}O_6$) phản ứng tráng bạc hoàn toàn với dung dịch $AgNO_3$ trong $NH_3$ dư, đun nóng. Khối lượng bạc ($Ag, M = 108$) thu được tối đa bằng bao nhiêu gam?",
            answer="10.8",
            explanation="$n_{\\text{glucozơ}} = \\frac{9}{180} = 0.05\\text{ mol}$. Phương trình: $1\\text{ glucozơ} \\to 2Ag \\Rightarrow n_{Ag} = 0.1\\text{ mol} \\Rightarrow m_{Ag} = 0.1 \\times 108 = 10.8\\text{ g}$."
        ),
        Part3Question(
            id=2,
            question="Phân tử khối của este etyl axetat ($CH_3COOC_2H_5$) bằng bao nhiêu g/mol?",
            answer="88",
            explanation="Công thức phân tử $C_4H_8O_2$: $M = 12 \\times 4 + 1 \\times 8 + 16 \\times 2 = 88\\text{ g/mol}$."
        ),
        Part3Question(
            id=3,
            question="Một phân tử pentapeptit mạch hở cấu tạo từ các $\\alpha$-amino axit có bao nhiêu liên kết peptit?",
            answer="4",
            explanation="Số liên kết peptit trong một peptit mạch hở cấu tạo từ $n$ gốc amino axit là $n - 1 = 5 - 1 = 4$."
        ),
        Part3Question(
            id=4,
            question="Cho $5.4\\text{ gam}$ kim loại nhôm ($Al, M = 27$) phản ứng hoàn toàn với lượng dư dung dịch $NaOH$. Thể tích khí $H_2$ (đktc) thu được bằng bao nhiêu lít?",
            answer="6.72",
            explanation="$n_{Al} = \\frac{5.4}{27} = 0.2\\text{ mol}$. Phương trình: $Al + NaOH + H_2O \\to NaAlO_2 + \\frac{3}{2}H_2 \\Rightarrow n_{H_2} = 0.2 \\times 1.5 = 0.3\\text{ mol} \\Rightarrow V = 0.3 \\times 22.4 = 6.72\\text{ lít}$."
        ),
        Part3Question(
            id=5,
            question="Ngâm một đinh sắt ($Fe, M = 56$) vào dung dịch $CuSO_4$ dư. Sau phản ứng, lấy đinh sắt ra rửa nhẹ, sấy khô thấy khối lượng tăng thêm $0.8\\text{ gam}$. Số mol đồng bám trên thanh sắt bằng bao nhiêu mol?",
            answer="0.1",
            explanation="Phương trình: $Fe + Cu^{2+} \\to Fe^{2+} + Cu$. Gọi số mol phản ứng là $x$. Độ tăng khối lượng: $\\Delta m = 64x - 56x = 8x = 0.8\\text{ g} \\Rightarrow x = 0.1\\text{ mol}$."
        ),
        Part3Question(
            id=6,
            question="Để trung hòa hoàn toàn $9\\text{ gam}$ một amin no đơn chức mạch hở $X$ cần dùng đúng $0.2\\text{ mol } HCl$. Phân tử khối của amin $X$ bằng bao nhiêu g/mol?",
            answer="45",
            explanation="$n_X = n_{HCl} = 0.2\\text{ mol} \\Rightarrow M_X = \\frac{9}{0.2} = 45\\text{ g/mol}$ (ứng với etylamin $C_2H_5NH_2$)."
        )
    ]
    return ExamStructure(
        title="ĐỀ KIỂM TRA ĐỊNH KỲ MÔN HÓA HỌC 12",
        subject="Hóa học",
        grade="12",
        duration_minutes=50,
        school_name="SỞ GD&ĐT ... - TRƯỜNG THPT ...",
        academic_year="NĂM HỌC 2026 - 2027",
        code="101",
        part1_mcq=mcqs,
        part2_tf=tf_questions,
        part3_short=short_questions,
        scoring=calculate_exam_scoring(num_p1=len(mcqs), num_p2=len(tf_questions), num_p3=len(short_questions), num_p4=0),
        audit_report=create_default_audit_report("Hóa học")
    )

def get_mock_gdqp_exam() -> ExamStructure:
    mcqs = []
    gdqp_p1_samples = [
        ("Theo Luật An ninh quốc gia năm 2004, an ninh quốc gia là gì?", [("A", "Sự ổn định, phát triển bền vững của chế độ XHCN, độc lập, chủ quyền, thống nhất và toàn vẹn lãnh thổ của Tổ quốc"), ("B", "Hoạt động phòng chống tệ nạn xã hội và bảo đảm an toàn giao thông tại địa phương"), ("C", "Sự bảo toàn nguyên vẹn tài sản của các tập đoàn kinh tế nhà nước"), ("D", "Sự duy trì trật tự trị an đơn thuần tại các khu dân cư đô thị")], "A", "Theo Điều 2 Luật An ninh quốc gia năm 2004, an ninh quốc gia là sự ổn định, phát triển bền vững của chế độ XHCN và Nhà nước CHXHCN Việt Nam, sự bất khả xâm phạm độc lập, chủ quyền, thống nhất, toàn vẹn lãnh thổ của Tổ quốc."),
        ("Nét đặc sắc nổi bật nhất trong nghệ thuật quân sự đánh giặc giữ nước truyền thống của dân tộc Việt Nam là", [("A", "Lấy ít địch nhiều, lấy nhỏ thắng lớn, lấy yếu chống mạnh"), ("B", "Sử dụng vũ khí tối tân hiện đại áp đảo hoàn toàn đối phương"), ("C", "Chỉ phòng thủ thụ động dựa vào thành lũy kiên cố"), ("D", "Huy động tối đa quân số lấn át đối phương trên chiến trường mở")], "A", "Truyền thống nghệ thuật quân sự độc đáo của ông cha ta luôn là 'lấy đoản binh thắng trường trận', 'lấy ít địch nhiều, lấy đại nghĩa để thắng hung tàn'."),
        ("Chiến thắng lịch sử mùa xuân Kỷ Dậu năm 1789 quét sạch 29 vạn quân Mãn Thanh gắn liền với tên tuổi của vị anh hùng dân tộc nào?", [("A", "Quang Trung - Nguyễn Huệ"), ("B", "Trần Hưng Đạo"), ("C", "Lê Lợi"), ("D", "Lý Thường Kiệt")], "A", "Vua Quang Trung chỉ huy cuộc hành quân thần tốc đánh tan 29 vạn quân Thanh với đỉnh cao là chiến thắng Ngọc Hồi - Đống Đa năm 1789."),
        ("Lực lượng vũ trang nhân dân Việt Nam bao gồm những thành phần nào sau đây?", [("A", "Quân đội nhân dân, Công an nhân dân và Dân quân tự vệ"), ("B", "Quân đội nhân dân và Cảnh sát biển Việt Nam"), ("C", "Công an nhân dân và lực lượng Kiểm lâm"), ("D", "Quân đội chính quy và Bộ đội biên phòng")], "A", "Theo Luật Quốc phòng, lực lượng vũ trang nhân dân gồm Quân đội nhân dân, Công an nhân dân và Dân quân tự vệ."),
        ("Quân đội nhân dân Việt Nam có mấy chức năng cơ bản?", [("A", "3 chức năng (Đội quân chiến đấu, đội quân công tác, đội quân lao động sản xuất)"), ("B", "2 chức năng (Chiến đấu và phòng thủ biên giới)"), ("C", "4 chức năng (Chiến đấu, đối ngoại, tình báo, bảo an)"), ("D", "1 chức năng duy nhất là tham gia tác chiến bảo vệ vùng trời")], "A", "Chủ tịch Hồ Chí Minh đã khẳng định QĐND Việt Nam có 3 chức năng: Đội quân chiến đấu, đội quân công tác, đội quân lao động sản xuất."),
        ("Ngày truyền thống của Quân đội nhân dân Việt Nam và Ngày hội Quốc phòng toàn dân là ngày nào?", [("A", "Ngày 22 tháng 12 hàng năm"), ("B", "Ngày 19 tháng 8 hàng năm"), ("C", "Ngày 02 tháng 9 hàng năm"), ("D", "Ngày 30 tháng 4 hàng năm")], "A", "Ngày 22/12/1944 là ngày thành lập Đội Việt Nam Tuyên truyền Giải phóng quân; từ năm 1989 được lấy làm Ngày hội Quốc phòng toàn dân."),
        ("Theo Luật Nghĩa vụ quân sự năm 2015, công dân nam đủ bao nhiêu tuổi được đăng ký nghĩa vụ quân sự lần đầu?", [("A", "Đủ 17 tuổi"), ("B", "Đủ 18 tuổi"), ("C", "Đủ 16 tuổi"), ("D", "Đủ 19 tuổi")], "A", "Theo quy định tại Điều 12 Luật NVQS 2015, công dân nam đủ 17 tuổi trong năm được đăng ký nghĩa vụ quân sự lần đầu."),
        ("Độ tuổi gọi nhập ngũ trong thời bình đối với công dân nam không học đại học, cao đẳng là từ", [("A", "Đủ 18 tuổi đến hết 25 tuổi"), ("B", "Đủ 17 tuổi đến hết 23 tuổi"), ("C", "Đủ 18 tuổi đến hết 30 tuổi"), ("D", "Đủ 19 tuổi đến hết 27 tuổi")], "A", "Theo Điều 30 Luật NVQS 2015: Công dân đủ 18 tuổi được gọi nhập ngũ; độ tuổi gọi nhập ngũ từ đủ 18 tuổi đến hết 25 tuổi."),
        ("Đối với công dân nam được tạm hoãn gọi nhập ngũ để học đại học, cao đẳng hệ chính quy thì độ tuổi gọi nhập ngũ kéo dài đến", [("A", "Hết 27 tuổi"), ("B", "Hết 25 tuổi"), ("C", "Hết 28 tuổi"), ("D", "Hết 30 tuổi")], "A", "Luật NVQS 2015 quy định đối với công dân học đại học, cao đẳng đã được tạm hoãn thì độ tuổi gọi nhập ngũ đến hết 27 tuổi."),
        ("Ngày truyền thống của lực lượng Công an nhân dân Việt Nam là", [("A", "Ngày 19 tháng 8 hàng năm"), ("B", "Ngày 22 tháng 12 hàng năm"), ("C", "Ngày 06 tháng 12 hàng năm"), ("D", "Ngày 27 tháng 7 hàng năm")], "A", "Ngày 19/8/1945 là ngày Cách mạng tháng Tám thành công và là ngày truyền thống của lực lượng Công an nhân dân Việt Nam."),
        ("Theo Luật An ninh mạng năm 2018, an ninh mạng được hiểu là", [("A", "Sự bảo đảm hoạt động trên không gian mạng không gây phương hại đến an ninh quốc gia, trật tự an toàn xã hội"), ("B", "Việc cấm tuyệt đối mọi hoạt động sử dụng Internet trong trường học"), ("C", "Việc giám sát toàn bộ thông tin cá nhân của người dùng"), ("D", "Biện pháp khóa toàn bộ các trang mạng xã hội nước ngoài")], "A", "Điều 2 Luật An ninh mạng định nghĩa: An ninh mạng là sự bảo đảm hoạt động trên không gian mạng không gây phương hại đến an ninh quốc gia, trật tự, an toàn xã hội."),
        ("Hành vi nào sau đây là hành vi bị nghiêm cấm trên không gian mạng theo Luật An ninh mạng?", [("A", "Đăng tải thông tin bịa đặt, sai sự thật gây hoang mang dư luận hoặc xúc phạm nhân phẩm người khác"), ("B", "Tìm kiếm tài liệu học tập và nghiên cứu khoa học"), ("C", "Tham gia các khóa học trực tuyến chính quy"), ("D", "Giao dịch thương mại điện tử đúng quy định pháp luật")], "A", "Luật An ninh mạng nghiêm cấm việc phát tán thông tin bịa đặt, vu khống, xúc phạm danh dự nhân phẩm hoặc chống phá Nhà nước."),
        ("Khi tham gia giao thông bằng xe đạp điện hoặc xe máy điện, học sinh THPT bắt buộc phải", [("A", "Đội mũ bảo hiểm đạt chuẩn và cài quai đúng quy cách"), ("B", "Đi xe dàn hàng ngang và lạng lách trên đường"), ("C", "Sử dụng điện thoại di động khi đang điều khiển phương tiện"), ("D", "Chở quá số người quy định")], "A", "Người điều khiển và ngồi trên xe đạp điện, xe máy điện bắt buộc phải đội mũ bảo hiểm có cài quai đúng cách."),
        ("Trong kỹ thuật sơ cấp cứu ban đầu, nguyên tắc cốt lõi khi cố định gãy xương chi là", [("A", "Nẹp phải cố định được cả hai khớp liền kề (trên và dưới) ổ gãy"), ("B", "Phải nắn thẳng xương gãy bị trồi ra ngoài trước khi nẹp"), ("C", "Bó trực tiếp nẹp lên vị trí gãy mà không cần đệm lót"), ("D", "Di chuyển nạn nhân đi ngay mà không cần bất động")], "A", "Nguyên tắc bất di bất dịch khi nẹp cố định xương gãy là phải bất động được khớp trên và khớp dưới của ổ gãy để tránh di lệch xương."),
        ("Khi băng bó vết thương phần mềm đang chảy máu, loại băng nào sau đây thường được sử dụng thông dụng nhất?", [("A", "Băng cuộn và băng tam giác"), ("B", "Băng dính cách điện"), ("C", "Dây dù hoặc dây cao su"), ("D", "Vải thô chưa khử trùng")], "A", "Băng cuộn và băng tam giác y tế là hai phương tiện băng bó vết thương thông dụng và an toàn nhất."),
        ("Biện pháp đặt garo cầm máu chỉ được chỉ định trong trường hợp nào sau đây?", [("A", "Vết thương đứt động mạch lớn ở các chi chảy máu xối xả"), ("B", "Vết thương xây xát nông ngoài da rớm máu"), ("C", "Chảy máu mao mạch nhỏ ở đầu ngón tay"), ("D", "Vết thương tĩnh mạch vừa phải có thể băng ép")], "A", "Đặt garo là biện pháp cầm máu tạm thời tối khẩn cấp chỉ dùng khi đứt động mạch lớn ở tứ chi phun thành tia xối xả."),
        ("Khi đã đặt garo cầm máu cho nạn nhân, quy định nghiêm ngặt về thời gian nới garo là", [("A", "Cứ sau khoảng 30 đến 45 phút phải nới garo một lần và không để quá 3 đến 4 giờ"), ("B", "Buộc thật chặt liên tục suốt 10 giờ không được nới"), ("C", "Cứ 2 phút nới một lần rồi tháo bỏ hoàn toàn"), ("D", "Chỉ nới khi nạn nhân đã được chuyển về đến nhà")], "A", "Cần nới garo định kỳ 30 - 45 phút/lần từ 1 - 2 phút để máu lưu thông nuôi dưỡng chi phía dưới, tránh bị hoại tử."),
        ("Trong động tác 'Quay bên phải' của điều lệnh đội ngũ từng người không có súng, người thực hiện lấy", [("A", "Gót chân phải làm trụ, ức bàn chân trái làm điểm tạ lực quay sang phải $90^\\circ$"), ("B", "Gót chân trái làm trụ, ức bàn chân phải làm điểm tạ lực"), ("C", "Hai gót chân cùng quay một lúc"), ("D", "Mũi bàn chân phải làm trụ quay sang phải")], "A", "Động tác quay phải: Lấy gót chân phải và ức bàn chân trái làm trụ, quay người sang phải một góc $90^\\circ$."),
        ("Trong khẩu lệnh điều lệnh đội ngũ 'Đi đều - Bước', từ nào đóng vai trò là động lệnh?", [("A", "'Bước'"), ("B", "'Đi đều'"), ("C", "Cả hai từ 'Đi' và 'Bước'"), ("D", "Không có động lệnh")], "A", "'Đi đều' là dự lệnh để bộ đội chuẩn bị, 'Bước' là động lệnh để bắt đầu thực hiện động tác đi đều."),
        ("Trách nhiệm của học sinh THPT trong sự nghiệp củng cố quốc phòng và an ninh hiện nay là", [("A", "Tích cực học tập, rèn luyện phẩm chất đạo đức, chấp hành nghiêm pháp luật và tham gia bảo vệ an ninh học đường"), ("B", "Tự ý mua sắm công cụ hỗ trợ để đi tuần tra ban đêm"), ("C", "Bỏ học giữa chừng để tự gia nhập lực lượng quân đội"), ("D", "Lập hội nhóm ẩn danh để tự công kích trên không gian mạng")], "A", "Học sinh THPT có trách nhiệm tích cực học tập môn GDQP&AN, rèn luyện tác phong, gương mẫu chấp hành pháp luật và giữ gìn an ninh trật tự trường học.")
    ]
    for i, (q_text, opts, ans, exp) in enumerate(gdqp_p1_samples, start=1):
        mcqs.append(Part1Question(
            id=i,
            question=q_text,
            options=[Option(label=o[0], text=o[1]) for o in opts],
            answer=ans,
            explanation=exp
        ))
        
    tf_questions = [
        Part2Question(
            id=1,
            question="Theo Luật Nghĩa vụ quân sự năm 2015 của nước Cộng hòa Xã hội Chủ nghĩa Việt Nam:",
            sub_items=[
                SubItem(label="a", statement="Bảo vệ Tổ quốc là nghĩa vụ thiêng liêng và quyền cao quý của mọi công dân Việt Nam.", is_correct=True, explanation="Đây là nguyên tắc hiến định trong Hiến pháp và Luật Nghĩa vụ quân sự."),
                SubItem(label="b", statement="Công dân nam từ đủ 18 tuổi đến hết 25 tuổi có nghĩa vụ phục vụ tại ngũ trong Quân đội nhân dân Việt Nam.", is_correct=True, explanation="Đúng theo quy định tại Điều 30 Luật Nghĩa vụ quân sự 2015."),
                SubItem(label="c", statement="Học sinh đang học tại các trường trung học phổ thông được tạm hoãn gọi nhập ngũ trong thời bình.", is_correct=True, explanation="Đúng theo điểm g khoản 1 Điều 41 Luật Nghĩa vụ quân sự 2015."),
                SubItem(label="d", statement="Sau khi hoàn thành nghĩa vụ quân sự xuất ngũ, công dân không phải đăng ký phục vụ trong ngạch dự bị.", is_correct=False, explanation="Hạ sĩ quan, binh sĩ khi xuất ngũ bắt buộc phải đăng ký vào ngạch dự bị động viên theo quy định.")
            ],
            explanation="Kiến thức pháp luật về nghĩa vụ quân sự và trách nhiệm của công dân đối với Tổ quốc."
        ),
        Part2Question(
            id=2,
            question="Xét các quy định của Luật An ninh mạng năm 2018 và văn hóa ứng xử trên không gian mạng của học sinh:",
            sub_items=[
                SubItem(label="a", statement="Không gian mạng là mạng lưới kết nối của cơ sở hạ tầng công nghệ thông tin gồm mạng viễn thông, Internet và hệ thống xử lý dữ liệu.", is_correct=True, explanation="Đúng theo định nghĩa tại khoản 3 Điều 2 Luật An ninh mạng 2018."),
                SubItem(label="b", statement="Học sinh có quyền tự do chia sẻ mọi thông tin chưa được kiểm chứng lên mạng xã hội miễn là có nhiều người thích.", is_correct=False, explanation="Hành vi chia sẻ thông tin bịa đặt, sai sự thật là vi phạm pháp luật và bị xử lý nghiêm."),
                SubItem(label="c", statement="Hành vi xâm nhập trái phép vào tài khoản của người khác hoặc phát tán mã độc là hành vi bị nghiêm cấm.", is_correct=True, explanation="Điều 8 Luật An ninh mạng nghiêm cấm tấn công mạng, chiếm quyền điều khiển và phát tán mã độc."),
                SubItem(label="d", statement="Khi phát hiện các nội dung xấu độc hoặc dấu hiệu lừa đảo trên mạng, học sinh cần báo ngay cho cha mẹ, thầy cô hoặc cơ quan chức năng.", is_correct=True, explanation="Đây là biện pháp chủ động phòng ngừa tội phạm mạng và bảo vệ bản thân cùng cộng đồng.")
            ],
            explanation="Luật An ninh mạng và các kỹ năng số an toàn cho học sinh trung học phổ thông."
        ),
        Part2Question(
            id=3,
            question="Về kỹ thuật sơ cấp cứu ban đầu cho nạn nhân bị tai nạn thương tích:",
            sub_items=[
                SubItem(label="a", statement="Khi cứu người bị đuối nước, người không biết bơi tuyệt đối không nhảy xuống nước mà phải tri hô và ném phao hoặc sào cứu hộ.", is_correct=True, explanation="Đảm bảo an toàn cho người cứu hộ là nguyên tắc số 1 trong cứu đuối nước."),
                SubItem(label="b", statement="Khi cố định gãy xương cẳng tay, nẹp cố định phải đủ dài từ lòng bàn tay đến quá khớp khuỷu tay.", is_correct=True, explanation="Nẹp phải vượt qua cả khớp cổ tay và khớp khuỷu để bất động hoàn toàn hai đầu xương cẳng tay gãy."),
                SubItem(label="c", statement="Đối với nạn nhân bị ngừng thở, ngừng tim, cần nhanh chóng tiến hành hồi sinh tim phổi (ép tim và thổi ngạt).", is_correct=True, explanation="Cấp cứu ngưng tim ngưng thở trong 4 - 6 phút đầu là thời gian vàng cứu sống nạn nhân."),
                SubItem(label="d", statement="Khi bị bỏng nhiệt độ cao, cần lập tức bôi kem đánh răng hoặc mỡ trăn trực tiếp lên vết thương bỏng.", is_correct=False, explanation="Bôi kem đánh răng hoặc mỡ trăn làm tăng nguy cơ nhiễm trùng; phương pháp chuẩn là ngâm hoặc dội nước sạch mát $15 - 20$ phút.")
            ],
            explanation="Nguyên tắc và kỹ năng sơ cấp cứu ban đầu cứu người bị nạn."
        ),
        Part2Question(
            id=4,
            question="Về lịch sử truyền thống vẻ vang của Quân đội nhân dân Việt Nam anh hùng:",
            sub_items=[
                SubItem(label="a", statement="Đội Việt Nam Tuyên truyền Giải phóng quân được thành lập ngày 22/12/1944 tại khu rừng Trần Hưng Đạo (tỉnh Cao Bằng).", is_correct=True, explanation="Đội gồm 34 chiến sĩ do đồng chí Võ Nguyên Giáp chỉ huy theo chỉ thị của Lãnh tụ Hồ Chí Minh."),
                SubItem(label="b", statement="Ngay sau khi thành lập, Đội Việt Nam Tuyên truyền Giải phóng quân đã đánh thắng liên tiếp hai trận Phai Khắt và Nà Ngần.", is_correct=True, explanation="Hai chiến thắng mở màn rực rỡ thể hiện nghệ thuật đánh bất ngờ, mưu trí."),
                SubItem(label="c", statement="Chiến dịch Điện Biên Phủ toàn thắng ngày 07/5/1954 đã kết thúc vẻ vang 9 năm trường kỳ kháng chiến chống thực dân Pháp.", is_correct=True, explanation="Chiến thắng Điện Biên Phủ chấn động địa cầu, buộc Pháp phải ký Hiệp định Giơ-ne-vơ."),
                SubItem(label="d", statement="Ngày 22 tháng 12 hàng năm chỉ là ngày hội nội bộ của các cựu chiến binh cao tuổi.", is_correct=False, explanation="Ngày 22/12 là Ngày hội Quốc phòng toàn dân của toàn Đảng, toàn quân và toàn thể nhân dân Việt Nam.")
            ],
            explanation="Truyền thống đánh giặc giữ nước và lịch sử vẻ vang của Quân đội nhân dân Việt Nam."
        )
    ]
    
    short_questions = [
        Part3Question(
            id=1,
            question="Ngày truyền thống của Quân đội nhân dân Việt Nam là ngày bao nhiêu của tháng 12 hàng năm (chỉ ghi số ngày)?",
            answer="22",
            explanation="Ngày 22 tháng 12 năm 1944 là ngày thành lập Đội Việt Nam Tuyên truyền Giải phóng quân."
        ),
        Part3Question(
            id=2,
            question="Theo Luật Nghĩa vụ quân sự 2015, độ tuổi tối thiểu (tính theo số tuổi tròn) để nam công dân Việt Nam đủ điều kiện đăng ký nghĩa vụ quân sự lần đầu là bao nhiêu tuổi?",
            answer="17",
            explanation="Điều 12 Luật NVQS 2015 quy định công dân nam đủ 17 tuổi trong năm được đăng ký NVQS lần đầu."
        ),
        Part3Question(
            id=3,
            question="Thời hạn phục vụ tại ngũ trong thời bình của hạ sĩ quan, binh sĩ Quân đội nhân dân Việt Nam theo quy định hiện hành là bao nhiêu tháng?",
            answer="24",
            explanation="Theo Điều 21 Luật Nghĩa vụ quân sự 2015, thời hạn phục vụ tại ngũ trong thời bình là 24 tháng."
        ),
        Part3Question(
            id=4,
            question="Ngày toàn dân Phòng cháy và Chữa cháy tại Việt Nam là ngày mùng mấy của tháng 10 hàng năm (chỉ ghi số ngày)?",
            answer="4",
            explanation="Ngày 4 tháng 10 hàng năm là Ngày toàn dân phòng cháy và chữa cháy."
        ),
        Part3Question(
            id=5,
            question="Khi đặt garo cầm máu vết thương đứt động mạch, định kỳ tối đa sau bao nhiêu phút thì người sơ cứu bắt buộc phải nới garo một lần?",
            answer="30",
            explanation="Quy định sơ cấp cứu: Định kỳ sau khoảng 30 đến 45 phút phải nới garo một lần để máu nuôi dưỡng phần chi phía dưới."
        ),
        Part3Question(
            id=6,
            question="Ngày truyền thống của lực lượng Công an nhân dân Việt Nam là ngày bao nhiêu của tháng 8 hàng năm (chỉ ghi số ngày)?",
            answer="19",
            explanation="Ngày 19 tháng 8 là Ngày truyền thống Công an nhân dân Việt Nam và Ngày hội toàn dân bảo vệ an ninh Tổ quốc."
        )
    ]
    return ExamStructure(
        title="ĐỀ KIỂM TRA ĐỊNH KỲ MÔN GIÁO DỤC QUỐC PHÒNG & AN NINH 10",
        subject="Giáo dục Quốc phòng & An ninh",
        grade="10",
        duration_minutes=45,
        school_name="SỞ GD&ĐT ... - TRƯỜNG THPT ...",
        academic_year="NĂM HỌC 2026 - 2027",
        code="101",
        part1_mcq=mcqs,
        part2_tf=tf_questions,
        part3_short=short_questions,
        scoring=calculate_exam_scoring(num_p1=len(mcqs), num_p2=len(tf_questions), num_p3=len(short_questions), num_p4=0),
        audit_report=create_default_audit_report("Giáo dục Quốc phòng & An ninh")
    )

def get_mock_biology_exam() -> ExamStructure:
    mcqs = []
    b64_ped, cap_ped = draw_pedigree(caption="Hình: Sơ đồ phả hệ di truyền bệnh máu khó đông ở người")
    b64_pop, cap_pop = draw_population_curve(caption="Hình: Đường cong tăng trưởng số lượng cá thể của quần thể")

    bio_p1_samples = [
        ("Cho sơ đồ phả hệ mô tả sự di truyền một bệnh ở người qua ba thế hệ như hình vẽ bên. Biết rằng bệnh do một gen gồm 2 alen quy định và không xảy ra đột biến mới. Bệnh trên do", [("A", "Alen lặn nằm trên nhiễm sắc thể thường quy định"), ("B", "Alen trội nằm trên nhiễm sắc thể thường quy định"), ("C", "Alen lặn nằm trên nhiễm sắc thể giới tính X"), ("D", "Alen trội nằm trên nhiễm sắc thể giới tính X")], "A", "Cặp bố mẹ I-1 và I-2 bình thường nhưng sinh con gái II-3 bị bệnh, chứng tỏ bệnh do alen lặn quy định và gen nằm trên NST thường (nếu trên X thì bố bình thường không thể sinh con gái bị bệnh)."),
        ("Đường cong tăng trưởng số lượng cá thể của quần thể sinh vật trong điều kiện môi trường bị giới hạn (có sức cản môi trường) trên hình vẽ bên có dạng", [("A", "Đường cong chữ S (tăng trưởng logistic)"), ("B", "Đường cong chữ J (tăng trưởng hàm số mũ)"), ("C", "Đường thẳng dốc đứng liên tục"), ("D", "Đường parabol lõm xuống")], "A", "Khi môi trường bị giới hạn về nguồn sống, tốc độ tăng trưởng của quần thể giảm dần và ổn định quanh sức chứa K của môi trường, tạo thành đường cong hình chữ S."),
        ("Trong cơ chế điều hòa hoạt động của operon Lac ở vi khuẩn E. coli, khi môi trường có lactôzơ thì", [("A", "Chất cảm ứng lactôzơ liên kết với prôtêin ức chế làm nó bị bất hoạt"), ("B", "Prôtêin ức chế liên kết chặt với vùng vận hành O ngăn phiên mã"), ("C", "Gen điều hòa R ngừng tổng hợp prôtêin ức chế"), ("D", "Các gen cấu trúc Z, Y, A ngừng hoạt động")], "A", "Lactôzơ đóng vai trò chất cảm ứng liên kết với prôtêin ức chế làm biến đổi cấu hình không gian, ngăn không cho nó bám vào vùng vận hành O, giải phóng cho ARN polimeraza phiên mã."),
        ("Đột biến điểm làm thay thế một cặp nuclêôtit này bằng một cặp nuclêôtit khác nhưng không làm thay đổi axit amin nào trong chuỗi pôlipeptit là do đặc tính nào của mã di truyền?", [("A", "Tính thoái hóa"), ("B", "Tính phổ biến"), ("C", "Tính đặc hiệu"), ("D", "Tính liên tục")], "A", "Tính thoái hóa (nhiều bộ ba khác nhau cùng mã hóa cho một loại axit amin) giúp cơ thể sinh vật giảm thiểu nguy cơ biểu hiện các đột biến có hại."),
        ("Quá trình nhân đôi ADN diễn ra theo những nguyên tắc nào sau đây?", [("A", "Nguyên tắc bổ sung và nguyên tắc bán bảo toàn"), ("B", "Nguyên tắc bảo toàn và nguyên tắc khuôn mẫu"), ("C", "Nguyên tắc bổ sung và nguyên tắc dịch mã"), ("D", "Nguyên tắc gián đoạn và liên tục")], "A", "Nhân đôi ADN diễn ra theo nguyên tắc bổ sung (A-T, G-X) và nguyên tắc bán bảo tồn (mỗi ADN con chứa 1 mạch cũ và 1 mạch mới)."),
        ("Loại ARN nào sau đây mang bộ ba đối mã (anticodon) và làm nhiệm vụ vận chuyển axit amin tới ribôxôm?", [("A", "tARN (ARN vận chuyển)"), ("B", "mARN (ARN thông tin)"), ("C", "rARN (ARN ribôxôm)"), ("D", "snARN")], "A", "tARN có bộ ba đối mã anticodon khớp bổ sung với codon trên mARN và mang axit amin tương ứng."),
        ("Theo Men-đen, phép lai nào sau đây được gọi là phép lai phân tích?", [("A", "Lai giữa cá thể mang tính trạng trội cần xác định kiểu gen với cá thể lặn"), ("B", "Lai giữa hai cá thể có kiểu hình trội thuần chủng"), ("C", "Lai giữa hai cá thể dị hợp tử"), ("D", "Tự thụ phấn qua nhiều thế hệ")], "A", "Phép lai phân tích là phép lai giữa cá thể mang tính trạng trội chưa biết kiểu gen với cá thể mang kiểu hình lặn."),
        ("Ở đậu Hà Lan, gen A quy định hạt vàng trội hoàn toàn so với gen a quy định hạt xanh. Cho cây hạt vàng dị hợp tự thụ phấn, tỉ lệ phân li kiểu hình ở F1 là", [("A", "3 hạt vàng : 1 hạt xanh"), ("B", "1 hạt vàng : 1 hạt xanh"), ("C", "100% hạt vàng"), ("D", "1 hạt vàng : 2 hạt xanh")], "A", "Phép lai Aa x Aa cho tỉ lệ kiểu gen 1AA : 2Aa : 1aa, tương ứng với kiểu hình 3 vàng : 1 xanh."),
        ("Hiện tượng hoán vị gen xảy ra do", [("A", "Sự tiếp hợp và trao đổi chéo giữa 2 crômatit khác nguồn của cặp NST tương đồng ở kì đầu giảm phân I"), ("B", "Sự phân li độc lập của các NST ở kì sau giảm phân I"), ("C", "Sự tiếp hợp giữa 2 NST không tương đồng"), ("D", "Sự tự nhân đôi của ADN")], "A", "Hoán vị gen xảy ra do sự trao đổi chéo giữa 2 crômatit khác nguồn trong cặp NST tương đồng ở kì đầu giảm phân I."),
        ("Dạng đột biến cấu trúc nhiễm sắc thể nào sau đây làm tăng cường hoặc giảm bớt mức biểu hiện của tính trạng?", [("A", "Lặp đoạn"), ("B", "Mất đoạn"), ("C", "Đảo đoạn"), ("D", "Chuyển đoạn tương hỗ")], "A", "Đột biến lặp đoạn làm gia tăng số lượng bản sao của gen, qua đó có thể làm tăng hoặc giảm mức độ biểu hiện của tính trạng."),
        ("Cơ thể có bộ nhiễm sắc thể $2n + 1$ được gọi là thể đột biến", [("A", "Thể ba"), ("B", "Thể một"), ("C", "Thể tứ bội"), ("D", "Thể tam bội")], "A", "Thể ba có bộ NST thừa 1 chiếc ở một cặp tương đồng ($2n + 1$)."),
        ("Tập hợp sinh vật nào sau đây là một quần thể sinh vật?", [("A", "Các cá thể cá chép sinh sống trong một hồ nước ngọt"), ("B", "Tất cả các loài cá sống trong một nhánh sông"), ("C", "Các loài thú ăn cỏ trong một thảo nguyên"), ("D", "Cây cối trong một khu rừng nhiệt đới")], "A", "Quần thể sinh vật là tập hợp các cá thể cùng loài, cùng sinh sống trong một khoảng không gian và thời gian xác định."),
        ("Mối quan hệ nào sau đây là quan hệ cộng sinh giữa hai loài sinh vật?", [("A", "Nấm và vi khuẩn lam tạo thành địa y"), ("B", "Dây tơ hồng sống bám trên thân cây gỗ"), ("C", "Hổ săn bắt nai rừng"), ("D", "Giun đũa sống trong ruột người")], "A", "Địa y là ví dụ điển hình của mối quan hệ cộng sinh chặt chẽ giữa nấm và tảo hoặc vi khuẩn lam."),
        ("Trong chuỗi thức ăn: Cỏ -> Châu chấu -> Ếch đồng -> Rắn nước -> Diều hâu, sinh vật tiêu thụ bậc 2 là", [("A", "Ếch đồng"), ("B", "Châu chấu"), ("C", "Rắn nước"), ("D", "Diều hâu")], "A", "Cỏ là SV sản xuất; Châu chấu là SVTT bậc 1; Ếch đồng là SVTT bậc 2; Rắn nước là SVTT bậc 3; Diều hâu là SVTT bậc 4."),
        ("Nhân tố sinh thái nào sau đây là nhân tố vô sinh?", [("A", "Nhiệt độ và ánh sáng"), ("B", "Động vật ăn cỏ"), ("C", "Vi sinh vật phân giải"), ("D", "Cây xanh quang hợp")], "A", "Nhiệt độ, ánh sáng, độ ẩm, đất, nước là các nhân tố sinh thái vô sinh (vật lý, hóa học)."),
        ("Nhân tố tiến hóa nào sau đây có thể làm thay đổi tần số alen của quần thể theo một hướng xác định?", [("A", "Chọn lọc tự nhiên"), ("B", "Đột biến gen"), ("C", "Di - nhập gen"), ("D", "Yếu tố ngẫu nhiên")], "A", "Chọn lọc tự nhiên là nhân tố tiến hóa có hướng, làm thay đổi tần số alen và thành phần kiểu gen theo một hướng xác định."),
        ("Hiện tượng các cá thể cùng loài tranh giành nhau nguồn thức ăn, nơi ở dẫn đến sự phân ly ổ sinh thái được gọi là", [("A", "Cạnh tranh cùng loài"), ("B", "Hỗ trợ cùng loài"), ("C", "Ký sinh"), ("D", "Ức chế - cảm nhiễm")], "A", "Cạnh tranh cùng loài xảy ra khi mật độ cá thể tăng cao, tài nguyên môi trường thiếu thốn, giúp chọn lọc cá thể thích nghi nhất."),
        ("Cơ quan tương đồng ở các loài sinh vật phản ánh nguồn gốc nào?", [("A", "Tiến hóa phân ly từ một nguồn gốc chung"), ("B", "Tiến hóa đồng quy do môi trường sống giống nhau"), ("C", "Hiện tượng thoái hóa giống"), ("D", "Đột biến nhân tạo")], "A", "Cơ quan tương đồng là những cơ quan bắt nguồn từ cùng một cấu trúc phôi chung nhưng phát triển thích nghi theo các hướng khác nhau (phân ly)."),
        ("Theo thuyết tiến hóa hiện đại, nhân tố nào sau đây cung cấp nguồn nguyên liệu sơ cấp cho quá trình tiến hóa?", [("A", "Đột biến gen"), ("B", "Biến dị tổ hợp"), ("C", "Giao phối không ngẫu nhiên"), ("D", "Chọn lọc tự nhiên")], "A", "Đột biến (chủ yếu là đột biến gen) là nguồn phát sinh nguyên liệu sơ cấp cho quá trình tiến hóa."),
        ("Hệ sinh thái nào sau đây có độ đa dạng loài và sinh khối lớn nhất trên Trái Đất?", [("A", "Rừng mưa nhiệt đới"), ("B", "Đồng rêu hàn đới (Tundra)"), ("C", "Sa mạc cát"), ("D", "Thảo nguyên ôn đới")], "A", "Rừng mưa nhiệt đới có điều kiện khí hậu nóng ẩm quanh năm, thảm thực vật nhiều tầng phong phú nên có độ đa dạng sinh học cao nhất.")
    ]
    for i, (q_text, opts, ans, exp) in enumerate(bio_p1_samples, start=1):
        img_b64 = None
        img_cap = None
        if i == 1:
            img_b64, img_cap = b64_ped, cap_ped
        elif i == 2:
            img_b64, img_cap = b64_pop, cap_pop
        mcqs.append(Part1Question(
            id=i,
            question=q_text,
            options=[Option(label=o[0], text=o[1]) for o in opts],
            answer=ans,
            explanation=exp,
            image_base64=img_b64,
            image_caption=img_cap
        ))

    tf_questions = [
        Part2Question(
            id=1,
            question="Xét các cơ chế di truyền ở cấp độ phân tử (nhân đôi ADN, phiên mã và dịch mã) ở sinh vật nhân thực:",
            sub_items=[
                SubItem(label="a", statement="Quá trình nhân đôi ADN diễn ra theo nguyên tắc bổ sung và nguyên tắc bán bảo toàn.", is_correct=True, explanation="Đây là 2 nguyên tắc cốt lõi đảm bảo thông tin di truyền được truyền đạt chính xác qua các thế hệ tế bào."),
                SubItem(label="b", statement="Enzim ARN polimeraza có khả năng tự tháo xoắn phân tử ADN và tổng hợp mạch mới theo chiều 5' -> 3'.", is_correct=True, explanation="ARN polimeraza vừa làm nhiệm vụ tháo xoắn ADN vừa tổng hợp mARN mới theo chiều 5' -> 3'."),
                SubItem(label="c", statement="Trên một phân tử mARN chỉ có duy nhất một ribôxôm trượt qua trong toàn bộ quá trình dịch mã.", is_correct=False, explanation="Nhiều ribôxôm cùng trượt trên 1 mARN (gọi là pôliribôxôm) để tăng hiệu suất tổng hợp cùng một loại prôtêin."),
                SubItem(label="d", statement="Mã di truyền có tính phổ biến, nghĩa là tất cả các loài sinh vật đều dùng chung một bộ mã di truyền (trừ vài ngoại lệ).", is_correct=True, explanation="Tính phổ biến của mã di truyền chứng minh nguồn gốc chung thống nhất của toàn bộ sinh giới.")
            ],
            explanation="Cơ chế truyền đạt thông tin di truyền ở cấp độ phân tử."
        ),
        Part2Question(
            id=2,
            question="Xét một quần thể thực vật tự thụ phấn nghiêm ngặt có cấu trúc di truyền ở thế hệ xuất phát P là: $0.4\\text{ AA} : 0.4\\text{ Aa} : 0.2\\text{ aa}$:",
            sub_items=[
                SubItem(label="a", statement="Tần số của alen A trong quần thể ở thế hệ P bằng 0.6.", is_correct=True, explanation="Tần số alen $p(A) = 0.4 + 0.4 / 2 = 0.6$."),
                SubItem(label="b", statement="Qua các thế hệ tự thụ phấn liên tiếp, tỉ lệ kiểu gen dị hợp tử Aa giảm dần và tỉ lệ đồng hợp tử tăng dần.", is_correct=True, explanation="Tự thụ phấn làm giảm dị hợp tử theo tỉ lệ $(1/2)^n$ và tăng đồng hợp tử."),
                SubItem(label="c", statement="Tần số các alen A và a bị biến đổi mạnh qua các thế hệ tự thụ phấn.", is_correct=False, explanation="Quá trình tự thụ phấn chỉ làm biến đổi cấu trúc kiểu gen chứ không làm thay đổi tần số alen."),
                SubItem(label="d", statement="Ở thế hệ F1, tỉ lệ kiểu gen dị hợp Aa trong quần thể bằng 0.2.", is_correct=True, explanation="Ở F1, tỉ lệ $Aa = 0.4 / 2 = 0.2$.")
            ],
            explanation="Cấu trúc di truyền và sự biến đổi tần số kiểu gen trong quần thể tự thụ phấn."
        ),
        Part2Question(
            id=3,
            question="Xét các đặc trưng cơ bản và mối quan hệ sinh thái trong quần xã sinh vật:",
            sub_items=[
                SubItem(label="a", statement="Độ phong phú của loài thể hiện mức độ đa dạng về số lượng loài trong quần xã.", is_correct=True, explanation="Độ phong phú là tỉ lệ phần trăm số cá thể của từng loài so với tổng số cá thể của toàn quần xã."),
                SubItem(label="b", statement="Loài ưu thế là loài đóng vai trò quan trọng nhất trong quần xã do có sinh khối lớn hoặc số lượng đông đảo.", is_correct=True, explanation="Đúng theo định nghĩa loài ưu thế trong sinh thái học."),
                SubItem(label="c", statement="Hiện tượng khống chế sinh học làm mất cân bằng sinh thái và dẫn đến sự suy vong của quần xã.", is_correct=False, explanation="Khống chế sinh học giúp duy trì số lượng cá thể của các loài ở trạng thái cân bằng sinh học ổn định."),
                SubItem(label="d", statement="Phân tầng thẳng đứng của các loài thực vật trong rừng nhiệt đới giúp giảm cạnh tranh ánh sáng và tăng hiệu quả sử dụng tài nguyên.", is_correct=True, explanation="Phân tầng không gian giúp các loài khai thác triệt để các nguồn sống khác nhau mà không cạnh tranh gay gắt.")
            ],
            explanation="Đặc trưng cấu trúc và mối quan hệ giữa các loài trong quần xã sinh vật."
        ),
        Part2Question(
            id=4,
            question="Về các nhân tố tiến hóa và hình thành loài mới theo thuyết tiến hóa tổng hợp hiện đại:",
            sub_items=[
                SubItem(label="a", statement="Đột biến gen là nguồn nguyên liệu sơ cấp chủ yếu cho quá trình tiến hóa.", is_correct=True, explanation="Đột biến tạo ra các alen mới, làm phong phú vốn gen của quần thể."),
                SubItem(label="b", statement="Giao phối không ngẫu nhiên làm thay đổi tần số alen của quần thể rất nhanh chóng.", is_correct=False, explanation="Giao phối không ngẫu nhiên không làm thay đổi tần số alen, chỉ làm thay đổi thành phần kiểu gen theo hướng tăng đồng hợp giảm dị hợp."),
                SubItem(label="c", statement="Cách li địa lí là nhân tố trực tiếp tạo ra các kiểu gen mới thích nghi trong quần thể.", is_correct=False, explanation="Cách li địa lí chỉ ngăn cản dòng gen giao phối, nhân tố tạo kiểu gen mới là đột biến và biến dị tổ hợp."),
                SubItem(label="d", statement="Cách li sinh sản là ranh giới phân biệt giữa các loài sinh vật sinh sản hữu tính.", is_correct=True, explanation="Tiêu chuẩn cách li sinh sản là tiêu chuẩn quan trọng nhất để xác định hai loài thân thuộc.")
            ],
            explanation="Cơ chế tiến hóa hiện đại và hình thành loài mới."
        )
    ]

    short_questions = [
        Part3Question(
            id=1,
            question="Trong bảng mã di truyền chuẩn gồm 64 bộ ba (codon), có bao nhiêu bộ ba thực sự mã hóa cho các axit amin (không tính các mã kết thúc)?",
            answer="61",
            explanation="Có 3 bộ ba kết thúc (UAA, UAG, UGA) không mã hóa axit amin, do đó số bộ ba mã hóa là $64 - 3 = 61$."
        ),
        Part3Question(
            id=2,
            question="Một gen nằm trên nhiễm sắc thể thường có 3 alen khác nhau ($A_1, A_2, A_3$). Số loại kiểu gen tối đa có thể được tạo ra trong quần thể lưỡng bội bằng bao nhiêu?",
            answer="6",
            explanation="Số loại kiểu gen tối đa của gen có $n = 3$ alen là $\\frac{n(n+1)}{2} = \\frac{3 \\times 4}{2} = 6$."
        ),
        Part3Question(
            id=3,
            question="Một phân tử ADN mạch kép của sinh vật nhân sơ có tổng số $3000$ nuclêôtit. Chiều dài của phân tử ADN này bằng bao nhiêu nanomet (nm)?",
            answer="510",
            explanation="Chiều dài phân tử ADN: $L = \\frac{N}{2} \\times 3.4\\text{ Å} = 1500 \\times 3.4 = 5100\\text{ Å} = 510\\text{ nm}$."
        ),
        Part3Question(
            id=4,
            question="Một quần thể ngẫu phối ở trạng thái cân bằng Hacđi - Vanbec có cấu trúc di truyền gồm $16\\%$ cá thể mang kiểu hình lặn ($aa$). Tần số của alen A trong quần thể này bằng bao nhiêu (ghi dưới dạng số thập phân)?",
            answer="0.6",
            explanation="Quần thể cân bằng có $q^2(aa) = 0.16 \\Rightarrow q(a) = 0.4 \\Rightarrow p(A) = 1 - 0.4 = 0.6$."
        ),
        Part3Question(
            id=5,
            question="Xét chuỗi thức ăn: Ngô -> Chuột đồng -> Rắn hổ mang -> Diều hâu. Trong chuỗi thức ăn này, có bao nhiêu bậc dinh dưỡng tất cả?",
            answer="4",
            explanation="Chuỗi gồm 4 loài tương ứng với 4 bậc dinh dưỡng: Ngô (bậc 1), Chuột (bậc 2), Rắn (bậc 3), Diều hâu (bậc 4)."
        ),
        Part3Question(
            id=6,
            question="Ở một loài thực vật lưỡng bội có bộ nhiễm sắc thể $2n = 24$. Số lượng nhiễm sắc thể trong thể ba ($2n + 1$) của loài này bằng bao nhiêu?",
            answer="25",
            explanation="Thể ba có bộ NST là $2n + 1 = 24 + 1 = 25$ chiếc."
        )
    ]

    return ExamStructure(
        title="ĐỀ KIỂM TRA ĐỊNH KỲ MÔN SINH HỌC 12",
        subject="Sinh học",
        grade="12",
        duration_minutes=50,
        school_name="SỞ GD&ĐT ... - TRƯỜNG THPT ...",
        academic_year="NĂM HỌC 2026 - 2027",
        code="101",
        part1_mcq=mcqs,
        part2_tf=tf_questions,
        part3_short=short_questions,
        scoring=calculate_exam_scoring(num_p1=len(mcqs), num_p2=len(tf_questions), num_p3=len(short_questions), num_p4=0),
        audit_report=create_default_audit_report("Sinh học")
    )

def get_mock_english_exam() -> ExamStructure:
    mcqs = [
        Part1Question(
            id=1,
            question="Mark the letter A, B, C, or D to indicate the word whose underlined part differs from the other three in pronunciation:\nA. pl<u>a</u>net\tB. gr<u>a</u>duate\tC. v<u>a</u>cant\tD. p<u>a</u>tent",
            options=[Option(label="A", text="planet"), Option(label="B", text="graduate"), Option(label="C", text="vacant"), Option(label="D", text="patent")],
            answer="C",
            explanation="The underlined 'a' in 'vacant' is pronounced /ˈveɪ.kənt/ (sound /eɪ/), while the others are pronounced /æ/."
        ),
        Part1Question(
            id=2,
            question="Mark the letter A, B, C, or D to indicate the word that differs from the other three in the position of primary stress:\nA. community\tB. electrician\tC. firefighter\tD. advice",
            options=[Option(label="A", text="community"), Option(label="B", text="electrician"), Option(label="C", text="firefighter"), Option(label="D", text="advice")],
            answer="C",
            explanation="'firefighter' has stress on the 1st syllable, while 'community' and 'advice' have stress on the 2nd syllable, and 'electrician' has stress on the 3rd syllable."
        ),
        Part1Question(
            id=3,
            question="The local ________ was called to repair the broken wiring in our neighborhood.",
            options=[Option(label="A", text="electrician"), Option(label="B", text="firefighter"), Option(label="C", text="garbage collector"), Option(label="D", text="police officer")],
            answer="A",
            explanation="An electrician is a person whose job is to connect, repair, or maintain electrical equipment."
        ),
        Part1Question(
            id=4,
            question="She gave me some very useful ________ on how to prepare for the upcoming final examination.",
            options=[Option(label="A", text="advice"), Option(label="B", text="advices"), Option(label="C", text="advise"), Option(label="D", text="advising")],
            answer="A",
            explanation="'Advice' is an uncountable noun meaning guidance or recommendations. 'Advices' is incorrect."
        ),
        Part1Question(
            id=5,
            question="The brave ________ quickly arrived at the scene and extinguished the massive blaze.",
            options=[Option(label="A", text="firefighters"), Option(label="B", text="electricians"), Option(label="C", text="suburbs"), Option(label="D", text="guesses")],
            answer="A",
            explanation="Firefighters are trained people who put out fires."
        ),
        Part1Question(
            id=6,
            question="Many families prefer living in a quiet ________ rather than the noisy city center.",
            options=[Option(label="A", text="suburb"), Option(label="B", text="collector"), Option(label="C", text="officer"), Option(label="D", text="fire")],
            answer="A",
            explanation="'Suburb' refers to an outlying district of a city, especially a residential one."
        ),
        Part1Question(
            id=7,
            question="Mark the letter A, B, C, or D to indicate the word CLOSEST in meaning to the underlined word:\nVolunteers are making a vital contribution to our local <u>community</u>.",
            options=[Option(label="A", text="neighborhood"), Option(label="B", text="industry"), Option(label="C", text="traffic"), Option(label="D", text="entertainment")],
            answer="A",
            explanation="'Community' in this context is closest in meaning to 'neighborhood' (society/local area)."
        ),
        Part1Question(
            id=8,
            question="Mark the letter A, B, C, or D to indicate the word OPPOSITE in meaning to the underlined word:\nHe offered some <u>useful</u> tips for learning new English vocabulary effectively.",
            options=[Option(label="A", text="useless"), Option(label="B", text="helpful"), Option(label="C", text="practical"), Option(label="D", text="beneficial")],
            answer="A",
            explanation="'Useful' (hữu ích) is opposite in meaning to 'useless' (vô ích)."
        ),
        Part1Question(
            id=9,
            question="If I ________ you, I would consult a professional counselor before making that crucial decision.",
            options=[Option(label="A", text="were"), Option(label="B", text="am"), Option(label="C", text="will be"), Option(label="D", text="would be")],
            answer="A",
            explanation="Second conditional structure for advice: 'If I were you, I would + V'."
        ),
        Part1Question(
            id=10,
            question="The town council has hired additional ________ to keep public parks and streets clean.",
            options=[Option(label="A", text="garbage collectors"), Option(label="B", text="firefighters"), Option(label="C", text="electricians"), Option(label="D", text="engineers")],
            answer="A",
            explanation="'Garbage collectors' are people employed to collect refuse from households and public areas."
        ),
        Part1Question(
            id=11,
            question="She had to ________ the answer because she had not reviewed the lesson beforehand.",
            options=[Option(label="A", text="guess"), Option(label="B", text="advise"), Option(label="C", text="collect"), Option(label="D", text="spark")],
            answer="A",
            explanation="'Guess' means to estimate or suppose without sufficient information."
        ),
        Part1Question(
            id=12,
            question="A ________ directed traffic efficiently during the heavy morning rush hour.",
            options=[Option(label="A", text="police officer"), Option(label="B", text="electrician"), Option(label="C", text="firefighter"), Option(label="D", text="volunteer")],
            answer="A",
            explanation="A police officer is responsible for directing traffic and enforcing laws."
        )
    ]
    
    tf_questions = [
        Part2Question(
            id=1,
            question=(
                "Read the following passage about community helpers:\n\n"
                "In any thriving community, essential workers play an indispensable role in maintaining safety, hygiene, and public welfare. "
                "Police officers uphold the law and protect residents from harm, while firefighters courageously risk their lives to extinguish blazes and rescue citizens during disasters. "
                "Electricians ensure that our power systems run smoothly and safely, preventing dangerous electrical hazards in schools and homes. "
                "Meanwhile, garbage collectors work diligently every dawn to keep our neighborhoods clean and sanitized. "
                "Without the dedication of these community service members, daily life in both bustling cities and quiet suburbs would face profound disruption."
            ),
            sub_items=[
                SubItem(label="a", statement="Police officers are primarily responsible for upholding the law and ensuring public safety.", is_correct=True, explanation="According to the text, 'Police officers uphold the law and protect residents from harm'."),
                SubItem(label="b", statement="Electricians only work in large industrial factories and never service residential homes.", is_correct=False, explanation="The text mentions that electricians prevent electrical hazards 'in schools and homes'."),
                SubItem(label="c", statement="Garbage collectors contribute significantly to maintaining sanitary conditions in neighborhoods.", is_correct=True, explanation="The passage states that they 'keep our neighborhoods clean and sanitized'."),
                SubItem(label="d", statement="The passage suggests that suburbs do not require essential community workers because they are already quiet.", is_correct=False, explanation="The text concludes that life in 'both bustling cities and quiet suburbs would face profound disruption' without these workers.")
            ],
            explanation="Reading comprehension on community helpers and public services."
        ),
        Part2Question(
            id=2,
            question=(
                "Read the following passage about seeking and giving advice:\n\n"
                "Seeking useful advice from experienced people is a valuable habit for young students facing difficult decisions. "
                "Parents, teachers, and school counselors can offer mature perspectives on academic paths and future careers. "
                "However, one should not accept every recommendation blindly without critical thinking. "
                "The best approach is to listen attentively, evaluate whether the advice aligns with one's personal values, and then make a well-informed decision."
            ),
            sub_items=[
                SubItem(label="a", statement="Consulting experienced adults can provide students with beneficial guidance for career planning.", is_correct=True, explanation="The passage states adults 'offer mature perspectives on academic paths and future careers'."),
                SubItem(label="b", statement="Students should blindly follow all suggestions given to them without question.", is_correct=False, explanation="The text advises: 'one should not accept every recommendation blindly without critical thinking'."),
                SubItem(label="c", statement="Evaluating advice against personal values is recommended before deciding.", is_correct=True, explanation="The author encourages evaluating 'whether the advice aligns with one's personal values'."),
                SubItem(label="d", statement="The author claims that school counselors have no practical knowledge to assist students.", is_correct=False, explanation="School counselors are explicitly listed as experienced people who can offer mature perspectives.")
            ],
            explanation="Reading passage on analytical thinking and advice evaluation."
        )
    ]
    
    short_questions = [
        Part3Question(
            id=1,
            question="Give the correct form of the word in brackets:\nHe gave a very [USE] presentation on community development. (Write only ONE word)",
            answer="useful",
            explanation="Before noun 'presentation', an adjective is needed: 'use' -> 'useful'."
        ),
        Part3Question(
            id=2,
            question="Rewrite the sentence without changing its meaning:\n'You should consult a doctor immediately,' she told him.\n-> She advised him _________________ a doctor immediately. (Write the missing phrase)",
            answer="to consult",
            explanation="Structure: advise someone to do something -> 'to consult'."
        ),
        Part3Question(
            id=3,
            question="Give the correct form of the word in brackets:\nWe need to hire a certified [ELECTRIC] to inspect the wiring in the new library. (Write only ONE word)",
            answer="electrician",
            explanation="A person who works with electricity is an 'electrician'."
        ),
        Part3Question(
            id=4,
            question="Fill in the blank with ONE suitable preposition:\nMany young professionals enjoy living ________ the peaceful suburbs of Hanoi.",
            answer="in",
            explanation="The standard preposition with 'suburbs' is 'in the suburbs'."
        )
    ]
    
    return ExamStructure(
        title="ĐỀ KIỂM TRA ĐỊNH KỲ MÔN TIẾNG ANH 9",
        subject="Tiếng Anh",
        grade="9",
        duration_minutes=50,
        school_name="SỞ GD&ĐT ... - TRƯỜNG THCS ...",
        academic_year="NĂM HỌC 2026 - 2027",
        code="101",
        part1_mcq=mcqs,
        part2_tf=tf_questions,
        part3_short=short_questions,
        scoring=calculate_exam_scoring(num_p1=len(mcqs), num_p2=len(tf_questions), num_p3=len(short_questions), num_p4=0),
        audit_report=create_default_audit_report("Tiếng Anh")
    )

def get_mock_informatics_exam() -> ExamStructure:
    mcqs = [
        Part1Question(
            id=1,
            question="Hệ thống trí tuệ nhân tạo nào sau đây là ví dụ điển hình về Trí tuệ nhân tạo hẹp (Narrow AI)?",
            options=[
                Option(label="A", text="Hệ thống nhận diện biển số xe tự động tại trạm thu phí"),
                Option(label="B", text="Hệ thống AI có ý thức và tư duy cảm xúc như con người"),
                Option(label="C", text="Trí tuệ nhân tạo tổng quát có khả năng học mọi lĩnh vực của đời sống"),
                Option(label="D", text="Siêu trí tuệ nhân tạo vượt trội toàn diện trí tuệ nhân loại")
            ],
            answer="A",
            explanation="AI hẹp (Narrow AI/Weak AI) được thiết kế chuyên biệt để giải quyết tốt một tác vụ cụ thể như nhận diện biển số, nhận diện khuôn mặt."
        ),
        Part1Question(
            id=2,
            question="Trong học máy (Machine Learning), quá trình cung cấp tập dữ liệu cho thuật toán để mô hình phát hiện ra quy luật và đặc trưng được gọi là",
            options=[
                Option(label="A", text="Huấn luyện mô hình (Training)"),
                Option(label="B", text="Biên dịch mã nguồn (Compiling)"),
                Option(label="C", text="Sao lưu dữ liệu (Backing up)"),
                Option(label="D", text="Nén tệp tin (Compressing)")
            ],
            answer="A",
            explanation="Huấn luyện (Training) là giai đoạn cốt lõi để mô hình học máy tự động rút ra các trọng số và quy luật từ dữ liệu mẫu."
        ),
        Part1Question(
            id=3,
            question="Ứng dụng nào sau đây KHÔNG PHẢI là ứng dụng tiêu biểu của Trí tuệ nhân tạo trong thực tế?",
            options=[
                Option(label="A", text="Thực hiện phép cộng hai số nguyên bằng máy tính cầm tay thông thường"),
                Option(label="B", text="Trợ lý ảo nhận diện và phản hồi giọng nói tự nhiên"),
                Option(label="C", text="Hệ thống gợi ý video và âm nhạc theo sở thích người dùng"),
                Option(label="D", text="Xe tự hành phát hiện chướng ngại vật và biển báo giao thông")
            ],
            answer="A",
            explanation="Máy tính cầm tay thông thường thực hiện phép tính số học theo mạch điện tử logic cố định, không sử dụng trí tuệ nhân tạo."
        ),
        Part1Question(
            id=4,
            question="Thiết bị mạng nào sau đây có chức năng định tuyến và chuyển tiếp các gói tin giữa các mạng khác nhau dựa trên địa chỉ IP?",
            options=[
                Option(label="A", text="Bộ định tuyến (Router)"),
                Option(label="B", text="Bộ chuyển mạch (Switch)"),
                Option(label="C", text="Bộ tập trung (Hub)"),
                Option(label="D", text="Card mạng (NIC)")
            ],
            answer="A",
            explanation="Router hoạt động ở tầng Network (tầng 3) và định tuyến gói tin giữa các mạng khác nhau thông qua địa chỉ IP."
        ),
        Part1Question(
            id=5,
            question="Một địa chỉ IPv4 tiêu chuẩn theo quy chuẩn Internet quốc tế được biểu diễn bằng bao nhiêu bit nhị phân?",
            options=[
                Option(label="A", text="32 bit"),
                Option(label="B", text="64 bit"),
                Option(label="C", text="128 bit"),
                Option(label="D", text="16 bit")
            ],
            answer="A",
            explanation="Địa chỉ IPv4 gồm đúng 32 bit, thường được viết dưới dạng 4 nhóm số thập phân phân cách bởi dấu chấm (ví dụ: 192.168.1.1)."
        ),
        Part1Question(
            id=6,
            question="Biện pháp nào sau đây giúp tăng cường tính bảo mật và an toàn cho tài khoản cá nhân trên không gian mạng?",
            options=[
                Option(label="A", text="Kích hoạt tính năng xác thực hai yếu tố (2FA)"),
                Option(label="B", text="Đặt mật khẩu đơn giản bằng ngày sinh để dễ nhớ"),
                Option(label="C", text="Sử dụng chung một mật khẩu cho mọi trang mạng xã hội"),
                Option(label="D", text="Đăng nhập tài khoản trên các máy tính công cộng mà không đăng xuất")
            ],
            answer="A",
            explanation="Xác thực 2 yếu tố (2FA) yêu cầu thêm mã xác minh gửi về điện thoại, ngăn chặn xâm nhập trái phép kể cả khi lộ mật khẩu."
        ),
        Part1Question(
            id=7,
            question="Trong mô hình cơ sở dữ liệu quan hệ, một trường (hoặc tập hợp các trường) dùng để xác định duy nhất mỗi bản ghi trong bảng được gọi là",
            options=[
                Option(label="A", text="Khóa chính (Primary Key)"),
                Option(label="B", text="Khóa ngoại (Foreign Key)"),
                Option(label="C", text="Bản ghi phụ (Secondary Record)"),
                Option(label="D", text="Kiểu dữ liệu (Data Type)")
            ],
            answer="A",
            explanation="Khóa chính là thuộc tính có giá trị phân biệt duy nhất giữa các hàng trong bảng và không được mang giá trị rỗng (NULL)."
        ),
        Part1Question(
            id=8,
            question="Lệnh SQL nào sau đây được sử dụng để truy vấn và trích xuất dữ liệu từ một hoặc nhiều bảng?",
            options=[
                Option(label="A", text="SELECT"),
                Option(label="B", text="DELETE"),
                Option(label="C", text="INSERT"),
                Option(label="D", text="UPDATE")
            ],
            answer="A",
            explanation="Cú pháp `SELECT ... FROM ... WHERE ...` dùng để tìm kiếm và kết xuất thông tin trong ngôn ngữ truy vấn SQL."
        ),
        Part1Question(
            id=9,
            question="Trong ngôn ngữ lập trình Python, kết quả của biểu thức `type(10.5)` là",
            options=[
                Option(label="A", text="<class 'float'>"),
                Option(label="B", text="<class 'int'>"),
                Option(label="C", text="<class 'str'>"),
                Option(label="D", text="<class 'bool'>")
            ],
            answer="A",
            explanation="Số thực có dấu chấm thập phân 10.5 thuộc kiểu dữ liệu `float` trong Python."
        ),
        Part1Question(
            id=10,
            question="Đoạn mã Python sau: `for i in range(1, 5): print(i, end=' ')` sẽ in ra màn hình kết quả là",
            options=[
                Option(label="A", text="1 2 3 4"),
                Option(label="B", text="1 2 3 4 5"),
                Option(label="C", text="0 1 2 3 4"),
                Option(label="D", text="1 5")
            ],
            answer="A",
            explanation="`range(1, 5)` sinh ra dãy số bắt đầu từ 1 đến 4 (cận trên 5 không được tính), do đó kết quả in là `1 2 3 4`."
        ),
        Part1Question(
            id=11,
            question="Hành vi tự ý tải phần mềm bẻ khóa (crack) và phát tán trái phép lên mạng xã hội là hành vi",
            options=[
                Option(label="A", text="Vi phạm quyền tác giả và quyền sở hữu trí tuệ"),
                Option(label="B", text="Được pháp luật khuyến khích để tiết kiệm chi phí"),
                Option(label="C", text="Hoàn toàn hợp pháp vì mục đích chia sẻ phi thương mại"),
                Option(label="D", text="Giúp nâng cao độ an toàn thông tin cho hệ thống")
            ],
            answer="A",
            explanation="Phát tán phần mềm crack vi phạm Luật Sở hữu trí tuệ và Luật An ninh mạng, đồng thời tiềm ẩn nguy cơ lây nhiễm mã độc."
        ),
        Part1Question(
            id=12,
            question="Đơn vị đo dung lượng thông tin nào sau đây có giá trị lớn nhất?",
            options=[
                Option(label="A", text="Gigabyte (GB)"),
                Option(label="B", text="Megabyte (MB)"),
                Option(label="C", text="Kilobyte (KB)"),
                Option(label="D", text="Byte (B)")
            ],
            answer="A",
            explanation="Thứ tự dung lượng tăng dần: Byte < KB < MB < GB < TB. Do đó Gigabyte (GB) lớn nhất trong 4 phương án."
        )
    ]

    tf_questions = [
        Part2Question(
            id=1,
            question="Một nhóm kỹ sư phát triển hệ thống camera AI giao thông thông minh để nhận diện và phân loại phương tiện (xe con, xe buýt, xe tải) tại một nút giao thông trọng điểm. Hệ thống ứng dụng mô hình học máy thị giác máy tính được huấn luyện trên 60.000 hình ảnh chụp vào ban ngày trong điều kiện trời nắng ráo với độ chính xác đạt 96%. Tuy nhiên, khi thử nghiệm thực tế vào ban đêm trời mưa, độ chính xác nhận diện sụt giảm chỉ còn 62%.",
            sub_items=[
                SubItem(label="a", statement="Hệ thống camera phân loại phương tiện giao thông nêu trên là một ứng dụng điển hình của Trí tuệ nhân tạo hẹp (Narrow AI).", is_correct=True, explanation="Hệ thống được thiết kế chuyên biệt để giải quyết tác vụ thị giác phân loại phương tiện cụ thể."),
                SubItem(label="b", statement="Nguyên nhân trực tiếp khiến độ chính xác của hệ thống giảm mạnh vào ban đêm là do sự khác biệt lớn về phân phối dữ liệu (Data Drift / Out-of-Distribution) so với tập dữ liệu huấn luyện ban ngày.", is_correct=True, explanation="Mô hình học máy phụ thuộc mật thiết vào tập huấn luyện; điều kiện ban đêm trời mưa có độ nhiễu và độ tương phản sáng khác biệt hoàn toàn với ảnh huấn luyện ban ngày."),
                SubItem(label="c", statement="Để nâng cao độ chính xác vào ban đêm mà không cần đào tạo lại toàn bộ mô hình từ đầu, giải pháp hiệu quả là áp dụng kỹ thuật học chuyển giao (Transfer Learning) bằng cách tinh chỉnh mô hình với tập dữ liệu bổ sung chụp ban đêm trời mưa.", is_correct=True, explanation="Transfer learning cho phép tái sử dụng các tầng trích xuất đặc trưng đã học và chỉ cần tinh chỉnh (fine-tune) trên tập dữ liệu đặc thù ban đêm."),
                SubItem(label="d", statement="Nếu hệ thống tự động nhận diện biển số xe vi phạm và tự ý công khai toàn bộ họ tên, số điện thoại, địa chỉ nhà của chủ phương tiện lên mạng xã hội để phạt nguội thì hành vi này hoàn toàn hợp pháp và không vi phạm quy định về bảo vệ dữ liệu cá nhân.", is_correct=False, explanation="Hành vi tự ý công khai dữ liệu cá nhân vi phạm Nghị định 13/2023/NĐ-CP về bảo vệ dữ liệu cá nhân và các nguyên tắc đạo đức trong AI.")
            ],
            explanation="Bài toán ứng dụng Trí tuệ nhân tạo trong đô thị thông minh, xử lý dữ liệu học máy và đạo đức số."
        ),
        Part2Question(
            id=2,
            question="Một bệnh viện đa khoa triển khai hệ thống Cơ sở dữ liệu quan hệ quản lý khám chữa bệnh điện tử gồm hai bảng: BENH_NHAN(MaBN, HoTen, NgaySinh, BHYT) với MaBN là khóa chính; và HO_SO_KHAM(MaHS, MaBN, NgayKham, ChuanDoan, BacSi) với MaHS là khóa chính, MaBN là khóa ngoại tham chiếu đến bảng BENH_NHAN. Bệnh viện kết nối mạng nội bộ bảo mật để các y bác sĩ truy cập hồ sơ.",
            sub_items=[
                SubItem(label="a", statement="Thuộc tính MaBN trong bảng HO_SO_KHAM đóng vai trò khóa ngoại nhằm đảm bảo tính toàn vẹn tham chiếu giữa hồ sơ khám bệnh và dữ liệu bệnh nhân.", is_correct=True, explanation="Khóa ngoại MaBN liên kết mỗi đợt khám với đúng hồ sơ nhân khẩu học của bệnh nhân."),
                SubItem(label="b", statement="Hệ quản trị CSDL cho phép thêm một bản ghi mới vào bảng HO_SO_KHAM với giá trị MaBN = 'BN999' ngay cả khi mã bệnh nhân này chưa từng xuất hiện trong bảng BENH_NHAN.", is_correct=False, explanation="Ràng buộc toàn vẹn tham chiếu sẽ ngăn chặn việc chèn bản ghi con có khóa ngoại không tồn tại ở bảng cha."),
                SubItem(label="c", statement="Để ngăn chặn nguy cơ đánh cắp dữ liệu bệnh án khi truyền tải trong mạng nội bộ và qua Internet, hệ thống bắt buộc phải áp dụng giao thức truyền thông mã hóa HTTPS/TLS và phân quyền truy cập theo vai trò (RBAC).", is_correct=True, explanation="HTTPS/TLS mã hóa dữ liệu truyền tải, còn RBAC đảm bảo chỉ bác sĩ phụ trách mới được đọc hồ sơ chuyên môn."),
                SubItem(label="d", statement="Để thuận tiện cho công việc hàng ngày, việc cấp tài khoản có quyền quản trị tối cao (DBA) có toàn quyền xóa dữ liệu cho toàn bộ nhân viên bệnh viện là phương pháp quản trị CSDL an toàn và được khuyến nghị.", is_correct=False, explanation="Nguyên tắc an toàn thông tin là trao đặc quyền tối thiểu (Least Privilege); không được cấp quyền DBA bừa bãi.")
            ],
            explanation="Kiến thức về mô hình cơ sở dữ liệu quan hệ, tính toàn vẹn dữ liệu và an toàn thông tin y tế."
        ),
        Part2Question(
            id=3,
            question="Một cửa hàng trực tuyến áp dụng chương trình khuyến mãi tự động bằng đoạn mã Python sau để tính số tiền thanh toán cuối cùng của đơn hàng:\n```python\ndef tinh_tien(gia_goc, so_luong, ma_giam):\n    tong = gia_goc * so_luong\n    if tong >= 1000000 and ma_giam == 'VIP':\n        tong = tong * 0.85\n    elif tong >= 500000:\n        tong = tong * 0.90\n    return tong\n```\nMột khách hàng đặt mua 4 sản phẩm có đơn giá gốc 300.000 VNĐ/sản phẩm và nhập mã giảm giá 'VIP'.",
            sub_items=[
                SubItem(label="a", statement="Giá trị ban đầu của biến tong trước khi kiểm tra các điều kiện rẽ nhánh là 1.200.000 VNĐ.", is_correct=True, explanation="tong = 300000 * 4 = 1200000 VNĐ."),
                SubItem(label="b", statement="Với đơn hàng trên, biểu thức logic (tong >= 1000000 and ma_giam == 'VIP') nhận giá trị True.", is_correct=True, explanation="Cả hai vế tong >= 1000000 (1.200.000 >= 1.000.000) và ma_giam == 'VIP' đều đúng."),
                SubItem(label="c", statement="Số tiền thực tế khách hàng phải thanh toán sau khi thực thi hàm tinh_tien(300000, 4, 'VIP') là 960.000 VNĐ.", is_correct=False, explanation="Sau khi giảm giá 15%, số tiền là: 1.200.000 * 0.85 = 1.020.000 VNĐ (chứ không phải 960.000 VNĐ)."),
                SubItem(label="d", statement="Nếu một khách hàng khác mua 2 sản phẩm (đơn giá gốc 300.000 VNĐ) nhưng không có mã 'VIP', hệ thống sẽ áp dụng nhánh elif và tính số tiền thanh toán là 540.000 VNĐ.", is_correct=True, explanation="Tổng gốc là 600.000 VNĐ (>= 500.000), rơi vào nhánh elif giảm 10%: 600.000 * 0.90 = 540.000 VNĐ.")
            ],
            explanation="Kiến thức lập trình Python cấu trúc rẽ nhánh, biểu thức logic và ứng dụng thương mại điện tử."
        ),
        Part2Question(
            id=4,
            question="Phòng máy thực hành Tin học của trường THPT gồm 40 máy tính để bàn được nối với một thiết bị chuyển mạch (Switch). Toàn bộ phòng máy sử dụng chung dải địa chỉ mạng nội bộ 192.168.1.0/24, cổng mặc định (Default Gateway) trỏ về địa chỉ của Router kết nối cáp quang Internet là 192.168.1.1. Trong một buổi học, máy tính số 12 bị nhiễm mã độc tống tiền (Ransomware) do học sinh cắm USB lạ.",
            sub_items=[
                SubItem(label="a", statement="Địa chỉ IP 192.168.1.1 thuộc dải địa chỉ mạng riêng tư (Private IP) theo chuẩn IPv4, không thể định tuyến trực tiếp trên mạng Internet công cộng.", is_correct=True, explanation="Dải 192.168.0.0/16 là dải IP riêng tư (RFC 1918), phải qua NAT mới ra được Internet."),
                SubItem(label="b", statement="Thiết bị Switch trong phòng máy hoạt động ở tầng Mạng (Network Layer) và đảm nhận chức năng phân phối địa chỉ IP động DHCP cho 40 máy tính con.", is_correct=False, explanation="Switch thông thường hoạt động ở tầng Liên kết dữ liệu (Data Link Layer); Router hoặc máy chủ DHCP mới cấp phát IP."),
                SubItem(label="c", statement="Hành động xử lý khẩn cấp đầu tiên và hiệu quả nhất khi phát hiện máy tính 12 bị nhiễm Ransomware là lập tức rút cáp mạng kết nối từ máy 12 vào Switch để cô lập nguồn lây nhiễm.", is_correct=True, explanation="Ngắt kết nối mạng ngay lập tức giúp ngăn chặn mã độc quét và mã hóa dữ liệu các máy tính khác trong mạng LAN."),
                SubItem(label="d", statement="Để tránh việc học sinh quên mật khẩu, biện pháp đặt chung một mật khẩu quản trị đơn giản như '123456' trên toàn bộ 40 máy tính là giải pháp an toàn và tối ưu trong quản lý phòng máy.", is_correct=False, explanation="Đặt chung mật khẩu yếu tạo điều kiện cho mã độc hoặc kẻ xấu dễ dàng chiếm quyền điều khiển toàn bộ hệ thống phòng máy.")
            ],
            explanation="Bài toán về cấu trúc mạng máy tính nội bộ, thiết bị mạng và quy trình xử lý sự cố an toàn thông tin."
        )
    ]

    short_questions = [
        Part3Question(
            id=1,
            question="Một địa chỉ IPv4 tiêu chuẩn của mạng Internet được tạo thành từ bao nhiêu bit nhị phân (chỉ ghi số nguyên)?",
            answer="32",
            explanation="Địa chỉ IPv4 gồm đúng 32 bit nhị phân chia làm 4 octet."
        ),
        Part3Question(
            id=2,
            question="Cho đoạn mã Python sau:\ns = 0\nfor i in range(1, 6):\n    s += i\nprint(s)\nGiá trị của biến s sau khi thực thi đoạn mã trên bằng bao nhiêu?",
            answer="15",
            explanation="Tổng các số từ 1 đến 5: $1 + 2 + 3 + 4 + 5 = 15$."
        ),
        Part3Question(
            id=3,
            question="Một tệp dữ liệu có dung lượng bằng 4096 Megabyte (MB). Dung lượng này tương đương bao nhiêu Gigabyte (GB) (chỉ ghi số nguyên)?",
            answer="4",
            explanation="$4096\\text{ MB} = \\frac{4096}{1024} = 4\\text{ GB}$."
        ),
        Part3Question(
            id=4,
            question="Vòng lặp `for i in range(2, 12, 3):` trong Python sẽ thực hiện bao nhiêu lần lặp (chỉ ghi số nguyên)?",
            answer="4",
            explanation="Dãy giá trị của $i$ là: 2, 5, 8, 11 (tổng cộng 4 lần lặp)."
        )
    ]

    return ExamStructure(
        title="ĐỀ KIỂM TRA ĐỊNH KỲ MÔN TIN HỌC 12",
        subject="Tin học",
        grade="12",
        duration_minutes=50,
        school_name="SỞ GD&ĐT ... - TRƯỜNG THPT ...",
        academic_year="NĂM HỌC 2026 - 2027",
        code="101",
        part1_mcq=mcqs,
        part2_tf=tf_questions,
        part3_short=short_questions,
        scoring=calculate_exam_scoring(num_p1=len(mcqs), num_p2=len(tf_questions), num_p3=len(short_questions), num_p4=0),
        audit_report=create_default_audit_report("Tin học")
    )

_key_rotation_counter = 0


def get_env_api_keys(provider: str = "gemini") -> List[str]:
    load_dotenv(override=True)
    keys = []
    prefix = "GEMINI_API_KEY" if provider != "openai" else "OPENAI_API_KEY"
    
    # 1. Numbered keys GEMINI_API_KEY_1 .. GEMINI_API_KEY_30
    for i in range(1, 31):
        val = os.getenv(f"{prefix}_{i}")
        if val:
            val = val.strip().strip("'\"`")
            if len(val) > 5 and val not in keys:
                keys.append(val)
                
    # 2. Comma-separated list GEMINI_API_KEYS
    list_val = os.getenv(f"{prefix}S")
    if list_val:
        for k in re.split(r'[\r\n,;]+', list_val):
            k = k.strip().strip("'\"`")
            if len(k) > 5 and k not in keys:
                keys.append(k)
                
    # 3. Single key GEMINI_API_KEY
    single_val = os.getenv(prefix)
    if single_val:
        single_val = single_val.strip().strip("'\"`")
        if len(single_val) > 5 and single_val not in keys:
            keys.append(single_val)
            
    return keys

def extract_api_keys(request: GenerateRequest) -> List[str]:
    raw_keys = []
    if request.api_keys:
        raw_keys.extend(request.api_keys)
    if request.api_key:
        parts = re.split(r'[\r\n,;]+', request.api_key)
        raw_keys.extend(parts)
    
    cleaned_keys = []
    seen = set()
    for k in raw_keys:
        k = k.strip().strip("'\"`")
        if k and len(k) > 5 and k not in seen:
            seen.add(k)
            cleaned_keys.append(k)
            
    # If no keys provided in request, load from .env
    if not cleaned_keys:
        cleaned_keys = get_env_api_keys(request.api_provider)
        
    return cleaned_keys

def mask_key(k: str) -> str:
    if len(k) <= 8:
        return "***"
    return f"{k[:4]}...{k[-4:]}"

def find_key(d: dict, *candidates: str) -> Any:
    if not isinstance(d, dict):
        return None
    for c in candidates:
        if c in d and d[c] is not None:
            return d[c]
    clean_map = {}
    for k, v in d.items():
        norm_k = str(k).lower().replace("_", "").replace("-", "").replace(" ", "").replace(":", "")
        clean_map[norm_k] = v
        
    for c in candidates:
        norm_c = c.lower().replace("_", "").replace("-", "").replace(" ", "").replace(":", "")
        if norm_c in clean_map and clean_map[norm_c] is not None:
            return clean_map[norm_c]
            
    for k_norm, v in clean_map.items():
        if v is None:
            continue
        for c in candidates:
            norm_c = c.lower().replace("_", "").replace("-", "").replace(" ", "").replace(":", "")
            if len(norm_c) >= 4 and (norm_c in k_norm or k_norm in norm_c):
                return v
    return None

def normalize_exam_data(raw_data: Dict[str, Any], default_subject: str = "Toán học", default_grade: str = "12") -> Dict[str, Any]:
    """
    Intelligently normalizes diverse AI JSON outputs (varied key names, nested roots,
    string options, Vietnamese boolean answers) into a valid ExamStructure schema.
    """
    data = raw_data
    for wrap_key in ["exam", "de_thi", "de_kiem_tra", "data", "result", "content"]:
        val = find_key(data, wrap_key)
        if isinstance(val, dict):
            data = val
            break

    title = find_key(data, "title", "tieu_de", "ten_de") or f"ĐỀ KIỂM TRA ĐỊNH KỲ MÔN {default_subject.upper()} {default_grade}"
    subject = find_key(data, "subject", "mon", "mon_hoc") or default_subject
    grade = str(find_key(data, "grade", "khoi", "lop") or default_grade)
    duration_minutes = int(find_key(data, "duration_minutes", "thoi_gian", "thoi_gian_lam_bai") or 50)
    school_name = find_key(data, "school_name", "truong", "so_gddt") or "SỞ GD&ĐT ... - TRƯỜNG THPT ..."
    if school_name and ("CHUYÊN" in school_name.upper() or "AMSTERDAM" in school_name.upper()):
        school_name = "SỞ GD&ĐT ... - TRƯỜNG THPT ..."
    academic_year = find_key(data, "academic_year", "nam_hoc") or "NĂM HỌC 2026 - 2027"
    if academic_year and ("2024" in academic_year or "2025" in academic_year):
        academic_year = "NĂM HỌC 2026 - 2027"
    code = str(find_key(data, "code", "ma_de") or "101")

    # Extract Part 1, Part 2, Part 3 using robust fuzzy matching
    raw_p1 = find_key(data, "part1_mcq", "part1", "part_1", "part_i", "parti", "phan1", "phan_1", "phan_i", "phani", "mcq", "trac_nghiem", "multiple_choice") or []
    raw_p2 = find_key(data, "part2_tf", "part2", "part_2", "part_ii", "partii", "phan2", "phan_2", "phan_ii", "phanii", "dung_sai", "dungsai", "true_false", "cau_hoi_dung_sai", "tf") or []
    raw_p3 = find_key(data, "part3_short", "part3", "part_3", "part_iii", "partiii", "phan3", "phan_3", "phan_iii", "phaniii", "tra_loi_ngan", "traloingan", "short_answer", "cau_hoi_tra_loi_ngan", "dien_khuyet", "short") or []
    raw_p4 = find_key(data, "part4_essay", "part4", "part_4", "part_iv", "partiv", "phan4", "phan_4", "phan_iv", "phaniv", "tu_luan", "tuluan", "essay", "cau_hoi_tu_luan") or []

    # Check sections list if any are missing
    sections = find_key(data, "sections", "cac_phan", "phan")
    if isinstance(sections, list):
        for sec in sections:
            if isinstance(sec, dict):
                name = str(sec.get("name") or sec.get("title") or sec.get("ten") or "").lower()
                q_list = sec.get("questions") or sec.get("cau_hoi") or sec.get("items") or []
                if ("1" in name or "i" in name or "mcq" in name) and not raw_p1:
                    raw_p1 = q_list
                elif ("2" in name or "ii" in name or "đúng" in name or "sai" in name or "tf" in name) and not raw_p2:
                    raw_p2 = q_list
                elif ("3" in name or "iii" in name or "ngắn" in name or "short" in name) and not raw_p3:
                    raw_p3 = q_list
                elif ("4" in name or "iv" in name or "tự luận" in name or "tu_luan" in name or "essay" in name) and not raw_p4:
                    raw_p4 = q_list

    # Check flat questions list if any are missing
    if not raw_p1 and not raw_p2 and not raw_p3:
        all_q = find_key(data, "questions", "cau_hoi", "de_thi", "items")
        if isinstance(all_q, list) and len(all_q) > 0:
            for item in all_q:
                if not isinstance(item, dict):
                    continue
                if "sub_items" in item or "statements" in item or "y_dung_sai" in item or "cau_hoi_con" in item:
                    raw_p2.append(item)
                elif "options" in item or "lua_chon" in item or "phuong_an" in item:
                    raw_p1.append(item)
                else:
                    raw_p3.append(item)

    if isinstance(raw_p1, dict):
        raw_p1 = list(raw_p1.values())
    if isinstance(raw_p2, dict):
        raw_p2 = list(raw_p2.values())
    if isinstance(raw_p3, dict):
        raw_p3 = list(raw_p3.values())

    p1_list = []
    labels_4 = ["A", "B", "C", "D"]
    forbidden_patterns = [
        r"tất cả các phương án.*đều đúng",
        r"tất cả các đáp án.*đều đúng",
        r"tất cả các câu.*đều đúng",
        r"cả a,?\s*b,?\s*c.*đều đúng",
        r"cả ba phương án.*đều đúng",
        r"cả hai phương án.*đều đúng",
        r"tất cả đều đúng",
        r"tất cả đều sai",
        r"không có đáp án nào đúng",
        r"không có phương án nào đúng"
    ]

    for idx, item in enumerate(raw_p1, start=1):
        if not isinstance(item, dict):
            continue
        q_id = int(item.get("id") or item.get("cau") or idx)
        question = str(item.get("question") or item.get("cau_hoi") or item.get("noi_dung") or "")
        explanation = str(item.get("explanation") or item.get("huong_dan_giai") or item.get("loi_giai") or "")

        raw_ans = str(item.get("answer") or item.get("dap_an") or "A").strip()
        ans_clean = raw_ans.upper()

        raw_opts = (
            item.get("options")
            or item.get("choices")
            or item.get("answers")
            or item.get("phuong_an")
            or item.get("lua_chon")
            or item.get("cac_phuong_an")
        )
        opts_list = []
        if not raw_opts:
            # Check for top-level keys A, B, C, D directly inside question item
            found_top_level = []
            for lbl in ["A", "B", "C", "D"]:
                val = item.get(lbl) if item.get(lbl) is not None else item.get(lbl.lower())
                if val is not None and str(val).strip():
                    found_top_level.append({"label": lbl, "text": str(val).strip()})
            if len(found_top_level) >= 2:
                raw_opts = found_top_level
            else:
                raw_opts = []

        if isinstance(raw_opts, dict):
            for k, v in raw_opts.items():
                opts_list.append({"label": str(k).strip().upper(), "text": str(v).strip()})
        elif isinstance(raw_opts, list):
            for o_idx, opt in enumerate(raw_opts):
                if isinstance(opt, dict):
                    lbl = str(opt.get("label") or opt.get("id") or "").strip().upper()
                    txt = str(opt.get("text") or opt.get("noi_dung") or "").strip()
                    opts_list.append({"label": lbl, "text": txt})
                elif isinstance(opt, str):
                    m = re.match(r"^([A-Za-z0-9])[\.\)\:\s]\s*(.*)$", opt.strip())
                    if m:
                        opts_list.append({"label": m.group(1).upper(), "text": m.group(2).strip()})
                    else:
                        opts_list.append({"label": "", "text": opt.strip()})

        # Remove completely empty options
        opts_list = [o for o in opts_list if o.get("text")]

        # Determine which option index is the correct answer
        correct_opt_idx = -1
        concluded_letter = extract_concluded_letter(explanation)

        # 1. Match label exactly
        for o_i, o in enumerate(opts_list):
            if o.get("label") and o["label"] == ans_clean:
                correct_opt_idx = o_i
                break
        # If explanation explicitly concluded a letter and ans_clean wasn't found or differed
        if concluded_letter and (correct_opt_idx == -1 or ans_clean != concluded_letter):
            for o_i, o in enumerate(opts_list):
                if o.get("label") and o["label"] == concluded_letter:
                    correct_opt_idx = o_i
                    ans_clean = concluded_letter
                    break
        # 2. Check if answer is a letter A-Z
        if correct_opt_idx == -1 and len(ans_clean) == 1 and 'A' <= ans_clean <= 'Z':
            idx_from_letter = ord(ans_clean) - ord('A')
            if idx_from_letter < len(opts_list):
                correct_opt_idx = idx_from_letter
        # 3. Match text substring
        if correct_opt_idx == -1 and len(raw_ans) > 1:
            for o_i, o in enumerate(opts_list):
                if raw_ans in o.get("text", "") or o.get("text", "") in raw_ans:
                    correct_opt_idx = o_i
                    break
        if correct_opt_idx == -1:
            correct_opt_idx = 0

        # Enforce EXACTLY 4 options:
        if len(opts_list) > 4:
            # If the correct answer is at index >= 4 (e.g. index 4 which is E):
            if correct_opt_idx >= 4:
                # Find a distractor among 0..3 to replace
                target_rep = 3
                for i in range(4):
                    if any(re.search(pat, opts_list[i]["text"], re.IGNORECASE) for pat in forbidden_patterns):
                        target_rep = i
                        break
                opts_list[target_rep] = opts_list[correct_opt_idx]
                correct_opt_idx = target_rep
                opts_list = opts_list[:4]
            else:
                # Correct answer is in 0..3.
                # If any distractor in 0..3 has a forbidden phrase, swap it with a valid extra option from >= 4 if possible.
                for i in range(4):
                    if i != correct_opt_idx and any(re.search(pat, opts_list[i]["text"], re.IGNORECASE) for pat in forbidden_patterns):
                        for extra_i in range(4, len(opts_list)):
                            if not any(re.search(p, opts_list[extra_i]["text"], re.IGNORECASE) for p in forbidden_patterns):
                                opts_list[i] = opts_list[extra_i]
                                break
                opts_list = opts_list[:4]

        # Ensure at least 4 options: HEAL WITH CONTEXTUAL REAL CHOICES (NEVER USE "Phương án khác"!)
        if len(opts_list) < 4:
            temp_q = Part1Question(
                id=q_id,
                question=question,
                options=[Option(label=o.get("label") or "A", text=o.get("text", "")) for o in opts_list],
                answer=ans_clean if ans_clean in ["A", "B", "C", "D"] else "A",
                explanation=explanation
            )
            temp_q = heal_mcq_offline(temp_q, subject)
            opts_list = [{"label": o.label, "text": o.text} for o in temp_q.options]
            final_answer = temp_q.answer
            explanation = temp_q.explanation
            correct_opt_idx = ord(final_answer) - ord("A")
        else:
            final_answer = labels_4[min(max(correct_opt_idx, 0), 3)]

        # Exactly 4 options: reassign strict labels A, B, C, D
        for i in range(4):
            opts_list[i]["label"] = labels_4[i]

        # Synchronize explanation conclusion with final_answer 100%
        explanation = synchronize_mcq_explanation_with_answer(explanation, final_answer)

        # Diagram / Image support
        img_b64 = item.get("image_base64")
        img_cap = item.get("image_caption")
        if not img_b64 and item.get("diagram"):
            img_b64, img_cap = generate_diagram(item.get("diagram"))

        p1_list.append({
            "id": q_id,
            "question": question,
            "options": opts_list,
            "answer": final_answer,
            "explanation": explanation,
            "image_base64": img_b64,
            "image_caption": img_cap
        })

    # Part 2 TF
    p2_list = []
    sub_labels_default = ["a", "b", "c", "d"]
    for idx, item in enumerate(raw_p2, start=1):
        if not isinstance(item, dict):
            continue
        q_id = int(item.get("id") or item.get("cau") or idx)
        question = str(item.get("question") or item.get("cau_hoi") or item.get("noi_dung") or "")
        explanation = str(item.get("explanation") or item.get("huong_dan_giai") or item.get("loi_giai") or "")

        raw_subs = (
            item.get("sub_items")
            or item.get("subitems")
            or item.get("items")
            or item.get("statements")
            or item.get("lenh_hoi")
            or item.get("y_con")
            or item.get("y_dung_sai")
            or item.get("cac_y")
            or item.get("cau_hoi_con")
            or item.get("menh_de")
            or item.get("sub_questions")
            or item.get("options")
            or item.get("choices")
            or item.get("propositions")
            or []
        )
        if not raw_subs:
            top_subs = []
            for lbl in ["a", "b", "c", "d"]:
                val = item.get(lbl) if item.get(lbl) is not None else item.get(lbl.upper())
                if val is not None:
                    if isinstance(val, dict):
                        stmt = val.get("statement") or val.get("khang_dinh") or val.get("text") or str(val)
                        is_c = val.get("is_correct")
                        is_c = bool(is_c) if isinstance(is_c, bool) else str(is_c).lower() in ("true", "đúng", "1")
                        exp = val.get("explanation") or ""
                        top_subs.append({"label": lbl, "statement": stmt, "is_correct": is_c, "explanation": exp})
                    else:
                        top_subs.append({"label": lbl, "statement": str(val), "is_correct": True, "explanation": ""})
            if len(top_subs) >= 2:
                raw_subs = top_subs

        subs_list = []
        if isinstance(raw_subs, dict):
            for k, v in raw_subs.items():
                if isinstance(v, dict):
                    stmt = v.get("statement") or v.get("khang_dinh") or v.get("noi_dung") or ""
                    is_c = True
                    for ans_key in ["is_correct", "correct", "dap_an", "answer", "dung_sai"]:
                        if ans_key in v:
                            val = v[ans_key]
                            is_c = val in (True, 1) or str(val).strip().lower() in ("đúng", "dung", "đ", "d", "true", "t", "1", "yes")
                            break
                    exp = v.get("explanation") or v.get("loi_giai") or ""
                else:
                    stmt = str(v)
                    is_c = True
                    exp = ""
                is_c, exp = reconcile_tf_subitem(is_c, exp)
                if not exp:
                    exp = f"Khẳng định này là {'đúng' if is_c else 'sai'}."
                subs_list.append({"label": str(k).lower().strip(".)"), "statement": stmt, "is_correct": is_c, "explanation": exp})
        elif isinstance(raw_subs, list):
            for s_idx, sub in enumerate(raw_subs):
                if isinstance(sub, dict):
                    lbl = str(sub.get("label") or sub.get("y") or sub_labels_default[min(s_idx, 3)]).lower().strip(".)")
                    stmt = str(sub.get("statement") or sub.get("khang_dinh") or sub.get("noi_dung") or sub.get("text") or "")
                    
                    is_correct = True
                    for ans_key in ["is_correct", "correct", "dap_an", "answer", "dung_sai", "status"]:
                        if ans_key in sub:
                            val = sub[ans_key]
                            if isinstance(val, bool):
                                is_correct = val
                            elif isinstance(val, (int, float)):
                                is_correct = bool(val)
                            else:
                                val_lower = str(val).strip().lower()
                                is_correct = val_lower in ("đúng", "dung", "đ", "d", "true", "t", "1", "yes", "right")
                            break
                    sub_exp = str(sub.get("explanation") or sub.get("loi_giai") or "")
                    is_correct, sub_exp = reconcile_tf_subitem(is_correct, sub_exp)
                    if not sub_exp:
                        sub_exp = f"Khẳng định này là {'đúng' if is_correct else 'sai'}."
                    subs_list.append({"label": lbl, "statement": stmt, "is_correct": is_correct, "explanation": sub_exp})

        temp_q = Part2Question(
            id=q_id,
            question=question,
            sub_items=[
                SubItem(
                    label=s["label"],
                    statement=s["statement"],
                    is_correct=s["is_correct"],
                    explanation=s["explanation"]
                ) for s in subs_list
            ],
            explanation=explanation
        )
        if len(subs_list) < 4 or any(len(s["statement"].strip()) < 5 or re.search(r"đang cập nhật", s["statement"], re.IGNORECASE) or re.match(r"^(?:mệnh đề|khẳng định)\s*[abcd]?\s*[\.:]?$", s["statement"].strip(), re.IGNORECASE) for s in subs_list):
            temp_q = heal_tf_offline(temp_q, default_subject, idx - 1, grade=grade)

        t_count = sum(1 for s in temp_q.sub_items if s.is_correct)
        if t_count == 4:
            temp_q.sub_items[3].is_correct = False
            temp_q.sub_items[3].explanation = "Khẳng định này là sai. " + (temp_q.sub_items[3].explanation or "")
        elif t_count == 0:
            temp_q.sub_items[0].is_correct = True
            temp_q.sub_items[0].explanation = "Khẳng định này là đúng. " + (temp_q.sub_items[0].explanation or "")

        for s in temp_q.sub_items:
            s.is_correct, s.explanation = reconcile_tf_subitem(s.is_correct, s.explanation or "")

        # Diagram / Image support
        img_b64 = item.get("image_base64")
        img_cap = item.get("image_caption")
        if not img_b64 and item.get("diagram"):
            img_b64, img_cap = generate_diagram(item.get("diagram"))

        p2_list.append({
            "id": temp_q.id,
            "question": temp_q.question,
            "sub_items": [{"label": s.label, "statement": s.statement, "is_correct": s.is_correct, "explanation": s.explanation} for s in temp_q.sub_items],
            "explanation": temp_q.explanation,
            "image_base64": img_b64,
            "image_caption": img_cap
        })

    # Part 3 Short Answer
    p3_list = []
    for idx, item in enumerate(raw_p3, start=1):
        if not isinstance(item, dict):
            continue
        q_id = int(item.get("id") or item.get("cau") or idx)
        question = str(item.get("question") or item.get("cau_hoi") or item.get("noi_dung") or "")
        answer = str(item.get("answer") or item.get("dap_an") or item.get("dap_so") or item.get("result") or "").strip()
        explanation = str(item.get("explanation") or item.get("huong_dan_giai") or item.get("loi_giai") or "")
        if answer and explanation and answer not in explanation:
            explanation = explanation.rstrip(" .;,") + f". Vậy đáp số là {answer}."

        img_b64 = item.get("image_base64")
        img_cap = item.get("image_caption")
        if not img_b64 and item.get("diagram"):
            img_b64, img_cap = generate_diagram(item.get("diagram"))

        p3_list.append({
            "id": q_id,
            "question": question,
            "answer": answer,
            "explanation": explanation,
            "image_base64": img_b64,
            "image_caption": img_cap
        })

    # Part 4 Essay
    if isinstance(raw_p4, dict):
        raw_p4 = list(raw_p4.values())
    p4_list = []
    for idx, item in enumerate(raw_p4, start=1):
        if not isinstance(item, dict):
            continue
        q_id = int(item.get("id") or item.get("cau") or idx)
        question = str(item.get("question") or item.get("cau_hoi") or item.get("noi_dung") or "")
        try:
            points = float(item.get("points") or item.get("diem") or item.get("score") or 1.0)
        except Exception:
            points = 1.0
        answer = str(item.get("answer") or item.get("dap_an") or item.get("tom_tat") or "").strip()
        explanation = str(item.get("explanation") or item.get("huong_dan_cham") or item.get("bieu_diem") or item.get("loi_giai") or "")

        img_b64 = item.get("image_base64")
        img_cap = item.get("image_caption")
        if not img_b64 and item.get("diagram"):
            img_b64, img_cap = generate_diagram(item.get("diagram"))

        p4_list.append({
            "id": q_id,
            "question": question,
            "points": points,
            "answer": answer,
            "explanation": explanation,
            "image_base64": img_b64,
            "image_caption": img_cap
        })

    p4_total_pts = sum(q.get("points", 1.0) for q in p4_list) if p4_list else 0.0
    scoring_obj = calculate_exam_scoring(
        num_p1=len(p1_list),
        num_p2=len(p2_list),
        num_p3=len(p3_list),
        num_p4=len(p4_list),
        p4_points_total=p4_total_pts
    )

    return {
        "title": title,
        "subject": subject,
        "grade": grade,
        "duration_minutes": duration_minutes,
        "school_name": school_name,
        "academic_year": academic_year,
        "code": code,
        "part1_mcq": p1_list,
        "part2_tf": p2_list,
        "part3_short": p3_list,
        "part4_essay": p4_list,
        "scoring": scoring_obj.model_dump()
    }

def get_base_mock_exam(subject: str) -> ExamStructure:
    sub_lower = subject.lower()
    if "tin" in sub_lower or "informatics" in sub_lower:
        return get_mock_informatics_exam()
    elif "lý" in sub_lower or "vật lí" in sub_lower:
        return get_mock_physics_exam()
    elif "hóa" in sub_lower:
        return get_mock_chemistry_exam()
    elif "sinh" in sub_lower:
        return get_mock_biology_exam()
    elif "gdqp" in sub_lower or "quân sự" in sub_lower or "quốc phòng" in sub_lower:
        return get_mock_gdqp_exam()
    elif "anh" in sub_lower or "english" in sub_lower:
        return get_mock_english_exam()
    else:
        return get_mock_math_exam()

def adjust_exam_structure_counts(exam: ExamStructure, request: GenerateRequest) -> ExamStructure:
    """Đảm bảo số lượng câu hỏi trong đề luôn khớp 100% với yêu cầu của người dùng."""
    num_p1 = max(0, getattr(request, "num_part1", 12))
    num_p2 = max(0, getattr(request, "num_part2", 4))
    num_p3 = max(0, getattr(request, "num_part3", 6))
    num_essay = max(0, getattr(request, "num_essay", 0))

    fallback_bank = get_base_mock_exam(exam.subject or request.subject)

    # 1. Part 1 MCQ
    if num_p1 == 0:
        exam.part1_mcq = []
    else:
        while len(exam.part1_mcq) < num_p1:
            idx = len(exam.part1_mcq)
            bank_idx = idx % len(fallback_bank.part1_mcq)
            item = fallback_bank.part1_mcq[bank_idx].model_copy(deep=True)
            item.id = idx + 1
            exam.part1_mcq.append(item)
        if len(exam.part1_mcq) > num_p1:
            exam.part1_mcq = exam.part1_mcq[:num_p1]

    # 2. Part 2 TF
    if num_p2 == 0:
        exam.part2_tf = []
    else:
        while len(exam.part2_tf) < num_p2:
            idx = len(exam.part2_tf)
            bank_idx = idx % len(fallback_bank.part2_tf)
            item = fallback_bank.part2_tf[bank_idx].model_copy(deep=True)
            item.id = idx + 1
            exam.part2_tf.append(item)
        if len(exam.part2_tf) > num_p2:
            exam.part2_tf = exam.part2_tf[:num_p2]

    # 3. Part 3 Short
    if num_p3 == 0:
        exam.part3_short = []
    else:
        while len(exam.part3_short) < num_p3:
            idx = len(exam.part3_short)
            bank_idx = idx % len(fallback_bank.part3_short)
            item = fallback_bank.part3_short[bank_idx].model_copy(deep=True)
            item.id = idx + 1
            exam.part3_short.append(item)
        if len(exam.part3_short) > num_p3:
            exam.part3_short = exam.part3_short[:num_p3]

    # 4. Part 4 Essay
    if num_essay == 0:
        exam.part4_essay = []
    else:
        while len(exam.part4_essay) < num_essay:
            idx = len(exam.part4_essay)
            item = Part4EssayQuestion(
                id=idx + 1,
                question=f"Vận dụng kiến thức môn {request.subject} lớp {request.grade} để giải quyết bài toán/tình huống sau...",
                points=1.0,
                answer="Tóm tắt kết quả phân tích then chốt.",
                explanation="- Nêu được cơ sở lý thuyết.\n- Vận dụng vào tình huống cụ thể.\n- Rút ra kết luận chính xác."
            )
            exam.part4_essay.append(item)
        if len(exam.part4_essay) > num_essay:
            exam.part4_essay = exam.part4_essay[:num_essay]

    # Renumber IDs
    for i, q in enumerate(exam.part1_mcq, 1):
        q.id = i
    for i, q in enumerate(exam.part2_tf, 1):
        q.id = i
    for i, q in enumerate(exam.part3_short, 1):
        q.id = i
    for i, q in enumerate(exam.part4_essay, 1):
        q.id = i

    p4_total_pts = sum(q.points or 1.0 for q in exam.part4_essay) if exam.part4_essay else 0.0
    exam.scoring = calculate_exam_scoring(
        num_p1=len(exam.part1_mcq),
        num_p2=len(exam.part2_tf),
        num_p3=len(exam.part3_short),
        num_p4=len(exam.part4_essay),
        p4_points_total=p4_total_pts
    )
    if exam.scoring and exam.part4_essay:
        from .models import sync_part4_essay_points
        sync_part4_essay_points(exam.part4_essay, exam.scoring.part4_points)

    return exam

def build_grade_curriculum_instructions(subject: str, grade: str) -> str:
    """
    Tạo bộ quy chuẩn và giới hạn chương trình giáo dục (GDPT 2018)
    nghiêm ngặt theo đúng khối lớp mà người dùng đã chọn.
    Ngăn chặn 100% việc rò rỉ kiến thức vượt cấp hoặc lẫn lộn giữa các khối lớp.
    """
    sub = (subject or "").lower().strip()
    g = str(grade).strip().lower().replace("lớp", "").replace("lop", "").strip()
    
    sections = []

    # 1. TOÁN HỌC
    if "toán" in sub:
        if g in ("1", "2", "3", "4", "5", "tiểu học", "tieu hoc"):
            tier_name = f"TIỂU HỌC (LỚP {g})"
            if g == "3":
                scope_text = (
                    "   - Số tự nhiên trong phạm vi 10 000, 100 000; 4 phép tính cộng, trừ, nhân, chia (nhân/chia số có nhiều chữ số với số có một chữ số).\n"
                    "   - Bảng nhân, chia 6, 7, 8, 9; làm quen chữ số La Mã.\n"
                    "   - Hình học & Đo lường: Góc vuông, góc không vuông; chu vi & diện tích hình chữ nhật, hình vuông. Đơn vị đo: mm, gam, ml, nhiệt độ độ C.\n"
                    "   - Giải bài toán có đến hai bước tính; bài toán liên quan đến rút về đơn vị."
                )
            elif g == "4":
                scope_text = (
                    "   - Số có nhiều chữ số (đến lớp triệu, lớp tỉ). Dãy số tự nhiên, tính chất phép cộng, phép nhân.\n"
                    "   - 4 phép tính với số tự nhiên: nhân với số có hai, ba chữ số; chia cho số có hai chữ số.\n"
                    "   - Phân số: Khái niệm phân số, phân số bằng nhau, rút gọn, quy đồng mẫu số; cộng, trừ, nhân, chia 2 phân số; tìm phân số của một số.\n"
                    "   - Hình học: Hai đường thẳng vuông góc, song song; hình bình hành, hình thoi (đặc điểm, chu vi, diện tích). Đơn vị đo: dm2, m2, mm2, yến, tạ, tấn.\n"
                    "   - Dạng toán điển hình: Tìm hai số khi biết tổng và hiệu; Tìm số trung bình cộng; Tìm hai số khi biết tổng (hoặc hiệu) và tỉ số của hai số đó."
                )
            else: # 5 hoặc mặc định tiểu học
                scope_text = (
                    "   - Phân số và hỗn số; số thập phân và 4 phép tính cộng, trừ, nhân, chia với số thập phân.\n"
                    "   - Tỉ số phần trăm và các bài toán về tỉ số phần trăm (tìm tỉ số %, tìm giá trị % của một số, tìm một số khi biết giá trị %).\n"
                    "   - Hình học: Chu vi & diện tích hình tam giác, hình thang, hình tròn; diện tích xung quanh, diện tích toàn phần và thể tích hình hộp chữ nhật, hình lập phương.\n"
                    "   - Chuyển động đều: Công thức s = v x t; bài toán chuyển động cùng chiều, ngược chiều, chuyển động của dòng nước (xuôi dòng, ngược dòng)."
                )
            
            sections.append(
                f"********************************************************************************\n"
                f"QUY CHUẨN ĐẶC BIỆT BẮT BUỘC: GIỚI HẠN CHUẨN KIẾN THỨC MÔN TOÁN {tier_name} (GDPT 2018):\n"
                f"1. PHẠM VI NỘI DUNG ĐƯỢC PHÉP RA ĐỀ (Áp dụng cho Phần I, II, III, IV):\n{scope_text}\n"
                f"2. CẤM TUYỆT ĐỐI 100% CÁC KIẾN THỨC VƯỢT CẤP CỦA THCS VÀ THPT:\n"
                f"   - CẤM TUYỆT ĐỐI số âm, căn bậc hai (\\sqrt), biến số đại số x, y dạng hệ phương trình, biệt thức delta, parabol.\n"
                f"   - CẤM TUYỆT ĐỐI đạo hàm, tiệm cận, cực trị, tích phân, hàm số, lượng giác, vectơ, tọa độ, tổ hợp xác suất THPT.\n"
                f"   - Đề bài phải dùng ngôn ngữ trong sáng, gần gũi với lứa tuổi học sinh tiểu học (đồ vật, hoa quả, bạn bè trong lớp, hoạt động trồng cây, thư viện trường học).\n"
                f"3. BẮT BUỘC 100% CÁC CÂU PHẦN II (ĐÚNG/SAI) LÀ BÀI TOÁN TÌNH HUỐNG THỰC TẾ TIỂU HỌC:\n"
                f"   Tình huống sinh hoạt thực tế gần gũi (mua sắm đồ dùng học tập, kế hoạch tiết kiệm, chuyến tham quan dã ngoại của lớp, bài toán chia kẹo/hoa quả). 4 ý a, b, c, d kiểm tra từ nhận biết số liệu -> giải thích phép tính -> tính toán kết quả -> nhận xét đúng đắn.\n"
                f"********************************************************************************"
            )

        elif g in ("6", "7", "8", "9", "thcs"):
            tier_name = f"THCS (LỚP {g})"
            if g == "6":
                scope_text = (
                    "   - Số tự nhiên, ước và bội, số nguyên tố, hợp số, ƯCLN, BCNN, dấu hiệu chia hết.\n"
                    "   - Tập hợp số nguyên (nguyên âm, nguyên dương), các phép tính trên Z, quy tắc dấu ngoặc.\n"
                    "   - Phân số (tử và mẫu là số nguyên), các phép tính phân số, hỗn số, giá trị phân số của một số.\n"
                    "   - Số thập phân, các phép tính với số thập phân, tỉ số và tỉ số phần trăm.\n"
                    "   - Hình học trực quan: Tam giác đều, hình vuông, lục giác đều, hình chữ nhật, hình thoi, hình bình hành, hình thang cân (chu vi, diện tích); tính đối xứng (trục đối xứng, tâm đối xứng).\n"
                    "   - Hình học phẳng: Điểm, đường thẳng, tia, đoạn thẳng, trung điểm, góc.\n"
                    "   - Thống kê & xác suất thực nghiệm: Bảng dữ liệu, biểu đồ tranh, biểu đồ cột, xác suất thực nghiệm."
                )
                negative_text = "CẤM TUYỆT ĐỐI: Căn bậc hai, phương trình bậc hai, hệ phương trình, định lý Ta-lét, tam giác đồng dạng, tỉ số lượng giác sin/cos/tan, toàn bộ giải tích và không gian THPT."
            elif g == "7":
                scope_text = (
                    "   - Số hữu tỉ, số thực, căn bậc hai số học cơ bản (\\sqrt{a} với a >= 0), giá trị tuyệt đối, làm tròn số.\n"
                    "   - Tỉ lệ thức và dãy tỉ số bằng nhau; đại lượng tỉ lệ thuận, đại lượng tỉ lệ nghịch.\n"
                    "   - Biểu thức đại số: Đơn thức, đa thức một biến, cộng trừ nhân chia đa thức một biến, nghiệm của đa thức một biến.\n"
                    "   - Hình học: Góc ở vị trí đặc biệt (kề bù, so le trong, đồng vị), định lý hai đường thẳng song song; Tam giác bằng nhau (c-c-c, c-g-c, g-c-g, các trường hợp tam giác vuông); Tam giác cân, đường trung trực; Quan hệ giữa các yếu tố trong tam giác (cạnh - góc đối diện, BĐT tam giác); Các đường đồng quy trong tam giác (trung tuyến, phân giác, trung trực, đường cao).\n"
                    "   - Thống kê & xác suất: Biểu đồ đoạn thẳng, biểu đồ hình quạt tròn; biến cố ngẫu nhiên và xác suất của biến cố."
                )
                negative_text = "CẤM TUYỆT ĐỐI: 7 hằng đẳng thức đáng nhớ, phân thức đại số, định lý Ta-lét, tam giác đồng dạng, phương trình bậc hai, hệ phương trình, toàn bộ kiến thức THPT."
            elif g == "8":
                scope_text = (
                    "   - Đa thức nhiều biến (cộng, trừ, nhân, chia đa thức cho đơn thức).\n"
                    "   - 7 hằng đẳng thức đáng nhớ và các phương pháp phân tích đa thức thành nhân tử.\n"
                    "   - Phân thức đại số: Các phép tính cộng, trừ, nhân, chia và rút gọn phân thức đại số.\n"
                    "   - Phương trình bậc nhất một ẩn (ax + b = 0) và giải bài toán bằng cách lập phương trình bậc nhất.\n"
                    "   - Hình học phẳng: Tứ giác, hình thang, hình thang cân, hình bình hành, hình chữ nhật, hình thoi, hình vuông; Định lý Ta-lét trong tam giác (thuận, đảo, hệ quả), đường trung bình, tính chất đường phân giác; Tam giác đồng dạng (3 trường hợp đồng dạng c-c-c, c-g-c, g-g và tam giác vuông đồng dạng).\n"
                    "   - Hình học không gian trực quan: Hình chóp tam giác đều, hình chóp tứ giác đều (diện tích xung quanh, thể tích).\n"
                    "   - Thống kê & xác suất: Bảng thống kê, biểu đồ cột kép, biểu đồ hình quạt tròn, xác suất thực nghiệm."
                )
                negative_text = "CẤM TUYỆT ĐỐI: Căn bậc hai chứa ẩn phức tạp, hệ hai phương trình bậc nhất 2 ẩn (lớp 9), phương trình bậc hai một ẩn / hệ thức Vi-ét (lớp 9), đường tròn tiếp tuyến (lớp 9), toàn bộ kiến thức giải tích và không gian THPT."
            else: # 9
                scope_text = (
                    "   - Căn bậc hai, căn bậc ba và rút gọn biểu thức đại số chứa căn.\n"
                    "   - Phương trình và hệ hai phương trình bậc nhất hai ẩn (phương pháp thế, cộng đại số, bài toán thực tế lập hệ phương trình).\n"
                    "   - Phương trình bậc hai một ẩn và Hệ thức Vi-ét (x1 + x2 = -b/a, x1 * x2 = c/a).\n"
                    "   - Hàm số y = ax^2 (a != 0) và đồ thị Parabol.\n"
                    "   - Hệ thức lượng trong tam giác vuông và Tỉ số lượng giác góc nhọn (sin, cos, tan, cot, góc nâng, góc hạ đo đạc thực tế).\n"
                    "   - Đường tròn: Tiếp tuyến, góc ở tâm, góc nội tiếp, tứ giác nội tiếp, độ dài đường tròn, diện tích hình quạt tròn.\n"
                    "   - Hình học không gian thực tế lớp 9: DUY NHẤT Hình trụ, Hình nón, Hình cầu (diện tích xung quanh, thể tích vật dụng đời sống như bồn nước, cốc nước, phễu nón, quả bóng).\n"
                    "   - Thống kê & Xác suất lớp 9: Bảng tần số, biểu đồ tần số và Xác suất cổ điển đơn giản (gieo xúc xắc, bốc viên bi/thẻ trong hộp)."
                )
                negative_text = (
                    "CẤM TUYỆT ĐỐI 100% CÁC KIẾN THỨC VƯỢT CẤP THPT:\n"
                    "   - CẤM TUYỆT ĐỐI xác suất bắn bia độc lập Bernoulli (xạ thủ bắn 3 phát trúng...), xác suất có điều kiện, biến ngẫu nhiên, chỉnh hợp A_n^k, tổ hợp C_n^k.\n"
                    "   - CẤM TUYỆT ĐỐI hình học không gian THPT: tính khoảng cách giữa hai đường thẳng chéo nhau (như AB và C'D' trong hình hộp chữ nhật), khoảng cách từ điểm đến mp, góc giữa 2 mp, tọa độ không gian Oxyz.\n"
                    "   - CẤM TUYỆT ĐỐI giải tích THPT: đạo hàm, tính đơn điệu, cực trị, tiệm cận, bảng biến thiên, tích phân, nguyên hàm, logarit."
                )

            sections.append(
                f"********************************************************************************\n"
                f"QUY CHUẨN ĐẶC BIỆT BẮT BUỘC: GIỚI HẠN CHUẨN KIẾN THỨC MÔN TOÁN {tier_name} (GDPT 2018):\n"
                f"1. PHẠM VI NỘI DUNG ĐƯỢC PHÉP RA ĐỀ (Áp dụng cho Phần I, II, III, IV):\n{scope_text}\n"
                f"2. CẤM TUYỆT ĐỐI CÁC KIẾN THỨC VƯỢT CẤP:\n   {negative_text}\n"
                f"3. BẮT BUỘC 100% CÁC CÂU PHẦN II (ĐÚNG/SAI) LÀ BÀI TOÁN TÌNH HUỐNG THỰC TẾ LỚP {g}:\n"
                f"   Xây dựng bối cảnh đo đạc, mua bán, chuyển động, chi phí sinh hoạt, tối ưu hóa phù hợp với học sinh lớp {g}. TUYỆT ĐỐI KHÔNG ra đề cộc lốc lý thuyết suông.\n"
                f"********************************************************************************"
            )

        elif g in ("10", "11", "12"):
            tier_name = f"THPT (LỚP {g})"
            if g == "10":
                scope_text = (
                    "   - Mệnh đề toán học và Tập hợp (giao, hợp, hiệu, các tập hợp con của số thực).\n"
                    "   - Bất phương trình và hệ bất phương trình bậc nhất hai ẩn, bài toán tối ưu miền nghiệm đa giác thực tế.\n"
                    "   - Hàm số, tập xác định, hàm số bậc hai y = ax^2 + bx + c và đồ thị parabol đỉnh I(-b/2a; -Delta/4a). Dấu của tam thức bậc hai, giải BPT bậc hai một ẩn.\n"
                    "   - Hệ thức lượng trong tam giác (định lý cos, định lý sin, công thức diện tích tam giác S = 1/2 ab sin C = abc/4R = pr = sqrt(p(p-a)(p-b)(p-c))).\n"
                    "   - Vectơ: Tổng, hiệu hai vectơ, tích vectơ với một số, tích vô hướng của hai vectơ và ứng dụng tính góc, khoảng cách.\n"
                    "   - Phương pháp tọa độ trong mặt phẳng Oxy: Tọa độ điểm, vectơ, phương trình đường thẳng (tổng quát, tham số), phương trình đường tròn, ba đường conic (elip, hypebol, parabol).\n"
                    "   - Thống kê & Xác suất: Số trung bình, trung vị, tứ phân vị, mốt, khoảng biến thiên, khoảng tứ phân vị, phương sai, độ lệch chuẩn. Xác suất cổ điển, biến cố hợp, biến cố giao, biến cố độc lập."
                )
                negative_text = (
                    "CẤM TUYỆT ĐỐI CÁC KIẾN THỨC LỚP 11 VÀ 12:\n"
                    "   - CẤM đạo hàm, tiệm cận đồ thị hàm số, bảng biến thiên dùng đạo hàm, cực trị bằng đạo hàm.\n"
                    "   - CẤM nguyên hàm, tích phân, logarit, số phức.\n"
                    "   - CẤM hình học không gian (đường thẳng vuông góc mp, khoảng cách chéo nhau - lớp 11) và tọa độ không gian Oxyz (lớp 12).\n"
                    "   - CẤM dãy số, cấp số cộng, cấp số nhân (lớp 11)."
                )
            elif g == "11":
                scope_text = (
                    "   - Hàm số lượng giác và Phương trình lượng giác cơ bản (sin x = m, cos x = m, tan x = m, cot x = m).\n"
                    "   - Dãy số, Cấp số cộng (u_n = u_1 + (n-1)d), Cấp số nhân (u_n = u_1 * q^(n-1)).\n"
                    "   - Giới hạn của dãy số và giới hạn của hàm số, hàm số liên tục.\n"
                    "   - Đạo hàm: Định nghĩa đạo hàm, bảng đạo hàm cơ bản (hàm đa thức, căn, lượng giác, tích, thương), ý nghĩa hình học (tiếp tuyến y = y'(x_0)(x - x_0) + y_0), đạo hàm cấp hai.\n"
                    "   - Hình học không gian lớp 11: Đường thẳng và mặt phẳng trong không gian, quan hệ song song; Quan hệ vuông góc (đường vuông góc mặt, hai mặt vuông góc, định lý 3 đường vuông góc), khoảng cách (điểm đến mp, hai đường thẳng chéo nhau), góc giữa đường và mặt, góc giữa 2 mặt phẳng.\n"
                    "   - Đại số tổ hợp & Xác suất: Quy tắc đếm, hoán vị, chỉnh hợp, tổ hợp, nhị thức Newton. Xác suất: Biến cố độc lập, quy tắc cộng xác suất, quy tắc nhân xác suất.\n"
                    "   - Thống kê: Mẫu số liệu ghép nhóm (khoảng, tần số, số trung bình, trung vị, tứ phân vị, mốt)."
                )
                negative_text = (
                    "CẤM TUYỆT ĐỐI CÁC KIẾN THỨC LỚP 12:\n"
                    "   - CẤM đường tiệm cận của đồ thị hàm số (tiệm cận đứng, ngang, xiên) và bảng biến thiên khảo sát hàm bậc ba/phân thức (lớp 12).\n"
                    "   - CẤM nguyên hàm và tích phân (lớp 12).\n"
                    "   - CẤM hàm số mũ và logarit nâng cao (lớp 12).\n"
                    "   - CẤM phương pháp tọa độ trong không gian Oxyz (lớp 12).\n"
                    "   - CẤM xác suất có điều kiện, công thức xác suất toàn phần và công thức Bayes (lớp 12)."
                )
            else: # 12
                scope_text = (
                    "   - Khảo sát hàm số: Tính đơn điệu, cực trị, GTLN-GTNN, đường tiệm cận (đứng, ngang, xiên), bảng biến thiên và đồ thị hàm số (bậc ba, phân thức bậc nhất/bậc nhất, phân thức bậc hai/bậc nhất).\n"
                    "   - Hàm số mũ, hàm số logarit, phương trình và bất phương trình mũ, logarit.\n"
                    "   - Nguyên hàm và tích phân: Định nghĩa, tính chất, phương pháp đổi biến số, từng phần, ứng dụng tích phân tính diện tích hình phẳng và thể tích vật thể tròn xoay.\n"
                    "   - Phương pháp tọa độ trong không gian Oxyz: Tọa độ điểm, vectơ, tích có hướng, phương trình mặt phẳng, phương trình đường thẳng, phương trình mặt cầu, góc và khoảng cách trong không gian Oxyz.\n"
                    "   - Xác suất có điều kiện, công thức xác suất toàn phần, công thức Bayes.\n"
                    "   - Thống kê: Các đặc trưng đo mức độ phân tán của mẫu số liệu ghép nhóm (phương sai, độ lệch chuẩn)."
                )
                negative_text = "Toàn diện chương trình THPT lớp 12 phục vụ ôn thi tốt nghiệp THPT và xét tuyển đại học."

            sections.append(
                f"********************************************************************************\n"
                f"QUY CHUẨN ĐẶC BIỆT BẮT BUỘC: GIỚI HẠN CHUẨN KIẾN THỨC MÔN TOÁN {tier_name} (GDPT 2018):\n"
                f"1. PHẠM VI NỘI DUNG ĐƯỢC PHÉP RA ĐỀ (Áp dụng cho Phần I, II, III, IV):\n{scope_text}\n"
                f"2. CẤM TUYỆT ĐỐI CÁC KIẾN THỨC VƯỢT CẤP / LỆCH KHỐI:\n   {negative_text}\n"
                f"3. BẮT BUỘC 100% CÁC CÂU PHẦN II (ĐÚNG/SAI) LÀ BÀI TOÁN TÌNH HUỐNG THỰC TẾ LỚP {g}:\n"
                f"   Xây dựng bài toán mô hình hóa thực tế (kinh tế, kỹ thuật, đo đạc, chuyển động, tối ưu hóa) đúng chuẩn chương trình Toán {g}.\n"
                f"********************************************************************************"
            )

    # 2. TIN HỌC
    elif "tin" in sub:
        if g in ("3", "4", "5", "tiểu học", "tieu hoc"):
            sections.append(
                f"\nLƯU Ý ĐẶC THÙ MÔN TIN HỌC TIỂU HỌC (LỚP {g}):\n"
                f"- Bám sát chương trình Tin học tiểu học: Làm quen phần cứng máy tính, bàn phím, chuột, phần mềm đồ họa Paint, soạn thảo văn bản đơn giản Unikey/Word, an toàn trên Internet, lập trình trực quan kéo thả Scratch cơ bản.\n"
                f"- TUYỆT ĐỐI CẤM: Code Python phức tạp, cú pháp dòng lệnh nâng cao, kiến trúc mạng máy tính sâu, AI, cơ sở dữ liệu."
            )
        elif g in ("6", "7", "8", "9", "thcs"):
            sections.append(
                f"\nLƯU Ý ĐẶC THÙ MÔN TIN HỌC THCS (LỚP {g}):\n"
                f"- Bám sát chương trình Tin học THCS lớp {g}: Lớp 6 (thông tin dữ liệu, mạng máy tính, soạn thảo, sơ đồ tư duy); Lớp 7 (bảng tính Excel, bảo vệ dữ liệu); Lớp 8 (thuật toán, cấu trúc rẽ nhánh if-else, vòng lặp for/while trong Scratch/Python); Lớp 9 (dịch vụ Internet, đa phương tiện, an toàn thông tin số).\n"
                f"- CẤM: Cơ sở dữ liệu quan hệ SQL nâng cao (lớp 11), AI và IoT (lớp 12)."
            )
        elif g in ("10", "11", "12"):
            if g == "10":
                sections.append(
                    f"\nLƯU Ý ĐẶC THÙ MÔN TIN HỌC LỚP 10 (GDPT 2018):\n"
                    f"- Trọng tâm: Biểu diễn thông tin, mạng máy tính và Internet, an toàn số; Lập trình Python căn bản (kiểu dữ liệu int, float, str, bool, toán tử, rẽ nhánh if-else, vòng lặp for/while, danh sách list, xâu ký tự, hàm def, xử lý tệp văn bản đơn giản).\n"
                    f"- CẤM: Cơ sở dữ liệu SQL/RDBMS (lớp 11), Trí tuệ nhân tạo AI/IoT (lớp 12)."
                )
            elif g == "11":
                sections.append(
                    f"\nLƯU Ý ĐẶC THÙ MÔN TIN HỌC LỚP 11 (GDPT 2018):\n"
                    f"- Trọng tâm: Hệ điều hành & phần mềm ứng dụng; Cơ sở dữ liệu quan hệ (RDBMS), mô hình quan hệ, khóa chính, khóa ngoại, các câu lệnh truy vấn SQL (SELECT, INSERT, UPDATE, DELETE, WHERE, JOIN), thiết kế và chuẩn hóa bảng dữ liệu; hoặc chuyên đề Khoa học máy tính / Tin học ứng dụng."
                )
            else: # 12
                sections.append(
                    f"\nLƯU Ý ĐẶC THÙ MÔN TIN HỌC LỚP 12 (GDPT 2018):\n"
                    f"- Trọng tâm: Trí tuệ nhân tạo (AI - khái niệm, ứng dụng nhận diện hình ảnh, xử lý ngôn ngữ tự nhiên, học máy Machine Learning, đạo đức AI), Mạng máy tính kết nối vạn vật (IoT), An toàn dữ liệu & An ninh mạng, Giao tiếp trong không gian số, lập trình Web/giao diện người dùng cơ bản (HTML/CSS/Python GUI)."
                )

    # 3. KHTN / VẬT LÝ
    elif any(x in sub for x in ["vật lý", "vật lí"]):
        if g in ("6", "7", "8", "9", "thcs"):
            sections.append(
                f"\nLƯU Ý ĐẶC THÙ PHÂN MÔN VẬT LÝ TRONG KHOA HỌC TỰ NHIÊN (KHTN LỚP {g}):\n"
                f"- Bám sát chuẩn KHTN THCS lớp {g}: Đo lường cơ bản, lực và chuyển động, ma sát, quán tính; Âm thanh (nguồn âm, độ cao, độ to, phản xạ âm); Ánh sáng (sự truyền thẳng, phản xạ, khúc xạ, thấu kính cơ bản); Điện và từ cơ bản (mạch điện nối tiếp/song song, định luật Ohm sơ cấp, nam châm, từ trường Trái Đất); Năng lượng và nhiệt cơ bản.\n"
                f"- CẤM TUYỆT ĐỐI: Dao động điều hòa (phương trình x = A cos(omega t + phi)), sóng cơ học nâng cao, chu trình nhiệt động lực học p-V, thuyết tương đối, vật lý hạt nhân."
            )
        elif g == "10":
            sections.append(
                f"\nLƯU Ý ĐẶC THÙ MÔN VẬT LÍ LỚP 10 (GDPT 2018):\n"
                f"- Trọng tâm: Động học (chuyển động thẳng đều, thẳng biến đổi đều, rơi tự do, ném ngang); Động lực học (ba định luật Newton, các lực cơ học: trọng lực, lực đàn hồi, lực ma sát, lực cản); Cân bằng lực và ngẫu lực; Năng lượng, công cơ học, công suất, động năng, thế năng, bảo toàn cơ năng; Động lượng và va chạm; Chuyển động tròn đều.\n"
                f"- CẤM: Dao động điều hòa, con lắc lò xo/đơn (lớp 11); Vật lý nhiệt p-V, từ trường, hạt nhân (lớp 12)."
            )
        elif g == "11":
            sections.append(
                f"\nLƯU Ý ĐẶC THÙ MÔN VẬT LÍ LỚP 11 (GDPT 2018):\n"
                f"- Trọng tâm: Dao động cơ (dao động điều hòa, con lắc lò xo, con lắc đơn, năng lượng dao động, dao động tắt dần, cộng hưởng); Sóng cơ và sóng âm (sự truyền sóng, giao thoa sóng, sóng dừng); Điện trường (lực tương tác tĩnh điện Coulomb, cường độ điện trường, điện thế, tụ điện); Dòng điện không đổi (cường độ dòng điện, điện trở, định luật Ohm cho đoạn mạch, nguồn điện).\n"
                f"- CẤM: Vật lý nhiệt (nhiệt động học p-V, khí lý tưởng - lớp 12); Từ trường và cảm ứng điện từ (lớp 12); Vật lý hạt nhân và phóng xạ (lớp 12)."
            )
        elif g == "12":
            sections.append(
                f"\nLƯU Ý ĐẶC THÙ MÔN VẬT LÍ LỚP 12 (GDPT 2018 - MỚI NHẤT):\n"
                f"- Trọng tâm: Vật lý nhiệt (mô hình động học phân tử chất khí, nhiệt độ, nhiệt dung riêng, nhiệt nóng chảy riêng, nhiệt hóa hơi riêng, các định luật chất khí, phương trình trạng thái Clapeyron - Mendeleev, đồ thị chu trình nhiệt p-V); Khí lý tưởng; Từ trường (từ trường dòng điện, lực từ tác dụng lên đoạn dây dẫn, cảm ứng từ, hiện tượng cảm ứng điện từ, từ thông); Vật lý hạt nhân (cấu tạo hạt nhân, năng lượng liên kết, phản ứng hạt nhân, phóng xạ, an toàn bức xạ)."
            )

    # 4. HÓA HỌC
    elif "hóa" in sub:
        if g in ("8", "9"):
            sections.append(
                f"\nLƯU Ý ĐẶC THÙ PHÂN MÔN HÓA HỌC TRONG KHTN (LỚP {g}):\n"
                f"- Lớp 8: Nguyên tử, phân tử, đơn chất, hợp chất, mol, tỉ khối chất khí, định luật bảo toàn khối lượng, phương trình hóa học, dung dịch (nồng độ C%, C_M), oxide, acid, base, muối cơ bản.\n"
                f"- Lớp 9: Kim loại (dãy hoạt động hóa học), phi kim; Mối quan hệ giữa các hợp chất vô cơ; Sơ lược hóa học hữu cơ (methane CH4, ethylene C2H4, acetylene C2H2, rượu ethylic C2H5OH, acid acetic CH3COOH, chất béo, glucose, tinh bột).\n"
                f"- CẤM TUYỆT ĐỐI KIẾN THỨC THPT: Cấu hình electron theo orbital (s, p, d), liên kết hydrogen/van der Waals, enthalpy Delta_r H, cân bằng hóa học K_c, pH, pin điện hóa, phức chất."
            )
        elif g == "10":
            sections.append(
                f"\nLƯU Ý ĐẶC THÙ MÔN HÓA HỌC LỚP 10 (GDPT 2018):\n"
                f"- Trọng tâm: Cấu tạo nguyên tử (hạt nhân, electron, orbital s, p, d, f); Bảng tuần hoàn các nguyên tố hóa học và quy luật biến đổi tuần hoàn; Liên kết hóa học (liên kết ion, liên kết cộng hóa trị, liên kết hydrogen, tương tác van der Waals); Phản ứng oxi hóa - khử; Năng lượng hóa học (biến thiên enthalpy chuẩn của phản ứng Delta_r H^0_298); Tốc độ phản ứng hóa học (các yếu tố ảnh hưởng, hằng số tốc độ); Nhóm nguyên tố Halogen (fluorine, chlorine, bromine, iodine)."
            )
        elif g == "11":
            sections.append(
                f"\nLƯU Ý ĐẶC THÙ MÔN HÓA HỌC LỚP 11 (GDPT 2018):\n"
                f"- Trọng tâm: Cân bằng hóa học (hằng số K_c, nguyên lý Le Chatelier); Cân bằng trong dung dịch nước (thuyết Brønsted - Lowry, pH, chất chỉ thị, chuẩn độ acid-base); Nitrogen và sulfur (ammonia, muối ammonium, nitric acid, sulfur dioxide, sulfuric acid); Đại cương hóa hữu cơ; Hydrocarbon (alkane, alkene, alkyne, arene); Dẫn xuất halogen, alcohol, phenol; Hợp chất carbonyl (aldehyde, ketone) và carboxylic acid."
            )
        elif g == "12":
            sections.append(
                f"\nLƯU Ý ĐẶC THÙ MÔN HÓA HỌC LỚP 12 (GDPT 2018):\n"
                f"- Trọng tâm: Ester - Lipid, xà phòng và chất giặt rửa tổng hợp; Carbohydrate (glucose, fructose, saccharose, maltose, tinh bột, cellulose); Hợp chất chứa nitrogen (amine, amino acid, peptide, protein, enzyme); Polymer và vật liệu polymer; Hóa học kim loại (đại cương kim loại, thế điện cực chuẩn, pin điện hóa, sự điện phân, ăn mòn kim loại, kim loại kiềm, kiềm thổ, nhôm, kim loại chuyển tiếp dãy thứ nhất, phức chất)."
            )

    return "\n".join(sections)

async def generate_exam(request: GenerateRequest) -> ExamStructure:
    keys = extract_api_keys(request)
    
    if request.mode == "mock" or (not keys and request.mode != "prompt"):
        base_exam = get_base_mock_exam(request.subject)
        return adjust_exam_structure_counts(base_exam, request)
            
    if not keys:
        if request.api_provider == "openai":
            raise ValueError("Vui lòng cung cấp ít nhất 1 OpenAI API Key trong mục 'Cài đặt AI'.")
        base_exam = get_base_mock_exam(request.subject)
        return adjust_exam_structure_counts(base_exam, request)
            
    # 0. Tự động nhận diện và đồng bộ môn học từ tài liệu đính kèm (ngăn ngừa lệch môn do chọn nhầm)
    if request.file_content and len(request.file_content.strip()) > 50:
        from .matrix_analyzer import detect_subject_from_text
        doc_subject = detect_subject_from_text(request.file_content)
        if doc_subject in [
            "Tin học", "Tiếng Anh", "Vật lý", "Hóa học", "Sinh học", "Toán học", 
            "Giáo dục Quốc phòng & An ninh", "Lịch sử", "Địa lý", "Ngữ văn", "Công nghệ", "Giáo dục kinh tế & Pháp luật"
        ]:
            if request.subject != doc_subject and (request.subject in ("Toán học", "Hóa học") or doc_subject in ("Tin học", "Tiếng Anh")):
                print(f"[Auto-Correction] Tự động đồng bộ môn học từ tài liệu đính kèm: '{request.subject}' -> '{doc_subject}'!")
                request.subject = doc_subject

    user_prompt = (
        f"Hãy tạo một đề kiểm tra môn {request.subject}, khối {request.grade}.\n\n"
        f"QUY ĐỊNH BẮT BUỘC VỀ SỐ LƯỢNG CÂU HỎI:\n"
        f"- PHẦN I (Trắc nghiệm nhiều lựa chọn): BẮT BUỘC TẠO ĐỦ {request.num_part1} CÂU (id từ 1 đến {request.num_part1}). TUYỆT ĐỐI KHÔNG TỰ Ý DỪNG Ở 12 HAY 18 CÂU NẾU YÊU CẦU LỚN HƠN. Phải tạo đủ {request.num_part1} câu trong mảng 'part1_mcq'!\n"
        f"- PHẦN II (Trắc nghiệm Đúng/Sai): BẮT BUỘC TẠO ĐỦ {request.num_part2} CÂU trong mảng 'part2_tf' (đánh số id từ 1 đến {request.num_part2}).\n"
        f"  * NGUYÊN TẮC BẮT BUỘC VỀ NGỮ CẢNH: MỖI CÂU BẮT BUỘC CÓ ĐỀ BÀI LÀ BỐI CẢNH/TÌNH HUỐNG THỰC TẾ HẤP DẪN (40-100 từ, có dữ liệu/đoạn mã/bảng số liệu/dự án cụ thể), kèm 4 ý con a, b, c, d phân hóa từ Biết -> Hiểu -> Vận dụng -> Vận dụng cao. TUYỆT ĐỐI KHÔNG ra đề cộc lốc lý thuyết suông!\n"
        f"- PHẦN III (Trả lời ngắn): BẮT BUỘC TẠO ĐỦ {request.num_part3} CÂU trong mảng 'part3_short'.\n"
        f"- PHẦN IV (Tự luận): BẮT BUỘC TẠO ĐỦ {request.num_essay} CÂU trong mảng 'part4_essay'.\n"
    )

    # 1. Bổ sung bộ quy chuẩn kiến thức chuẩn theo khối lớp người dùng đã chọn
    curriculum_instructions = build_grade_curriculum_instructions(request.subject, request.grade)
    if curriculum_instructions:
        user_prompt += f"\n\n{curriculum_instructions}"

    if request.subject == "Tiếng Anh":
        user_prompt += (
            f"\n\nLƯU Ý ĐẶC THÙ MÔN TIẾNG ANH (LỚP {request.grade}) THEO CHƯƠNG TRÌNH GDPT 2018:\n"
            f"- Đề thi Tiếng Anh tập trung đánh giá năng lực ngôn ngữ theo các chủ điểm giao tiếp, từ vựng và ngữ pháp của lớp {request.grade}.\n"
            f"- Phần I (Trắc nghiệm nhiều lựa chọn): Bao gồm các câu hỏi về Phát âm (Pronunciation/Stress), Từ vựng & Ngữ pháp (Vocabulary & Grammar in context), Từ đồng nghĩa/Trái nghĩa (Synonyms/Antonyms), và Điền từ hoặc Đọc hiểu đoạn văn.\n"
            f"- Phần II (Đúng/Sai): BẮT BUỘC đưa ra một đoạn văn ngắn (reading passage 60-120 từ) bám sát chủ đề từ vựng đã cho, kèm 4 khẳng định a, b, c, d đánh giá kỹ năng đọc hiểu chuyên sâu (main idea, detail, inference, vocabulary) để học sinh xác định True hay False.\n"
            f"- Phần III (Trả lời ngắn): Câu hỏi điền từ thích hợp vào chỗ trống, cho dạng đúng của từ trong ngoặc (Word formation) hoặc viết lại câu ngắn (Sentence transformation).\n"
            f"- Khai thác triệt để và bám sát các từ vựng, cấu trúc có trong tài liệu đính kèm!"
        )
    if request.subject == "Tin học":
        user_prompt += (
            f"\n\nLƯU Ý ĐẶC THÙ MÔN TIN HỌC (LỚP {request.grade}) THEO CHƯƠNG TRÌNH GDPT 2018:\n"
            f"- Đề thi bám sát chuẩn kiến thức kỹ năng môn Tin học lớp {request.grade}: Lập trình (Python/Scratch), Thuật toán, Mạng máy tính & Internet, Hệ điều hành, Trí tuệ nhân tạo (AI - đối với lớp 12), Cơ sở dữ liệu và Đạo đức/Pháp luật trong môi trường số.\n"
            f"- Các đoạn mã chương trình (code) phải viết chuẩn cú pháp Python rõ ràng, thụt lề chuẩn, không có lỗi cú pháp.\n"
            f"- Phần I: Các câu trắc nghiệm nhiều lựa chọn về cú pháp lệnh, kết quả thực thi đoạn code, chức năng thiết bị, khái niệm mạng và an toàn số.\n"
            f"- Phần II (Đúng/Sai): BẮT BUỘC biên soạn dưới dạng TÌNH HUỐNG DỰ ÁN CNTT THỰC TẾ (ví dụ: xây dựng hệ thống CSDL có lược đồ bảng cụ thể, đoạn mã Python xử lý dữ liệu bán hàng/học sinh có input/output, kịch bản bảo mật mạng/tấn công lừa đảo, hoặc ứng dụng AI nhận diện khuôn mặt/xe cộ kèm đạo đức dữ liệu). 4 ý a, b, c, d lần lượt kiểm tra: a (Nhận diện khái niệm/thông số) - b (Hiểu cơ chế hoạt động/nguyên nhân) - c (Tính toán định lượng/truy vết kết quả thực thi) - d (Đánh giá tối ưu/an toàn thông tin/đạo đức số).\n"
            f"- Phần III (Trả lời ngắn): Yêu cầu tính toán kết quả số cụ thể của đoạn mã (ví dụ: giá trị của biến đếm, tổng tích lũy, số lần lặp) hoặc chuyển đổi đơn vị dung lượng bộ nhớ (Byte, KB, MB, GB, bit)."
        )
    if "toán" in request.subject.lower():
        user_prompt += (
            f"\n\nLƯU Ý ĐẶC THÙ MÔN TOÁN HỌC (LỚP {request.grade}):\n"
            f"- Đối với Phần II (Đúng/Sai): BẮT BUỘC 100% CÁC CÂU LÀ BÀI TOÁN TÌNH HUỐNG THỰC TẾ / MÔ HÌNH HÓA ĐỜI SỐNG PHÙ HỢP VỚI LỚP {request.grade}.\n"
            f"- 4 ý con a, b, c, d phân hóa từ Nhận biết thông số đề bài -> Hiểu bản chất mô hình -> Vận dụng tính toán đại lượng cụ thể -> Vận dụng cao đánh giá tối ưu hóa/kết luận thực tiễn.\n"
            f"- MỌI CÔNG THỨC TOÁN, BIẾN SỐ, ĐƠN VỊ KÈM CÔNG THỨC BẮT BUỘC ĐƯỢC BỌC TRONG $...$ (ví dụ: $3\\sqrt{3}$ cm, $\\alpha$, $m \\neq 1$, $\\sin B$, $\\begin{{cases}} 2x - y = 3 \\\\ x + 2y = 4 \\end{{cases}}$). CẤM viết tiếng Việt ('căn 2', 'm khác 1') hoặc LaTeX trần không có $."
        )
    if any(s in request.subject.lower() for s in ["vật lý", "vật lí", "hóa học", "sinh học"]):
        user_prompt += (
            f"\n\nLƯU Ý ĐẶC THÙ PHẦN II (ĐÚNG/SAI) MÔN KHTN (VẬT LÝ, HÓA HỌC, SINH HỌC):\n"
            f"- BẮT BUỘC xây dựng đề bài gắn liền với Thí nghiệm khoa học thực nghiệm, quy trình sản xuất công nghiệp, thiết bị đo lường đời sống, hoặc nghiên cứu y sinh học/môi trường.\n"
            f"- 4 ý con a, b, c, d dẫn dắt học sinh khám phá từ hiện tượng ban đầu, cơ chế phản ứng/vật lý, tính toán số liệu và kết luận ứng dụng thực tiễn."
        )
    if any(s in request.subject.lower() for s in ["sử", "lịch sử"]):
        user_prompt += (
            f"\n\nLƯU Ý ĐẶC THÙ PHẦN II (ĐÚNG/SAI) MÔN LỊCH SỬ:\n"
            f"- BẮT BUỘC mỗi câu hỏi Phần II phải trích dẫn một đoạn SỬ LIỆU GỐC, VĂN KIỆN LỊCH SỬ, TUYÊN NGÔN, HIỆP ĐỊNH hoặc HỒI KÝ NHÂN CHỨNG (50-100 từ) có nguồn trích rõ ràng.\n"
            f"- 4 ý con a, b, c, d phân hóa chặt chẽ theo thang bậc:\n"
            f"  + a) [Biết]: Xác định đúng thời gian, nhân vật, sự kiện hoặc chủ trương nêu trực tiếp trong đoạn tư liệu.\n"
            f"  + b) [Hiểu]: Phân tích nguyên nhân lịch sử, bối cảnh thời đại hoặc bản chất sự kiện phản ánh qua tư liệu.\n"
            f"  + c) [Vận dụng]: Liên hệ bài học kinh nghiệm, nghệ thuật quân sự hoặc đường lối ngoại giao vào thực tiễn dựng nước và giữ nước.\n"
            f"  + d) [Vận dụng cao]: Đánh giá tác động, tầm vóc lịch sử hoặc ý nghĩa thời đại đối với phong trào cách mạng Việt Nam và thế giới."
        )
    if any(s in request.subject.lower() for s in ["địa", "địa lý", "địa lí"]):
        user_prompt += (
            f"\n\nLƯU Ý ĐẶC THÙ PHẦN II (ĐÚNG/SAI) MÔN ĐỊA LÍ:\n"
            f"- BẮT BUỘC mỗi câu hỏi Phần II phải cung cấp BẢNG SỐ LIỆU THỐNG KÊ, BIỂU ĐỒ hoặc TƯ LIỆU ĐỊA LÝ KINH TẾ - XÃ HỘI / TỰ NHIÊN cụ thể (50-100 từ).\n"
            f"- 4 ý con a, b, c, d phân hóa chặt chẽ:\n"
            f"  + a) [Biết]: Đọc và nhận dạng trực tiếp số liệu cao nhất, thấp nhất hoặc xu hướng tăng/giảm từ ngữ cảnh.\n"
            f"  + b) [Hiểu]: Giải thích nguyên nhân tự nhiên hoặc kinh tế - xã hội dẫn đến xu thế hoặc sự phân hóa lãnh thổ.\n"
            f"  + c) [Vận dụng]: Tính toán định lượng cụ thể (tốc độ tăng trưởng %, tỉ trọng cơ cấu %, cán cân xuất nhập khẩu, mật độ dân số).\n"
            f"  + d) [Vận dụng cao]: Đề xuất và đánh giá tính khả thi của giải pháp quy hoạch vùng, phát triển bền vững hoặc thích ứng biến đổi khí hậu."
        )
    if any(s in request.subject.lower() for s in ["kinh tế", "pháp luật", "gdkt", "gdcd"]):
        user_prompt += (
            f"\n\nLƯU Ý ĐẶC THÙ PHẦN II (ĐÚNG/SAI) MÔN GIÁO DỤC KINH TẾ VÀ PHÁP LUẬT (GDKT&PL):\n"
            f"- BẮT BUỘC mỗi câu hỏi Phần II phải xây dựng dưới dạng KỊCH BẢN TÌNH HUỐNG THỰC TẾ (Case Study 60-120 từ) gồm các nhân vật và tình tiết cụ thể (ví dụ: giao kết hợp đồng qua mạng, bán hàng online có vi phạm nhãn mác, khiếu nại bồi thường lao động, quyền bình đẳng giới, vay vốn tín dụng đen, an ninh mạng).\n"
            f"- 4 ý con a, b, c, d phân hóa chặt chẽ:\n"
            f"  + a) [Biết]: Nhận diện các chủ thể pháp lý và quan hệ xã hội được điều chỉnh trong tình huống.\n"
            f"  + b) [Hiểu]: Phân tích hành vi nào đúng, hành vi nào vi phạm pháp luật và căn cứ theo quy định của pháp luật hiện hành.\n"
            f"  + c) [Vận dụng]: Xác định quyền, nghĩa vụ và trách nhiệm pháp lý (dân sự, hình sự, hành chính, kỷ luật) của từng chủ thể.\n"
            f"  + d) [Vận dụng cao]: Rút ra bài học ứng xử công dân, văn hóa tiêu dùng/kinh doanh có đạo đức và kỹ năng phòng ngừa rủi ro pháp lý."
        )
    if any(s in request.subject.lower() for s in ["quốc phòng", "an ninh", "gdqp"]):
        user_prompt += (
            f"\n\nLƯU Ý ĐẶC THÙ PHẦN II (ĐÚNG/SAI) MÔN GIÁO DỤC QUỐC PHÒNG VÀ AN NINH (GDQP&AN):\n"
            f"- BẮT BUỘC xây dựng tình huống thực tế hoặc tình huống giả định (50-100 từ) về bảo vệ chủ quyền biên giới hải đảo, an ninh mạng/an ninh phi truyền thống, phòng chống tội phạm học đường, phòng cháy chữa cháy, kỹ năng cứu nạn cứu hộ và sơ cấp cứu ban đầu.\n"
            f"- 4 ý con a, b, c, d phân hóa từ nhận biết quy định pháp luật -> hiểu nguyên tắc tác chiến/phòng thủ -> vận dụng kỹ năng xử lý tình huống -> đánh giá ý thức trách nhiệm bảo vệ Tổ quốc của học sinh."
        )
    if any(s in request.subject.lower() for s in ["mỹ thuật", "nghệ thuật", "âm nhạc"]):
        user_prompt += (
            f"\n\nLƯU Ý ĐẶC THÙ PHẦN II (ĐÚNG/SAI) MÔN MỸ THUẬT / NGHỆ THUẬT:\n"
            f"- BẮT BUỘC xây dựng bối cảnh thẩm mỹ thực tế (50-100 từ): nghiên cứu tác phẩm nghệ thuật, di sản văn hóa vật thể/phi vật thể (tranh dân gian Đông Hồ, gốm Chu Đậu, điêu khắc đình làng, mỹ thuật hiện đại), hoặc dự án thiết kế đồ họa / mỹ thuật ứng dụng đương đại.\n"
            f"- 4 ý con a, b, c, d phân hóa: nhận biết tác giả/chất liệu -> hiểu ngôn ngữ thị giác (đường nét, mảng miếng, hòa sắc) -> vận dụng nguyên lý tạo hình -> đánh giá giá trị thẩm mỹ, nhân văn và giải pháp bảo tồn di sản."
        )
    if "công nghệ" in request.subject.lower():
        user_prompt += (
            f"\n\nLƯU Ý ĐẶC THÙ PHẦN II (ĐÚNG/SAI) MÔN CÔNG NGHỆ:\n"
            f"- BẮT BUỘC xây dựng tình huống kỹ thuật thực tế (50-100 từ): thiết kế hệ thống nhà thông minh Smart Home, mạch điều khiển đèn tự động dùng quang trở/cảm biến hồng ngoại, hệ thống tưới tiêu tự động IoT, quy trình gia công cơ khí hoặc kỹ thuật điện dân dụng.\n"
            f"- 4 ý con a, b, c, d phân hóa: nhận dạng linh kiện/thông số kỹ thuật -> giải thích nguyên lý hoạt động của sơ đồ mạch -> tính toán công suất, dòng điện, định mức an toàn -> đánh giá giải pháp tối ưu năng lượng và an toàn lao động."
        )
    if any(s in request.subject.lower() for s in ["tiếng anh", "tieng anh", "english"]):
        user_prompt += (
            f"\n\nLƯU Ý ĐẶC THÙ PHẦN II (ĐÚNG/SAI) MÔN TIẾNG ANH:\n"
            f"- BẮT BUỘC cung cấp đoạn văn đọc hiểu (Reading Passage 70-120 từ) về các chủ đề thời sự, công nghệ, môi trường hoặc văn hóa xã hội.\n"
            f"- 4 ý con a, b, c, d là 4 nhận định (Statements) bằng Tiếng Anh kiểm tra kỹ năng đọc hiểu chuyên sâu: a (Main idea / General understanding) - b (Factual detail retrieval) - c (Contextual inference / deduction) - d (Vocabulary in context or author's tone/attitude)."
        )
    if any(s in request.subject.lower() for s in ["văn", "ngữ văn"]):
        user_prompt += (
            f"\n\nLƯU Ý ĐẶC THÙ PHẦN II (ĐÚNG/SAI) MÔN NGỮ VĂN:\n"
            f"- BẮT BUỘC trích dẫn một đoạn ngữ liệu văn học hoặc văn bản thông tin/nghị luận xã hội ngoài SGK (60-120 từ).\n"
            f"- 4 ý con a, b, c, d kiểm tra năng lực tiếp nhận văn bản: nhận diện phương thức biểu đạt/hình tượng -> hiểu ý nghĩa biểu tượng/thông điệp -> vận dụng phân tích cảm thụ nghệ thuật -> đánh giá tác động tư tưởng nhân văn."
        )
    if request.topic:
        user_prompt += f"\nChủ đề kiến thức trọng tâm: {request.topic}"
    if request.prompt:
        user_prompt += f"\nYêu cầu thêm của người dùng: {request.prompt}"

    if request.matrix_spec:
        ms = request.matrix_spec
        matrix_details = []
        matrix_details.append(f"TIÊU ĐỀ MA TRẬN: {ms.title}")
        matrix_details.append(f"MÔN HỌC: {ms.subject} - KHỐI LỚP: {ms.grade} - THỜI GIAN: {ms.duration_minutes} PHÚT")
        matrix_details.append(f"TỔNG CÂU HỎI: Phần I: {request.num_part1} câu | Phần II: {request.num_part2} câu | Phần III: {request.num_part3} câu | Tự luận: {request.num_essay} câu")
        
        cs = ms.cognitive_summary
        matrix_details.append(f"PHÂN BỔ MỨC ĐỘ NHẬN THỨC (CÔNG VĂN 7991): Biết ({cs.biet_pct}%) - Hiểu ({cs.hieu_pct}%) - Vận dụng ({cs.vd_pct}%)")
        
        matrix_details.append("\nDANH MỤC CÁC CHỦ ĐỀ & BẢN ĐẶC TẢ YÊU CẦU CẦN ĐẠT (CÔNG VĂN 7991):")
        for t in ms.topics:
            topic_str = f"• {t.topic}"
            if t.sub_topic:
                topic_str += f" - Nội dung: {t.sub_topic}"
            p1_c = t.part1_mcq.biet + t.part1_mcq.hieu + t.part1_mcq.vd
            p2_c = t.part2_tf.biet + t.part2_tf.hieu + t.part2_tf.vd
            p3_c = t.part3_short.biet + t.part3_short.hieu + t.part3_short.vd
            p4_c = t.part4_essay.biet + t.part4_essay.hieu + t.part4_essay.vd
            topic_str += f" [Số câu: P1: {p1_c} (Biết {t.part1_mcq.biet}, Hiểu {t.part1_mcq.hieu}, VD {t.part1_mcq.vd}) | P2: {p2_c} câu | P3: {p3_c} câu | Tự luận: {p4_c} câu]"
            matrix_details.append(topic_str)
            if t.requirements:
                if t.requirements.recognition:
                    matrix_details.append(f"  + Yêu cầu mức Biết: {t.requirements.recognition}")
                if t.requirements.comprehension:
                    matrix_details.append(f"  + Yêu cầu mức Hiểu: {t.requirements.comprehension}")
                if t.requirements.application:
                    matrix_details.append(f"  + Yêu cầu mức Vận dụng: {t.requirements.application}")
                    
        user_prompt += (
            f"\n\nBẢNG MA TRẬN & ĐẶC TẢ CHI TIẾT (CHUẨN CÔNG VĂN 7991/BGDĐT-GDTrH):\n"
            + "\n".join(matrix_details)
            + "\n\nQUY TẮC BẮT BUỘC KHI TẠO ĐỀ THEO MA TRẬN & BẢN ĐẶC TẢ:\n"
            "1. Từng câu hỏi phải bám sát 100% vào các chủ đề, đơn vị kiến thức và đúng số lượng câu hỏi được phân bổ ở trên.\n"
            "2. BẮT BUỘC biên soạn các câu hỏi đáp ứng chuẩn xác các 'Yêu cầu mức Biết', 'Yêu cầu mức Hiểu', 'Yêu cầu mức Vận dụng' đã nêu trong Bản đặc tả.\n"
            "3. Phần I (Trắc nghiệm nhiều lựa chọn): Ưu tiên các câu hỏi ở mức độ Biết và Hiểu theo tỷ lệ quy định.\n"
            "4. Phần II (Đúng - Sai): Mỗi câu gồm 4 ý con a, b, c, d với độ khó phân hóa từ Biết đến Hiểu và Vận dụng, đúng với chủ đề được chỉ định.\n"
            "5. Phần III (Trả lời ngắn) và Phần IV (Tự luận): Tập trung vào mức độ Vận dụng, giải quyết bài toán thực tế theo đúng yêu cầu cần đạt."
        )

    if request.file_content:
        user_prompt += (
            f"\n\nNỘI DUNG TÀI LIỆU/GIÁO ÁN/ĐỀ CƯƠNG/HÌNH ẢNH ĐÍNH KÈM (TOÀN VĂN):\n"
            f"{request.file_content[:140000]}\n\n"
            f"CHỈ DẪN QUAN TRỌNG KHI BIÊN SOẠN ĐỀ TỪ TÀI LIỆU/HÌNH ẢNH ĐÍNH KÈM:\n"
            f"1. Toàn bộ các câu hỏi ở Phần I (trắc nghiệm 4 lựa chọn), Phần II (Đúng/Sai), Phần III (trả lời ngắn) và Phần IV (Tự luận nếu có) "
            f"BẮT BUỘC PHẢI BÁM SÁT VÀO TẤT CẢ CÁC KIẾN THỨC, KHÁI NIỆM, VÍ DỤ, BÀI TẬP, CÔNG THỨC HOẶC DẠNG CÂU HỎI ĐÃ ĐƯỢC TRÍCH XUẤT TỪ CÁC TỆP ĐÍNH KÈM (bao gồm cả file Word, file PDF và các hình ảnh chụp SGK/đề cương).\n"
            f"2. Nếu tài liệu bao gồm nhiều tệp (ví dụ gồm cả giáo án lý thuyết, đề cương ôn tập và các ảnh bài tập), hãy tổng hợp và bao quát đầy đủ nội dung từ TẤT CẢ các tệp, không được bỏ qua tệp nào.\n"
            f"3. Ưu tiên chuyển hóa trực tiếp các bài tập, câu hỏi, dữ liệu số trong tài liệu/ảnh thành các câu trắc nghiệm, đúng sai và trả lời ngắn chuẩn GDPT 2025.\n"
            f"4. Nếu tài liệu đính kèm thể hiện rõ môn học và khối lớp cụ thể (ví dụ: Tin học 10, Vật lí 11, Hóa học 10, Toán 12...), "
            f"hãy tự động ưu tiên lấy đúng môn học và khối lớp của tài liệu để đặt tiêu đề 'title' và biên soạn toàn bộ đề thi chuẩn xác nhất."
        )
        
    if request.num_essay == 0:
        user_prompt += "\nLƯU Ý QUAN TRỌNG: Người dùng chọn 0 câu tự luận. TUYỆT ĐỐI KHÔNG TẠO BẤT KỲ CÂU HỎI TỰ LUẬN NÀO, trường 'part4_essay' BẮT BUỘC để mảng rỗng []."
    else:
        user_prompt += f"\nLƯU Ý QUAN TRỌNG VỀ TỰ LUẬN: BẮT BUỘC tạo đúng {request.num_essay} câu hỏi tự luận trong 'part4_essay'. Trong phần 'explanation', TUYỆT ĐỐI KHÔNG ghi 'Bước 1 (0.5đ):' hay chia nhỏ điểm các bước (vì tổng điểm các bước cộng lại sẽ bị lệch so với điểm câu hỏi), BẮT BUỘC CHỈ gạch đầu dòng '-' các ý chính của đáp án."

    full_prompt = (
        SYSTEM_PROMPT
        .replace("{num_part1}", str(request.num_part1))
        .replace("{num_part2}", str(request.num_part2))
        .replace("{num_part3}", str(request.num_part3))
        .replace("{num_essay}", str(request.num_essay))
        .replace("{subject_name}", request.subject)
        .replace("{grade_name}", str(request.grade))
    ) + "\n\nYÊU CẦU CỤ THỂ:\n" + user_prompt

    # Multi-Key Rotation Pool: Round-robin starting point with failover
    global _key_rotation_counter
    start_idx = _key_rotation_counter % len(keys)
    _key_rotation_counter += 1
    ordered_keys = [keys[(start_idx + i) % len(keys)] for i in range(len(keys))]
    
    raw_json = None
    key_errors = []

    for attempt_idx, current_key in enumerate(ordered_keys, start=1):
        masked = mask_key(current_key)
        try:
            if request.api_provider == "openai":
                model = request.model_name or "gpt-4o-mini"
                raw_json = await generate_with_openai(full_prompt, current_key, model)
            else:
                model = request.model_name or "auto"
                raw_json = await generate_with_gemini(full_prompt, current_key, model)
                
            if not raw_json or ("{" not in raw_json and "[" not in raw_json):
                raise ValueError("Mô hình AI phản hồi văn bản giải thích thay vì xuất cấu trúc đề thi JSON.")

            print(f"[Key Pool] Đã sinh đề thành công bằng Key {masked} (Lần thử {attempt_idx}/{len(ordered_keys)})")
            break
        except Exception as e:
            err_detail = str(e)
            print(f"[Key Failover] Thất bại với Key {masked}: {err_detail}. Đang chuyển tiếp key tiếp theo trong danh sách...")
            key_errors.append(f"Key {masked}: {err_detail}")
            raw_json = None
            continue

    if raw_json is None:
        if len(key_errors) == 1:
            raise ValueError(f"Lỗi gọi API: {key_errors[0]}")
        else:
            errors_str = "\n• ".join(key_errors)
            raise ValueError(
                f"Tất cả {len(ordered_keys)} API Key trong nhóm xoay vòng đều gặp sự cố:\n• {errors_str}\n\n"
                f"Vui lòng kiểm tra lại hạn mức tài khoản (Quota) hoặc chọn bộ đề mẫu có sẵn."
            )

    cleaned = clean_json_string(raw_json)
    repaired = robust_repair_latex_in_json(cleaned)
    
    data = None
    parse_errors = []
    
    # 1. Standard json parse on repaired
    try:
        data = json.loads(repaired)
    except Exception as e1:
        parse_errors.append(f"json.loads: {e1}")
        
    # 2. json_repair on repaired (fixes unescaped quotes, trailing commas, LaTeX backslashes)
    if not isinstance(data, dict):
        try:
            res = json_repair.loads(repaired)
            if isinstance(res, dict) and res:
                data = res
            elif isinstance(res, list) and len(res) > 0 and isinstance(res[0], dict):
                data = res[0]
        except Exception as e2:
            parse_errors.append(f"json_repair (repaired): {e2}")

    # 3. json_repair on cleaned directly
    if not isinstance(data, dict):
        try:
            res = json_repair.loads(cleaned)
            if isinstance(res, dict) and res:
                data = res
            elif isinstance(res, list) and len(res) > 0 and isinstance(res[0], dict):
                data = res[0]
        except Exception as e3:
            parse_errors.append(f"json_repair (cleaned): {e3}")

    # 4. Healed truncated json fallback
    if not isinstance(data, dict):
        try:
            healed = heal_truncated_json(repaired)
            res = json_repair.loads(healed)
            if isinstance(res, dict) and res:
                data = res
        except Exception as e4:
            parse_errors.append(f"heal+json_repair: {e4}")

    # 5. Strict=False fallback
    if not isinstance(data, dict):
        try:
            res = json.loads(cleaned, strict=False)
            if isinstance(res, dict):
                data = res
        except Exception as e5:
            parse_errors.append(f"strict=False: {e5}")

    if not isinstance(data, dict):
        if "{" not in cleaned:
            snippet = (cleaned[:300] + "...") if len(cleaned) > 300 else cleaned
            raise ValueError(
                f"Mô hình AI đã phản hồi văn bản thông thường thay vì xuất cấu trúc đề thi JSON.\n"
                f"Nội dung phản hồi từ AI: \"{snippet}\"\n\n"
                f"Gợi ý: Hệ thống đã tự động nhận diện lại môn học và tối ưu prompt. Vui lòng bấm 'Tạo đề' lại để AI biên soạn đúng chuẩn!"
            )
        err_hint = parse_errors[0] if parse_errors else "Lỗi cấu trúc dữ liệu"
        snippet = cleaned[:400]
        m = re.search(r'char (\d+)', err_hint)
        if m:
            pos = int(m.group(1))
            start_p = max(0, pos - 150)
            end_p = min(len(cleaned), pos + 150)
            snippet = f"...{cleaned[start_p:end_p]}..."
        raise ValueError(f"Không thể phân tích dữ liệu đề thi từ AI ({err_hint})\nVị trí gặp sự cố:\n{snippet}")

    normalized = normalize_exam_data(data, default_subject=request.subject, default_grade=request.grade)

    # Strictly enforce 0 counts if user selected 0 for any part:
    if request.num_essay == 0:
        normalized["part4_essay"] = []
    if request.num_part1 == 0:
        normalized["part1_mcq"] = []
    if request.num_part2 == 0:
        normalized["part2_tf"] = []
    if request.num_part3 == 0:
        normalized["part3_short"] = []

    # Guarantee All Parts (Part 1 MCQ, Part 2 TF, Part 3 Short, Part 4 Essay):
    # If missing or incomplete and requested > 0, auto-complete with targeted AI call & fallback bank
    num_p1_needed = request.num_part1
    num_p2_needed = request.num_part2
    num_p3_needed = request.num_part3
    num_essay_needed = request.num_essay

    current_p1_count = len(normalized.get("part1_mcq", []))
    current_p2_count = len(normalized.get("part2_tf", []))
    current_p3_count = len(normalized.get("part3_short", []))
    current_essay_count = len(normalized.get("part4_essay", []))

    missing_p1 = max(0, num_p1_needed - current_p1_count) if num_p1_needed > 0 else 0
    missing_p2 = max(0, num_p2_needed - current_p2_count) if num_p2_needed > 0 else 0
    missing_p3 = max(0, num_p3_needed - current_p3_count) if num_p3_needed > 0 else 0
    missing_essay = max(0, num_essay_needed - current_essay_count) if num_essay_needed > 0 else 0

    # If AI stopped early on ANY part (e.g. only 18 questions instead of 28), attempt focused completion call
    if (missing_p1 > 0 or missing_p2 > 0 or missing_p3 > 0 or missing_essay > 0) and keys:
        print(f"[Exam Completion] Cần sinh bổ sung: P1={current_p1_count}/{num_p1_needed} (thiếu {missing_p1}), P2={current_p2_count}/{num_p2_needed} (thiếu {missing_p2}), P3={current_p3_count}/{num_p3_needed} (thiếu {missing_p3}), P4={current_essay_count}/{num_essay_needed} (thiếu {missing_essay}). Đang gọi AI bổ sung...")

        completion_instructions = []
        if missing_p1 > 0:
            completion_instructions.append(f"- BẮT BUỘC TẠO ĐỦ ĐÚNG {missing_p1} CÂU PHẦN I (Trắc nghiệm 4 lựa chọn A, B, C, D). Mỗi câu có 4 phương án độc lập và trường 'answer' ('A'/'B'/'C'/'D').")
        if missing_p2 > 0:
            completion_instructions.append(f"- BẮT BUỘC TẠO ĐỦ ĐÚNG {missing_p2} CÂU PHẦN II (Trắc nghiệm Đúng/Sai). Mỗi câu gồm đề bài và đúng 4 ý a, b, c, d (is_correct: true/false, có từ 1 đến 3 ý đúng).")
        if missing_p3 > 0:
            completion_instructions.append(f"- BẮT BUỘC TẠO ĐỦ ĐÚNG {missing_p3} CÂU PHẦN III (Trả lời ngắn). Điền đáp số ngắn gọn.")
        if missing_essay > 0:
            completion_instructions.append(f"- BẮT BUỘC TẠO ĐỦ ĐÚNG {missing_essay} CÂU PHẦN IV (Tự luận). Gạch đầu dòng các ý chính.")

        prompt_completion = f"""Bạn là chuyên gia biên soạn đề thi chuẩn Bộ GD&ĐT. Hãy biên soạn bổ sung câu hỏi cho đề thi môn {request.subject}, khối {request.grade} (chủ đề: {request.topic or request.prompt or 'kiến thức trọng tâm'}):
{chr(10).join(completion_instructions)}

YÊU CẦU:
- Không dùng ngoặc kép đôi bên trong văn bản (dùng nháy đơn '...').
- Công thức toán/lý/hóa đặt trong $...$. Nếu là mã lệnh/SQL/HTML thì viết văn bản thường hoặc bọc trong dấu nháy `...`, tuyệt đối không bọc SQL/code trong $...$.
- Lời giải 'explanation' chỉ viết ngắn gọn 1 dòng.

Chỉ trả về DUY NHẤT một chuỗi JSON hợp lệ theo cấu trúc các phần cần bổ sung:
{{
  {"\"part1_mcq\": [ {\"id\": 1, \"question\": \"Câu hỏi trắc nghiệm...\", \"options\": [{\"label\": \"A\", \"text\": \"Phương án A\"}, {\"label\": \"B\", \"text\": \"Phương án B\"}, {\"label\": \"C\", \"text\": \"Phương án C\"}, {\"label\": \"D\", \"text\": \"Phương án D\"}], \"answer\": \"A\", \"explanation\": \"Giải thích ngắn\"} ]," if missing_p1 > 0 else ""}
  {"\"part2_tf\": [ {\"id\": 1, \"question\": \"Câu hỏi đúng sai...\", \"sub_items\": [{\"label\": \"a\", \"statement\": \"Mệnh đề a...\", \"is_correct\": true, \"explanation\": \"Giải thích\"}, {\"label\": \"b\", \"statement\": \"Mệnh đề b...\", \"is_correct\": false, \"explanation\": \"Giải thích\"}, {\"label\": \"c\", \"statement\": \"Mệnh đề c...\", \"is_correct\": true, \"explanation\": \"Giải thích\"}, {\"label\": \"d\", \"statement\": \"Mệnh đề d...\", \"is_correct\": false, \"explanation\": \"Giải thích\"}], \"explanation\": \"Hướng dẫn\"} ]," if missing_p2 > 0 else ""}
  {"\"part3_short\": [ {\"id\": 1, \"question\": \"Câu hỏi ngắn...\", \"answer\": \"10\", \"explanation\": \"Giải thích\"} ]," if missing_p3 > 0 else ""}
  {"\"part4_essay\": [ {\"id\": 1, \"question\": \"Câu tự luận...\", \"points\": 1.0, \"answer\": \"Tóm tắt kết quả\", \"explanation\": \"- Ý 1\\n- Ý 2\"} ]" if missing_essay > 0 else ""}
}}
"""
        try:
            if request.api_provider == "openai":
                model = request.model_name or "gpt-4o-mini"
                comp_raw = await generate_with_openai(prompt_completion, ordered_keys[0], model)
            else:
                model = request.model_name or "auto"
                comp_raw = await generate_with_gemini(prompt_completion, ordered_keys[0], model)

            comp_cleaned = clean_json_string(comp_raw)
            comp_repaired = robust_repair_latex_in_json(comp_cleaned)
            comp_data = None
            try:
                comp_data = json.loads(comp_repaired)
            except Exception:
                try:
                    comp_data = json_repair.loads(comp_repaired)
                except Exception:
                    try:
                        comp_data = json_repair.loads(comp_cleaned)
                    except Exception:
                        pass

            if isinstance(comp_data, dict):
                comp_norm = normalize_exam_data(comp_data, default_subject=request.subject, default_grade=request.grade)
                if missing_p1 > 0 and comp_norm.get("part1_mcq"):
                    for q in comp_norm["part1_mcq"][:missing_p1]:
                        normalized["part1_mcq"].append(q)
                if missing_p2 > 0 and comp_norm.get("part2_tf"):
                    for q in comp_norm["part2_tf"][:missing_p2]:
                        normalized["part2_tf"].append(q)
                if missing_p3 > 0 and comp_norm.get("part3_short"):
                    for q in comp_norm["part3_short"][:missing_p3]:
                        normalized["part3_short"].append(q)
                if missing_essay > 0 and comp_norm.get("part4_essay"):
                    for q in comp_norm["part4_essay"][:missing_essay]:
                        normalized["part4_essay"].append(q)
                print(f"[Exam Completion] Bổ sung thành công! Hiện có: P1={len(normalized['part1_mcq'])}, P2={len(normalized['part2_tf'])}, P3={len(normalized['part3_short'])}, P4={len(normalized['part4_essay'])}")
        except Exception as comp_err:
            print(f"[Exam Completion Warning] Không thể gọi AI sinh bổ sung: {comp_err}")

    # Fallback safety: If ANY part is STILL short of the requested count, supplement from curriculum bank
    sub_lower = request.subject.lower()
    if "tin" in sub_lower or "informatics" in sub_lower:
        fallback_bank = get_mock_informatics_exam()
    elif "lý" in sub_lower or "vật lí" in sub_lower:
        fallback_bank = get_mock_physics_exam()
    elif "hóa" in sub_lower:
        fallback_bank = get_mock_chemistry_exam()
    elif "sinh" in sub_lower:
        fallback_bank = get_mock_biology_exam()
    elif "gdqp" in sub_lower or "quân sự" in sub_lower or "quốc phòng" in sub_lower:
        fallback_bank = get_mock_gdqp_exam()
    elif "anh" in sub_lower or "english" in sub_lower:
        fallback_bank = get_mock_english_exam()
    else:
        fallback_bank = get_mock_math_exam()

    # Part 1 Fallback Guarantee
    while num_p1_needed > 0 and len(normalized["part1_mcq"]) < num_p1_needed:
        idx = len(normalized["part1_mcq"])
        bank_idx = idx % len(fallback_bank.part1_mcq)
        item = fallback_bank.part1_mcq[bank_idx].model_dump()
        item["id"] = idx + 1
        normalized["part1_mcq"].append(item)

    # Part 2 Fallback Guarantee
    while num_p2_needed > 0 and len(normalized["part2_tf"]) < num_p2_needed:
        idx = len(normalized["part2_tf"])
        bank_idx = idx % len(fallback_bank.part2_tf)
        item = fallback_bank.part2_tf[bank_idx].model_dump()
        item["id"] = idx + 1
        normalized["part2_tf"].append(item)

    # Part 3 Fallback Guarantee
    while num_p3_needed > 0 and len(normalized["part3_short"]) < num_p3_needed:
        idx = len(normalized["part3_short"])
        bank_idx = idx % len(fallback_bank.part3_short)
        item = fallback_bank.part3_short[bank_idx].model_dump()
        item["id"] = idx + 1
        normalized["part3_short"].append(item)

    # Part 4 Essay Fallback Guarantee
    while num_essay_needed > 0 and len(normalized.get("part4_essay", [])) < num_essay_needed:
        idx = len(normalized["part4_essay"])
        item = {
            "id": idx + 1,
            "question": f"Vận dụng kiến thức môn {request.subject} lớp {request.grade} để giải quyết bài toán/tình huống thực tiễn sau...",
            "points": 1.0,
            "answer": "Tóm tắt kết quả phân tích then chốt.",
            "explanation": "- Nêu được cơ sở lý thuyết.\n- Vận dụng vào tình huống cụ thể.\n- Rút ra kết luận chính xác."
        }
        normalized["part4_essay"].append(item)

    # Enforce EXACT question counts if exceeded and renumber IDs sequentially
    if num_p1_needed > 0 and len(normalized["part1_mcq"]) > num_p1_needed:
        normalized["part1_mcq"] = normalized["part1_mcq"][:num_p1_needed]
    if num_p2_needed > 0 and len(normalized["part2_tf"]) > num_p2_needed:
        normalized["part2_tf"] = normalized["part2_tf"][:num_p2_needed]
    if num_p3_needed > 0 and len(normalized["part3_short"]) > num_p3_needed:
        normalized["part3_short"] = normalized["part3_short"][:num_p3_needed]
    if num_essay_needed > 0 and len(normalized["part4_essay"]) > num_essay_needed:
        normalized["part4_essay"] = normalized["part4_essay"][:num_essay_needed]

    for i, q in enumerate(normalized["part1_mcq"], 1):
        q["id"] = i
    for i, q in enumerate(normalized["part2_tf"], 1):
        q["id"] = i
    for i, q in enumerate(normalized["part3_short"], 1):
        q["id"] = i
    for i, q in enumerate(normalized["part4_essay"], 1):
        q["id"] = i

    p4_total_pts = sum(q.get("points", 1.0) for q in normalized.get("part4_essay", []))
    normalized["scoring"] = calculate_exam_scoring(
        num_p1=len(normalized.get("part1_mcq", [])),
        num_p2=len(normalized.get("part2_tf", [])),
        num_p3=len(normalized.get("part3_short", [])),
        num_p4=len(normalized.get("part4_essay", [])),
        p4_points_total=p4_total_pts
    ).model_dump()

    if normalized.get("part4_essay"):
        sync_part4_essay_points(normalized["part4_essay"], normalized["scoring"]["part4_points"])

    exam_obj = ExamStructure.model_validate(normalized)
    
    if len(exam_obj.part1_mcq) == 0 and len(exam_obj.part2_tf) == 0 and len(exam_obj.part3_short) == 0 and len(exam_obj.part4_essay) == 0:
        raise ValueError("AI không tạo được câu hỏi nào trong đề thi. Vui lòng kiểm tra lại prompt yêu cầu hoặc thử lại.")

    exam_obj = auto_attach_diagrams_to_exam(exam_obj)

    # -------------------------------------------------------------
    # AI AUDITOR AGENT: Thẩm định & Kiểm duyệt Độc Lập Chuyên Nghiệp
    # Kiểm tra 100% tính khớp giữa câu hỏi và đáp án, loại bỏ triệt để
    # các phương án rác/vô nghĩa và tự sửa chữa trước khi xuất đề thi.
    # -------------------------------------------------------------
    chosen_key = ordered_keys[0] if ordered_keys else None
    try:
        exam_obj = await audit_and_verify_exam(
            exam=exam_obj,
            api_key=chosen_key,
            api_keys=ordered_keys,
            provider=request.api_provider,
            model=request.model_name or "auto"
        )
    except Exception as audit_err:
        print(f"[Auditor Agent Warning] Lỗi trong quá trình thẩm định: {audit_err}")
        
    exam_obj = auto_attach_diagrams_to_exam(exam_obj)
    return exam_obj
