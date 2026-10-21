# 🛡️ AegisAgent: Sub-120ms Guardrails & Adaptive Model Routing with AWS Strands Decider 2B

[![AWS Hackathon](https://img.shields.io/badge/AWS%20Hackathon-Strands%20Decider%202B-FF9900?logo=amazon-aws)](https://aws.amazon.com)
[![Model](https://img.shields.io/badge/Model-Strands%20Decider%202B%20(~115ms)-238636)](https://aws.amazon.com)
[![Bedrock](https://img.shields.io/badge/Amazon%20Bedrock-Claude%203.5%20Sonnet%20%7C%20Haiku-blue)](https://aws.amazon.com/bedrock)
[![Tests](https://img.shields.io/badge/Tests-12%2F12%20Passing-success)](run_tests.py)
[![Tags](https://img.shields.io/badge/Tags-%23strands--decider--2b%20%7C%20%23guardrails-purple)](#tags)

A high-performance autonomous SRE & Security Incident Commander agent that pairs **AWS Strands Decider 2B** for sub-120ms safety guardrails and adaptive model routing with **Amazon Bedrock** (Claude 3.5 Sonnet & Claude 3 Haiku) for deep generative reasoning.

---

## 🌟 Key Highlights

- **11.7x Faster Guardrails:** Slashes pre-flight tool verification latency from **1,373ms (Pure LLM)** down to **118ms (Decider 2B)**.
- **96.5% Cost Reduction:** Completely eliminates generative token consumption for high-frequency safety checks.
- **Zero-Token Defense Perimeter:** Intercepts prompt injections and destructive commands before LLM execution.
- **5 Reusable Decider 2B Intervention Handlers:** Ready-to-use drop-in Python patterns for the AWS builder community.
- **Full Interactive Suite:** Includes terminal demo runner, web visualizer dashboard, and automated benchmark suite.

---

## 🏗️ Architecture

```
User / Alert Prompt
       │
       ▼
[ Strands Decider 2B Policy Gate (115ms) ] ──(Prohibited)──> 🛑 Safe Early Abort (0 Bedrock Tokens)
       │ (Approved)
       ▼
[ Strands Decider 2B Model Router (115ms)] ───────────────> Triage (Haiku vs Sonnet)
       │
       ▼
[ Amazon Bedrock Generative Reasoning ] ──────────────────> Propose SRE Diagnostic / Tool Calls
       │
       ▼
[ Strands Decider 2B Guardrail Interceptor (115ms) ] ────> Validate Blast Radius & Grounding
       │
       ├── Approved ──> ✅ Execute Tool (Scale EKS, Restart Pod, Isolate SG)
       └── Denied   ──> 🛑 Abort Unsafe Action
```

---

## 🚀 Quickstart

### Prerequisites
- Python 3.9+
- Optional: AWS credentials configured for live Bedrock calls (automatic high-fidelity simulation enabled if credentials omitted)

### Installation
```bash
git clone https://github.com/aws-builder/strands-decider-aegis-agent.git
cd strands-decider-agent
```

### 1. Run Interactive Terminal Walkthrough
```bash
PYTHONPATH=. python3 demo.py
```

### 2. Launch Live Web Dashboard & API Server
```bash
PYTHONPATH=. python3 web_server.py
# Open your browser at http://localhost:8080
```

### 3. Run Automated Latency & Cost Benchmark Suite
```bash
PYTHONPATH=. python3 benchmarks/benchmark_suite.py
```

### 4. Run Unit & Integration Tests
```bash
PYTHONPATH=. python3 run_tests.py
```

---

## 📦 The Reusable Asset: Decider 2B Decision Recipes

This project packages `strands_decider_sdk` providing 5 standardized `InterventionHandler` recipes:

| Decision Pattern Tag | Handler Class | Description |
| :--- | :--- | :--- |
| **`#guardrails`** (Primary) | `GuardrailInterventionHandler` | Verifies proposed tool calls & arguments are grounded in prompt and safe. |
| **`#model-routing`** | `ModelRoutingInterventionHandler` | Dynamically routes requests between fast (Haiku) and frontier (Sonnet) models. |
| **`#tool-selection`** | `ToolSelectionInterventionHandler` | Fast 1-of-N tool selection in 115ms before LLM generation. |
| **`#context-memory`** | `ContextScorerInterventionHandler` | Scores and filters RAG memory context chunks to keep prompt windows compact. |
| **`#policy`** | `PolicyGateInterventionHandler` | Classifies requests into policy compliance tiers (`READ_ONLY`, `PROHIBITED`, etc.). |

### Drop-in Code Example:
```python
from strands_decider_sdk import StrandsDecider2BClient, GuardrailInterventionHandler

decider = StrandsDecider2BClient()
guardrail = GuardrailInterventionHandler(decider_client=decider, confidence_threshold=0.85)

response = guardrail.validate_tool_call(
    tool_name="scale_k8s_deployment",
    tool_args={"deployment": "payment-service", "replicas": 4},
    user_prompt="Scale up payment service to 4 replicas"
)

if response.is_allowed:
    print(f"Tool approved in {response.decision_result.latency_ms:.1f}ms!")
```

---

## 📊 Benchmark Findings

```
========================================================================================
🏆 STRANDS DECIDER 2B BENCHMARK REPORT: LATENCY & COST SAVINGS
========================================================================================

1. Tool Guardrail Pre-flight Verification Benchmark (20 iterations)
----------------------------------------------------------------------------------------
| Metric                   | Strands Decider 2B      | Pure Bedrock (Claude 3.5 Sonnet) | Delta / Improvement     |
|--------------------------|-------------------------|----------------------------------|-------------------------|
| P50 Latency (Median)     |      118.1 ms       |              1384.5 ms          |   11.7x Faster (p50)   |
| P90 Latency              |      121.8 ms       |              1403.1 ms          |   11.5x Faster (p90)   |
| Mean Latency             |      117.9 ms       |              1373.5 ms          | **11.6x Speedup**       |
| Total Generative Tokens  |          0          |                1456          | **100% Token Elimination**|
| Estimated Cost (20 reqs) | $  0.00040        | $           0.01157          | **96.5% Cost Reduction**|

2. Multi-tier Model Routing Benchmark (20 iterations)
----------------------------------------------------------------------------------------
| Metric                   | Decider 2B Dynamic Route| All Claude 3.5 Sonnet (Unrouted) | Savings / Improvement   |
|--------------------------|-------------------------|----------------------------------|-------------------------|
| Mean Turn Latency        |      135.1 ms       |              1490.0 ms          | -1354.9 ms saved/turn |
| Total Cost (20 turns)     | $  0.00409        | $           0.08400          | **95.1% Cost Savings** |
```

---

## 🏷️ Tags
- `#strands-decider-2b`
- `#guardrails`
- `#model-routing`

---

## 📄 Submission Files
- [AWS Builder Center Article](docs/BUILDER_CENTER_ARTICLE.md)
- [3-Minute Video Demo Script](docs/DEMO_VIDEO_SCRIPT.md)
- [Reusable Decision Recipes Guide](docs/DECISION_RECIPES.md)
