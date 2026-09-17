import sys
import json
import json_repair

sys.stdout.reconfigure(encoding='utf-8')

# Test 1: Unescaped quotes inside a string
s1 = '{"explanation": "Phương trình có dạng "ax + b = 0" nên ta có nghiệm duy nhất."}'
try:
    json.loads(s1)
    print("Standard json succeeded (unexpected)")
except Exception as e:
    print(f"Standard json failed as expected: {e}")

res1 = json_repair.loads(s1)
print(f"json_repair result: {res1}")

# Test 2: Unescaped LaTeX commands
s2 = r'{"math": "Ta có \tan(x) + \cot(x) = \frac{1}{\sin(x)\cos(x)} và \beta \neq 0"}'
res2 = json_repair.loads(s2)
print(f"json_repair LaTeX result: {res2}")

# Test 3: Truncated JSON
s3 = '{"title": "Đề thi", "part1_mcq": [{"id": 1, "question": "Hàm số nào đồng biến?", "options": [{"label": "A", "text": "y = x"'
res3 = json_repair.loads(s3)
print(f"json_repair truncated result: {res3}")
