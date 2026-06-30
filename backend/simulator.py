"""Workflow Simulator for ComplaintIQ (v3.0).

Feature 12: Developer-facing simulation tool.
Provides predefined complaint scenarios that trigger the full pipeline
(13-agent analysis + self-healing) without requiring real user input
or external APIs.

All executions run in simulator_mode=True which ensures:
  - Mock action executors are used
  - No real notifications are sent
  - Results are clearly tagged as simulated
  - Safe for development and CI environments
"""
from __future__ import annotations

import logging
import uuid
from typing import Any

logger = logging.getLogger("complaintiq.simulator")

# ─────────────────────────────────────────────────────────────────────────────
# Predefined scenario templates
# ─────────────────────────────────────────────────────────────────────────────

SCENARIOS: dict[str, dict[str, Any]] = {
    "refund": {
        "domain": "ecommerce",
        "description": (
            "I ordered a laptop from your website 3 weeks ago, order #ORD-98761. "
            "The product arrived damaged and I returned it immediately. "
            "I was promised a refund of $1,299 within 7 days but it has been 21 days "
            "and I have not received my money back. This is completely unacceptable. "
            "I need my refund processed immediately or I will file a chargeback."
        ),
        "category": "Refund Delay",
        "expected_intent": "Refund",
        "expected_action_type": "refund",
        "scenario_label": "Damaged Product Refund",
    },
    "replacement": {
        "domain": "ecommerce",
        "description": (
            "I received my order #ORD-55432 yesterday but the wrong item was delivered. "
            "I ordered a blue headphone (model XB900N) but received a red one. "
            "The packaging was sealed so this was a warehouse packing error. "
            "Please send me the correct product as soon as possible."
        ),
        "category": "Wrong Item",
        "expected_intent": "Replacement",
        "expected_action_type": "replacement",
        "scenario_label": "Wrong Product Delivered",
    },
    "delivery_delay": {
        "domain": "ecommerce",
        "description": (
            "My shipment with tracking number TRACK-88321 has been stuck in transit "
            "for 12 days. The estimated delivery was last Monday and I have not received "
            "any update from the courier. I urgently need this product for an event this weekend. "
            "Please escalate this with the courier immediately."
        ),
        "category": "Delivery Delay",
        "expected_intent": "Delivery Delay",
        "expected_action_type": "courier_escalation",
        "scenario_label": "Package Stuck in Transit",
    },
    "fraud_complaint": {
        "domain": "banking",
        "description": (
            "I noticed three unauthorized transactions on my account today totaling $2,450. "
            "Transaction IDs: TXN-001, TXN-002, TXN-003. I did not make these purchases. "
            "I believe my account has been compromised by a phishing attack I received last week. "
            "Please freeze my account immediately and investigate this fraud."
        ),
        "category": "Unauthorized Transaction",
        "expected_intent": "Fraud",
        "expected_action_type": "fraud_investigation",
        "scenario_label": "Account Fraud / Unauthorized Transactions",
    },
    "technical_issue": {
        "domain": "telecom",
        "description": (
            "My internet connection has been dropping every 30 minutes since yesterday evening. "
            "I have tried restarting the router multiple times and run the diagnostics tool — "
            "error code: E-3307. This is affecting my work from home. "
            "I need a technician to visit as soon as possible."
        ),
        "category": "Service Outage",
        "expected_intent": "General Complaint",
        "expected_action_type": "it_support_ticket",
        "scenario_label": "Recurring Internet Drops",
    },
    "billing_issue": {
        "domain": "utilities",
        "description": (
            "My electricity bill for this month is $847, which is 3 times higher than usual. "
            "Invoice #INV-20241105. My usage has not changed and the meter reading seems wrong. "
            "I suspect either a billing system error or a faulty meter. "
            "Please investigate and correct the invoice immediately."
        ),
        "category": "Incorrect Bill",
        "expected_intent": "Billing Issue",
        "expected_action_type": "finance_investigation",
        "scenario_label": "Electricity Bill 3x Overcharge",
    },
    "password_reset": {
        "domain": "banking",
        "description": (
            "I cannot log in to my online banking account. I have tried resetting my password "
            "three times using the self-service link but the reset email never arrives. "
            "I checked spam as well. My account email is registered correctly. "
            "I need access to my account urgently to pay a bill today."
        ),
        "category": "Account Access",
        "expected_intent": "Account Issue",
        "expected_action_type": "account_recovery",
        "scenario_label": "Cannot Access Account",
    },
    "wrong_product": {
        "domain": "ecommerce",
        "description": (
            "The TV I received (order #ORD-77890) is a completely different model than what I ordered. "
            "I ordered a 65-inch Samsung QLED but received a 55-inch LG LED. "
            "The price difference is $400. This is clearly a warehouse cataloging error. "
            "I need the correct TV picked up and the right one delivered within 2 days."
        ),
        "category": "Wrong Product",
        "expected_intent": "Replacement",
        "expected_action_type": "warehouse_return",
        "scenario_label": "Completely Wrong TV Model",
    },
}


def get_scenario(name: str) -> dict[str, Any] | None:
    """Return a simulator scenario by name, or None if not found."""
    return SCENARIOS.get(name.lower())


def list_scenarios() -> list[dict[str, Any]]:
    """Return list of all available simulator scenarios."""
    return [
        {
            "name": k,
            "label": v["scenario_label"],
            "domain": v["domain"],
            "category": v["category"],
            "expected_intent": v["expected_intent"],
            "expected_action_type": v["expected_action_type"],
            "description_preview": v["description"][:120] + "...",
        }
        for k, v in SCENARIOS.items()
    ]


def build_simulator_complaint(
    scenario_name: str,
    customer_name: str = "Simulator User",
    description_override: str | None = None,
) -> dict[str, Any]:
    """Build a complaint dict ready for simulator execution.

    Returns a dict compatible with ComplaintCreate fields plus
    simulator metadata.
    """
    scenario = SCENARIOS.get(scenario_name)
    if not scenario:
        raise ValueError(f"Unknown scenario: {scenario_name}. Available: {list(SCENARIOS.keys())}")

    complaint_id = str(uuid.uuid4())
    return {
        "id": complaint_id,
        "domain": scenario["domain"],
        "category": scenario.get("category"),
        "description": description_override or scenario["description"],
        "customer_name": customer_name,
        "customer_email": f"simulator+{scenario_name}@complaintiq.mock",
        "simulator_mode": True,
        "scenario": scenario_name,
        "scenario_label": scenario["scenario_label"],
        "expected_intent": scenario["expected_intent"],
        "expected_action_type": scenario["expected_action_type"],
    }
