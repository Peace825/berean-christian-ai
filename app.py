import os
import time
import streamlit as st
from google import genai
from google.genai import types

MODEL = "gemini-3.5-flash"  # if you ever get a model error, change this name
FALLBACK_MODEL = "gemini-2.5-flash"  # used automatically if the main model is busy or fails

SYSTEM_PROMPT = """
You are Berean Christian AI. Your slogan: "Search the Scriptures. Know it's true." (Acts 17:11).

RULES:
1. BIBLE ONLY. Answer only from Scripture. Do not use outside books or other teachings.
   If a question is not about the Bible, faith, or Christian living, politely say:
   "I can only help with the Bible."
   (The only exceptions are rules 13 and 14 below.)
2. ALWAYS quote the verse text with its reference, like (John 3:16). Use the KJV.
   NEVER invent a verse. If you are not sure a verse exists, say so.
3. Give Scripture first, then a short, simple explanation.
4. SABBATH: When asked about the Sabbath, give a full, detailed answer using
   Genesis 2:2-3, Exodus 20:8-11, Isaiah 58:13-14, Mark 2:27-28, Luke 4:16 and Hebrews 4:9.
   This app teaches from a Sabbath-keeping perspective. Say so plainly when it matters.
5. DECENCY AND DRESS: Teach modest dress and reverence using Leviticus 19:28 (tattoos),
   1 Timothy 2:9 and 1 Peter 3:3-4 (dress), and 1 Corinthians 11:14 (men's hair).
   Clearly separate what the verse says from what this app's perspective teaches.
6. BAREFOOT PRAYER: It is a personal act of reverence, not a requirement for anyone.
   Share Exodus 3:5 and Joshua 5:15, and explain that some believers pray barefoot
   in a set-apart place to honor God's presence.
7. Remind people to pray for understanding (James 1:5, Psalm 119:18). Understanding grows
   and can differ between believers.
8. Be honest and bold with the truth from Scripture, but always loving and respectful, never harsh.
9. On topics where Christians disagree, show what the verses say and note that believers see it differently.
10. MEMORY VERSES: If asked for a memory verse, give it with its reference. If asked to be quizzed,
    give the reference, ask the person to say the verse, then check their answer kindly.
11. If someone is hurting or in danger, respond with compassion and encourage them to talk to a
    pastor or a trusted person. If they may harm themselves, urge them to contact local emergency help.
12. Keep answers short and simple so they read well on a phone.
13. DEVELOPER: If anyone asks who your developer or creator is, answer only: "Amos." Say nothing more about it.
14. WHAT HUMAN BEINGS ARE MADE OF: If anyone asks what human beings are made of or comprise of, answer that
    a human being is made of spirit, soul and body (the flesh). Explain that when a person believes
    in Jesus Christ and studies God's Word, God also gives them the Holy Spirit, so a believer
    comprises spirit, soul and body with the Holy Spirit dwelling in them. Always defend this with
    these memory verses, quoted accurately in the KJV with their references:
    - 1 Thessalonians 5:23: "...your whole spirit and soul and body be preserved blameless unto the coming of our Lord Jesus Christ."
    - Ephesians 1:13: "...after that ye believed, ye were sealed with that holy Spirit of promise."
    - 1 Corinthians 6:19: "What? know ye not that your body is the temple of the Holy Ghost which is in you, which ye have of God, and ye are not your own?"
"""

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

st.markdown(
    """
<style>
:root { --accent: #8B84FF; --accent2: #5B9CFF; --glass: rgba(255,255,255,.05); --line: rgba(255,255,255,.10); }

.stApp { background: radial-gradient(900px 520px at 90% -8%, #2B2578 0%, #0B0F1A 62%); }
header[data-testid="stHeader"] { background: transparent; }
#MainMenu, footer { visibility: hidden; }
.block-container { max-width: 760px; padding-top: 2rem; padding-bottom: 7rem; }

/* Hero */
.hero { padding: .6rem 0 1.4rem; animation: rise .6s cubic-bezier(.2,.7,.2,1) both; }
.badge {
  display: inline-block; font-size: .78rem; font-weight: 600; letter-spacing: .02em;
  padding: .3rem .8rem; border-radius: 999px;
  background: rgba(139,132,255,.15); border: 1px solid rgba(139,132,255,.35); color: #C9C5FF;
}
.hero h1 {
  font-size: clamp(2.3rem, 9vw, 3.6rem); font-weight: 800; line-height: 1.02;
  letter-spacing: -.04em; margin: .9rem 0 .5rem; padding: 0;
}
.hero h1 span {
  background: linear-gradient(90deg, #B5B0FF, #6EA8FF);
  -webkit-background-clip: text; background-clip: text; color: transparent;
}
.hero .tag { font-size: 1.1rem; color: #AEB4D6; margin: 0 0 1.1rem; font-style: italic; }
.verse {
  background: var(--glass); border: 1px solid var(--line);
  border-left: 4px solid var(--accent); border-radius: 0 16px 16px 0;
  padding: .9rem 1.1rem; color: #E4E6F7; line-height: 1.55;
}
.verse b { color: #C9C5FF; }

.mini { font-size: 1.25rem; font-weight: 800; letter-spacing: -.02em; padding-top: .35rem; }

@keyframes rise { from { opacity: 0; transform: translateY(14px); } }

/* Buttons and starter chips */
.stButton > button {
  width: 100%; min-height: 3.2rem; border-radius: 16px;
  background: var(--glass); border: 1px solid var(--line); color: #EDEFFA;
  font-weight: 600; transition: transform .15s, border-color .2s, background .2s;
}
.stButton > button:hover { border-color: var(--accent); background: rgba(139,132,255,.14); transform: translateY(-2px); color: #fff; }
.stButton > button:active { transform: scale(.98); }

/* Chat bubbles */
[data-testid="stChatMessage"] {
  background: var(--glass); border: 1px solid var(--line);
  border-radius: 20px; padding: 1rem 1.1rem; margin-bottom: .8rem;
  animation: rise .4s cubic-bezier(.2,.7,.2,1) both;
}
[data-testid="stChatMessage"] blockquote {
  border-left: 4px solid var(--accent); background: rgba(139,132,255,.10);
  border-radius: 0 12px 12px 0; padding: .5rem 1rem; margin: .6rem 0; color: #E4E6F7;
}
[data-testid="stChatMessageAvatarUser"], [data-testid="stChatMessageAvatarAssistant"] {
  background: transparent !important; font-size: 1.3rem;
}

/* Input */
[data-testid="stChatInput"] { border-radius: 999px; border: 1px solid var(--line); background: #151B2E; }
[data-testid="stChatInput"]:focus-within { border-color: var(--accent); box-shadow: 0 0 0 3px rgba(139,132,255,.25); }
[data-testid="stBottom"] > div { background: transparent; }

@media (prefers-reduced-motion: reduce) { * { animation: none !important; transition: none !important; } }
</style>
""",
    unsafe_allow_html=True,
)

# ---------- API key ----------
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
    except Exception:
        api_key = None
if not api_key:
    st.error("API key not found. Add a secret named GEMINI_API_KEY in your app settings.")
    st.stop()

client = genai.Client(api_key=api_key)

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


BUSY_WORDS = ("503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED", "overloaded", "high demand")


def generate(contents):
    """Try the main model, retry when it is busy, then try the backup model."""
    for model in (MODEL, FALLBACK_MODEL):
        for attempt in range(3):
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
                    time.sleep(2 * (attempt + 1))  # busy: wait a little and retry
                    continue
                break  # not a busy error: move on to the backup model
    return None


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
    st.caption("Tap one to start, or type your own question below.")
    cols = st.columns(2)
    for i, (label, prompt) in enumerate(STARTERS):
        cols[i % 2].button(label, key=f"starter{i}", on_click=ask, args=(prompt,))
else:
    left, right = st.columns([3, 1])
    left.markdown('<div class="mini">📖 Berean Christian AI</div>', unsafe_allow_html=True)
    right.button("New chat", key="top_new", on_click=new_chat)

# ---------- Conversation ----------
for m in st.session_state.messages:
    avatar = "🙂" if m["role"] == "user" else "📖"
    with st.chat_message(m["role"], avatar=avatar):
        st.markdown(m["text"])

typed = st.chat_input("Ask a Bible question...")
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
