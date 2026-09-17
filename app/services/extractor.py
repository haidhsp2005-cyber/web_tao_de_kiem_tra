import io
import docx
import fitz  # PyMuPDF

def extract_text_from_docx(file_bytes: bytes) -> str:
    doc = docx.Document(io.BytesIO(file_bytes))
    full_text = []
    for para in doc.paragraphs:
        text = para.text.strip()
        if text:
            full_text.append(text)
    
    for table in doc.tables:
        for row in table.rows:
            row_text = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if row_text:
                full_text.append(' | '.join(row_text))
                
    return '\n'.join(full_text)

def extract_text_from_pdf(file_bytes: bytes) -> str:
    doc = fitz.open(stream=file_bytes, filetype='pdf')
    full_text = []
    for page in doc:
        text = page.get_text('text')
        if text:
            full_text.append(text.strip())
    doc.close()
    return '\n\n'.join(full_text)

def extract_file_content(filename: str, file_bytes: bytes) -> str:
    lower = filename.lower()
    if lower.endswith('.docx') or lower.endswith('.doc'):
        return extract_text_from_docx(file_bytes)
    elif lower.endswith('.pdf'):
        return extract_text_from_pdf(file_bytes)
    elif lower.endswith('.txt'):
        return file_bytes.decode('utf-8', errors='replace')
    else:
        raise ValueError('Dinh dang tep khong hop le. Vui long tai len file docx hoac pdf')
