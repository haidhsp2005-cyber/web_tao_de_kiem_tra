import os
import io
import re
import zipfile
import unicodedata
import urllib.parse
import traceback
from typing import Optional, List
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .services.models import (
    ExamStructure, ExamVariant, ShuffleRequest, ShuffleResponse,
    GenerateRequest, ExportDocxRequest
)
from .services.extractor import extract_file_content
from .services.ai_generator import (
    generate_exam, get_mock_math_exam, get_mock_physics_exam, get_mock_chemistry_exam, get_mock_gdqp_exam,
    get_env_api_keys, mask_key
)
from .services.shuffler import shuffle_exam
from .services.docx_exporter import create_exam_document

app = FastAPI(
    title="EduExam AI 2026 - Hệ Thống Biên Soạn & Trộn Đề Kiểm Tra Chuẩn Bộ GD&ĐT 2026 - 2027",
    description="Tạo đề thi đa môn, hỗ trợ công thức Toán-Lý-Hóa bản xứ, trộn đề và xuất file Word 3 phần.",
    version="2026.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_no_cache_headers(request: Request, call_next):
    response = await call_next(request)
    if request.url.path == "/" or any(request.url.path.endswith(ext) for ext in [".html", ".js", ".css"]):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
EXPORTS_DIR = os.path.join(os.path.dirname(BASE_DIR), "exports")
os.makedirs(EXPORTS_DIR, exist_ok=True)

def make_ascii_filename(name: str) -> str:
    nfkd = unicodedata.normalize("NFKD", name)
    ascii_text = "".join([c for c in nfkd if not unicodedata.combining(c)])
    ascii_text = ascii_text.replace("đ", "d").replace("Đ", "D")
    clean = re.sub(r"[^a-zA-Z0-9_.-]", "_", ascii_text)
    return re.sub(r"_+", "_", clean).strip("_")

try:
    from dotenv import load_dotenv
except ImportError:
    pass

# 0. Lấy cấu hình hệ thống & API Keys từ .env
@app.get("/api/config")
async def api_get_config(include_raw: bool = False):
    gemini_keys = get_env_api_keys("gemini")
    openai_keys = get_env_api_keys("openai")
    res = {
        "has_env_keys": len(gemini_keys) > 0 or len(openai_keys) > 0,
        "gemini_keys_count": len(gemini_keys),
        "gemini_masked_keys": [mask_key(k) for k in gemini_keys],
        "openai_keys_count": len(openai_keys),
        "openai_masked_keys": [mask_key(k) for k in openai_keys],
    }
    if include_raw:
        res["gemini_keys"] = gemini_keys
        res["openai_keys"] = openai_keys
    return res

@app.get("/api/env-status")
async def api_env_status():
    return await api_get_config()

class SaveEnvRequest(BaseModel):
    provider: str = "gemini"
    keys: List[str]

@app.post("/api/save-env")
async def api_save_env(req: SaveEnvRequest):
    try:
        env_path = os.path.join(os.path.dirname(BASE_DIR), ".env")
        
        # Parse and clean keys
        clean_keys = []
        for k in req.keys:
            k = k.strip().strip("'\"`")
            if k and len(k) > 5 and k not in clean_keys:
                clean_keys.append(k)
                
        # Format .env file with exact template from the user's image
        content_lines = [
            "# Hướng dẫn:",
            "# 1. Đổi tên tệp này thành `.env` (hoặc sao chép ra tệp `.env`).",
            "# 2. Dán các mã API Key của bạn vào bên dưới.",
            "# 3. Khi máy chủ chạy, hệ thống sẽ tự nạp các key này vào bộ nhớ và tự động xoay vòng.",
            "#    Trên giao diện web bạn sẽ không cần phải nhập hay hiển thị key nữa!",
            "# ==============================================================================",
            "",
            "# Cách 1: Danh sách nhiều key ngăn cách bởi dấu phẩy",
            '# GEMINI_API_KEYS="AizaSyYourKey1Here,AIzaSyYourKey2Here,AIzaSyYourKey3Here"',
            "",
            "# Hoặc Cách 2: Từng key trên từng dòng"
        ]
        
        if req.provider == "openai":
            for i, k in enumerate(clean_keys, start=1):
                content_lines.append(f'OPENAI_API_KEY_{i}="{k}"')
        else:
            for i, k in enumerate(clean_keys, start=1):
                content_lines.append(f'GEMINI_API_KEY_{i}="{k}"')
                
        content_lines.append("")
        new_env_content = "\n".join(content_lines)
        
        with open(env_path, "w", encoding="utf-8") as f:
            f.write(new_env_content)
            
        # Clean out old keys from environment
        prefix = "GEMINI_API_KEY" if req.provider != "openai" else "OPENAI_API_KEY"
        for i in range(1, 35):
            if f"{prefix}_{i}" in os.environ:
                del os.environ[f"{prefix}_{i}"]
                
        load_dotenv(env_path, override=True)
        return await api_get_config()
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Không thể lưu file .env: {str(e)}")

# 1. Trích xuất file Word/PDF
@app.post("/api/extract")
async def api_extract(file: UploadFile = File(...)):
    try:
        content_bytes = await file.read()
        extracted_text = extract_file_content(file.filename, content_bytes)
        return {
            "filename": file.filename,
            "length": len(extracted_text),
            "text": extracted_text
        }
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=f"Lỗi đọc tệp: {str(e)}")

# 2. Sinh đề thi (AI hoặc Mẫu)
@app.post("/api/generate", response_model=ExamStructure)
async def api_generate(req: GenerateRequest):
    try:
        exam = await generate_exam(req)
        return exam
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Lỗi tạo đề: {str(e)}")

# 3. Lấy mẫu nhanh theo môn
@app.get("/api/samples/{subject}", response_model=ExamStructure)
async def api_sample(subject: str):
    sub = subject.lower()
    if "gdqp" in sub or "quoc_phong" in sub or "quốc phòng" in sub:
        return get_mock_gdqp_exam()
    elif "ly" in sub or "vật" in sub:
        return get_mock_physics_exam()
    elif "hoa" in sub:
        return get_mock_chemistry_exam()
    else:
        return get_mock_math_exam()

# 4. Trộn đề thi
@app.post("/api/shuffle", response_model=ShuffleResponse)
async def api_shuffle(req: ShuffleRequest):
    try:
        res = shuffle_exam(
            exam=req.exam,
            num_variants=req.num_variants,
            start_code=req.start_code,
            shuffle_part1_options=req.shuffle_part1_options,
            shuffle_part2_subitems=req.shuffle_part2_subitems
        )
        return res
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Lỗi trộn đề: {str(e)}")

# 5. Xuất file Word (.docx)
@app.post("/api/export-docx")
async def api_export_docx(req: ExportDocxRequest):
    try:
        doc = create_exam_document(
            exam=req.exam,
            variant_code=req.variant_code,
            include_answers=req.include_answers,
            include_explanations=req.include_explanations,
            all_variants=req.all_variants
        )
        buffer = io.BytesIO()
        doc.save(buffer)
        buffer.seek(0)
        code = req.variant_code or req.exam.code or "101"
        sub_ascii = make_ascii_filename(req.exam.subject)
        safe_filename = f"De_thi_{sub_ascii}_Ma_{code}.docx"
        return StreamingResponse(
            buffer,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f"attachment; filename={safe_filename}"}
        )
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Lỗi xuất file Word: {str(e)}")

class ZipExportRequest(BaseModel):
    exam: ExamStructure
    variants: List[ExamVariant]
    include_answers: bool = True
    include_explanations: bool = True

# 6. Xuất trọn bộ ZIP gồm từng mã đề riêng biệt
@app.post("/api/export-zip")
async def api_export_zip(req: ZipExportRequest):
    try:
        zip_buffer = io.BytesIO()
        sub_ascii = make_ascii_filename(req.exam.subject)
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for v in req.variants:
                doc_v = create_exam_document(
                    exam=v.exam,
                    variant_code=v.code,
                    include_answers=req.include_answers,
                    include_explanations=req.include_explanations
                )
                v_buf = io.BytesIO()
                doc_v.save(v_buf)
                v_buf.seek(0)
                v_filename = f"De_thi_{sub_ascii}_Ma_{v.code}.docx"
                zf.writestr(v_filename, v_buf.getvalue())
            
            doc_master = create_exam_document(
                exam=req.exam,
                variant_code="TONG_HOP",
                include_answers=True,
                include_explanations=True,
                all_variants=req.variants
            )
            m_buf = io.BytesIO()
            doc_master.save(m_buf)
            m_buf.seek(0)
            zf.writestr(f"Tong_hop_De_va_Ma_tran_Dap_an_{sub_ascii}.docx", m_buf.getvalue())
            
        zip_buffer.seek(0)
        zip_name = f"Bo_de_thi_{sub_ascii}_{len(req.variants)}_ma_de.zip"
        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename={zip_name}"}
        )
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Lỗi tạo tệp ZIP: {str(e)}")

# Phục vụ giao diện tĩnh SPA
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
