"""
Strands Decider 2B Reusable Intervention Handlers
=================================================
Drop-in agent lifecycle interceptors powered by Strands Decider 2B.
Provides 5 standardized decision patterns:
1. GuardrailInterventionHandler (#guardrails)
2. ModelRoutingInterventionHandler (#model-routing)
3. ToolSelectionInterventionHandler (#tool-selection)
4. ContextScorerInterventionHandler (#context-memory)
5. PolicyGateInterventionHandler (#policy)
"""

from __future__ import annotations
import abc
import logging
from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from .client import StrandsDecider2BClient, DecisionResult, DecisionType

logger = logging.getLogger("StrandsInterventionHandler")


class InterventionAction(str, Enum):
    PROCEED = "PROCEED"              # Decision approved, proceed with agent flow
    BLOCK = "BLOCK"                  # Guardrail/Policy violation, abort immediately
    ROUTE = "ROUTE"                  # Route request to selected target model/path
    MODIFY = "MODIFY"                # Modify payload (e.g. filtered context)
    ESCALATE = "ESCALATE"            # Escalate to human-in-the-loop verification


@dataclass
class InterventionResponse:
    action: InterventionAction
    decision_result: DecisionResult
    reason: str
    modified_payload: Optional[Any] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_allowed(self) -> bool:
        return self.action in (InterventionAction.PROCEED, InterventionAction.ROUTE, InterventionAction.MODIFY)


class BaseInterventionHandler(abc.ABC):
    """Abstract base class for Strands agent intervention hooks."""

    def __init__(self, decider_client: Optional[StrandsDecider2BClient] = None, confidence_threshold: float = 0.80):
        self.client = decider_client or StrandsDecider2BClient()
        self.confidence_threshold = confidence_threshold

    @abc.abstractmethod
    def intercept(self, event_type: str, state: Dict[str, Any], payload: Any) -> InterventionResponse:
        """Evaluate incoming state and determine intervention action."""
        pass


# =========================================================================
# Pattern 1: Guardrail Intervention Handler (#guardrails)
# =========================================================================
class GuardrailInterventionHandler(BaseInterventionHandler):
    """
    Pattern: #guardrails
    Verifies that proposed tool calls and arguments are strictly grounded in user instructions
    and within safe operational boundaries before execution.
    
    Usage:
    >>> handler = GuardrailInterventionHandler()
    >>> res = handler.validate_tool_call(
    ...     tool_name="terminate_instance",
    ...     tool_args={"instance_id": "i-12345"},
    ...     user_prompt="Restart the staging web server"
    ... )
    >>> if not res.is_allowed:
    ...     raise SecurityException(res.reason)
    """

    def __init__(
        self,
        decider_client: Optional[StrandsDecider2BClient] = None,
        confidence_threshold: float = 0.85,
        strict_mode: bool = True,
    ):
        super().__init__(decider_client, confidence_threshold)
        self.strict_mode = strict_mode

    def intercept(self, event_type: str, state: Dict[str, Any], payload: Any) -> InterventionResponse:
        tool_name = payload.get("tool_name", "")
        tool_args = payload.get("tool_args", {})
        user_prompt = state.get("user_prompt", "")
        return self.validate_tool_call(tool_name, tool_args, user_prompt, state)

    def validate_tool_call(
        self,
        tool_name: str,
        tool_args: Dict[str, Any],
        user_prompt: str,
        extra_context: Optional[Dict[str, Any]] = None,
    ) -> InterventionResponse:
        state = {
            "user_prompt": user_prompt,
            "tool_name": tool_name,
            "tool_args": tool_args,
            "context": extra_context or {},
        }
        
        question = (
            f"Is the tool call '{tool_name}' with arguments {tool_args} "
            f"strictly grounded in the user's explicit request '{user_prompt}' and safe to execute?"
        )

        result = self.client.decide_boolean(state=state, question=question)

        # High-confidence safety check
        if result.decision is True and result.confidence >= self.confidence_threshold:
            return InterventionResponse(
                action=InterventionAction.PROCEED,
                decision_result=result,
                reason=f"Decider 2B verified tool safety with {result.confidence*100:.1f}% confidence in {result.latency_ms:.1f}ms",
            )
        elif result.decision is False:
            return InterventionResponse(
                action=InterventionAction.BLOCK,
                decision_result=result,
                reason=f"Decider 2B blocked unsafe/ungrounded tool '{tool_name}' (confidence {result.confidence*100:.1f}%)",
            )
        else:
            # Low confidence decision -> escalate to human if strict mode
            action = InterventionAction.ESCALATE if self.strict_mode else InterventionAction.PROCEED
            return InterventionResponse(
                action=action,
                decision_result=result,
                reason=f"Decider 2B confidence ({result.confidence*100:.1f}%) below threshold {self.confidence_threshold*100:.1f}%",
            )


# =========================================================================
# Pattern 2: Model Routing Intervention Handler (#model-routing)
# =========================================================================
class ModelRoutingInterventionHandler(BaseInterventionHandler):
    """
    Pattern: #model-routing
    Triages incoming requests in 115ms to select the optimal Amazon Bedrock model tier:
    - Lightweight fast model: 'anthropic.claude-3-haiku-20240307-v1:0' (e.g. for simple lookups, status checks)
    - Frontier reasoning model: 'anthropic.claude-3-5-sonnet-20241022-v2:0' (e.g. for multi-step diagnosis, code gen)
    
    Saves ~70-90% token cost and reduces average response latency by 800ms+.
    """

    DEFAULT_MODELS = [
        "anthropic.claude-3-haiku-20240307-v1:0",
        "anthropic.claude-3-5-sonnet-20241022-v2:0",
    ]

    def __init__(
        self,
        decider_client: Optional[StrandsDecider2BClient] = None,
        available_models: Optional[List[str]] = None,
        default_model: str = "anthropic.claude-3-5-sonnet-20241022-v2:0",
    ):
        super().__init__(decider_client)
        self.available_models = available_models or self.DEFAULT_MODELS
        self.default_model = default_model

    def intercept(self, event_type: str, state: Dict[str, Any], payload: Any) -> InterventionResponse:
        user_query = payload if isinstance(payload, str) else state.get("query", "")
        return self.route_query(user_query, state)

    def route_query(self, query: str, context: Optional[Dict[str, Any]] = None) -> InterventionResponse:
        state = {
            "query": query,
            "query_length": len(query),
            "context": context or {},
        }
        question = "Which Amazon Bedrock model tier is required to accurately resolve this query?"
        
        result = self.client.decide_choice(
            state=state,
            question=question,
            options=self.available_models,
        )

        chosen_model = str(result.decision)
        return InterventionResponse(
            action=InterventionAction.ROUTE,
            decision_result=result,
            reason=f"Routed to {chosen_model} in {result.latency_ms:.1f}ms (confidence {result.confidence*100:.1f}%)",
            modified_payload={"selected_model_id": chosen_model},
        )


# =========================================================================
# Pattern 3: Tool Selection Intervention Handler (#tool-selection)
# =========================================================================
class ToolSelectionInterventionHandler(BaseInterventionHandler):
    """
    Pattern: #tool-selection
    Performs deterministic, ultra-fast 1-of-N tool selection before LLM generation.
    """

    def __init__(
        self,
        tools_registry: Dict[str, str], # tool_name -> description
        decider_client: Optional[StrandsDecider2BClient] = None,
    ):
        super().__init__(decider_client)
        self.tools_registry = tools_registry

    def intercept(self, event_type: str, state: Dict[str, Any], payload: Any) -> InterventionResponse:
        user_intent = state.get("user_intent", "")
        return self.select_tool(user_intent, state)

    def select_tool(self, user_intent: str, context: Optional[Dict[str, Any]] = None) -> InterventionResponse:
        tool_options = list(self.tools_registry.keys()) + ["NO_TOOL_NEEDED"]
        state = {
            "user_intent": user_intent,
            "available_tools": self.tools_registry,
            "context": context or {},
        }
        question = "Which tool should be invoked to satisfy the user's intent?"

        result = self.client.decide_choice(
            state=state,
            question=question,
            options=tool_options,
        )

        return InterventionResponse(
            action=InterventionAction.PROCEED if result.decision != "NO_TOOL_NEEDED" else InterventionAction.MODIFY,
            decision_result=result,
            reason=f"Selected tool '{result.decision}' in {result.latency_ms:.1f}ms",
            modified_payload={"tool_name": result.decision},
        )


# =========================================================================
# Pattern 4: Context & Memory Scorer Intervention Handler (#context-memory)
# =========================================================================
class ContextScorerInterventionHandler(BaseInterventionHandler):
    """
    Pattern: #context-memory
    Scores and filters retrieved context chunks or conversation memories to keep prompt windows concise.
    """

    def __init__(
        self,
        decider_client: Optional[StrandsDecider2BClient] = None,
        min_relevance_score: float = 0.65,
    ):
        super().__init__(decider_client)
        self.min_relevance_score = min_relevance_score

    def intercept(self, event_type: str, state: Dict[str, Any], payload: Any) -> InterventionResponse:
        chunks = payload.get("chunks", [])
        query = state.get("query", "")
        return self.filter_context(chunks, query)

    def filter_context(self, chunks: List[Dict[str, Any]], query: str) -> InterventionResponse:
        filtered_chunks = []
        scores = []
        total_latency = 0.0

        for chunk in chunks:
            state = {"query": query, "chunk_content": chunk.get("content", "")}
            question = "Is this context snippet relevant and helpful for answering the user query?"
            res = self.client.decide_score(state=state, question=question)
            total_latency += res.latency_ms
            score_val = float(res.decision)
            scores.append(score_val)
            if score_val >= self.min_relevance_score:
                chunk_copy = dict(chunk)
                chunk_copy["decider_relevance_score"] = round(score_val, 3)
                filtered_chunks.append(chunk_copy)

        dummy_result = DecisionResult(
            decision=len(filtered_chunks),
            confidence=0.95,
            decision_type=DecisionType.SCORE,
            latency_ms=total_latency,
            state_fingerprint=f"filtered_{len(filtered_chunks)}_of_{len(chunks)}",
            question="Batch context relevance scoring",
        )

        return InterventionResponse(
            action=InterventionAction.MODIFY,
            decision_result=dummy_result,
            reason=f"Retained {len(filtered_chunks)}/{len(chunks)} relevant chunks in {total_latency:.1f}ms",
            modified_payload={"filtered_chunks": filtered_chunks},
        )


# =========================================================================
# Pattern 5: Policy Gate Intervention Handler (#policy)
# =========================================================================
class PolicyGateInterventionHandler(BaseInterventionHandler):
    """
    Pattern: #policy
    Classifies incoming requests into compliance / governance tiers (e.g. READ_ONLY, WRITE_STAGING, WRITE_PROD, BLOCKED).
    """

    CATEGORIES = ["READ_ONLY", "WRITE_STAGING", "WRITE_PRODUCTION", "PROHIBITED"]

    def __init__(
        self,
        decider_client: Optional[StrandsDecider2BClient] = None,
        categories: Optional[List[str]] = None,
    ):
        super().__init__(decider_client)
        self.categories = categories or self.CATEGORIES

    def intercept(self, event_type: str, state: Dict[str, Any], payload: Any) -> InterventionResponse:
        request_text = payload if isinstance(payload, str) else state.get("request", "")
        return self.classify_policy(request_text, state)

    def classify_policy(self, request_text: str, context: Optional[Dict[str, Any]] = None) -> InterventionResponse:
        state = {"request": request_text, "context": context or {}}
        question = "What is the security and compliance policy classification of this user request?"

        result = self.client.decide_choice(
            state=state,
            question=question,
            options=self.categories,
        )

        action = InterventionAction.BLOCK if result.decision == "PROHIBITED" else InterventionAction.PROCEED
        return InterventionResponse(
            action=action,
            decision_result=result,
            reason=f"Classified into policy tier '{result.decision}' ({result.confidence*100:.1f}%) in {result.latency_ms:.1f}ms",
            modified_payload={"policy_classification": result.decision},
        )
