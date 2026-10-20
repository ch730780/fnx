"""Streamlit chat UI for the Phoenix (fnx.co.il) website bot."""

import base64
import logging
from pathlib import Path

import streamlit as st

from rag.answer import answer
from rag.retrieve import clients

MAX_QUESTIONS_PER_SESSION = 30
ASSETS = Path(__file__).parent / "assets"
CSS_PATH = ASSETS / "style.css"
HOME_PATH = ASSETS / "home.html"
LOGO_PATH = ASSETS / "fnx-logo.png"
CUSTOMER_SERVICE_URL = "https://www.fnx.co.il/customer-service/"
ERROR_MESSAGE = "משהו השתבש, נסי שוב בעוד רגע."
LIMIT_MESSAGE = "הגעת למגבלת השאלות לשיחה. תודה שניסית את הבוט!"

NOT_FOUND_TITLES = {
    "not_found": "המידע לא מופיע באתר",
    "personal": "מידע אישי לא מופיע באתר",
    "advice": "ייעוץ אישי לא מופיע באתר",
    "off_topic": "הנושא לא מופיע באתר",
}

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
    if "chat_open" not in st.session_state:
        st.session_state.chat_open = False


def start_new_chat() -> None:
    """Clear the conversation. The question counter is NOT reset."""
    st.session_state.messages = []


def open_chat() -> None:
    st.session_state.chat_open = True


def close_chat() -> None:
    st.session_state.chat_open = False


def limit_reached() -> bool:
    return st.session_state.question_count >= MAX_QUESTIONS_PER_SESSION


def build_history() -> list[dict]:
    """Previous turns in the contract format (role + content), skipping failed turns."""
    return [
        {"role": m["role"], "content": m["content"]}
        for m in st.session_state.messages
        if not m.get("error")
    ]


INFO_SVG = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="#C2410C" stroke-width="2" '
    'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
    '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>'
    "</svg>"
)


def logo_src() -> str:
    """The Phoenix logo (white text) as an inline image, so st.markdown can show it."""
    return "data:image/png;base64," + base64.b64encode(LOGO_PATH.read_bytes()).decode()


def render_homepage() -> None:
    """A home page behind the chat, so the bot is shown in context."""
    html = HOME_PATH.read_text(encoding="utf-8").replace("{logo}", logo_src())
    st.markdown(html, unsafe_allow_html=True)


def render_launcher() -> None:
    """The closed bot: one orange button in the corner that opens the chat."""
    st.button("צ'אט AI", key="open_chat", icon=":material/chat:", on_click=open_chat)


def render_chat_header() -> None:
    """Dark blue bar: logo, name, new-chat and close buttons."""
    with st.container(key="chat_header", horizontal=True, vertical_alignment="center"):
        st.markdown(
            f"""<div class="chat-title">
<img class="chat-logo" src="{logo_src()}" alt="הפניקס">
<div class="chat-divider"></div>
<div><div class="chat-name">הבוט של האתר</div><div class="chat-sub">מבוסס בינה מלאכותית</div></div>
</div>""",
            unsafe_allow_html=True,
            width="stretch",
        )
        st.button("שיחה חדשה", key="new_chat", icon=":material/add:", on_click=start_new_chat)
        st.button(":material/close:", key="close_chat", help="סגירת הצ'אט", on_click=close_chat)


def render_disclaimer() -> None:
    st.markdown(
        f"""<div class="chat-disclaimer">{INFO_SVG}
<p>זהו אינו שירות רשמי של הפניקס, והתשובות אינן מהוות ייעוץ אישי.</p>
</div>""",
        unsafe_allow_html=True,
    )


def render_welcome() -> None:
    """Greeting shown while the chat is still empty."""
    st.markdown(
        f"""<div class="chat-welcome">
<div class="chat-welcome-logo"><img src="{logo_src()}" alt="הפניקס"></div>
<h2>שלום! אני הבוט של אתר הפניקס</h2>
<p>אפשר לשאול אותי על ביטוח רכב, דירה, בריאות, נסיעות, חיסכון ופנסיה. אני עונה לפי המידע שבאתר הפניקס.</p>
</div>""",
        unsafe_allow_html=True,
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


def render_chat() -> None:
    """The open bot: a chat window in the corner of the page."""
    with st.container(key="chat_panel", gap=None):
        render_chat_header()
        render_disclaimer()
        body = st.container(key="chat_body", height="stretch", autoscroll=True)
        typed = st.chat_input("שאלי שאלה על ביטוח, תביעות, חיסכון...", disabled=limit_reached())

    with body:
        if not st.session_state.messages and not typed:
            render_welcome()
        for index, message in enumerate(st.session_state.messages):
            render_message(message, index)
        if typed:
            handle_question(typed)
        if limit_reached():
            st.warning(LIMIT_MESSAGE)


def main() -> None:
    st.set_page_config(page_title="הבוט של אתר הפניקס", page_icon="💬", layout="wide")
    load_css()
    init_state()
    render_homepage()

    if st.session_state.chat_open:
        render_chat()
    else:
        render_launcher()

    try:
        clients()   # connect to OpenAI and Pinecone now, so the first question doesn't wait for it
    except Exception:
        logger.exception("warm-up failed")   # the page still loads; full details go to the server log


if __name__ == "__main__":
    main()
