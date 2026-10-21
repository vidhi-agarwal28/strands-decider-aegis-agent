"""
Unit Tests for StrandsDecider2BClient
"""

import unittest
from strands_decider_sdk.client import StrandsDecider2BClient, DecisionType, DecisionResult


class TestStrandsDeciderClient(unittest.TestCase):

    def setUp(self):
        self.client = StrandsDecider2BClient(mean_latency_ms=10.0, latency_jitter_ms=1.0)

    def test_decide_boolean_safe(self):
        state = {"command": "kubectl get pods", "env": "staging"}
        question = "Is this read-only command safe to run?"
        res = self.client.decide_boolean(state, question)

        self.assertIsInstance(res, DecisionResult)
        self.assertEqual(res.decision_type, DecisionType.BOOLEAN)
        self.assertTrue(res.decision)
        self.assertGreaterEqual(res.confidence, 0.80)
        self.assertGreater(res.latency_ms, 0.0)

    def test_decide_boolean_dangerous(self):
        state = {"command": "rm -rf / --no-preserve-root", "user": "guest"}
        question = "Is this command safe and allowed?"
        res = self.client.decide_boolean(state, question)

        self.assertFalse(res.decision)
        self.assertGreaterEqual(res.confidence, 0.90)

    def test_decide_choice(self):
        state = {"query": "Diagnose complex distributed deadlock in database"}
        options = ["anthropic.claude-3-haiku", "anthropic.claude-3-5-sonnet"]
        question = "Which model tier is best suited for complex reasoning?"

        res = self.client.decide_choice(state, question, options)
        self.assertEqual(res.decision_type, DecisionType.CHOICE)
        self.assertIn(res.decision, options)
        self.assertEqual(res.decision, "anthropic.claude-3-5-sonnet")

    def test_decide_score(self):
        state = {"log_entry": "FATAL Kernel Panic at 0x00021A", "severity": "critical"}
        question = "How critical is this incident?"

        res = self.client.decide_score(state, question)
        self.assertEqual(res.decision_type, DecisionType.SCORE)
        self.assertIsInstance(res.decision, float)
        self.assertGreaterEqual(res.decision, 0.8)


if __name__ == "__main__":
    unittest.main()
