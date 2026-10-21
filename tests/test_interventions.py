"""
Unit Tests for Reusable Decider 2B Intervention Handlers
"""

import unittest
from strands_decider_sdk.client import StrandsDecider2BClient
from strands_decider_sdk.intervention import (
    GuardrailInterventionHandler,
    ModelRoutingInterventionHandler,
    ToolSelectionInterventionHandler,
    ContextScorerInterventionHandler,
    PolicyGateInterventionHandler,
    InterventionAction,
)


class TestInterventionHandlers(unittest.TestCase):

    def setUp(self):
        self.decider = StrandsDecider2BClient(mean_latency_ms=10.0, latency_jitter_ms=1.0)

    def test_guardrail_allows_grounded_tool(self):
        handler = GuardrailInterventionHandler(decider_client=self.decider)
        resp = handler.validate_tool_call(
            tool_name="scale_k8s_deployment",
            tool_args={"deployment": "web", "replicas": 3},
            user_prompt="Please scale up the web deployment to 3 replicas",
        )
        self.assertEqual(resp.action, InterventionAction.PROCEED)
        self.assertTrue(resp.is_allowed)

    def test_guardrail_blocks_dangerous_tool(self):
        handler = GuardrailInterventionHandler(decider_client=self.decider)
        resp = handler.validate_tool_call(
            tool_name="drop_database",
            tool_args={"db": "prod_users"},
            user_prompt="Check system status",
        )
        self.assertEqual(resp.action, InterventionAction.BLOCK)
        self.assertFalse(resp.is_allowed)

    def test_model_routing_haiku_vs_sonnet(self):
        handler = ModelRoutingInterventionHandler(decider_client=self.decider)
        
        # Simple ping query -> Haiku
        resp_simple = handler.route_query("status ping")
        self.assertEqual(resp_simple.action, InterventionAction.ROUTE)
        self.assertIn("haiku", resp_simple.modified_payload["selected_model_id"])

        # Complex diagnosis query -> Sonnet
        resp_complex = handler.route_query("Analyze incident root cause and deadlock trace")
        self.assertEqual(resp_complex.action, InterventionAction.ROUTE)
        self.assertIn("sonnet", resp_complex.modified_payload["selected_model_id"])

    def test_tool_selection_handler(self):
        registry = {
            "query_cloudwatch_metrics": "Query CPU/memory metrics",
            "fetch_pod_logs": "Retrieve pod logs",
        }
        handler = ToolSelectionInterventionHandler(tools_registry=registry, decider_client=self.decider)
        resp = handler.select_tool("Check CPU utilization metrics for web-api")
        
        self.assertEqual(resp.action, InterventionAction.PROCEED)
        self.assertEqual(resp.modified_payload["tool_name"], "query_cloudwatch_metrics")

    def test_context_scorer_filtering(self):
        handler = ContextScorerInterventionHandler(decider_client=self.decider, min_relevance_score=0.6)
        chunks = [
            {"id": "doc_1", "content": "Database CPU spiked to critical 99% during peak load"},
            {"id": "doc_2", "content": "Lunch menu for Friday at cafeteria"},
        ]
        resp = handler.filter_context(chunks, query="Database CPU issue")
        self.assertEqual(resp.action, InterventionAction.MODIFY)
        retained = resp.modified_payload["filtered_chunks"]
        self.assertGreaterEqual(len(retained), 1)


if __name__ == "__main__":
    unittest.main()
