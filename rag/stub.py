"""
MOCK BOT - for UI development only. NOT part of the final version.

This file fakes the real RAG answer layer so the chat UI can be built and
tested without OpenAI / Pinecone. Later, app.py will switch to
`from rag.answer import answer`, which has the exact same signature.

Keyword triggers (to exercise every UI state):
    "שגיאה"        -> raises RuntimeError (error handling)
    "הפוליסה שלי"  -> answerable=False (personal policy questions)
    "תביעה"        -> normal answer with 2 sample sources
    anything else  -> answerable=False (not on the site)
"""

import time

FAKE_DELAY_SECONDS = 1.5
CLAIMS_BASE_URL = "https://www.fnx.co.il/claims-customer-service/"


def answer(question: str, history: list[dict]) -> dict:
    """Return a fake answer that follows the same contract as rag.answer.answer."""
    # Simulate the time a real search + language model would take
    time.sleep(FAKE_DELAY_SECONDS)

    if "שגיאה" in question:
        raise RuntimeError("Simulated failure for UI testing")

    if "הפוליסה שלי" in question:
        return {
            "answer": (
                "אני לא יכול לבדוק פרטים של פוליסה אישית. "
                "אני עונה רק על מידע כללי שמופיע באתר הפניקס. "
                "כדי לבדוק מה הפוליסה שלך מכסה, כדאי לפנות לשירות הלקוחות."
            ),
            "sources": [],
            "answerable": False,
        }

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

    return {
        "answer": "המידע הזה לא מופיע באתר הפניקס, ולכן אני לא יכול לענות עליו.",
        "sources": [],
        "answerable": False,
    }
