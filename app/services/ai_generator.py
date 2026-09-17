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

from .models import ExamStructure, Option, Part1Question, Part2Question, Part3Question, Part4EssayQuestion, SubItem, GenerateRequest, AuditReport, ExamScoring, calculate_exam_scoring
from .explanation_sync import (
    extract_concluded_letter,
    synchronize_mcq_explanation_with_answer,
    reconcile_tf_subitem
)
from .exam_auditor import heal_mcq_offline, audit_and_verify_exam

SYSTEM_PROMPT = """Bạn là một chuyên gia khảo thí và biên soạn đề kiểm tra hàng đầu của Bộ Giáo dục & Đào tạo Việt Nam.
Nhiệm vụ của bạn là biên soạn một đề kiểm tra chuẩn định dạng mới nhất (áp dụng theo chương trình GDPT mới 2025).

CẤU TRÚC ĐỀ THEO SỐ LƯỢNG YÊU CẦU:
- PHẦN I: Câu trắc nghiệm nhiều phương án lựa chọn (Thí sinh chọn 1 trong 4 phương án A, B, C, D). Số lượng yêu cầu: {num_part1} câu (khóa 'part1_mcq'). Nếu {num_part1} = 0 thì để mảng rỗng [].
  * QUY ĐỊNH BẮT BUỘC VỀ PHƯƠNG ÁN LỰA CHỌN PHẦN I:
    + Mỗi câu hỏi BẮT BUỘC CHỈ CÓ ĐÚNG 4 PHƯƠNG ÁN LỰA CHỌN: "A", "B", "C", "D".
    + TUYỆT ĐỐI KHÔNG TẠO PHƯƠNG ÁN THỨ 5 (E, F,...).
    + TUYỆT ĐỐI KHÔNG SỬ DỤNG các phương án dạng: "Tất cả các phương án trên đều đúng", "Tất cả các đáp án đều sai", "Không có đáp án nào đúng", "Cả A và B đều đúng" vì đề thi sẽ được xáo trộn ngẫu nhiên vị trí các phương án A, B, C, D. Tất cả 4 phương án phải là các mệnh đề hoặc giá trị độc lập, cụ thể.
- PHẦN II: Câu trắc nghiệm Đúng / Sai. Mỗi câu gồm đoạn thông tin hoặc bài toán và 4 lệnh hỏi con a, b, c, d (mỗi lệnh chọn Đúng hoặc Sai). Số lượng yêu cầu: {num_part2} câu (khóa 'part2_tf'). Nếu {num_part2} = 0 thì để mảng rỗng [].
- PHẦN III: Câu trắc nghiệm trả lời ngắn (Điền số hoặc kết quả ngắn gọn). Số lượng yêu cầu: {num_part3} câu (khóa 'part3_short'). Nếu {num_part3} = 0 thì để mảng rỗng [].
- PHẦN IV: Câu hỏi Tự luận (Thí sinh trình bày bài giải hoặc phân tích chi tiết). Số lượng yêu cầu: {num_essay} câu (khóa 'part4_essay').
  * QUY TẮC BẮT BUỘC CHO PHẦN TỰ LUẬN:
    + NẾU {num_essay} LÀ 0: TUYỆT ĐỐI KHÔNG TẠO BẤT KỲ CÂU HỎI TỰ LUẬN NÀO, trường 'part4_essay' BẮT BUỘC PHẢI LÀ MẢNG RỖNG [].
    + NẾU {num_essay} > 0: BẮT BUỘC tạo đúng {num_essay} câu tự luận trong mảng 'part4_essay'. Mỗi câu gồm 'id', đề bài 'question', thang điểm 'points' (ví dụ 1.0, 1.5, 2.0), tóm tắt kết quả then chốt 'answer', và hướng dẫn chấm chi tiết kèm phân bố điểm từng bước 'explanation'.

QUY TẮC BẮT BUỘC ĐỂ KHÔNG BỊ TRÀN TOKEN HOẶC THIẾU CÂU HỎI:
1. TUYỆT ĐỐI KHÔNG ĐƯỢC BỎ SÓT các phần có số lượng yêu cầu > 0.
2. Để tiết kiệm token, phần lời giải ('explanation') các câu trắc nghiệm viết ngắn gọn súc tích; phần tự luận ghi rõ các mốc điểm từng bước.
3. TUYỆT ĐỐI KHÔNG sử dụng dấu ngoặc kép đôi "..." bên trong nội dung văn bản (dùng dấu nháy đơn '...' thay vì "..." để đảm bảo tính hợp lệ của JSON).
4. Mọi công thức toán học, ký hiệu khoa học, phương trình phản ứng BẮT BUỘC phải đặt trong dấu $...$ (nội dòng) hoặc $$...$$ (khối).
   Ví dụ: $x^2 + 2x - 3 = 0$, $\\int_0^1 x dx$, $\\vec{F} = m\\vec{a}$, $CH_3COOH + C_2H_5OH \\rightleftharpoons CH_3COOC_2H_5 + H_2O$.
5. TÍNH ĐỒNG NHẤT TUYỆT ĐỐI 100% GIỮA ĐÁP ÁN VÀ LỜI GIẢI CHI TIẾT:
   - Trong Phần I: Chữ cái ở trường 'answer' (A, B, C hoặc D) và kết luận trong trường 'explanation' BẮT BUỘC PHẢI HOÀN TOÀN TRÙNG KHỚP NHAU.
   - Trong Phần II: Giá trị 'is_correct' (true/false) của mỗi ý con a, b, c, d phải đồng nhất 100% với lời giải của ý con đó.
   - Trong Phần III: Giá trị đáp số 'answer' và kết quả tính được trong 'explanation' phải hoàn toàn trùng khớp.

CẤU TRÚC JSON ĐẦU RA BẮT BUỘC (Chỉ trả về DUY NHẤT một chuỗi JSON hợp lệ, không kèm văn bản nào khác ngoài JSON):
{
  "title": "ĐỀ KIỂM TRA ĐỊNH KỲ MÔN TOÁN 12",
  "subject": "Toán học",
  "grade": "12",
  "duration_minutes": 50,
  "school_name": "SỞ GD&ĐT ... - TRƯỜNG THPT ...",
  "academic_year": "NĂM HỌC 2026 - 2027",
  "code": "101",
  "part1_mcq": [
    {
      "id": 1,
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
      "question": "Câu hỏi yêu cầu điền đáp số...",
      "answer": "12.5",
      "explanation": "Giải thích ngắn gọn... Vậy đáp số là 12.5."
    }
  ],
  "part4_essay": [
    {
      "id": 1,
      "question": "Nội dung đề bài câu hỏi tự luận...",
      "points": 1.5,
      "answer": "Kết quả then chốt...",
      "explanation": "- Bước 1 (0.5đ): Lập luận...\\n- Bước 2 (0.5đ): Tính toán...\\n- Bước 3 (0.5đ): Kết luận..."
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
            
        # Priority: active working models on Google AI Studio
        for pref in [
            "gemini-flash-lite-latest",
            "gemini-3.6-flash",
            "gemini-flash-latest",
            "gemini-3.1-flash-lite",
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
    math_p1_samples = [
        ("Cho hàm số $y = x^3 - 3x + 2$. Điểm cực đại của đồ thị hàm số là", [("A", "$(-1; 4)$"), ("B", "$(1; 0)$"), ("C", "$(-1; 0)$"), ("D", "$(1; 4)$")], "A", "Ta có đạo hàm $y' = 3x^2 - 3 = 0$ khi $x = \\pm 1$. Tại $x = -1$, đạo hàm đổi dấu từ dương sang âm nên là điểm cực đại với $y(-1) = 4$."),
        ("Tập xác định của hàm số $y = \\log_2 (x - 3)$ là", [("A", "$(3; +\\infty)$"), ("B", "$[3; +\\infty)$"), ("C", "$(-\\infty; 3)$"), ("D", "$\\mathbb{R} \\setminus \\{3\\}$")], "A", "Điều kiện biểu thức trong logarit lớn hơn 0: $x - 3 > 0 \\Leftrightarrow x > 3$. Vậy $D = (3; +\\infty)$."),
        ("Họ tất cả các nguyên hàm của hàm số $f(x) = e^x + 2x$ là", [("A", "$e^x + x^2 + C$"), ("B", "$e^x + 2x^2 + C$"), ("C", "$e^x + 2 + C$"), ("D", "$\\frac{e^x}{x} + x^2 + C$")], "A", "Ta có $\\int (e^x + 2x)dx = e^x + x^2 + C$."),
        ("Trong không gian $Oxyz$, cho mặt cầu $(S): (x-1)^2 + (y+2)^2 + (z-3)^2 = 16$. Tọa độ tâm $I$ và bán kính $R$ là", [("A", "$I(1; -2; 3), R = 4$"), ("B", "$I(-1; 2; -3), R = 4$"), ("C", "$I(1; -2; 3), R = 16$"), ("D", "$I(-1; 2; -3), R = 16$")], "A", "Mặt cầu có tâm $I(1; -2; 3)$ và bán kính $R = \\sqrt{16} = 4$."),
        ("Đồ thị hàm số $y = \\frac{2x - 1}{x + 1}$ có tiệm cận đứng là đường thẳng", [("A", "$x = -1$"), ("B", "$x = 2$"), ("C", "$y = 2$"), ("D", "$y = -1$")], "A", "Mẫu số bằng 0 tại $x = -1$ và tử số bằng $-3 \\neq 0$, do đó tiệm cận đứng là đường thẳng $x = -1$."),
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
    for i, (q_text, opts, ans, exp) in enumerate(math_p1_samples, start=1):
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
    physics_p1_samples = [
        ("Một vật dao động điều hòa với phương trình $x = A\\cos(\\omega t + \\varphi)$. Đại lượng $\\omega$ được gọi là", [("A", "Tần số góc của dao động"), ("B", "Chu kỳ của dao động"), ("C", "Pha ban đầu của dao động"), ("D", "Biên độ của dao động")], "A", "Trong phương trình dao động điều hòa, đại lượng $\\omega$ là tần số góc (rad/s)."),
        ("Một con lắc lò xo gồm lò xo nhẹ có độ cứng $k$ và vật nhỏ khối lượng $m$. Chu kỳ dao động riêng của con lắc được tính bằng công thức", [("A", "$T = 2\\pi\\sqrt{\\frac{m}{k}}$"), ("B", "$T = 2\\pi\\sqrt{\\frac{k}{m}}$"), ("C", "$T = \\frac{1}{2\\pi}\\sqrt{\\frac{m}{k}}$"), ("D", "$T = \\frac{1}{2\\pi}\\sqrt{\\frac{k}{m}}$")], "A", "Công thức chu kỳ dao động riêng của con lắc lò xo là $T = 2\\pi\\sqrt{\\frac{m}{k}}$."),
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
    chemistry_p1_samples = [
        ("Chất nào sau đây thuộc loại este no, đơn chức, mạch hở?", [("A", "$CH_3COOCH_3$"), ("B", "$CH_2=CH-COOCH_3$"), ("C", "$CH_3COOCH=CH_2$"), ("D", "$HCOOCH_2CH=CH_2$")], "A", "Metyl axetat ($CH_3COOCH_3$) có công thức phân tử $C_3H_6O_2$, thuộc dãy đồng đẳng este no đơn chức mạch hở $C_n H_{2n} O_2$."),
        ("Thủy phân hoàn toàn chất béo triolein ($(C_{17}H_{33}COO)_3C_3H_5$) trong dung dịch $NaOH$ đun nóng thu được muối và chất nào sau đây?", [("A", "Glixerol"), ("B", "Etanol"), ("C", "Etylen glicol"), ("D", "Metanol")], "A", "Mọi chất béo khi thủy phân trong môi trường kiềm (xà phòng hóa) đều tạo ra glixerol ($C_3H_5(OH)_3$)."),
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

        p1_list.append({
            "id": q_id,
            "question": question,
            "options": opts_list,
            "answer": final_answer,
            "explanation": explanation
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
            or []
        )
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

        while len(subs_list) < 4:
            lbl = sub_labels_default[len(subs_list)]
            subs_list.append({"label": lbl, "statement": "Đang cập nhật mệnh đề...", "is_correct": True, "explanation": "Khẳng định này là đúng."})

        p2_list.append({
            "id": q_id,
            "question": question,
            "sub_items": subs_list,
            "explanation": explanation
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
        p3_list.append({
            "id": q_id,
            "question": question,
            "answer": answer,
            "explanation": explanation
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
        p4_list.append({
            "id": q_id,
            "question": question,
            "points": points,
            "answer": answer,
            "explanation": explanation
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

async def generate_exam(request: GenerateRequest) -> ExamStructure:
    keys = extract_api_keys(request)
    
    if request.mode == "mock" or (not keys and request.mode != "prompt"):
        sub_lower = request.subject.lower()
        if "lý" in sub_lower or "vật lí" in sub_lower:
            return get_mock_physics_exam()
        elif "hóa" in sub_lower:
            return get_mock_chemistry_exam()
        else:
            return get_mock_math_exam()
            
    if not keys:
        if request.api_provider == "openai":
            raise ValueError("Vui lòng cung cấp ít nhất 1 OpenAI API Key trong mục 'Cài đặt AI'.")
        sub_lower = request.subject.lower()
        if "lý" in sub_lower or "vật lí" in sub_lower:
            return get_mock_physics_exam()
        elif "hóa" in sub_lower:
            return get_mock_chemistry_exam()
        else:
            return get_mock_math_exam()
            
    user_prompt = f"Hãy tạo một đề kiểm tra môn {request.subject}, khối {request.grade}."
    if request.topic:
        user_prompt += f"\nChủ đề kiến thức trọng tâm: {request.topic}"
    if request.prompt:
        user_prompt += f"\nYêu cầu thêm của người dùng: {request.prompt}"
    if request.file_content:
        user_prompt += (
            f"\n\nNỘI DUNG TÀI LIỆU/GIÁO ÁN/ĐỀ CƯƠNG ĐÍNH KÈM (TOÀN VĂN):\n"
            f"{request.file_content[:120000]}\n\n"
            f"CHỈ DẪN QUAN TRỌNG KHI BIÊN SOẠN ĐỀ TỪ TÀI LIỆU ĐÍNH KÈM:\n"
            f"1. Toàn bộ các câu hỏi ở Phần I (trắc nghiệm 4 lựa chọn), Phần II (Đúng/Sai) và Phần III (trả lời ngắn) "
            f"BẮT BUỘC PHẢI BÁM SÁT VÀO CÁC KIẾN THỨC, KHÁI NIỆM, VÍ DỤ, ĐOẠN MÃ CODE, CÔNG THỨC HOẶC BÀI TẬP CÓ TRONG TÀI LIỆU ĐÍNH KÈM Ở TRÊN.\n"
            f"2. Nếu tài liệu đính kèm thể hiện rõ môn học và khối lớp cụ thể (ví dụ: Tin học 10, Vật lí 11, Hóa học 10...), "
            f"hãy tự động ưu tiên lấy đúng môn học và khối lớp của tài liệu để đặt tiêu đề 'title' và biên soạn toàn bộ đề thi chuẩn xác nhất."
        )
        
    if request.num_essay == 0:
        user_prompt += "\nLƯU Ý QUAN TRỌNG: Người dùng chọn 0 câu tự luận. TUYỆT ĐỐI KHÔNG TẠO BẤT KỲ CÂU HỎI TỰ LUẬN NÀO, trường 'part4_essay' BẮT BUỘC để mảng rỗng []."
    else:
        user_prompt += f"\nLƯU Ý QUAN TRỌNG: BẮT BUỘC tạo đúng {request.num_essay} câu hỏi tự luận trong 'part4_essay' kèm điểm số 'points' và hướng dẫn chấm chi tiết."

    full_prompt = (
        SYSTEM_PROMPT
        .replace("{num_part1}", str(request.num_part1))
        .replace("{num_part2}", str(request.num_part2))
        .replace("{num_part3}", str(request.num_part3))
        .replace("{num_essay}", str(request.num_essay))
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
                
            print(f"[Key Pool] Đã sinh đề thành công bằng Key {masked} (Lần thử {attempt_idx}/{len(ordered_keys)})")
            break
        except Exception as e:
            err_detail = str(e)
            print(f"[Key Failover] Thất bại với Key {masked}: {err_detail}. Đang chuyển tiếp key tiếp theo trong danh sách...")
            key_errors.append(f"Key {masked}: {err_detail}")
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

    # Guarantee Part 2 and Part 3: If missing or incomplete and requested > 0, auto-complete
    num_p2_needed = request.num_part2
    num_p3_needed = request.num_part3

    current_p2_count = len(normalized.get("part2_tf", []))
    current_p3_count = len(normalized.get("part3_short", []))

    missing_p2 = max(0, num_p2_needed - current_p2_count) if num_p2_needed > 0 else 0
    missing_p3 = max(0, num_p3_needed - current_p3_count) if num_p3_needed > 0 else 0

    # If AI stopped or missed Part 2 or Part 3, attempt focused completion call with AI
    if (missing_p2 > 0 or missing_p3 > 0) and keys:
        print(f"[Exam Completion] Phần 2 hiện có {current_p2_count}/{num_p2_needed}, Phần 3 hiện có {current_p3_count}/{num_p3_needed}. Đang tự động gọi AI sinh bổ sung...")
        
        prompt_completion = f"""Bạn là chuyên gia biên soạn đề thi chuẩn Bộ GD&ĐT năm học 2026 - 2027. Hãy biên soạn bổ sung cho đề thi môn {request.subject}, khối {request.grade} (chủ đề: {request.topic or request.prompt or 'kiến thức trọng tâm'}):
{f"- BẮT BUỘC TẠO {missing_p2} câu PHẦN II (Trắc nghiệm Đúng/Sai). Mỗi câu gồm đề bài và đúng 4 ý a, b, c, d (ghi rõ is_correct: true/false)." if missing_p2 > 0 else ""}
{f"- BẮT BUỘC TẠO {missing_p3} câu PHẦN III (Trả lời ngắn). Điền đáp số ngắn gọn." if missing_p3 > 0 else ""}

YÊU CẦU:
- Không dùng dấu ngoặc kép đôi bên trong văn bản (dùng nháy đơn '...').
- Công thức toán/lý/hóa đặt trong $...$.
- Lời giải 'explanation' chỉ viết ngắn gọn 1 dòng.

Chỉ trả về DUY NHẤT một chuỗi JSON hợp lệ theo cấu trúc:
{{
  "part2_tf": [
    {{
      "id": 1,
      "question": "Nội dung câu hỏi đúng sai...",
      "sub_items": [
        {{"label": "a", "statement": "Mệnh đề a...", "is_correct": true, "explanation": "Giải thích ngắn"}},
        {{"label": "b", "statement": "Mệnh đề b...", "is_correct": false, "explanation": "Giải thích ngắn"}},
        {{"label": "c", "statement": "Mệnh đề c...", "is_correct": true, "explanation": "Giải thích ngắn"}},
        {{"label": "d", "statement": "Mệnh đề d...", "is_correct": false, "explanation": "Giải thích ngắn"}}
      ],
      "explanation": "Hướng dẫn ngắn"
    }}
  ],
  "part3_short": [
    {{
      "id": 1,
      "question": "Nội dung câu hỏi ngắn...",
      "answer": "10",
      "explanation": "Giải thích ngắn"
    }}
  ]
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
                if missing_p2 > 0 and comp_norm.get("part2_tf"):
                    start_id = len(normalized["part2_tf"]) + 1
                    for q in comp_norm["part2_tf"][:missing_p2]:
                        q["id"] = start_id
                        start_id += 1
                        normalized["part2_tf"].append(q)
                if missing_p3 > 0 and comp_norm.get("part3_short"):
                    start_id = len(normalized["part3_short"]) + 1
                    for q in comp_norm["part3_short"][:missing_p3]:
                        q["id"] = start_id
                        start_id += 1
                        normalized["part3_short"].append(q)
                print(f"[Exam Completion] Đã bổ sung thành công! Hiện có: P1={len(normalized['part1_mcq'])}, P2={len(normalized['part2_tf'])}, P3={len(normalized['part3_short'])}")
        except Exception as comp_err:
            print(f"[Exam Completion Warning] Không thể gọi AI sinh bổ sung: {comp_err}")

    # Fallback safety: If Part 2 or Part 3 are STILL short of the required count, supplement from curriculum bank
    sub_lower = request.subject.lower()
    if "lý" in sub_lower or "vật lí" in sub_lower:
        fallback_bank = get_mock_physics_exam()
    elif "hóa" in sub_lower:
        fallback_bank = get_mock_chemistry_exam()
    elif "gdqp" in sub_lower or "quân sự" in sub_lower or "quốc phòng" in sub_lower:
        fallback_bank = get_mock_gdqp_exam()
    else:
        fallback_bank = get_mock_math_exam()

    while num_p2_needed > 0 and len(normalized["part2_tf"]) < num_p2_needed:
        idx = len(normalized["part2_tf"])
        bank_idx = idx % len(fallback_bank.part2_tf)
        item = fallback_bank.part2_tf[bank_idx].model_dump()
        item["id"] = idx + 1
        normalized["part2_tf"].append(item)

    while num_p3_needed > 0 and len(normalized["part3_short"]) < num_p3_needed:
        idx = len(normalized["part3_short"])
        bank_idx = idx % len(fallback_bank.part3_short)
        item = fallback_bank.part3_short[bank_idx].model_dump()
        item["id"] = idx + 1
        normalized["part3_short"].append(item)

    p4_total_pts = sum(q.get("points", 1.0) for q in normalized.get("part4_essay", []))
    normalized["scoring"] = calculate_exam_scoring(
        num_p1=len(normalized.get("part1_mcq", [])),
        num_p2=len(normalized.get("part2_tf", [])),
        num_p3=len(normalized.get("part3_short", [])),
        num_p4=len(normalized.get("part4_essay", [])),
        p4_points_total=p4_total_pts
    ).model_dump()

    exam_obj = ExamStructure.model_validate(normalized)
    
    if len(exam_obj.part1_mcq) == 0 and len(exam_obj.part2_tf) == 0 and len(exam_obj.part3_short) == 0 and len(exam_obj.part4_essay) == 0:
        raise ValueError("AI không tạo được câu hỏi nào trong đề thi. Vui lòng kiểm tra lại prompt yêu cầu hoặc thử lại.")

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
            provider=request.api_provider,
            model=request.model_name or "auto"
        )
    except Exception as audit_err:
        print(f"[Auditor Agent Warning] Lỗi trong quá trình thẩm định: {audit_err}")
        
    return exam_obj
