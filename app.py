import os
import re
import html
import time
import requests
import streamlit as st
from google import genai
from google.genai import types

MODEL = "gemini-3.5-flash"  # if you ever get a model error, change this name
FALLBACK_MODEL = "gemini-2.5-flash"  # used automatically if the main model is busy or fails
GROQ_MODELS = ["openai/gpt-oss-120b", "qwen/qwen3.6-27b"]  # backup AI (Groq), tried in order
FIRST_AI = "groq"  # which AI answers first: "groq" or "gemini". The other one is the backup.

def load_rules():
    """Read the AI's rules from rules.txt (lines starting with # are ignored)."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rules.txt")
    try:
        with open(path, encoding="utf-8") as f:
            lines = [ln.rstrip() for ln in f if not ln.lstrip().startswith("#")]
        text = "\n".join(lines).strip()
        if text:
            return text
    except Exception as e:  # noqa: BLE001
        print(f"[Berean] could not read rules.txt: {e}")
    return (
        'You are Berean Christian AI. Be friendly, teach only from the Bible (KJV), '
        'quote verses accurately with references, and never invent a verse.'
    )


SYSTEM_PROMPT = load_rules()

STARTERS = [
    ("🧠 Memory verse", "Give me a memory verse to learn today."),
    ("🎯 Quiz me", "Quiz me on a memory verse."),
    ("🕊️ The Sabbath", "What does the Bible say about the Sabbath?"),
    ("🧍 What are we made of?", "What are human beings made of?"),
]

st.set_page_config(
    page_title="Berean Christian AI",
    page_icon="📖",
    initial_sidebar_state="collapsed",
)

# ---------- Theme: SACRED GOLD (navy + gold + cream) ----------
st.markdown(
    """
<style>
:root {
  --gold: #E3BF5C; --gold2: #B8902F; --cream: #F4EBD0; --muted: #B9B2A0;
  --navy: #0A1128; --card: #131D3B; --line: rgba(227,191,92,.22);
}

.stApp { background: radial-gradient(900px 560px at 90% -8%, #1D2B5E 0%, #0A1128 58%, #060A18 100%); color: var(--cream); }
header[data-testid="stHeader"] { background: transparent; }
#MainMenu, footer { visibility: hidden; }
.block-container { max-width: 760px; padding-top: 2rem; padding-bottom: 7rem; }
[data-testid="stSidebar"] { background: #0C1530; border-right: 1px solid var(--line); }

/* Make all normal text cream so it is readable */
.stApp [data-testid="stMarkdownContainer"] p,
.stApp [data-testid="stMarkdownContainer"] li,
.stApp [data-testid="stMarkdownContainer"] span,
.stApp [data-testid="stMarkdownContainer"] strong,
.stApp [data-testid="stMarkdownContainer"] em,
.stApp [data-testid="stMarkdownContainer"] h1,
.stApp [data-testid="stMarkdownContainer"] h2,
.stApp [data-testid="stMarkdownContainer"] h3,
.stApp [data-testid="stMarkdownContainer"] h4 { color: var(--cream) !important; }
.stApp [data-testid="stCaptionContainer"], .stApp [data-testid="stCaptionContainer"] p { color: var(--muted) !important; }
[data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 { color: var(--gold) !important; }

/* Hero */
.hero { padding: .6rem 0 1.4rem; animation: rise .6s cubic-bezier(.2,.7,.2,1) both; }
.stApp .hero .badge {
  display: inline-block; font-size: .78rem; font-weight: 600; letter-spacing: .02em;
  padding: .3rem .8rem; border-radius: 999px;
  background: rgba(227,191,92,.13); border: 1px solid rgba(227,191,92,.4); color: var(--gold) !important;
}
.hero h1 {
  font-size: clamp(2.3rem, 9vw, 3.6rem); font-weight: 800; line-height: 1.02;
  letter-spacing: -.04em; margin: .9rem 0 .5rem; padding: 0;
}
.stApp .hero h1 span {
  background: linear-gradient(90deg, #F3D985, #D9A93A);
  -webkit-background-clip: text; background-clip: text; color: transparent !important;
}
.stApp .hero .tag { font-size: 1.1rem; color: var(--muted) !important; margin: 0 0 1.1rem; font-style: italic; }
.hero .verse {
  background: rgba(255,255,255,.04); border: 1px solid var(--line);
  border-left: 4px solid var(--gold); border-radius: 0 16px 16px 0;
  padding: .9rem 1.1rem; color: var(--cream); line-height: 1.55;
}
.stApp .hero .verse b { color: var(--gold) !important; }
.mini { font-size: 1.25rem; font-weight: 800; letter-spacing: -.02em; padding-top: .35rem; color: var(--gold); }

@keyframes rise { from { opacity: 0; transform: translateY(14px); } }

/* Buttons and starter chips */
.stButton > button {
  width: 100%; min-height: 3.2rem; border-radius: 16px;
  background: rgba(255,255,255,.04); border: 1px solid var(--line); color: var(--cream);
  font-weight: 600; transition: transform .15s, border-color .2s, background .2s;
}
.stButton > button:hover { border-color: var(--gold); background: rgba(227,191,92,.12); transform: translateY(-2px); color: #fff; }
.stButton > button:active { transform: scale(.98); }

/* ---------- Chat layout: AI on the left, user on the right ---------- */
[data-testid="stChatMessage"] {
  background: var(--card) !important; border: 1px solid var(--line);
  border-radius: 20px 20px 20px 6px; padding: .9rem 1.1rem; margin: 0 auto .8rem 0;
  width: fit-content; max-width: 92%;
  animation: rise .4s cubic-bezier(.2,.7,.2,1) both;
}
/* the user's messages carry a hidden marker, so we can move them to the right */
[data-testid="stChatMessage"]:has(.user-marker) {
  flex-direction: row-reverse; margin: 0 0 .8rem auto;
  background: linear-gradient(135deg, #F0CF7A, #D4A93E) !important; border: none;
  border-radius: 20px 20px 6px 20px;
}
.stApp [data-testid="stChatMessage"]:has(.user-marker) [data-testid="stMarkdownContainer"] p,
.stApp [data-testid="stChatMessage"]:has(.user-marker) [data-testid="stMarkdownContainer"] span,
.stApp [data-testid="stChatMessage"]:has(.user-marker) [data-testid="stMarkdownContainer"] strong,
.stApp [data-testid="stChatMessage"]:has(.user-marker) [data-testid="stMarkdownContainer"] li { color: #1B1405 !important; }
.user-marker { display: none; }

[data-testid="stChatMessage"] blockquote {
  border-left: 4px solid var(--gold); background: rgba(227,191,92,.08);
  border-radius: 0 12px 12px 0; padding: .5rem 1rem; margin: .6rem 0;
}
[data-testid="stChatMessageAvatarUser"], [data-testid="stChatMessageAvatarAssistant"],
[data-testid="stChatMessageAvatarCustom"] { background: transparent !important; font-size: 1.3rem; }

/* Input */
[data-testid="stChatInput"] { border-radius: 999px; border: 1px solid var(--line); background: #131D3B; }
[data-testid="stChatInput"]:focus-within { border-color: var(--gold); box-shadow: 0 0 0 3px rgba(227,191,92,.22); }
[data-testid="stChatInput"] textarea { color: var(--cream) !important; }
[data-testid="stChatInput"] textarea::placeholder { color: #8F8A7A !important; }
[data-testid="stChatInputSubmitButton"] { color: var(--gold) !important; }
[data-testid="stBottom"] > div { background: transparent; }

@media (prefers-reduced-motion: reduce) { * { animation: none !important; transition: none !important; } }
</style>
""",
    unsafe_allow_html=True,
)

# ---------- API keys ----------
def get_secret(name):
    value = os.environ.get(name)
    if not value:
        try:
            value = st.secrets[name]
        except Exception:
            value = None
    return value


api_key = get_secret("GEMINI_API_KEY")
if not api_key:
    st.error("API key not found. Add a secret named GEMINI_API_KEY in your app settings.")
    st.stop()

client = genai.Client(api_key=api_key)
groq_key = get_secret("GROQ_API_KEY")  # optional backup

# ---------- State ----------
if "messages" not in st.session_state:
    st.session_state.messages = []
if "pending" not in st.session_state:
    st.session_state.pending = False


def ask(text):
    st.session_state.messages.append({"role": "user", "text": text})
    st.session_state.pending = True


def new_chat():
    st.session_state.messages = []
    st.session_state.pending = False


# ---------- User emoji: starts as 🙂, becomes 👨 or 👩 if the user says so ----------
_SELF = r"(?:\bi\s*am|\bi['’]m|\bim|\bas)\s+(?:(?!not\b|n['’]t\b)[\w'’-]+\s+){0,3}?"
MALE_RE = re.compile(_SELF + r"(?:male|man|boy|guy|gentleman|husband|father|dad)\b", re.I)
FEMALE_RE = re.compile(_SELF + r"(?:female|woman|girl|lady|wife|mother|mom|mum)\b", re.I)


def user_avatar():
    gender = None
    for m in st.session_state.messages:
        if m["role"] != "user":
            continue
        male = MALE_RE.search(m["text"])
        female = FEMALE_RE.search(m["text"])
        if male and not female:
            gender = "male"
        elif female and not male:
            gender = "female"
    return {"male": "👨", "female": "👩"}.get(gender, "🙂")


BUSY_WORDS = ("503", "UNAVAILABLE", "overloaded", "high demand")


def groq_generate():
    """Backup AI: Groq. Used when Gemini is busy or out of free requests."""
    if not groq_key:
        return None
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + [
        {"role": "user" if m["role"] == "user" else "assistant", "content": m["text"]}
        for m in st.session_state.messages
    ]
    for model in GROQ_MODELS:
        try:
            r = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {groq_key}"},
                json={"model": model, "messages": messages, "temperature": 0.6},
                timeout=45,
            )
            if r.status_code == 200:
                text = (r.json()["choices"][0]["message"].get("content") or "")
                text = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()
                if text:
                    return text
            else:
                print(f"[Berean] Groq {model} failed: {r.status_code} {r.text[:200]}")
        except Exception as e:  # noqa: BLE001
            print(f"[Berean] Groq {model} error: {e}")
    return None


def gemini_generate(contents):
    """Gemini: main model, then the backup Gemini model."""
    for model in (MODEL, FALLBACK_MODEL):
        for attempt in range(2):
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=contents,
                    config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT),
                )
                if response.text:
                    return response.text
                break
            except Exception as e:  # noqa: BLE001
                print(f"[Berean] {model} attempt {attempt + 1} failed: {e}")
                if any(w in str(e) for w in BUSY_WORDS):
                    time.sleep(1.5)  # briefly busy: wait a moment and retry
                    continue
                break  # out of free requests or another error: move on right away
    return None


def generate(contents):
    """Ask the first AI, and use the other one as the backup."""
    if FIRST_AI == "groq":
        return groq_generate() or gemini_generate(contents)
    return gemini_generate(contents) or groq_generate()


# ---------- Sidebar ----------
with st.sidebar:
    st.header("📖 Berean Christian AI")
    st.button("New chat", on_click=new_chat, use_container_width=True)
    st.caption("Berean Christian AI teaches from a Sabbath-keeping perspective.")
    st.caption("Built by Amos.")

# ---------- Header ----------
if not st.session_state.messages:
    st.markdown(
        """
<div class="hero">
  <span class="badge">KJV · Bible only</span>
  <h1>Berean <span>Christian AI</span></h1>
  <p class="tag">Search the Scriptures. Know it's true.</p>
  <div class="verse">"...searched the scriptures daily, whether those things were so." <b>Acts 17:11</b></div>
</div>
""",
        unsafe_allow_html=True,
    )
    st.caption("Tap one to start, or type your own message below.")
    cols = st.columns(2)
    for i, (label, prompt) in enumerate(STARTERS):
        cols[i % 2].button(label, key=f"starter{i}", on_click=ask, args=(prompt,))
else:
    left, right = st.columns([3, 1])
    left.markdown('<div class="mini">📖 Berean Christian AI</div>', unsafe_allow_html=True)
    right.button("New chat", key="top_new", on_click=new_chat)

# ---------- Conversation ----------
me = user_avatar()
for m in st.session_state.messages:
    if m["role"] == "user":
        with st.chat_message("user", avatar=me):
            safe = html.escape(m["text"])
            st.markdown(f'<span class="user-marker"></span>{safe}', unsafe_allow_html=True)
    else:
        with st.chat_message("assistant", avatar="📖"):
            st.markdown(m["text"])

typed = st.chat_input("Ask a question or just say hi...")
if typed:
    ask(typed)
    st.rerun()

if st.session_state.pending:
    contents = [
        types.Content(
            role="user" if m["role"] == "user" else "model",
            parts=[types.Part(text=m["text"])],
        )
        for m in st.session_state.messages
    ]
    with st.chat_message("assistant", avatar="📖"):
        with st.spinner("Searching the Scriptures..."):
            answer = generate(contents)
        if answer is None:
            answer = "The AI is very busy right now. Please wait a few seconds and ask again."
        st.markdown(answer)
    st.session_state.messages.append({"role": "assistant", "text": answer})
    st.session_state.pending = False
