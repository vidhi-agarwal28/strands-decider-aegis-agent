"""
Strands Decider 2B Python SDK & Reusable Patterns
=================================================
AWS Hackathon Submission: Reusable Decision Patterns for Strands Decider 2B & Amazon Bedrock
"""

__version__ = "1.0.0"
__author__ = "AWS Builder"

from .client import StrandsDecider2BClient, DecisionResult, DecisionType
from .intervention import (
    BaseInterventionHandler,
    GuardrailInterventionHandler,
    ModelRoutingInterventionHandler,
    ToolSelectionInterventionHandler,
    ContextScorerInterventionHandler,
    PolicyGateInterventionHandler,
    InterventionAction,
    InterventionResponse,
)

__all__ = [
    "StrandsDecider2BClient",
    "DecisionResult",
    "DecisionType",
    "BaseInterventionHandler",
    "GuardrailInterventionHandler",
    "ModelRoutingInterventionHandler",
    "ToolSelectionInterventionHandler",
    "ContextScorerInterventionHandler",
    "PolicyGateInterventionHandler",
    "InterventionAction",
    "InterventionResponse",
]
