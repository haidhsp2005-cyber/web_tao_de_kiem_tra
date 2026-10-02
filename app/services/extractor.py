import os
import io
import re
import base64
import asyncio
from typing import List, Tuple, Dict, Any, Optional
import httpx
import docx
import fitz  # PyMuPDF

def format_file_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"

def extract_text_from_docx(file_bytes: bytes) -> str:
    doc = docx.Document(io.BytesIO(file_bytes))
    full_text = []
    
    # 1. Đoạn văn thông thường
    for para in doc.paragraphs:
        text = para.text.strip()
        if text:
            full_text.append(text)
    
    # 2. Bảng biểu (xử lý ô gộp merged cells và định dạng Markdown Table)
    if doc.tables:
        full_text.append("\n[BẢNG BIỂU / MA TRẬN TRÍCH XUẤT]:")
        for table_idx, table in enumerate(doc.tables, 1):
            table_lines = []
            for row in table.rows:
                seen_tc = set()
                row_vals = []
                for cell in row.cells:
                    if cell._tc in seen_tc:
                        continue
                    seen_tc.add(cell._tc)
                    clean_cell = " ".join(cell.text.split())
                    row_vals.append(clean_cell)
                if any(row_vals):
                    table_lines.append("| " + " | ".join(row_vals) + " |")
            if table_lines:
                full_text.append(f"\n--- Bảng {table_idx} ---")
                full_text.extend(table_lines)
                
    return '\n'.join(full_text)

def extract_text_from_pdf(file_bytes: bytes) -> str:
    doc = fitz.open(stream=file_bytes, filetype='pdf')
    full_text = []
    for page_idx, page in enumerate(doc, 1):
        # 1. Trích xuất bảng nếu có
        table_lines = []
        try:
            tabs = page.find_tables()
            if tabs and tabs.tables:
                for tab in tabs.tables:
                    extracted = tab.extract()
                    for r in extracted:
                        cleaned_r = [" ".join(str(c).split()) if c is not None else "" for c in r]
                        if any(cleaned_r):
                            table_lines.append("| " + " | ".join(cleaned_r) + " |")
        except Exception:
            pass

        # 2. Trích xuất văn bản thông thường
        text = page.get_text('text')
        if text:
            full_text.append(text.strip())
        if table_lines:
            full_text.append(f"\n[BẢNG BIỂU TRANG {page_idx}]:\n" + "\n".join(table_lines))
            
    doc.close()
    return '\n\n'.join(full_text)

async def extract_text_from_image(filename: str, file_bytes: bytes, api_keys: Optional[List[str]] = None) -> str:
    """
    Sử dụng Gemini Vision Multimodal OCR để trích xuất chữ, công thức toán LaTeX ($...$),
    bảng biểu, câu hỏi và bài tập từ file ảnh (giáo án, đề cương, đề kiểm tra, ảnh chụp SGK).
    """
    try:
        from .ai_generator import get_env_api_keys
        keys = api_keys or get_env_api_keys("gemini")
    except Exception:
        keys = []
        
    if not keys:
        return (
            f"[TỆP ẢNH {filename}]: Đã tải lên ảnh thành công nhưng chưa kích hoạt OCR. "
            f"Vui lòng vào mục 'Cài đặt AI' để cấu hình GEMINI_API_KEY giúp tự động nhận diện chữ & công thức từ ảnh."
        )

    ext = os.path.splitext(filename)[1].lower()
    mime_map = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".bmp": "image/bmp"
    }
    mime_type = mime_map.get(ext, "image/jpeg")
    b64_data = base64.b64encode(file_bytes).decode("utf-8")

    prompt = (
        "Bạn là chuyên gia số hóa tài liệu giáo dục từ hình ảnh (giáo án, đề cương ôn tập, sách giáo khoa, bài tập, đề kiểm tra).\n"
        "Nhiệm vụ của bạn là đọc và trích xuất TOÀN BỘ nội dung trong bức ảnh này một cách trung thực, đầy đủ và chính xác 100%:\n"
        "1. Trích xuất nguyên vẹn mọi câu chữ, tiêu đề bài học, đề mục, câu hỏi, bài tập, các ý con a, b, c, d hoặc các phương án A, B, C, D (nếu có).\n"
        "2. Toàn bộ công thức toán học, vật lý, hóa học BẮT BUỘC định dạng chuẩn LaTeX kẹp giữa cặp dấu $...$ (ví dụ: $y = x^3 - 3x + 2$, $\\int f(x)dx$, $\\vec{a}\\cdot\\vec{b}$, $\\Delta = b^2 - 4ac$, $2H_2 + O_2 \\rightarrow 2H_2O$).\n"
        "3. Nếu có bảng số liệu, bảng biến thiên hoặc ma trận, hãy định dạng chuẩn Markdown Table (| Cột 1 | Cột 2 |).\n"
        "4. Giữ nguyên trật tự từ trên xuống dưới, không bỏ sót bất kỳ dòng nội dung nào.\n"
        "CHỈ XUẤT RA NỘI DUNG ĐÃ TRÍCH XUẤT, TUYỆT ĐỐI KHÔNG THÊM LỜI CHÀO, BÌNH LUẬN HAY GIẢI THÍCH."
    )

    candidate_models = ["gemini-flash-latest", "gemini-3.8-flash", "gemini-3.5-flash", "gemini-3.1-flash-lite"]
    last_err = ""

    async with httpx.AsyncClient(timeout=45.0) as client:
        for k in keys[:6]:  # Thử xoay vòng tối đa 6 key
            for model_name in candidate_models:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={k}"
                payload = {
                    "contents": [{
                        "parts": [
                            {"text": prompt},
                            {"inline_data": {"mime_type": mime_type, "data": b64_data}}
                        ]
                    }],
                    "generationConfig": {
                        "temperature": 0.1,
                        "maxOutputTokens": 8192
                    }
                }
                try:
                    resp = await client.post(url, json=payload)
                    if resp.status_code == 200:
                        data = resp.json()
                        candidates = data.get("candidates", [])
                        if candidates:
                            parts = candidates[0].get("content", {}).get("parts", [])
                            if parts and "text" in parts[0]:
                                text = parts[0]["text"].strip()
                                if text:
                                    return text
                    elif resp.status_code in (404, 503, 429):
                        last_err = f"{model_name} (Status {resp.status_code})"
                        continue
                    else:
                        last_err = f"Status {resp.status_code}: {resp.text[:120]}"
                except Exception as ex:
                    last_err = str(ex)
                    continue

    return f"[{filename} (Ảnh)]: Không thể trích xuất tự động qua AI ({last_err}). Vui lòng kiểm tra lại API Key."

async def extract_text_from_pdf_async(file_bytes: bytes, api_keys: Optional[List[str]] = None) -> str:
    """
    Trích xuất PDF: Ưu tiên trích xuất text và bảng trực tiếp. Nếu phát hiện trang scan (ít chữ),
    tự động chuyển trang thành ảnh và gọi Gemini Vision OCR để đọc toàn văn.
    """
    doc = fitz.open(stream=file_bytes, filetype='pdf')
    full_text = []
    
    for page_idx, page in enumerate(doc, 1):
        # 1. Trích xuất bảng nếu có
        table_lines = []
        try:
            tabs = page.find_tables()
            if tabs and tabs.tables:
                for tab in tabs.tables:
                    extracted = tab.extract()
                    for r in extracted:
                        cleaned_r = [" ".join(str(c).split()) if c is not None else "" for c in r]
                        if any(cleaned_r):
                            table_lines.append("| " + " | ".join(cleaned_r) + " |")
        except Exception:
            pass

        # 2. Trích xuất văn bản thông thường
        text = page.get_text('text').strip()
        
        # 3. Kiểm tra trang scan (ít hơn 30 ký tự và không có bảng biểu) -> OCR trang
        if len(text) < 30 and not table_lines:
            try:
                pix = page.get_pixmap(dpi=150)
                img_bytes = pix.tobytes("png")
                ocr_text = await extract_text_from_image(f"PDF_Trang_{page_idx}.png", img_bytes, api_keys=api_keys)
                if ocr_text and not ocr_text.startswith("[PDF_Trang_"):
                    text = f"[TRANG SCAN {page_idx} (ĐÃ OCR)]:\n{ocr_text}"
            except Exception:
                pass
                
        if text:
            full_text.append(text)
        if table_lines:
            full_text.append(f"\n[BẢNG BIỂU TRANG {page_idx}]:\n" + "\n".join(table_lines))
            
    doc.close()
    return '\n\n'.join(full_text)

def extract_file_content(filename: str, file_bytes: bytes) -> str:
    """Hàm đồng bộ tương thích ngược với các bài kiểm thử và module hiện có."""
    lower = filename.lower()
    if lower.endswith('.docx') or lower.endswith('.doc'):
        return extract_text_from_docx(file_bytes)
    elif lower.endswith('.pdf'):
        return extract_text_from_pdf(file_bytes)
    elif lower.endswith('.txt') or lower.endswith('.md') or lower.endswith('.csv'):
        return file_bytes.decode('utf-8', errors='replace')
    elif any(lower.endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.webp', '.bmp']):
        try:
            return asyncio.run(extract_text_from_image(filename, file_bytes))
        except Exception:
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, extract_text_from_image(filename, file_bytes))
                return future.result()
    else:
        raise ValueError('Định dạng tệp không hợp lệ. Vui lòng tải lên file docx, pdf, txt hoặc file ảnh (png, jpg, webp).')

async def extract_file_content_async(filename: str, file_bytes: bytes, api_keys: Optional[List[str]] = None) -> str:
    """Hàm bất đồng bộ xử lý toàn diện mọi định dạng (Word, PDF có OCR scan, Text, Ảnh)."""
    lower = filename.lower()
    if lower.endswith('.docx') or lower.endswith('.doc'):
        return extract_text_from_docx(file_bytes)
    elif lower.endswith('.pdf'):
        return await extract_text_from_pdf_async(file_bytes, api_keys=api_keys)
    elif lower.endswith('.txt') or lower.endswith('.md') or lower.endswith('.csv'):
        return file_bytes.decode('utf-8', errors='replace')
    elif any(lower.endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.webp', '.bmp']):
        return await extract_text_from_image(filename, file_bytes, api_keys=api_keys)
    else:
        raise ValueError(f'Định dạng tệp không được hỗ trợ: {filename}. Vui lòng chọn .docx, .pdf, .txt hoặc ảnh .png, .jpg, .webp')

def detect_file_category(filename: str) -> str:
    lower = filename.lower()
    if lower.endswith('.docx') or lower.endswith('.doc'):
        return "Word"
    elif lower.endswith('.pdf'):
        return "PDF"
    elif any(lower.endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.webp', '.bmp']):
        return "Ảnh"
    else:
        return "Văn bản"

async def extract_multiple_files(files_data: List[Tuple[str, bytes]], api_keys: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Xử lý đồng thời hoặc tuần tự nhiều tệp (ảnh, Word, PDF, Text),
    tổng hợp nội dung và cấu trúc thành một văn bản thống nhất cho AI biên soạn đề.
    """
    if not files_data:
        raise ValueError("Danh sách tệp rỗng.")

    results = []
    combined_sections = []
    
    total_files = len(files_data)
    
    for idx, (filename, content_bytes) in enumerate(files_data, 1):
        cat = detect_file_category(filename)
        size_bytes = len(content_bytes)
        size_str = format_file_size(size_bytes)
        status = "success"
        err_msg = ""
        text = ""
        
        try:
            text = await extract_file_content_async(filename, content_bytes, api_keys=api_keys)
        except Exception as e:
            status = "error"
            err_msg = str(e)
            text = f"[Lỗi trích xuất tệp {filename}: {err_msg}]"
            
        char_count = len(text)
        results.append({
            "index": idx,
            "filename": filename,
            "category": cat,
            "size_bytes": size_bytes,
            "size_formatted": size_str,
            "length": char_count,
            "status": status,
            "error": err_msg,
            "text": text
        })
        
        header = f"=== [TỆP {idx}/{total_files}]: {filename} ({cat.upper()}) - Dung lượng: {size_str} ==="
        combined_sections.append(f"{header}\n{text}\n")
        
    combined_text = (
        f"================================================================================\n"
        f"TỔNG HỢP NỘI DUNG TỪ {total_files} TÀI LIỆU, GIÁO ÁN, ĐỀ CƯƠNG VÀ HÌNH ẢNH ĐÍNH KÈM\n"
        f"================================================================================\n\n"
        + "\n\n".join(combined_sections)
    )
    
    # Gợi ý chủ đề từ tên file đầu tiên hoặc nội dung
    suggested_topic = ""
    for f in results:
        clean_name = re.sub(r'\.[^/.]+$', '', f["filename"]).replace('_', ' ').replace('-', ' ').strip()
        if len(clean_name) > 3 and not re.match(r'^(image|img|screenshot|anh|untitled)', clean_name, re.IGNORECASE):
            suggested_topic = clean_name
            break
            
    if not suggested_topic and results:
        suggested_topic = re.sub(r'\.[^/.]+$', '', results[0]["filename"]).replace('_', ' ').replace('-', ' ').strip()

    total_chars = sum(f["length"] for f in results)
    
    return {
        "total_files": total_files,
        "total_length": total_chars,
        "files": results,
        "combined_text": combined_text,
        "suggested_topic": suggested_topic,
        # Các trường tương thích ngược tuyệt đối:
        "filename": ", ".join(f["filename"] for f in results),
        "length": total_chars,
        "text": combined_text
    }
