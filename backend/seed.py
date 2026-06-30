"""Seed demo users, knowledge base documents and historical complaints.

Runs idempotently on backend startup if the corresponding collection is empty.
"""
from __future__ import annotations

import asyncio
import random
from datetime import datetime, timedelta, timezone

from auth_utils import hash_password
from db import get_db
from models import KBDocument, new_id, utcnow_iso

DEMO_USERS = [
    {"email": "admin@complaintiq.com", "password": "Admin@123", "full_name": "Aanya Sharma", "role": "admin"},
    {"email": "manager@complaintiq.com", "password": "Manager@123", "full_name": "Rohan Mehta", "role": "manager"},
    {"email": "support@complaintiq.com", "password": "Support@123", "full_name": "Priya Iyer", "role": "support"},
    {"email": "customer@complaintiq.com", "password": "Customer@123", "full_name": "Karan Verma", "role": "customer"},
]

KB_DOCS = [
    # E-commerce
    ("Refund Policy", "policy", "ecommerce", "Customers may request a refund within 30 days of delivery for defective or wrong items. Refunds are processed to the original payment method within 7-10 business days. Items must be returned in original packaging. Digital goods are non-refundable unless faulty."),
    ("Return Policy", "policy", "ecommerce", "Returns accepted within 30 days. Item must be unused with original tags. Initiate return from the orders page; pickup is free for prepaid orders. Cash-on-delivery returns incur a small reverse logistics fee. Refunds processed within 7 business days of receiving the returned item."),
    ("Shipping Policy", "policy", "ecommerce", "Standard shipping 3-5 business days, express 1-2 business days. Delays exceeding 2 days beyond promised delivery date qualify the customer for shipping fee waiver and a goodwill voucher. Track via the order tracking page."),
    ("Warranty Policy", "policy", "ecommerce", "Electronic products carry a 12-month manufacturer warranty. Warranty covers manufacturing defects, not physical damage or liquid ingress. For warranty claims, raise a complaint with order ID and photos of the defect. Replacement or repair decision rests with the service partner."),
    ("Cancellation FAQ", "faq", "ecommerce", "Orders can be cancelled before they are shipped from our warehouse. Once shipped, you must initiate a return after delivery. Cancellation refunds are credited back within 5 business days."),
    ("Duplicate Complaint SOP", "sop", "general", "If duplicate score exceeds 0.6, agent should reference the original complaint, share its resolution, and only escalate if customer disagrees. Avoid creating a fresh investigation thread."),
    # Banking
    ("Fraud Reporting Policy", "policy", "banking", "Report unauthorized transactions within 3 days for zero liability. Bank initiates chargeback within 7 working days and provides provisional credit within 10 days for confirmed fraud cases. Card is hot-listed immediately upon reporting."),
    ("Payment Failure SOP", "sop", "banking", "For failed UPI/card transactions where the amount was debited, the reversal happens automatically within T+5 working days as per RBI guidelines. Compensation of Rs.100/day applies after T+5."),
    ("Account Issue FAQ", "faq", "banking", "Account freeze can occur due to KYC pending, suspicious activity, or court order. KYC pending freezes are lifted within 24 hours of document submission. Always verify with branch before sharing OTP."),
    # Telecom
    ("Billing Dispute Policy", "policy", "telecom", "Customers may dispute a bill within 30 days of issue. Disputed amount need not be paid pending resolution, but undisputed portion must be cleared to avoid service suspension. Resolution SLA is 7 working days."),
    ("Service Outage SOP", "sop", "telecom", "For outages > 24 hours in a billing cycle, customer is entitled to pro-rata rental waiver. Verify via network ticket ID and outage logs before approving the waiver."),
    # Insurance
    ("Claims Processing Policy", "policy", "insurance", "Cashless claims at network hospitals are processed within 6 hours of pre-authorization. Reimbursement claims processed within 15 working days of complete document submission. Rejection always includes a written reason."),
    # Healthcare
    ("Patient Grievance SOP", "sop", "healthcare", "All clinical complaints are escalated to the medical superintendent within 24 hours. Non-clinical complaints (billing, hospitality) are handled by the patient experience desk with a 48-hour SLA."),
    # Utilities
    ("Power Outage Compensation", "policy", "utilities", "Continuous outages over 12 hours qualify for fixed compensation as per state regulator. File complaint with consumer number and outage duration. Verification done via SCADA logs."),
    # General
    ("Privacy Policy", "policy", "general", "We collect minimum personal data required to deliver our service. Data is encrypted at rest and in transit. Customers may request data export or deletion at any time via the profile page. We never sell personal data to third parties."),
    ("Terms and Conditions", "policy", "general", "By using this service you agree to follow community guidelines, provide accurate information, and not misuse the complaint system. Frivolous or abusive complaints may lead to account suspension."),
    ("Escalation Matrix", "sop", "general", "Level 1: support executive (24h). Level 2: team lead (48h). Level 3: department manager (72h). Critical severity complaints skip to Level 2 immediately."),
]

SAMPLE_COMPLAINTS = [
    ("ecommerce", "I ordered a Samsung 55-inch TV (order ID #ECM98321) on the 5th but it never arrived. Tracking says delivered but I have not received anything. Please investigate urgently.", "Karan Verma", "Delivery Delay", "high"),
    ("ecommerce", "The headphones I received are defective. Right speaker has no sound. I want a replacement immediately. Order #ECM10245.", "Karan Verma", "Replacement", "medium"),
    ("ecommerce", "I want a refund for the kitchen mixer that broke within a week. Invoice INV-77821. The warranty period is 1 year.", "Karan Verma", "Warranty", "high"),
    ("ecommerce", "My order was cancelled without my permission and the refund has not been processed for 2 weeks. Order ECM55512, paid Rs 4,599.", "Karan Verma", "Refund", "high"),
    ("ecommerce", "Package shows delivered but I haven't received it. Order #ECM77881, delivery agent did not call.", "Karan Verma", "Delivery Delay", "high"),
    ("banking", "There is an unauthorized debit of Rs 35,000 from my savings account today. I did not authorize this transaction. Please block my card and investigate.", "Karan Verma", "Fraud", "critical"),
    ("banking", "My UPI payment of Rs 2,500 failed but the amount was debited. Transaction ID UPI98712. It has been 4 days, please refund.", "Karan Verma", "Payment Failure", "high"),
    ("banking", "My account has been frozen without notification. I cannot access my salary. Please resolve immediately.", "Karan Verma", "Account Issue", "critical"),
    ("telecom", "My broadband has been down for 6 days. Multiple complaints with no resolution. I am paying for a service I cannot use.", "Karan Verma", "General Complaint", "high"),
    ("telecom", "I was billed Rs 1,899 for international roaming I never used. Please reverse the charge.", "Karan Verma", "Billing Issue", "medium"),
    ("insurance", "My cashless claim was rejected at the hospital without giving any written reason. Policy ID INS-44120.", "Karan Verma", "General Complaint", "high"),
    ("healthcare", "I was billed twice for the same lab test. Receipt MED-9912. Please refund the duplicate charge.", "Karan Verma", "Billing Issue", "medium"),
    ("utilities", "Power has been out in our area for 18 hours. No update from the electricity board. Consumer number 998877.", "Karan Verma", "General Complaint", "high"),
    ("ecommerce", "Wrong size of shoes delivered. I ordered UK 9 but received UK 7. Order ECM33221.", "Karan Verma", "Replacement", "medium"),
    ("ecommerce", "Delivery is late by 5 days and no update. Order #ECM77123.", "Karan Verma", "Delivery Delay", "medium"),
]


async def seed_users():
    db = get_db()
    existing = await db.users.count_documents({})
    if existing > 0:
        return 0
    docs = []
    for u in DEMO_USERS:
        docs.append({
            "id": new_id(),
            "email": u["email"],
            "full_name": u["full_name"],
            "role": u["role"],
            "phone": None,
            "avatar_url": None,
            "created_at": utcnow_iso(),
            "password_hash": hash_password(u["password"]),
        })
    await db.users.insert_many(docs)
    await db.users.create_index("email", unique=True)
    return len(docs)


async def seed_kb():
    db = get_db()
    existing = await db.kb_documents.count_documents({})
    if existing > 0:
        return 0
    docs = []
    for title, dt, dom, content in KB_DOCS:
        docs.append(KBDocument(title=title, doc_type=dt, domain=dom, content=content, tags=[dt, dom]).model_dump())
    await db.kb_documents.insert_many(docs)
    return len(docs)


async def seed_complaints():
    db = get_db()
    existing = await db.complaints.count_documents({})
    if existing > 0:
        return 0
    # link to customer demo user
    cust = await db.users.find_one({"role": "customer"}, {"_id": 0, "id": 1, "email": 1, "full_name": 1})
    if not cust:
        return 0
    now = datetime.now(timezone.utc)
    docs = []
    intents = ["Refund", "Replacement", "Delivery Delay", "Payment Failure", "Billing Issue", "Warranty", "Fraud", "Account Issue", "Cancellation", "General Complaint"]
    sentiments = ["Negative", "Neutral", "Negative", "Negative", "Negative"]
    emotions = ["Frustrated", "Concerned", "Angry", "Urgent", "Frustrated"]
    statuses = ["resolved", "in_progress", "assigned", "analyzed", "submitted"]
    depts = {"Refund": "Finance", "Replacement": "Operations", "Delivery Delay": "Logistics", "Payment Failure": "Payments", "Billing Issue": "Billing", "Warranty": "After-Sales", "Fraud": "Risk & Compliance", "Account Issue": "Customer Success", "Cancellation": "Customer Success", "General Complaint": "Support"}

    for i, (domain, desc, name, intent_hint, severity) in enumerate(SAMPLE_COMPLAINTS):
        created = now - timedelta(days=random.randint(0, 60), hours=random.randint(0, 23))
        status = random.choice(statuses)
        intent = intent_hint or random.choice(intents)
        sentiment = random.choice(sentiments)
        emotion = random.choice(emotions)
        priority = severity
        resolved_at = (created + timedelta(hours=random.randint(2, 72))).isoformat() if status == "resolved" else None
        analysis = {
            "summary": desc[:140],
            "keywords": [],
            "intent": intent,
            "intent_confidence": round(random.uniform(0.75, 0.97), 2),
            "category": intent,
            "entities": [],
            "sentiment": sentiment,
            "sentiment_score": round(random.uniform(-0.95, -0.2), 2),
            "emotion": emotion,
            "severity": severity,
            "severity_reason": "Seeded historical complaint",
            "priority": priority,
            "department": depts.get(intent, "Support"),
            "duplicate_score": 0.0,
            "similar_complaint_ids": [],
            "similar_complaints": [],
            "retrieved_policies": [],
            "recommendation": "Resolution handled per policy.",
            "recommendation_action": "Refund" if intent == "Refund" else "Escalation",
            "recommendation_confidence": round(random.uniform(0.7, 0.92), 2),
            "explanation": {"reasoning": "Seeded.", "evidence": [], "policy_basis": [], "confidence": 0.8, "caveats": None},
            "customer_response": "We are reviewing your complaint and will get back shortly.",
            "support_notes": "",
            "manager_notes": "",
            "agent_trace": [],
        }
        docs.append({
            "id": new_id(),
            "user_id": cust["id"],
            "domain": domain,
            "category": intent,
            "description": desc,
            "customer_name": name,
            "customer_email": cust["email"],
            "customer_phone": None,
            "status": status,
            "analysis": analysis,
            "created_at": created.isoformat(),
            "updated_at": created.isoformat(),
            "resolved_at": resolved_at,
            "history": [{"at": created.isoformat(), "status": "submitted", "note": "Complaint submitted"}],
        })
    await db.complaints.insert_many(docs)
    return len(docs)


async def run_all():
    u = await seed_users()
    k = await seed_kb()
    c = await seed_complaints()
    return {"users_seeded": u, "kb_seeded": k, "complaints_seeded": c}


if __name__ == "__main__":
    asyncio.run(run_all())
