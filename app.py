"""Streamlit chat UI for the Phoenix (fnx.co.il) website bot."""

import logging
from pathlib import Path

import streamlit as st

from rag.answer import answer
from rag.retrieve import clients

MAX_QUESTIONS_PER_SESSION = 30
CSS_PATH = Path(__file__).parent / "assets" / "style.css"
CUSTOMER_SERVICE_URL = "https://www.fnx.co.il/customer-service/"
ERROR_MESSAGE = "משהו השתבש, נסי שוב בעוד רגע."
LIMIT_MESSAGE = "הגעת למגבלת השאלות לשיחה. תודה שניסית את הבוט!"

NOT_FOUND_TITLES = {
    "not_found": "המידע לא מופיע באתר",
    "personal": "מידע אישי לא מופיע באתר",
    "advice": "ייעוץ אישי לא מופיע באתר",
    "off_topic": "הנושא לא מופיע באתר",
}

EXAMPLE_QUESTIONS = [
    ("💧", "איך מגישים תביעה על נזקי מים?"),
    ("✈️", 'מה כולל ביטוח נסיעות לחו"ל?'),
    ("📄", "האם הפוליסה שלי מכסה נזילה?"),
]

logger = logging.getLogger(__name__)


def load_css() -> None:
    """Inject our stylesheet into the page."""
    css = CSS_PATH.read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def init_state() -> None:
    """Create the session variables on the first run."""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "question_count" not in st.session_state:
        st.session_state.question_count = 0


def start_new_chat() -> None:
    """Clear the conversation. The question counter is NOT reset."""
    st.session_state.messages = []


def queue_question(question: str) -> None:
    """Remember a clicked example question so the next run handles it."""
    st.session_state.pending_question = question


def limit_reached() -> bool:
    return st.session_state.question_count >= MAX_QUESTIONS_PER_SESSION


def build_history() -> list[dict]:
    """Previous turns in the contract format (role + content), skipping failed turns."""
    return [
        {"role": m["role"], "content": m["content"]}
        for m in st.session_state.messages
        if not m.get("error")
    ]


def render_sidebar() -> None:
    with st.sidebar:
        st.button("🔄 שיחה חדשה", on_click=start_new_chat, width="stretch")
        st.markdown("### איך זה עובד")
        st.markdown(
            "- הבוט מחפש **רק** באתר הפניקס (fnx.co.il)\n"
            "- כל תשובה מגיעה עם קישור לעמוד המקור\n"
            "- כשהמידע לא מופיע באתר — הבוט אומר זאת במפורש\n"
            "- הבוט לא ניגש לפוליסות או לפרטים אישיים"
        )
        st.caption("המידע נאסף מהאתר בתאריך: —")
        remaining = MAX_QUESTIONS_PER_SESSION - st.session_state.question_count
        st.caption(f"שאלות שנותרו: {max(remaining, 0)} מתוך {MAX_QUESTIONS_PER_SESSION}")


HERO_ICON_SVG = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="#FFFFFF" stroke-width="2" '
    'stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12z"/>'
    '<path d="M8.5 12l2.5 2.5 4.5-5"/>'
    "</svg>"
)


def render_header() -> None:
    """Hero banner with our icon, title, subtitle, badge and disclaimer."""
    st.markdown(
        f"""<div class="hero">
<div class="hero-icon">{HERO_ICON_SVG}</div>
<div class="hero-title">הבוט של אתר הפניקס</div>
<p class="hero-subtitle">עונה רק לפי המידע שבאתר fnx.co.il, עם קישור למקור</p>
<span class="hero-badge">✓ מבוסס רק על fnx.co.il</span>
</div>
<p class="disclaimer">פרויקט האקתון — לא שירות רשמי של הפניקס. אין לראות בתשובות ייעוץ אישי.</p>""",
        unsafe_allow_html=True,
    )


def render_footer() -> None:
    st.markdown('<p class="app-footer">נבנה בהאקתון AI קוד פתוח 2026</p>', unsafe_allow_html=True)


def render_examples() -> None:
    """Show clickable example questions (only when the chat is empty)."""
    st.markdown("**אפשר להתחיל מאחת השאלות האלה:**")
    columns = st.columns(len(EXAMPLE_QUESTIONS))
    for column, (icon, question) in zip(columns, EXAMPLE_QUESTIONS):
        with column:
            st.button(
                f"{icon} {question}",
                on_click=queue_question,
                args=(question,),
                width="stretch",
            )


def render_sources(sources: list[dict]) -> None:
    if not sources:
        return
    st.markdown("**מקורות:**")
    for source in sources:
        st.markdown(f"🔗 [{source['title']}]({source['url']})")


def render_not_found(text: str, index: int, reason: str | None) -> None:
    """Card for questions the website does not answer, titled by the reason."""
    title = NOT_FOUND_TITLES.get(reason, NOT_FOUND_TITLES["not_found"])
    st.info(f"**{title}**\n\n{text}", icon="ℹ️")
    st.link_button("פנייה לשירות לקוחות", CUSTOMER_SERVICE_URL, key=f"service_{index}")


def render_message(message: dict, index: int) -> None:
    """Draw one chat message according to its type."""
    with st.chat_message(message["role"]):
        if message["role"] == "user":
            st.markdown(message["content"])
        elif message.get("error"):
            st.error(message["content"])
        elif message["answerable"]:
            st.markdown(message["content"])
            render_sources(message["sources"])
        else:
            render_not_found(message["content"], index, message.get("reason"))


def ask_bot(question: str, history: list[dict]) -> dict:
    """Call the bot and turn any failure into a friendly error message."""
    try:
        result = answer(question, history)
    except Exception:
        logger.exception("answer() failed")  # full details go to the server log only
        return {"role": "assistant", "content": ERROR_MESSAGE,
                "sources": [], "answerable": False, "error": True}
    return {"role": "assistant", "content": result["answer"],
            "sources": result["sources"], "answerable": result["answerable"],
            "reason": result.get("reason")}


def handle_question(question: str) -> None:
    """Add the question to the chat, ask the bot, and show + store the reply."""
    if limit_reached():
        st.warning(LIMIT_MESSAGE)
        return

    history = build_history()  # built BEFORE adding the new question
    messages = st.session_state.messages

    user_message = {"role": "user", "content": question, "sources": [], "answerable": True}
    messages.append(user_message)
    render_message(user_message, len(messages) - 1)
    st.session_state.question_count += 1

    with st.spinner("מחפש באתר..."):
        reply = ask_bot(question, history)
    if reply.get("error"):
        user_message["error"] = True  # keep failed turns out of future history
    messages.append(reply)
    render_message(reply, len(messages) - 1)


def main() -> None:
    st.set_page_config(page_title="הבוט של אתר הפניקס", page_icon="💬", layout="centered")
    load_css()
    init_state()
    render_sidebar()
    render_header()

    for index, message in enumerate(st.session_state.messages):
        render_message(message, index)

    typed = st.chat_input("שאלי שאלה על ביטוח, תביעות, חיסכון...", disabled=limit_reached())
    question = typed or st.session_state.pop("pending_question", None)

    if question:
        handle_question(question)
    elif not st.session_state.messages:
        render_examples()

    if limit_reached():
        st.warning(LIMIT_MESSAGE)

    render_footer()
    try:
        clients()   # connect to OpenAI and Pinecone now, so the first question doesn't wait for it
    except Exception:
        logger.exception("warm-up failed")   # the page still loads; full details go to the server log


if __name__ == "__main__":
    main()
