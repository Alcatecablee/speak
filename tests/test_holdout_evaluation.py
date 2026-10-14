"""
Tests for Independent Holdout Benchmark Evaluation.
Runs the offline evaluator against the unseen HOLDOUT_CASES corpus.
Verifies that the generalized engine maintains:
  - >= 80% resolution classification accuracy on unseen GAAP support scenarios
  - 100% remote ID precision with 0 hallucinations
  - 100% evidence grounding rate with semantic entailment verification
"""

import unittest
from evaluation.evaluator import ConversationEvaluator
from evaluation.holdout_corpus import HOLDOUT_CASES


class TestHoldoutBenchmarkEvaluation(unittest.TestCase):
    """Evaluates generalization performance on unseen GAAP holdout scenarios."""

    def test_holdout_corpus_structure(self):
        """Holdout corpus contains 10 distinct, non-overlapping scenarios."""
        self.assertEqual(len(HOLDOUT_CASES), 10)
        for case in HOLDOUT_CASES:
            self.assertIn("id", case)
            self.assertIn("scenario", case)
            self.assertIn("transcript", case)
            self.assertIn("ground_truth", case)
            self.assertGreater(len(case["transcript"]["merged_turns"]), 0)

    def test_holdout_benchmark_metrics(self):
        """Evaluator runs blindly over all 10 holdout cases and satisfies CTO targets."""
        evaluator = ConversationEvaluator()
        report = evaluator.run_benchmark(corpus=HOLDOUT_CASES)

        self.assertEqual(report["total_cases_evaluated"], 10)
        self.assertGreaterEqual(report["resolution_status_accuracy"], 0.80)
        self.assertEqual(report["remote_id_accuracy"], 1.0)
        self.assertEqual(report["evidence_grounding_rate"], 1.0)
        self.assertEqual(report["error_count"], 0)


if __name__ == "__main__":
    unittest.main()
