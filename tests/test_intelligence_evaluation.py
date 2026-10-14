"""
Tests for P0.3 Stage 1 Offline Evaluation Benchmark.
Verifies that the offline benchmark executes across the 5 corpus scenarios,
measures evidence grounding, entity accuracy, and produces an error taxonomy.
"""

import unittest
from evaluation.evaluator import ConversationEvaluator
from evaluation.corpus import CORPUS_CASES


class TestIntelligenceEvaluationP03(unittest.TestCase):
    """Verifies the P0.3 Stage 1 evaluation harness."""

    def test_evaluation_corpus_structure(self):
        """Corpus contains 10 distinct scenarios with ground truth annotations."""
        self.assertEqual(len(CORPUS_CASES), 10)
        for case in CORPUS_CASES:
            self.assertIn("id", case)
            self.assertIn("scenario", case)
            self.assertIn("transcript", case)
            self.assertIn("ground_truth", case)
            self.assertGreater(len(case["transcript"]["merged_turns"]), 0)

    def test_benchmark_execution_and_metrics(self):
        """Evaluator runs across all corpus cases and produces metrics."""
        evaluator = ConversationEvaluator()
        report = evaluator.run_benchmark()

        self.assertEqual(report["total_cases_evaluated"], 10)
        self.assertIn("resolution_status_accuracy", report)
        self.assertIn("remote_id_accuracy", report)
        self.assertIn("evidence_grounding_rate", report)
        self.assertIn("error_taxonomy", report)
        self.assertIsInstance(report["case_results"], list)
        self.assertEqual(len(report["case_results"]), 10)
        self.assertGreaterEqual(report["resolution_status_accuracy"], 0.80)
        self.assertEqual(report["remote_id_accuracy"], 1.0)
        self.assertEqual(report["evidence_grounding_rate"], 1.0)


if __name__ == "__main__":
    unittest.main()
