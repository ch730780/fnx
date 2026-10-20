"""
MOCK BOT - for UI development only. NOT part of the final version.

This file fakes the real RAG answer layer so the chat UI can be built and
tested without OpenAI / Pinecone. Later, app.py will switch to
`from rag.answer import answer`, which has the exact same signature.

Keyword triggers (to exercise every UI state):
    "שגיאה"        -> raises RuntimeError (error handling)
    "הפוליסה שלי"  -> refusal, reason="personal"
    "ייעוץ"        -> refusal, reason="advice"
    "מזג אוויר"    -> refusal, reason="off_topic"
    "תביעה"        -> normal answer with 2 sample sources
    anything else  -> refusal, reason="not_found"
"""

import time

from rag.answer import refusal

FAKE_DELAY_SECONDS = 1.5
CLAIMS_BASE_URL = "https://www.fnx.co.il/claims-customer-service/"


def answer(question: str, history: list[dict]) -> dict:
    """Return a fake answer that follows the same contract as rag.answer.answer."""
    # Simulate the time a real search + language model would take
    time.sleep(FAKE_DELAY_SECONDS)

    if "שגיאה" in question:
        raise RuntimeError("Simulated failure for UI testing")

    if "הפוליסה שלי" in question:
        return refusal("personal")

    if "ייעוץ" in question:
        return refusal("advice")

    if "מזג אוויר" in question:
        return refusal("off_topic")

    if "תביעה" in question:
        return {
            "answer": (
                "אפשר להגיש תביעה באתר הפניקס, באזור האישי או בטופס מקוון. "
                "צריך לצרף מסמכים כמו תמונות של הנזק וחשבוניות. "
                "אחרי שהתביעה נקלטת, נציג חוזר אלייך ומעדכן על המשך הטיפול."
            ),
            "sources": [
                {"title": "שירות לקוחות תביעות", "url": CLAIMS_BASE_URL},
                {"title": "הגשת תביעה לביטוח דירה", "url": CLAIMS_BASE_URL + "home-insurance/"},
            ],
            "answerable": True,
        }

    return refusal("not_found")
