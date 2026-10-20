"""The bot: a question (and the chat so far) -> an answer from fnx.co.il with its sources, or a refusal.

app.py calls answer(question, history). Try it from the terminal: python -m rag.answer "<question>"
"""
import json
import logging
import sys

import openai

import config
from rag.prompts import REWRITE_PROMPT, SYSTEM_PROMPT
from rag.retrieve import clients, retrieve

HISTORY_MESSAGES = 10   # how many recent chat messages the rewrite model sees (5 questions + 5 answers)
MAX_SOURCES = 3        # at most this many links under an answer

REFUSALS = {
    "not_found": "המידע הזה לא מופיע באתר הפניקס. לבירור, אפשר לפנות לשירות הלקוחות.",
    "personal": "אין לי גישה לפוליסות או לפרטים אישיים, ואני עונה רק על מידע כללי מהאתר. "
                "לבירור לגבי הפוליסה או החשבון שלך, אפשר לפנות לשירות הלקוחות.",
    "advice": "אני לא נותן ייעוץ או המלצה אישית, אלא רק מידע כללי מהאתר. "
              "לייעוץ מותאם אישית, אפשר לפנות לשירות הלקוחות.",
    "off_topic": "אני עונה רק על שאלות בנושאים שמופיעים באתר הפניקס, כמו ביטוח, חיסכון, פנסיה ותביעות.",
}

logger = logging.getLogger(__name__)


def standalone_question(question: str, history: list[dict]) -> str:
    """Rewrite a follow-up question into a full question, using the recent chat."""
    if not history:
        return question
    openai_client, _, _ = clients()
    conversation = "\n".join(
        f"{'גולש' if message['role'] == 'user' else 'בוט'}: {message['content']}"
        for message in history[-HISTORY_MESSAGES:]
    )
    response = openai_client.chat.completions.create(
        model=config.REWRITE_MODEL,
        temperature=0,
        messages=[
            {"role": "system", "content": REWRITE_PROMPT},
            {"role": "user", "content": f"השיחה עד עכשיו:\n{conversation}\n\nהשאלה האחרונה: {question}"},
        ],
    )
    return response.choices[0].message.content.strip() or question


def format_chunks(chunks: list[dict]) -> str:
    """Number the chunks [1]..[n], as the system prompt describes."""
    if not chunks:
        return "לא נמצאו קטעים רלוונטיים."
    return "\n\n".join(f"[{n}] {chunk['text']}" for n, chunk in enumerate(chunks, start=1))


def refusal(kind: str) -> dict:
    return {"answer": REFUSALS[kind], "sources": [], "answerable": False, "reason": kind}


def ask_model(messages: list[dict]) -> dict:
    """Get the JSON answer from CHAT_MODEL; if it fails (error 429, outage), try FALLBACK_MODEL once."""
    openai_client, _, _ = clients()

    def call(model: str) -> dict:
        response = openai_client.chat.completions.create(
            model=model, temperature=0, response_format={"type": "json_object"}, messages=messages,
        )
        return json.loads(response.choices[0].message.content)

    try:
        return call(config.CHAT_MODEL)
    except openai.APIError:
        logger.exception(f"{config.CHAT_MODEL} failed - trying {config.FALLBACK_MODEL}")
        return call(config.FALLBACK_MODEL)


def answer(question: str, history: list[dict]) -> dict:
    """Answer one chat question: {"answer": str, "sources": [{"title", "url"}], "answerable": bool}."""
    full_question = standalone_question(question, history)
    chunks = [chunk for chunk in retrieve(full_question) if chunk["score"] >= config.MIN_RELEVANCE]

    result = ask_model([
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"שאלה: {full_question}\n\nקטעים מהאתר:\n{format_chunks(chunks)}"},
    ])

    kind = result.get("question_type")
    if kind != "info":
        return refusal(kind if kind in REFUSALS else "off_topic")

    used = [chunks[n - 1] for n in result.get("chunk_ids", []) if isinstance(n, int) and 1 <= n <= len(chunks)]
    if result.get("coverage") not in ("full", "partial") or not used or not result.get("answer"):
        return refusal("not_found")

    sources = {chunk["url"]: {"title": chunk["title"], "url": chunk["url"]} for chunk in used}
    return {"answer": result["answer"], "sources": list(sources.values())[:MAX_SOURCES], "answerable": True}


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")   # print Hebrew correctly in the Windows terminal
    print(json.dumps(answer(" ".join(sys.argv[1:]), []), ensure_ascii=False, indent=2))
