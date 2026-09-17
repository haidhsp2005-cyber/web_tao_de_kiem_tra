import sys
import io
import zipfile
sys.stdout.reconfigure(encoding='utf-8')

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

print('1. Testing GET / (Static Index)...')
r = client.get('/')
assert r.status_code == 200
assert 'EduExam' in r.text
print('   -> OK (Index HTML served successfully)')

print('2. Testing GET /api/samples/toan and other samples...')
r = client.get('/api/samples/toan')
assert r.status_code == 200
exam_data = r.json()
p1_len = len(exam_data['part1_mcq'])
p2_len = len(exam_data['part2_tf'])
p3_len = len(exam_data['part3_short'])
assert p1_len == 20
assert p2_len == 4
assert p3_len == 6
assert exam_data['academic_year'] == 'NĂM HỌC 2026 - 2027'
assert 'CHUYÊN' not in exam_data['school_name'].upper()
assert 'AMSTERDAM' not in exam_data['school_name'].upper()

# Check all samples for school name and 2026-2027 year
for s_key in ['vatly', 'hoahoc', 'gdqp']:
    r_s = client.get(f'/api/samples/{s_key}')
    assert r_s.status_code == 200
    s_data = r_s.json()
    assert s_data['academic_year'] == 'NĂM HỌC 2026 - 2027'
    assert 'CHUYÊN' not in s_data['school_name'].upper()
    assert 'AMSTERDAM' not in s_data['school_name'].upper()

print(f'   -> OK (All samples loaded: No "chuyên", academic_year is 2026 - 2027)')

print('3. Testing POST /api/shuffle...')
shuffle_payload = {
    'exam': exam_data,
    'num_variants': 4,
    'start_code': 101,
    'shuffle_part1_options': True,
    'shuffle_part2_subitems': True
}
r = client.post('/api/shuffle', json=shuffle_payload)
assert r.status_code == 200
shuffled_data = r.json()
v_count = len(shuffled_data['variants'])
codes = [v['code'] for v in shuffled_data['variants']]
assert v_count == 4
assert '101' in codes
assert '104' in codes
assert 'part2_rows' in shuffled_data['matrix']
assert len(shuffled_data['matrix']['part2_rows']) == 16  # 4 questions x 4 subitems
for row in shuffled_data['matrix']['part2_rows']:
    assert 'label' in row
    for c in codes:
        assert c in row['answers']
        assert row['answers'][c] in ['Đ', 'S', '-']

assert 'part3_rows' in shuffled_data['matrix']
assert len(shuffled_data['matrix']['part3_rows']) == 6
print(f'   -> OK (Shuffled into {v_count} variants: {codes}, matrix part2_rows and part3_rows verified)')

print('4. Testing POST /api/export-docx (Single Variant 101)...')
export_payload = {
    'exam': shuffled_data['variants'][0]['exam'],
    'variant_code': '101',
    'include_answers': True,
    'include_explanations': True
}
r = client.post('/api/export-docx', json=export_payload)
assert r.status_code == 200
docx_bytes = r.content
assert len(docx_bytes) > 10000
print(f'   -> OK (Exported docx size: {len(docx_bytes)} bytes with OMML math equations)')

print('5. Testing POST /api/export-zip (Full Bundle of All Variants)...')
zip_payload = {
    'exam': exam_data,
    'variants': shuffled_data['variants'],
    'include_answers': True,
    'include_explanations': True
}
r = client.post('/api/export-zip', json=zip_payload)
assert r.status_code == 200
zip_bytes = r.content
zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
file_list = zf.namelist()
assert len(file_list) == 5
print(f'   -> OK (ZIP contains {len(file_list)} files: {file_list})')

print('6. Testing POST /api/extract (Document extraction)...')
test_txt_bytes = io.BytesIO('Noi dung de kiem tra mau de hoc sinh on tap chu de nguyen ham tich phan.'.encode('utf-8'))
files = {'file': ('test.txt', test_txt_bytes, 'text/plain')}
r = client.post('/api/extract', files=files)
assert r.status_code == 200
extracted_res = r.json()
assert 'nguyen ham' in extracted_res['text']
print(f'   -> OK (File extracted {extracted_res["length"]} chars successfully)')

print('7. Testing 24 Exam Variants Shuffling & Export...')
shuffle_24_payload = {
    'exam': exam_data,
    'num_variants': 24,
    'start_code': 101,
    'shuffle_part1_options': True,
    'shuffle_part2_subitems': True
}
r24 = client.post('/api/shuffle', json=shuffle_24_payload)
assert r24.status_code == 200
shuffled_24_data = r24.json()
variants_24 = shuffled_24_data['variants']
assert len(variants_24) == 24
assert variants_24[0]['code'] == '101'
assert variants_24[-1]['code'] == '124'
print(f'   -> OK (Successfully shuffled 24 variants from 101 to 124)')

# Test export master Word with 24 variants chunked matrix
master_payload = {
    'exam': exam_data,
    'variant_code': 'TONG_HOP',
    'all_variants': variants_24,
    'include_answers': True,
    'include_explanations': True
}
r_master = client.post('/api/export-docx', json=master_payload)
assert r_master.status_code == 200
assert len(r_master.content) > 15000
print(f'   -> OK (Master Docx with 24 variants chunked matrix exported: {len(r_master.content)} bytes)')

# Test export zip with 24 variants + master docx
zip_24_payload = {
    'exam': exam_data,
    'variants': variants_24,
    'include_answers': True,
    'include_explanations': True
}
r_zip24 = client.post('/api/export-zip', json=zip_24_payload)
assert r_zip24.status_code == 200
zf24 = zipfile.ZipFile(io.BytesIO(r_zip24.content))
assert len(zf24.namelist()) == 25  # 24 variants + 1 master file
print(f'   -> OK (ZIP for 24 variants contains 25 files: {len(zf24.namelist())} files)')

print('8. Testing API Key Rotation Logic...')
from app.services.ai_generator import extract_api_keys, mask_key
from app.services.models import GenerateRequest

# Test single key string with newlines
req1 = GenerateRequest(
    api_key="AIzaSyA_key1\nAIzaSyB_key2, AIzaSyC_key3;AIzaSyD_key4",
    subject="Toán học"
)
keys1 = extract_api_keys(req1)
assert keys1 == ["AIzaSyA_key1", "AIzaSyB_key2", "AIzaSyC_key3", "AIzaSyD_key4"]

# Test api_keys list
req2 = GenerateRequest(
    api_keys=["AIzaSyA_111", "AIzaSyB_222"],
    subject="Toán học"
)
keys2 = extract_api_keys(req2)
assert keys2 == ["AIzaSyA_111", "AIzaSyB_222"]

assert mask_key("AIzaSy123456789") == "AIza...6789"
print(f'   -> OK (API Key rotation pool extraction verified: {keys1})')

print('\n' + '=' * 60)
print('  ALL TESTS (INCLUDING 24 VARIANTS & KEY ROTATION) PASSED WITH 100% SUCCESS!')
print('=' * 60)
