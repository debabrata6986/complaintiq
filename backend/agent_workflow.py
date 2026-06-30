"""ComplaintIQ Multi-Agent Workflow built with LangGraph.

Extended pipeline: 13 agents total (10 original + 3 new).
New agents are inserted cleanly after existing agents.

Agent order:
  1. ComplaintUnderstanding
  2. IntentClassification
  3. NER
  4. Sentiment+Emotion
  5. SeverityPrediction
  6. DuplicateComplaint        ← now uses hybrid retrieval
  7. KnowledgeRetrieval        ← now uses hybrid retrieval
  8. RootCauseAnalysis         ← NEW (Feature 4)
  9. ResolutionRecommendation
  10. RiskScoring              ← NEW (Feature 5)
  11. Escalation               ← extended with HITL (Feature 7)
  12. Explainability           ← enhanced (Feature 8)
  13. ResponseGeneration
"""
from __future__ import annotations

import time
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from config import cfg
from confidence import ConfidenceRecord, make_confidence, enrich_explanation_with_confidence
from db import get_db
from hybrid_retrieval import hybrid_similar_complaints, hybrid_knowledge_search
from llm_client import llm_json, llm_text
from risk_scoring import compute_risk_score
from similarity import top_k_similar  # TF-IDF fallback (kept for backward compat)


class ComplaintState(TypedDict, total=False):
    # ── input ──────────────────────────────────────────────
    complaint_id: str
    description: str
    domain: str
    category: str | None
    customer_name: str | None
    # ── agent outputs ───────────────────────────────────────
    summary: str
    keywords: list[str]
    intent: str
    intent_confidence: float
    nlu_category: str
    entities: list[dict[str, Any]]
    sentiment: str
    sentiment_score: float
    emotion: str
    severity: str
    severity_reason: str
    priority: str
    department: str
    duplicate_score: float
    similar_complaint_ids: list[str]
    similar_complaints: list[dict[str, Any]]
    retrieved_policies: list[dict[str, Any]]
    # ── NEW: root cause ─────────────────────────────────────
    root_causes: list[dict[str, Any]]
    root_cause_summary: str
    # ── NEW: risk scoring ───────────────────────────────────
    risk_score: int
    risk_category: str
    risk_components: dict[str, Any]
    risk_explanation: str
    # ── recommendation ──────────────────────────────────────
    recommendation: str
    recommendation_action: str
    recommendation_confidence: float
    decision_options: list[dict[str, Any]]
    escalation_required: bool
    escalation_reason: str
    routing: str
    # ── NEW: confidence records ──────────────────────────────
    confidence_records: list[dict[str, Any]]
    human_review_required: bool
    # ── explainability ──────────────────────────────────────
    explanation: dict[str, Any]
    customer_response: str
    support_notes: str
    manager_notes: str
    # ── tracing ─────────────────────────────────────────────
    trace: list[dict[str, Any]]


def _trace(
    state: ComplaintState,
    agent: str,
    started: float,
    output: dict[str, Any] | None = None,
    error: str | None = None,
) -> None:
    state.setdefault("trace", []).append(
        {
            "agent": agent,
            "status": "failure" if error else "success",
            "duration_ms": int((time.time() - started) * 1000),
            "output": output,
            "error": error,
        }
    )


def _add_confidence(state: ComplaintState, record: ConfidenceRecord) -> None:
    state.setdefault("confidence_records", []).append(record.to_dict())


# ═══════════════════════════════════════════════════════════════════════
# Agent 1 — Complaint Understanding (unchanged)
# ═══════════════════════════════════════════════════════════════════════

async def complaint_understanding(state: ComplaintState) -> ComplaintState:
    t = time.time()
    system = (
        "You are the Complaint Understanding Agent. Read the customer complaint and "
        "return a compact JSON object describing it. Output ONLY valid JSON."
    )
    user = (
        f"DOMAIN: {state.get('domain')}\n"
        f"COMPLAINT TEXT:\n{state['description']}\n\n"
        'Return JSON with this exact shape:\n'
        '{ "summary": "1-2 sentence neutral summary", '
        '"keywords": ["k1","k2","k3","k4","k5"], '
        '"detected_domain": "ecommerce|banking|telecom|insurance|healthcare|government|utilities" }'
    )
    out = await llm_json(system, user, max_tokens=600)
    state["summary"] = out.get("summary") or state["description"][:200]
    state["keywords"] = (out.get("keywords") or [])[:8]
    _trace(state, "ComplaintUnderstandingAgent", t, {"summary": state["summary"], "keywords": state["keywords"]})
    return state


# ═══════════════════════════════════════════════════════════════════════
# Agent 2 — Intent Classification (+ confidence record)
# ═══════════════════════════════════════════════════════════════════════

INTENT_LABELS = [
    "Refund", "Replacement", "Delivery Delay", "Payment Failure",
    "Billing Issue", "Warranty", "Fraud", "Account Issue",
    "Cancellation", "General Complaint",
]


async def intent_classification(state: ComplaintState) -> ComplaintState:
    t = time.time()
    system = (
        "You are the Intent Classification Agent. Pick the SINGLE best intent label "
        "from the provided list. Output ONLY valid JSON."
    )
    user = (
        f"LABELS: {INTENT_LABELS}\n"
        f"COMPLAINT: {state['description']}\n\n"
        'Return JSON: { "intent": "<one of the labels>", "category": "short category phrase", '
        '"confidence": 0.0-1.0 }'
    )
    out = await llm_json(system, user, max_tokens=300)
    state["intent"] = out.get("intent") if out.get("intent") in INTENT_LABELS else "General Complaint"
    state["intent_confidence"] = float(out.get("confidence") or 0.6)
    state["nlu_category"] = out.get("category") or state["intent"]

    rec = make_confidence(state["intent_confidence"], "IntentClassificationAgent", state["intent"])
    _add_confidence(state, rec)
    _trace(state, "IntentClassificationAgent", t, {"intent": state["intent"], "confidence": state["intent_confidence"]})
    return state


# ═══════════════════════════════════════════════════════════════════════
# Agent 3 — NER (unchanged logic)
# ═══════════════════════════════════════════════════════════════════════

async def ner_agent(state: ComplaintState) -> ComplaintState:
    t = time.time()
    system = (
        "You are the Named Entity Recognition Agent. Extract every relevant entity from "
        "the complaint. Output ONLY valid JSON."
    )
    user = (
        f"COMPLAINT: {state['description']}\n\n"
        'Return JSON: { "entities": [ {"type": "ORDER_ID|INVOICE|TRANSACTION_ID|COMPANY|PRODUCT|DATE|AMOUNT|PHONE|EMAIL|LOCATION|PERSON|DEPARTMENT", "value": "..."} ] }\n'
        "Only include entities actually present. Use empty list if none."
    )
    out = await llm_json(system, user, max_tokens=500)
    ents = out.get("entities") or []
    state["entities"] = [
        {"type": str(e.get("type", "")).upper(), "value": str(e.get("value", ""))}
        for e in ents if e.get("value")
    ]
    _trace(state, "NamedEntityRecognitionAgent", t, {"count": len(state["entities"])})
    return state


# ═══════════════════════════════════════════════════════════════════════
# Agent 4 — Sentiment + Emotion (+ confidence record)
# ═══════════════════════════════════════════════════════════════════════

async def sentiment_agent(state: ComplaintState) -> ComplaintState:
    t = time.time()
    system = "You are the Sentiment & Emotion Agent. Output ONLY valid JSON."
    user = (
        f"COMPLAINT: {state['description']}\n\n"
        'Return JSON: { "sentiment": "Positive|Neutral|Negative", '
        '"sentiment_score": -1.0 to 1.0, '
        '"emotion": "Happy|Concerned|Frustrated|Angry|Urgent", '
        '"confidence": 0.0-1.0 }'
    )
    out = await llm_json(system, user, max_tokens=200)
    state["sentiment"] = out.get("sentiment") or "Negative"
    state["sentiment_score"] = float(out.get("sentiment_score") or -0.3)
    state["emotion"] = out.get("emotion") or "Concerned"

    conf = float(out.get("confidence") or 0.75)
    rec = make_confidence(conf, "SentimentEmotionAgent", f"{state['sentiment']}/{state['emotion']}")
    _add_confidence(state, rec)
    _trace(state, "SentimentEmotionAgent", t, {"sentiment": state["sentiment"], "emotion": state["emotion"]})
    return state


# ═══════════════════════════════════════════════════════════════════════
# Agent 5 — Severity Prediction (+ confidence record)
# ═══════════════════════════════════════════════════════════════════════

_DEPT_MAP = {
    "Refund": "Finance", "Replacement": "Operations", "Delivery Delay": "Logistics",
    "Payment Failure": "Payments", "Billing Issue": "Billing", "Warranty": "After-Sales",
    "Fraud": "Risk & Compliance", "Account Issue": "Customer Success",
    "Cancellation": "Customer Success", "General Complaint": "Support",
}


async def severity_agent(state: ComplaintState) -> ComplaintState:
    t = time.time()
    system = (
        "You are the Severity Prediction Agent. Use intent, emotion and complaint content "
        "to assign severity. Output ONLY valid JSON."
    )
    user = (
        f"INTENT: {state['intent']}\nEMOTION: {state['emotion']}\n"
        f"SENTIMENT: {state['sentiment']}\nCOMPLAINT: {state['description']}\n\n"
        'Return JSON: { "severity": "critical|high|medium|low", '
        '"priority": "critical|high|medium|low", '
        '"reason": "one short sentence explaining severity", '
        '"confidence": 0.0-1.0 }'
    )
    out = await llm_json(system, user, max_tokens=250)
    sev = (out.get("severity") or "medium").lower()
    pri = (out.get("priority") or sev).lower()
    valid = {"critical", "high", "medium", "low"}
    state["severity"] = sev if sev in valid else "medium"
    state["priority"] = pri if pri in valid else state["severity"]
    state["severity_reason"] = out.get("reason") or "Severity inferred from intent and emotion."
    state["department"] = _DEPT_MAP.get(state["intent"], "Support")

    conf = float(out.get("confidence") or 0.72)
    rec = make_confidence(conf, "SeverityPredictionAgent", f"{state['severity']}/{state['priority']}")
    _add_confidence(state, rec)
    _trace(state, "SeverityPredictionAgent", t, {"severity": state["severity"], "priority": state["priority"]})
    return state


# ═══════════════════════════════════════════════════════════════════════
# Agent 6 — Duplicate Detection (hybrid retrieval)
# ═══════════════════════════════════════════════════════════════════════

async def duplicate_agent(state: ComplaintState) -> ComplaintState:
    t = time.time()
    db = get_db()
    cursor = db.complaints.find(
        {"id": {"$ne": state["complaint_id"]}, "domain": state["domain"]},
        {"_id": 0, "id": 1, "description": 1, "status": 1, "analysis.intent": 1, "created_at": 1},
    ).limit(500)
    corpus = await cursor.to_list(length=500)

    # Use hybrid retrieval (semantic + TF-IDF)
    similar = hybrid_similar_complaints(
        state["description"], corpus, "description",
        k=5, min_score=cfg.hybrid.min_score_duplicate,
    )

    state["similar_complaint_ids"] = [doc["id"] for doc, _ in similar]
    state["similar_complaints"] = [
        {
            "id": doc["id"],
            "snippet": (doc.get("description") or "")[:160],
            "similarity": score,
            "status": doc.get("status"),
            "intent": (doc.get("analysis") or {}).get("intent"),
            "created_at": doc.get("created_at"),
        }
        for doc, score in similar
    ]
    state["duplicate_score"] = similar[0][1] if similar else 0.0
    _trace(state, "DuplicateComplaintAgent", t, {"duplicate_score": state["duplicate_score"], "matches": len(similar)})
    return state


# ═══════════════════════════════════════════════════════════════════════
# Agent 7 — Knowledge Retrieval (hybrid RAG)
# ═══════════════════════════════════════════════════════════════════════

async def knowledge_retrieval_agent(state: ComplaintState) -> ComplaintState:
    t = time.time()
    db = get_db()
    cursor = db.kb_documents.find(
        {"$or": [{"domain": state["domain"]}, {"domain": "general"}]},
        {"_id": 0},
    ).limit(500)
    docs = await cursor.to_list(length=500)
    query = f"{state.get('summary', '')} {state['description']} intent:{state['intent']}"

    # Use hybrid retrieval
    matches = hybrid_knowledge_search(
        query, docs, "content",
        k=5, min_score=cfg.hybrid.min_score_knowledge,
    )

    state["retrieved_policies"] = [
        {
            "id": d["id"],
            "title": d["title"],
            "doc_type": d["doc_type"],
            "domain": d.get("domain", "general"),
            "excerpt": d["content"][:280],
            "score": score,
        }
        for d, score in matches
    ]
    _trace(state, "KnowledgeRetrievalAgent", t, {"retrieved": len(state["retrieved_policies"])})
    return state


# ═══════════════════════════════════════════════════════════════════════
# Agent 8 — Root Cause Analysis (NEW — Feature 4)
# ═══════════════════════════════════════════════════════════════════════

_ROOT_CAUSE_EXAMPLES = {
    "Delivery Delay": ["Courier Delay", "Inventory Shortage", "Warehouse Delay", "Vendor Delay", "Weather Event"],
    "Refund": ["Payment Gateway Issue", "Finance Processing Delay", "Bank Processing Delay", "Wrong Account Details"],
    "Replacement": ["Warehouse Packing Error", "Catalog Error", "Vendor Error", "Transit Damage"],
    "Payment Failure": ["Payment Gateway Timeout", "Insufficient Funds", "Bank Decline", "Network Error"],
    "Billing Issue": ["Billing System Error", "Incorrect Rate Applied", "Promo Code Failure", "Duplicate Charge"],
    "Fraud": ["Unauthorized Access", "Phishing Attack", "Account Takeover", "Internal Data Breach"],
    "Warranty": ["Product Manufacturing Defect", "Improper Use", "Expired Warranty", "Missing Documentation"],
    "Account Issue": ["Authentication Failure", "Data Migration Error", "Account Lockout Policy", "User Error"],
    "Cancellation": ["Service Dissatisfaction", "Better Alternative Found", "Financial Constraint", "Unresolved Complaint"],
    "General Complaint": ["Service Quality Issue", "Communication Failure", "Process Gap", "Policy Mismatch"],
}


async def root_cause_analysis_agent(state: ComplaintState) -> ComplaintState:
    t = time.time()
    intent = state.get("intent", "General Complaint")
    example_causes = _ROOT_CAUSE_EXAMPLES.get(intent, _ROOT_CAUSE_EXAMPLES["General Complaint"])

    system = (
        "You are the Root Cause Analysis Agent. Analyse the complaint and infer the most "
        "probable underlying root causes. Be specific and evidence-based. Output ONLY valid JSON."
    )
    user = (
        f"INTENT: {intent}\n"
        f"SEVERITY: {state.get('severity', 'medium')}\n"
        f"EMOTION: {state.get('emotion', 'Concerned')}\n"
        f"ENTITIES: {state.get('entities', [])}\n"
        f"COMPLAINT: {state['description']}\n\n"
        f"COMMON ROOT CAUSES FOR '{intent}': {example_causes}\n\n"
        "Identify 1–3 probable root causes.\n"
        'Return JSON: { "root_causes": [ '
        '{ "cause": "specific cause name", "confidence": 0.0-1.0, '
        '"category": "System|Process|Human|Vendor|External", '
        '"reasoning": "1-2 sentence evidence-based explanation" } ], '
        '"summary": "1-sentence overall root cause summary" }'
    )
    out = await llm_json(system, user, max_tokens=700)

    raw_causes = out.get("root_causes") or []
    state["root_causes"] = [
        {
            "cause": rc.get("cause", "Unknown"),
            "confidence": float(rc.get("confidence") or 0.5),
            "confidence_label": (
                "High" if float(rc.get("confidence") or 0.5) >= cfg.confidence.high_label_threshold
                else "Medium" if float(rc.get("confidence") or 0.5) >= cfg.confidence.medium_label_threshold
                else "Low"
            ),
            "category": rc.get("category", "Process"),
            "reasoning": rc.get("reasoning", ""),
        }
        for rc in raw_causes
        if rc.get("cause") and float(rc.get("confidence") or 0.5) >= cfg.root_cause.min_confidence
    ][: cfg.root_cause.max_causes]

    state["root_cause_summary"] = out.get("summary") or (
        state["root_causes"][0]["cause"] if state["root_causes"] else "Root cause undetermined"
    )

    # Confidence record for the primary root cause
    primary_conf = state["root_causes"][0]["confidence"] if state["root_causes"] else 0.5
    rec = make_confidence(primary_conf, "RootCauseAnalysisAgent", state["root_cause_summary"])
    _add_confidence(state, rec)

    _trace(state, "RootCauseAnalysisAgent", t, {
        "root_causes": len(state["root_causes"]),
        "summary": state["root_cause_summary"],
    })
    return state


# ═══════════════════════════════════════════════════════════════════════
# Agent 9 — Resolution Recommendation (+ confidence record)
# ═══════════════════════════════════════════════════════════════════════

async def recommendation_agent(state: ComplaintState) -> ComplaintState:
    t = time.time()
    system = (
        "You are the Resolution Recommendation Agent. Using the complaint, intent, severity "
        "and retrieved policies, pick the BEST action. Output ONLY valid JSON."
    )
    policies_txt = "\n".join(
        f"- [{p['doc_type']}] {p['title']}: {p['excerpt']}"
        for p in state.get("retrieved_policies", [])
    ) or "(no policies retrieved)"

    root_cause_txt = ""
    if state.get("root_causes"):
        root_cause_txt = f"ROOT CAUSE: {state.get('root_cause_summary', '')}\n"

    user = (
        f"COMPLAINT: {state['description']}\n"
        f"INTENT: {state['intent']}\nSEVERITY: {state['severity']}\nEMOTION: {state['emotion']}\n"
        f"{root_cause_txt}\n"
        f"POLICIES:\n{policies_txt}\n\n"
        "Provide the top recommendation AND 2 alternative options for a Decision Matrix.\n"
        'Return JSON: { "action": "Refund|Replacement|Escalation|Technician Visit|Reject|Hold", '
        '"recommendation": "2-3 sentence recommendation for the support agent", '
        '"confidence": 0.0-1.0, '
        '"options": [ { "action": "<action>", "rationale": "1 sentence", "confidence": 0.0-1.0, "business_risk": "low|medium|high" } ] }'
    )
    out = await llm_json(system, user, max_tokens=900)
    state["recommendation_action"] = out.get("action") or "Escalation"
    state["recommendation"] = out.get("recommendation") or "Escalate to support manager for manual review."
    state["recommendation_confidence"] = float(out.get("confidence") or 0.7)

    opts = out.get("options") or []
    primary = {
        "action": state["recommendation_action"],
        "rationale": state["recommendation"][:160],
        "confidence": state["recommendation_confidence"],
        "business_risk": "low",
    }
    state["decision_options"] = [primary] + [
        {
            "action": o.get("action", "Hold"),
            "rationale": o.get("rationale", ""),
            "confidence": float(o.get("confidence", 0.6)),
            "business_risk": o.get("business_risk", "medium"),
        }
        for o in opts if o.get("action") and o.get("action") != state["recommendation_action"]
    ][:2]

    rec = make_confidence(state["recommendation_confidence"], "ResolutionRecommendationAgent", state["recommendation_action"])
    _add_confidence(state, rec)
    _trace(state, "ResolutionRecommendationAgent", t, {
        "action": state["recommendation_action"],
        "confidence": state["recommendation_confidence"],
        "options": len(state["decision_options"]),
    })
    return state


# ═══════════════════════════════════════════════════════════════════════
# Agent 10 — Risk Scoring (NEW — Feature 5)
# ═══════════════════════════════════════════════════════════════════════

async def risk_scoring_agent(state: ComplaintState) -> ComplaintState:
    t = time.time()
    # Fetch reopen_count and history from DB for the current complaint
    reopen_count = 0
    history: list[dict] = []
    try:
        db = get_db()
        doc = await db.complaints.find_one(
            {"id": state["complaint_id"]},
            {"_id": 0, "reopen_count": 1, "history": 1},
        )
        if doc:
            reopen_count = int(doc.get("reopen_count") or 0)
            history = list(doc.get("history") or [])
    except Exception:  # noqa: BLE001
        pass

    result = compute_risk_score(
        severity=state.get("severity", "medium"),
        priority=state.get("priority", "medium"),
        sentiment=state.get("sentiment", "Negative"),
        emotion=state.get("emotion", "Concerned"),
        description=state.get("description", ""),
        duplicate_score=float(state.get("duplicate_score") or 0.0),
        reopen_count=reopen_count,
        history=history,
    )

    state["risk_score"] = result["risk_score"]
    state["risk_category"] = result["risk_category"]
    state["risk_components"] = result["components"]
    state["risk_explanation"] = result["explanation"]

    _trace(state, "RiskScoringAgent", t, {
        "risk_score": state["risk_score"],
        "risk_category": state["risk_category"],
    })
    return state


# ═══════════════════════════════════════════════════════════════════════
# Agent 11 — Escalation (extended with HITL — Feature 7)
# ═══════════════════════════════════════════════════════════════════════

_LEGAL_KEYWORDS = ("lawsuit", "legal action", "court", "consumer forum", "ombudsman", "police complaint", "fir")
_FRAUD_KEYWORDS = ("fraud", "unauthorized", "stolen", "scam", "phishing", "identity theft", "hacked")


async def escalation_agent(state: ComplaintState) -> ComplaintState:
    t = time.time()
    desc_l = state["description"].lower()
    has_legal = any(k in desc_l for k in _LEGAL_KEYWORDS)
    has_fraud = any(k in desc_l for k in _FRAUD_KEYWORDS)
    severity = state.get("severity", "medium")
    conf = state.get("recommendation_confidence", 0.7)
    risk_cat = state.get("risk_category", "Low")

    reasons: list[str] = []
    if severity == "critical":
        reasons.append("Severity is critical")
    if conf < cfg.confidence.human_review_threshold:
        reasons.append(f"AI confidence below {int(cfg.confidence.human_review_threshold * 100)}% ({int(conf * 100)}%)")
    if has_legal:
        reasons.append("Legal keywords detected")
    if has_fraud:
        reasons.append("Fraud keywords detected")
    if state.get("recommendation_action") == "Escalation":
        reasons.append("Recommendation is explicit escalation")
    if risk_cat in ("High", "Critical"):
        reasons.append(f"Risk category: {risk_cat} (score: {state.get('risk_score', 0)})")

    # HITL: check if any agent flagged low confidence
    conf_records = state.get("confidence_records") or []
    hitl_agents = [
        r["agent"] for r in conf_records
        if isinstance(r, dict) and r.get("human_review")
    ]
    if hitl_agents:
        reasons.append(f"Low confidence agents: {', '.join(hitl_agents)}")

    escalate = len(reasons) > 0
    state["human_review_required"] = escalate or bool(hitl_agents)

    if escalate:
        routing = "manager_review"
    elif conf >= 0.90:
        routing = "support_direct"
    else:
        routing = "support_review"

    state["escalation_required"] = escalate
    state["escalation_reason"] = "; ".join(reasons) if reasons else "Within support executive authority."
    state["routing"] = routing
    _trace(state, "EscalationAgent", t, {"escalate": escalate, "routing": routing, "reasons": reasons})
    return state


# ═══════════════════════════════════════════════════════════════════════
# Agent 12 — Explainability (enhanced — Feature 8)
# ═══════════════════════════════════════════════════════════════════════

async def explainability_agent(state: ComplaintState) -> ComplaintState:
    t = time.time()
    policies = [p["title"] for p in state.get("retrieved_policies", [])][:3]
    similar_ids = state.get("similar_complaint_ids", [])[:3]
    root_causes = state.get("root_causes", [])
    risk_score = state.get("risk_score", 0)
    risk_category = state.get("risk_category", "Low")

    system = (
        "You are the Explainability Agent. Produce a transparent, comprehensive explanation "
        "for why this recommendation was generated. Output ONLY valid JSON."
    )
    user = (
        f"INTENT: {state['intent']} ({state.get('intent_confidence', 0):.2f})\n"
        f"SEVERITY: {state['severity']} — {state.get('severity_reason', '')}\n"
        f"EMOTION: {state['emotion']} | SENTIMENT: {state['sentiment']}\n"
        f"ROOT CAUSE: {state.get('root_cause_summary', 'N/A')}\n"
        f"RISK SCORE: {risk_score}/100 ({risk_category})\n"
        f"ACTION: {state['recommendation_action']}\n"
        f"POLICIES USED: {policies}\n"
        f"SIMILAR PAST COMPLAINTS: {similar_ids}\n"
        f"DUPLICATE SCORE: {state.get('duplicate_score', 0):.2f}\n\n"
        'Return JSON: { "reasoning": "3-4 sentence plain-English chain-of-thought that explains the recommendation", '
        '"evidence": ["bullet 1","bullet 2","bullet 3","bullet 4"], '
        '"policy_basis": ["policy title 1","policy title 2"], '
        '"confidence": 0.0-1.0, '
        '"root_cause_impact": "1 sentence explaining how root cause influenced the recommendation", '
        '"risk_impact": "1 sentence explaining how risk score influenced the decision", '
        '"caveats": "any caveats or null" }'
    )
    out = await llm_json(system, user, max_tokens=800)

    base_explanation = {
        "reasoning": out.get("reasoning") or "Decision based on intent, severity and retrieved policies.",
        "evidence": out.get("evidence") or [],
        "policy_basis": out.get("policy_basis") or policies,
        "confidence": float(out.get("confidence") or state.get("recommendation_confidence", 0.7)),
        "caveats": out.get("caveats"),
        # Enhanced fields
        "root_cause_impact": out.get("root_cause_impact") or "",
        "risk_impact": out.get("risk_impact") or "",
        "entities_detected": state.get("entities", []),
        "sentiment_detected": state.get("sentiment"),
        "emotion_detected": state.get("emotion"),
        "root_causes": root_causes,
        "root_cause_summary": state.get("root_cause_summary"),
        "risk_score": risk_score,
        "risk_category": risk_category,
        "risk_explanation": state.get("risk_explanation"),
        "supporting_policies": state.get("retrieved_policies", [])[:3],
        "duplicate_score": state.get("duplicate_score", 0.0),
    }

    # Merge confidence breakdown from all agents
    from confidence import ConfidenceRecord, aggregate_confidence
    conf_records_raw = state.get("confidence_records") or []
    conf_records = []
    for r in conf_records_raw:
        if isinstance(r, dict):
            conf_records.append(ConfidenceRecord(**r))

    state["explanation"] = enrich_explanation_with_confidence(base_explanation, conf_records)
    _trace(state, "ExplainabilityAgent", t, {"confidence": state["explanation"]["confidence"]})
    return state


# ═══════════════════════════════════════════════════════════════════════
# Agent 13 — Response Generation (unchanged)
# ═══════════════════════════════════════════════════════════════════════

async def response_generation_agent(state: ComplaintState) -> ComplaintState:
    t = time.time()
    system = (
        "You are the Response Generation Agent. Produce three professional outputs. "
        "Output ONLY valid JSON."
    )
    risk_note = f" [Risk: {state.get('risk_category','Low')} {state.get('risk_score',0)}/100]" if state.get("risk_score") else ""
    user = (
        f"CUSTOMER: {state.get('customer_name') or 'Valued Customer'}\n"
        f"INTENT: {state['intent']} | ACTION: {state['recommendation_action']}{risk_note}\n"
        f"RECOMMENDATION: {state['recommendation']}\n"
        f"COMPLAINT: {state['description']}\n\n"
        'Return JSON: { "customer_response": "polite, empathetic 80-120 word reply addressed to the customer", '
        '"support_notes": "internal note for support agent (2-3 sentences)", '
        '"manager_notes": "internal note for manager (1-2 sentences, risk + escalation)" }'
    )
    out = await llm_json(system, user, max_tokens=900)
    state["customer_response"] = out.get("customer_response") or "Thank you for reaching out. We are reviewing your complaint and will respond shortly."
    state["support_notes"] = out.get("support_notes") or ""
    state["manager_notes"] = out.get("manager_notes") or ""
    _trace(state, "ResponseGenerationAgent", t, {"generated": True})
    return state


# ═══════════════════════════════════════════════════════════════════════
# LangGraph wiring (13-agent pipeline)
# ═══════════════════════════════════════════════════════════════════════

def build_workflow():
    g = StateGraph(ComplaintState)
    g.add_node("understand", complaint_understanding)
    g.add_node("intent", intent_classification)
    g.add_node("ner", ner_agent)
    g.add_node("sentiment", sentiment_agent)
    g.add_node("severity", severity_agent)
    g.add_node("duplicate", duplicate_agent)
    g.add_node("retrieve", knowledge_retrieval_agent)
    g.add_node("root_cause", root_cause_analysis_agent)    # NEW
    g.add_node("recommend", recommendation_agent)
    g.add_node("risk_score", risk_scoring_agent)           # NEW
    g.add_node("escalation", escalation_agent)
    g.add_node("explain", explainability_agent)
    g.add_node("respond", response_generation_agent)

    g.set_entry_point("understand")
    g.add_edge("understand", "intent")
    g.add_edge("intent", "ner")
    g.add_edge("ner", "sentiment")
    g.add_edge("sentiment", "severity")
    g.add_edge("severity", "duplicate")
    g.add_edge("duplicate", "retrieve")
    g.add_edge("retrieve", "root_cause")     # NEW
    g.add_edge("root_cause", "recommend")
    g.add_edge("recommend", "risk_score")   # NEW
    g.add_edge("risk_score", "escalation")
    g.add_edge("escalation", "explain")
    g.add_edge("explain", "respond")
    g.add_edge("respond", END)
    return g.compile()


_WORKFLOW = None


def get_workflow():
    global _WORKFLOW
    if _WORKFLOW is None:
        _WORKFLOW = build_workflow()
    return _WORKFLOW


async def run_workflow(
    *,
    complaint_id: str,
    description: str,
    domain: str,
    category: str | None = None,
    customer_name: str | None = None,
) -> ComplaintState:
    wf = get_workflow()
    initial: ComplaintState = {
        "complaint_id": complaint_id,
        "description": description,
        "domain": domain,
        "category": category,
        "customer_name": customer_name,
        "trace": [],
        "confidence_records": [],
    }
    result = await wf.ainvoke(initial)
    return result
