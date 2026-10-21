"""
AegisAgent: Autonomous SRE & Security Incident Commander Agent
==============================================================
Pairs AWS Strands Decider 2B for sub-120ms safety guardrails and model routing
with Amazon Bedrock (Claude 3.5 Sonnet & Claude 3 Haiku) for deep generative reasoning.
"""

from __future__ import annotations
import time
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from strands_decider_sdk.client import StrandsDecider2BClient
from strands_decider_sdk.intervention import (
    GuardrailInterventionHandler,
    ModelRoutingInterventionHandler,
    PolicyGateInterventionHandler,
    InterventionAction,
    InterventionResponse,
)
from .bedrock_connector import BedrockConnector, BedrockResponse
from .tools import AegisToolRegistry

logger = logging.getLogger("AegisAgent")


@dataclass
class AgentTurnAudit:
    user_input: str
    policy_decision: Optional[InterventionResponse] = None
    routing_decision: Optional[InterventionResponse] = None
    bedrock_response: Optional[BedrockResponse] = None
    guardrail_decisions: List[InterventionResponse] = field(default_factory=list)
    executed_tools: List[Dict[str, Any]] = field(default_factory=list)
    blocked_tools: List[Dict[str, Any]] = field(default_factory=list)
    total_latency_ms: float = 0.0
    decider_latency_ms: float = 0.0
    bedrock_latency_ms: float = 0.0
    total_cost_usd: float = 0.0
    final_output: str = ""


class AegisAgent:
    """
    Production-grade Autonomous Agent implementing Strands Decider 2B Intervention Handlers.
    
    Architecture:
    User Input
        │
        ├──> [1. Policy Gate (Decider 2B, ~115ms)] ──(Blocked)──> Immediate Safe Exit (0 Bedrock Tokens)
        │
        ├──> [2. Model Router (Decider 2B, ~115ms)] ───────────> Selects Haiku vs Sonnet
        │
        ├──> [3. Bedrock Generative Reasoning] ────────────────> Proposes SRE Actions / Diagnosis
        │
        └──> [4. Guardrail Interceptor (Decider 2B, ~115ms)] ──> Evaluates Blast Radius & Grounding
                 │
                 ├── Approved ──> Tool Execution
                 └── Denied   ──> Safety Abort
    """

    def __init__(
        self,
        decider_client: Optional[StrandsDecider2BClient] = None,
        bedrock_connector: Optional[BedrockConnector] = None,
    ):
        self.decider = decider_client or StrandsDecider2BClient()
        self.bedrock = bedrock_connector or BedrockConnector()

        # Wire reusable Strands Decider 2B Intervention Handlers
        self.policy_handler = PolicyGateInterventionHandler(decider_client=self.decider)
        self.router_handler = ModelRoutingInterventionHandler(decider_client=self.decider)
        self.guardrail_handler = GuardrailInterventionHandler(
            decider_client=self.decider,
            confidence_threshold=0.85,
            strict_mode=True,
        )

    def handle_request(self, user_prompt: str, context: Optional[Dict[str, Any]] = None) -> AgentTurnAudit:
        """Process an SRE or Security incident turn through Decider 2B lifecycle hooks."""
        overall_start = time.perf_counter()
        audit = AgentTurnAudit(user_input=user_prompt)

        # -------------------------------------------------------------
        # Step 1: Policy Gate Check (Strands Decider 2B)
        # -------------------------------------------------------------
        policy_res = self.policy_handler.classify_policy(user_prompt, context)
        audit.policy_decision = policy_res
        audit.decider_latency_ms += policy_res.decision_result.latency_ms

        if policy_res.action == InterventionAction.BLOCK:
            audit.final_output = (
                f"🛡️ [SECURITY POLICY REJECTION] Request was blocked by Strands Decider 2B in "
                f"{policy_res.decision_result.latency_ms:.1f}ms (Confidence: {policy_res.decision_result.confidence*100:.1f}%).\n"
                f"Reason: Classified as PROHIBITED action without spending any generative tokens."
            )
            audit.total_latency_ms = (time.perf_counter() - overall_start) * 1000.0
            return audit

        # -------------------------------------------------------------
        # Step 2: Adaptive Model Routing (Strands Decider 2B)
        # -------------------------------------------------------------
        routing_res = self.router_handler.route_query(user_prompt, context)
        audit.routing_decision = routing_res
        audit.decider_latency_ms += routing_res.decision_result.latency_ms
        selected_model = routing_res.modified_payload.get(
            "selected_model_id", "anthropic.claude-3-5-sonnet-20241022-v2:0"
        )

        # -------------------------------------------------------------
        # Step 3: Generative Reasoning (Amazon Bedrock)
        # -------------------------------------------------------------
        system_prompt = (
            "You are AegisAgent, an Autonomous AWS Cloud SRE and Security Incident Commander. "
            "Analyze telemetry, provide root-cause diagnosis, and propose safe remediation actions."
        )
        bedrock_res = self.bedrock.invoke(
            prompt=user_prompt,
            model_id=selected_model,
            system_prompt=system_prompt,
        )
        audit.bedrock_response = bedrock_res
        audit.bedrock_latency_ms = bedrock_res.latency_ms
        audit.total_cost_usd += bedrock_res.cost_usd

        # -------------------------------------------------------------
        # Step 4: Extract Proposed Tool Calls & Intercept with Guardrails (Strands Decider 2B)
        # -------------------------------------------------------------
        proposed_tools = self._extract_proposed_tools(user_prompt, bedrock_res.text)

        remediation_reports = []
        for tool_call in proposed_tools:
            t_name = tool_call["tool_name"]
            t_args = tool_call["tool_args"]

            guard_res = self.guardrail_handler.validate_tool_call(
                tool_name=t_name,
                tool_args=t_args,
                user_prompt=user_prompt,
                extra_context=context,
            )
            audit.guardrail_decisions.append(guard_res)
            audit.decider_latency_ms += guard_res.decision_result.latency_ms

            if guard_res.is_allowed:
                exec_result = AegisToolRegistry.execute(t_name, t_args)
                audit.executed_tools.append({"tool": t_name, "args": t_args, "result": exec_result})
                remediation_reports.append(
                    f"✅ [APPROVED & EXECUTED] Tool '{t_name}' verified by Decider 2B "
                    f"({guard_res.decision_result.latency_ms:.1f}ms, confidence: {guard_res.decision_result.confidence*100:.1f}%).\n"
                    f"   Result: {exec_result.get('message', exec_result)}"
                )
            else:
                audit.blocked_tools.append({"tool": t_name, "args": t_args, "reason": guard_res.reason})
                remediation_reports.append(
                    f"🛑 [BLOCKED BY DECIDER 2B] Dangerous or ungrounded tool call '{t_name}' intercepted!\n"
                    f"   Reason: {guard_res.reason}"
                )

        audit.total_latency_ms = (time.perf_counter() - overall_start) * 1000.0

        # Construct unified agent response
        tool_summary = "\n".join(remediation_reports) if remediation_reports else "No tools required for this turn."
        audit.final_output = (
            f"=== AegisAgent Incident Summary ===\n"
            f"{bedrock_res.text}\n\n"
            f"--- Active Interventions & Remediations ---\n"
            f"{tool_summary}\n\n"
            f"📊 Metrics: Total Turn: {audit.total_latency_ms:.1f}ms | Decider 2B: {audit.decider_latency_ms:.1f}ms | "
            f"Bedrock: {audit.bedrock_latency_ms:.1f}ms | Cost: ${audit.total_cost_usd:.6f}"
        )

        return audit

    def _extract_proposed_tools(self, user_prompt: str, bedrock_text: str) -> List[Dict[str, Any]]:
        """Parses tool invocations proposed by Bedrock text or query intent."""
        proposed = []
        text_lower = (user_prompt + " " + bedrock_text).lower()

        if "scale" in text_lower or "oom" in text_lower or "high cpu" in text_lower:
            proposed.append({
                "tool_name": "scale_k8s_deployment",
                "tool_args": {"namespace": "production", "deployment_name": "payment-processor", "replicas": 4},
            })
        
        if "metrics" in text_lower or "cloudwatch" in text_lower:
            proposed.append({
                "tool_name": "query_cloudwatch_metrics",
                "tool_args": {"service_name": "payment-processor", "metric_name": "CPUUtilization"},
            })

        if any(w in text_lower for w in ["drop", "rm -rf", "delete namespace", "terminate", "wipe", "force"]):
            proposed.append({
                "tool_name": "terminate_infrastructure",
                "tool_args": {"target": "prod-database-primary", "force": True},
            })

        return proposed
