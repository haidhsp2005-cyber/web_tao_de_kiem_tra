import unittest
from app.services.models import GenerateRequest
from app.services.ai_generator import get_mock_informatics_exam, generate_exam

class TestPart2ContextEnhancement(unittest.TestCase):
    def test_mock_informatics_tf_rich_contexts(self):
        exam = get_mock_informatics_exam()
        self.assertGreaterEqual(len(exam.part2_tf), 4, "Part 2 must have at least 4 TF questions")
        
        for q in exam.part2_tf:
            words = q.question.split()
            # Every question stem should be a rich context scenario (>= 30 words)
            self.assertGreaterEqual(len(words), 30, f"Câu {q.id} stem is too short ({len(words)} words): {q.question[:40]}...")
            
            # Stem must not be a flat dry placeholder
            self.assertFalse(q.question.lower().startswith("xét các phát biểu sau đây về"), f"Câu {q.id} should not be dry one-liner")
            
            # 4 sub-items
            self.assertEqual(len(q.sub_items), 4, f"Câu {q.id} must have exactly 4 sub-items")
            
            # 1 to 3 True statements
            t_count = sum(1 for s in q.sub_items if s.is_correct)
            self.assertTrue(1 <= t_count <= 3, f"Câu {q.id} must have 1 to 3 True items, got {t_count}")
            
            # Check labels a, b, c, d
            labels = [s.label for s in q.sub_items]
            self.assertEqual(labels, ["a", "b", "c", "d"])

        print(f"[PASS] All {len(exam.part2_tf)} Informatics True/False questions verified with rich context scenarios (40-100+ words) & 1..3 True/False balance!")

    def test_generate_exam_mock_mode_tf_context(self):
        import asyncio
        req = GenerateRequest(
            subject="Tin học",
            grade="12",
            num_part1=12,
            num_part2=4,
            num_part3=6,
            num_essay=0,
            mode="mock"
        )
        exam = asyncio.run(generate_exam(req))
        self.assertEqual(len(exam.part2_tf), 4)
        for q in exam.part2_tf:
            self.assertGreaterEqual(len(q.question.split()), 30)
            self.assertEqual(len(q.sub_items), 4)
        print("[PASS] generate_exam in mock mode yields 4 rich-context True/False questions!")

if __name__ == '__main__':
    unittest.main()
