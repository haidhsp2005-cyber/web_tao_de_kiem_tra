import unittest
from app.services.models import GenerateRequest, calculate_exam_scoring
from app.services.ai_generator import generate_exam, get_mock_informatics_exam

class Test28Mcq3Tf(unittest.TestCase):
    def test_scoring_28_mcq_3_tf(self):
        # 28 MCQ (0.25đ each) = 7.0đ
        # 3 TF (1.0đ each) = 3.0đ
        # Total = 10.0đ
        scoring = calculate_exam_scoring(num_p1=28, num_p2=3, num_p3=0, num_p4=0)
        self.assertEqual(scoring.part1_points, 7.0)
        self.assertEqual(scoring.part1_per_q, 0.25)
        self.assertEqual(scoring.part2_points, 3.0)
        self.assertEqual(scoring.part2_per_q, 1.0)
        self.assertEqual(scoring.part3_points, 0.0)
        self.assertEqual(scoring.part4_points, 0.0)
        self.assertEqual(scoring.total_points, 10.0)
        print("[PASS] Scoring for 28 MCQ (7.0đ) + 3 TF (3.0đ) = 10.0đ verified!")

    def test_mock_fallback_guarantee_for_28_mcq(self):
        # Even with offline mock mode or partial mock, 28 MCQs and 3 TF questions must be 100% fulfilled
        req = GenerateRequest(
            subject="Tin học",
            grade="12",
            num_part1=28,
            num_part2=3,
            num_part3=0,
            num_essay=0,
            mode="mock"
        )
        import asyncio
        exam = asyncio.run(generate_exam(req))
        self.assertEqual(len(exam.part1_mcq), 28, f"Expected 28 MCQs, got {len(exam.part1_mcq)}")
        self.assertEqual(len(exam.part2_tf), 3, f"Expected 3 TF, got {len(exam.part2_tf)}")
        self.assertEqual(len(exam.part3_short), 0)
        self.assertEqual(len(exam.part4_essay), 0)
        
        # Verify IDs are strictly 1..28 and 1..3
        for i, q in enumerate(exam.part1_mcq, 1):
            self.assertEqual(q.id, i)
        for i, q in enumerate(exam.part2_tf, 1):
            self.assertEqual(q.id, i)
            
        self.assertEqual(exam.scoring.part1_points, 7.0)
        self.assertEqual(exam.scoring.part2_points, 3.0)
        self.assertEqual(exam.scoring.total_points, 10.0)
        print(f"[PASS] Successfully generated EXACTLY {len(exam.part1_mcq)} MCQs and {len(exam.part2_tf)} TF questions with IDs 1..28 and 1..3!")

if __name__ == '__main__':
    unittest.main()
