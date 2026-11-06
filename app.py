import os
import re
import json
import html
import time
import difflib
import unicodedata
import requests
import streamlit as st
import streamlit.components.v1 as components
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


FEATURE_RULES = """

EXTRA FEATURES (technical format rules):
A. RELATED VERSES: After a Bible or faith answer, add one line that starts with "Related verses:"
   followed by 2 or 3 references only (no verse text), like: Related verses: Romans 8:28, Psalm 46:1.
   Skip this for small talk and when the person seems to be hurting or in crisis.
B. TOPIC LISTS: If the person asks for verses about a topic (like "verses about fear"), give a short
   list of up to 6 verses. Write each as "Reference - a few words about it" (10 words at most).
   Do not write out the full verse text in the list, because the app shows the real text below.
C. WORD STUDIES: If the person asks what a word means in the original Hebrew or Greek, explain the
   original word, its sound, and its meaning in simple words. Then, for each original word you
   discuss (2 at most), add a line at the very end that starts with [[W]] in this exact form:
   [[W]] G26 | agape
   (Strong's number, then a vertical bar, then the transliteration). Use G for Greek and H for
   Hebrew. Only add the line if you are sure of the Strong's number. Never mention these lines.
D. BALANCED VIEWS: On questions where sincere Christians disagree (for example how to baptize,
   the end times, spiritual gifts, predestination), present the main views side by side, calmly
   and fairly, with the verses each side uses. Do not push one view. Then encourage prayer for
   understanding (James 1:5). Exception: topics covered by this app's own perspective rules
   (the Sabbath, dress, tattoos, hair, barefoot prayer) are answered by those rules.
"""

FOLLOWUP_RULE = """

FOLLOW-UP QUESTIONS (technical format rule):
At the very end of a reply to a Bible or faith question, add exactly 3 short follow-up questions
the person might want to ask next. Put each on its own line, starting with [[Q]] and nothing else
on that line, for example:
[[Q]] What does this verse mean for my daily life?
Keep each under 10 words. Never mention or explain these lines.
Do NOT add them for simple replies like "ok", "thanks", "hi", or when the person seems to be
hurting or in crisis.
"""

def clean_rules(text):
    """Drop note lines (starting with #) from a rules text."""
    lines = [ln.rstrip() for ln in (text or "").splitlines() if not ln.lstrip().startswith("#")]
    return "\n".join(lines).strip()


def build_prompt(rules_text):
    """The full instructions for the AI: the rules plus the built-in feature rules."""
    return (clean_rules(rules_text) or load_rules()) + FEATURE_RULES + FOLLOWUP_RULE

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

/* Admin page: readable labels, tabs and inputs */
.stApp [data-testid="stWidgetLabel"] p, .stApp [data-testid="stTabs"] button p,
.stApp [data-testid="stExpander"] summary p, .stApp [data-testid="stExpander"] summary span { color: var(--cream) !important; }
.stApp [data-baseweb="textarea"], .stApp [data-baseweb="input"], .stApp [data-baseweb="base-input"] {
  background: #131D3B !important; border-color: var(--line) !important; }
.stApp [data-baseweb="textarea"] textarea, .stApp [data-baseweb="input"] input { color: var(--cream) !important; }
.stApp [data-testid="stExpander"] { border-color: var(--line); }

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

# ---------- Supabase: live rules + admin login (optional) ----------
SUPABASE_URL = (get_secret("SUPABASE_URL") or "").rstrip("/")
SUPABASE_KEY = get_secret("SUPABASE_KEY") or ""
SB_ON = bool(SUPABASE_URL and SUPABASE_KEY)


def _sb_headers(token=None, prefer=None):
    h = {"apikey": SUPABASE_KEY, "Content-Type": "application/json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    if prefer:
        h["Prefer"] = prefer
    return h


@st.cache_data(ttl=60, show_spinner=False)
def live_rules():
    """Latest published rules from Supabase, or None (then rules.txt is used). Checked about once a minute."""
    if not SB_ON:
        return None
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/ai_rules",
            headers=_sb_headers(),
            params={"select": "id,content", "order": "id.desc", "limit": "1"},
            timeout=5,
        )
        if r.status_code == 200:
            rows = r.json()
            if rows and (rows[0].get("content") or "").strip():
                return {"id": rows[0]["id"], "content": rows[0]["content"]}
        else:
            print(f"[Berean] live rules request failed: {r.status_code} {r.text[:150]}")
    except Exception as e:  # noqa: BLE001
        print(f"[Berean] live rules error: {e}")
    return None


def current_prompt():
    """The system prompt: the published rules if available, otherwise rules.txt."""
    live = live_rules()
    return build_prompt(live["content"] if live else load_rules())


def save_feedback(rating, answer):
    """Save a like / dislike (and the answer, not the question) for the admin to read."""
    if not SB_ON:
        return
    live = live_rules()
    try:
        requests.post(
            f"{SUPABASE_URL}/rest/v1/ai_feedback",
            headers=_sb_headers(prefer="return=minimal"),
            json={"rating": rating, "answer": (answer or "")[:1500], "rules_version": live["id"] if live else None},
            timeout=5,
        )
    except Exception as e:  # noqa: BLE001
        print(f"[Berean] could not save feedback: {e}")


def sb_login(email, password):
    try:
        r = requests.post(
            f"{SUPABASE_URL}/auth/v1/token",
            params={"grant_type": "password"},
            headers=_sb_headers(),
            json={"email": email, "password": password},
            timeout=10,
        )
        if r.status_code == 200:
            return r.json()
        print(f"[Berean] admin login failed: {r.status_code}")
    except Exception as e:  # noqa: BLE001
        print(f"[Berean] admin login error: {e}")
    return None


def sb_refresh(refresh_token):
    try:
        r = requests.post(
            f"{SUPABASE_URL}/auth/v1/token",
            params={"grant_type": "refresh_token"},
            headers=_sb_headers(),
            json={"refresh_token": refresh_token},
            timeout=10,
        )
        if r.status_code == 200:
            return r.json()
    except Exception as e:  # noqa: BLE001
        print(f"[Berean] token refresh error: {e}")
    return None


def sb_call(method, path, params=None, body=None, prefer=None):
    """A request made as the signed-in admin (refreshes the login once if it expired)."""
    adm = st.session_state.get("admin")
    if not adm:
        raise PermissionError("not signed in")
    r = None
    for attempt in (1, 2):
        r = requests.request(
            method,
            f"{SUPABASE_URL}{path}",
            headers=_sb_headers(adm["access"], prefer),
            params=params,
            json=body,
            timeout=10,
        )
        if r.status_code == 401 and attempt == 1:
            d = sb_refresh(adm.get("refresh", ""))
            if d:
                adm["access"], adm["refresh"] = d["access_token"], d.get("refresh_token", adm.get("refresh"))
                continue
            st.session_state.pop("admin", None)
            raise PermissionError("session expired")
        break
    return r


# ---------- Admin page (open the app link with ?admin=1) ----------
def read_rules_file_raw():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rules.txt")
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except Exception:  # noqa: BLE001
        return ""


def _when(ts):
    return (ts or "")[:16].replace("T", " ")


def _strip_markers(text):
    return re.sub(r"(?m)^\s*\[\[[QW]\]\].*$", "", text or "").strip()


def set_draft(text):
    st.session_state.draft = text


def sb_versions(limit=10):
    r = sb_call(
        "GET",
        "/rest/v1/ai_rules",
        params={"select": "id,content,created_by,created_at", "order": "id.desc", "limit": str(limit)},
    )
    return r.json() if r.status_code == 200 else []


def reload_live():
    rows = sb_versions(1)
    st.session_state.draft = rows[0]["content"] if rows else read_rules_file_raw()


def publish_rules():
    text = (st.session_state.get("draft") or "").strip()
    if len(text) < 20:
        st.session_state.admin_msg = ("err", "The rules are too short to publish.")
        return
    try:
        r = sb_call(
            "POST",
            "/rest/v1/ai_rules",
            body={"content": text, "created_by": st.session_state.admin["email"]},
            prefer="return=representation",
        )
    except PermissionError:
        st.session_state.admin_msg = ("err", "Your session expired. Please sign in again.")
        return
    if r.status_code in (200, 201):
        live_rules.clear()
        rows = r.json()
        vid = rows[0]["id"] if isinstance(rows, list) and rows else "?"
        st.session_state.admin_msg = ("ok", f"Published as version {vid}. The app will use it within a minute.")
    else:
        print(f"[Berean] publish failed: {r.status_code} {r.text[:200]}")
        st.session_state.admin_msg = ("err", "Could not publish. Check that your account is on the admins list.")


def sign_out():
    for k in ("admin", "draft", "test_msgs", "admin_msg"):
        st.session_state.pop(k, None)


def clear_test():
    st.session_state.test_msgs = []


def render_admin():
    st.markdown('<div class="mini">🔐 Admin · AI rules</div>', unsafe_allow_html=True)
    if not SB_ON:
        st.error("Supabase is not set up yet. Add SUPABASE_URL and SUPABASE_KEY in the app Secrets.")
        return

    adm = st.session_state.get("admin")
    if not adm:
        wait = st.session_state.get("admin_locked_until", 0) - time.time()
        if wait > 0:
            st.error(f"Too many wrong tries. Please wait {int(wait)} seconds.")
            return
        with st.form("admin_login"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            go = st.form_submit_button("Sign in")
        if go:
            d = sb_login(email.strip(), password)
            if d:
                st.session_state.admin = {
                    "access": d["access_token"],
                    "refresh": d.get("refresh_token", ""),
                    "email": (d.get("user") or {}).get("email", email.strip()),
                    "is_admin": False,
                }
                try:
                    r = sb_call("GET", "/rest/v1/ai_admins", params={"select": "email"})
                    st.session_state.admin["is_admin"] = r.status_code == 200 and len(r.json()) > 0
                except Exception as e:  # noqa: BLE001
                    print(f"[Berean] admin check failed: {e}")
                st.session_state.admin_fail = 0
                st.rerun()
            else:
                st.session_state.admin_fail = st.session_state.get("admin_fail", 0) + 1
                if st.session_state.admin_fail >= 5:
                    st.session_state.admin_locked_until = time.time() + 120
                    st.session_state.admin_fail = 0
                st.error("Wrong email or password.")
        return

    top, out = st.columns([3, 1])
    top.caption(f"Signed in as {adm['email']}")
    out.button("Sign out", on_click=sign_out)
    if not adm.get("is_admin"):
        st.error("This account is not allowed to edit the rules.")
        return

    try:
        if "draft" not in st.session_state:
            reload_live()
        if "test_msgs" not in st.session_state:
            st.session_state.test_msgs = []

        note = st.session_state.pop("admin_msg", None)
        if note:
            (st.success if note[0] == "ok" else st.error)(note[1])

        t_rules, t_test, t_hist, t_fb = st.tabs(["✏️ Rules", "🧪 Test", "🕘 History", "👍 Feedback"])

        with t_rules:
            st.text_area("Rules (the AI follows these)", key="draft", height=420)
            st.caption("Lines that start with # are notes for you. Nothing goes live until you tap Publish.")
            c1, c2, c3 = st.columns(3)
            c1.button("✅ Publish", on_click=publish_rules, type="primary")
            c2.button("↩️ Reload live", on_click=reload_live)
            c3.button("📄 From rules.txt", on_click=set_draft, args=(read_rules_file_raw(),))

        with t_test:
            st.caption("Chat with the AI using the draft rules from the Rules tab. Nothing is published.")
            for m in st.session_state.test_msgs:
                with st.chat_message(m["role"], avatar="🙂" if m["role"] == "user" else "📖"):
                    st.markdown(m["text"])
            with st.form("test_form", clear_on_submit=True):
                q = st.text_input("Ask the AI a question")
                sent = st.form_submit_button("Ask")
            if sent and q.strip():
                st.session_state.test_msgs.append({"role": "user", "text": q.strip()})
                contents = [
                    types.Content(
                        role="user" if m["role"] == "user" else "model",
                        parts=[types.Part(text=m["text"])],
                    )
                    for m in st.session_state.test_msgs
                ]
                with st.spinner("Thinking..."):
                    raw = generate(contents, st.session_state.test_msgs, build_prompt(st.session_state.draft))
                answer = _strip_markers(raw) if raw else "The AI is busy right now. Please try again in a moment."
                st.session_state.test_msgs.append({"role": "assistant", "text": answer})
                st.rerun()
            st.button("Clear test chat", on_click=clear_test)

        with t_hist:
            versions = sb_versions(10)
            if not versions:
                st.info("No published versions yet. Tap Publish on the Rules tab to save the first one.")
            for i, v in enumerate(versions):
                label = f"Version {v['id']} · {_when(v.get('created_at'))} · {v.get('created_by') or ''}"
                with st.expander(("🟢 LIVE · " if i == 0 else "") + label):
                    st.text(v["content"])
                    st.button(
                        "Load into editor",
                        key=f"load_{v['id']}",
                        on_click=set_draft,
                        args=(v["content"],),
                    )
                    st.caption("After loading, go to the Rules tab and tap Publish to make it live.")

        with t_fb:
            r = sb_call(
                "GET",
                "/rest/v1/ai_feedback",
                params={"select": "id,rating,answer,rules_version,created_at", "order": "id.desc", "limit": "50"},
            )
            rows = r.json() if r.status_code == 200 else []
            if not rows:
                st.info("No feedback yet.")
            else:
                ups = sum(1 for x in rows if x["rating"] == "up")
                st.caption(f"Last {len(rows)}: 👍 {ups} · 👎 {len(rows) - ups}. Only the answer is saved, never the question.")
                for x in rows:
                    icon = "👍" if x["rating"] == "up" else "👎"
                    with st.expander(f"{icon} rules v{x.get('rules_version') or '?'} · {_when(x.get('created_at'))}"):
                        st.write(x.get("answer") or "")
    except PermissionError:
        st.warning("Your session expired. Please sign in again.")
        sign_out()



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
    for k in list(st.session_state.keys()):
        if str(k).startswith(("fb_", "re_", "fu_")):
            del st.session_state[k]


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


def groq_generate(history=None, system=None):
    """Backup AI: Groq. Used when Gemini is busy or out of free requests."""
    if not groq_key:
        return None
    system = system or current_prompt()
    history = history if history is not None else st.session_state.messages
    messages = [{"role": "system", "content": system}] + [
        {"role": "user" if m["role"] == "user" else "assistant", "content": m["text"]}
        for m in history
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


def gemini_generate(contents, system=None):
    """Gemini: main model, then the backup Gemini model."""
    system = system or current_prompt()
    for model in (MODEL, FALLBACK_MODEL):
        for attempt in range(2):
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=contents,
                    config=types.GenerateContentConfig(system_instruction=system),
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


def generate(contents, history=None, system=None):
    """Ask the first AI, and use the other one as the backup."""
    system = system or current_prompt()
    if FIRST_AI == "groq":
        return groq_generate(history, system) or gemini_generate(contents, system)
    return gemini_generate(contents, system) or groq_generate(history, system)


def transcribe(audio_bytes):
    """Turn a voice recording into text. Groq Whisper first, Gemini as backup."""
    if groq_key:
        try:
            r = requests.post(
                "https://api.groq.com/openai/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {groq_key}"},
                files={"file": ("voice.wav", audio_bytes, "audio/wav")},
                data={"model": "whisper-large-v3-turbo"},
                timeout=60,
            )
            if r.status_code == 200:
                text = (r.json().get("text") or "").strip()
                if text:
                    return text
            else:
                print(f"[Berean] Groq transcription failed: {r.status_code} {r.text[:200]}")
        except Exception as e:  # noqa: BLE001
            print(f"[Berean] Groq transcription error: {e}")
    for model in (MODEL, FALLBACK_MODEL):
        try:
            resp = client.models.generate_content(
                model=model,
                contents=[
                    types.Part.from_bytes(data=audio_bytes, mime_type="audio/wav"),
                    "Transcribe this audio exactly. Reply with only the words that were spoken.",
                ],
            )
            if resp.text and resp.text.strip():
                return resp.text.strip()
        except Exception as e:  # noqa: BLE001
            print(f"[Berean] Gemini transcription ({model}) error: {e}")
    return None


if st.query_params.get("admin") == "1":
    render_admin()
    st.stop()


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
def split_extras(text):
    """Separate the answer from the [[Q]] follow-up lines and the [[W]] word-study lines."""
    keep, qs, words = [], [], []
    for ln in text.rstrip().split("\n"):
        s = ln.strip()
        if s.startswith("[[Q]]"):
            q = s[5:].strip()
            if q:
                qs.append(q)
        elif s.startswith("[[W]]"):
            num, _, translit = s[5:].partition("|")
            num = num.strip().upper()
            if re.fullmatch(r"[GH]\d{1,5}", num):
                words.append((num, translit.strip()))
        else:
            keep.append(ln)
    clean = "\n".join(keep).rstrip()
    return (clean or text.strip()), qs[:3], words[:2]


def typewriter(text):
    """Make the answer appear word by word."""
    parts = re.split(r"(\s+)", text)
    delay = min(0.025, 3.5 / max(len(parts), 1))
    for p in parts:
        yield p
        time.sleep(delay)


# ---------- Verified verses (real KJV text from bible-api.com) ----------
_NUMBERED = r"[123]\s?(?:Samuel|Kings|Chronicles|Corinthians|Thessalonians|Timothy|Peter|John)"
_PLAIN = (
    "Genesis|Exodus|Leviticus|Numbers|Deuteronomy|Joshua|Judges|Ruth|Ezra|Nehemiah|Esther|Job|"
    "Psalms|Psalm|Proverbs|Ecclesiastes|Song of Solomon|Song of Songs|Isaiah|Jeremiah|Lamentations|"
    "Ezekiel|Daniel|Hosea|Joel|Amos|Obadiah|Jonah|Micah|Nahum|Habakkuk|Zephaniah|Haggai|Zechariah|"
    "Malachi|Matthew|Mark|Luke|John|Acts|Romans|Galatians|Ephesians|Philippians|Colossians|Titus|"
    "Philemon|Hebrews|James|Jude|Revelation"
)
REF_RE = re.compile(
    r"\b((?:" + _NUMBERED + r")|(?:" + _PLAIN + r"))\s+(\d{1,3}):(\d{1,3})(?:\s*[-\u2013]\s*(\d{1,3}))?\b",
    re.I,
)


def extract_refs(text, limit=9):
    """Find Bible references like John 3:16 or Exodus 20:8-11 in an answer."""
    refs, seen = [], set()
    for m in REF_RE.finditer(text):
        book, chap, v1, v2 = m.group(1), m.group(2), m.group(3), m.group(4)
        if v2 and (int(v2) < int(v1) or int(v2) - int(v1) > 11):
            continue  # skip reversed or very long ranges
        book_clean = re.sub(r"\s+", " ", book)
        ref = f"{book_clean} {chap}:{v1}" + (f"-{v2}" if v2 else "")
        if ref.lower() not in seen:
            seen.add(ref.lower())
            refs.append(ref)
        if len(refs) >= limit:
            break
    return refs


@st.cache_data(show_spinner=False, ttl=60 * 60 * 24 * 30)
def fetch_kjv(ref):
    """Get the real KJV text. Failures raise an error, so they are not saved in the cache."""
    r = requests.get(
        "https://bible-api.com/" + requests.utils.quote(ref),
        params={"translation": "kjv"},
        timeout=10,
    )
    if r.status_code != 200:
        raise RuntimeError(f"bible-api {r.status_code}")
    data = r.json()
    verse_text = re.sub(r"\s+", " ", data.get("text", "")).strip()
    if not verse_text:
        raise RuntimeError("empty verse")
    return data.get("reference", ref), verse_text


def get_verified(text):
    found = []
    for ref in extract_refs(text):
        try:
            found.append(fetch_kjv(ref))
        except Exception as e:  # noqa: BLE001
            print(f"[Berean] could not verify {ref}: {e}")
    return found


def show_verified(found):
    if not found:
        return
    with st.expander(f"✅ Verified KJV text ({len(found)})"):
        for name, verse_text in found:
            st.markdown(f"**{name}**\n\n> {verse_text}")
        st.caption("Verse text from bible-api.com (King James Version).")


# ---------- Word study (real lexicon data from bolls.life) ----------
def _plain(s):
    s = re.sub(r"<[^>]+>", " ", s or "")
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def _norm(s):
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z]", "", s)


@st.cache_data(show_spinner=False, ttl=60 * 60 * 24 * 30)
def fetch_lexicon(strongs):
    """Look up a Strong's number (like G26 or H2617). Failures raise an error, so they are not cached."""
    r = requests.get(f"https://bolls.life/dictionary-definition/BDBT/{strongs}/", timeout=10)
    if r.status_code != 200:
        raise RuntimeError(f"bolls {r.status_code}")
    items = r.json()
    if not isinstance(items, list):
        raise RuntimeError("unexpected lexicon format")
    digits = strongs[1:]
    for it in items:
        topic = str(it.get("topic", "")).upper().strip()
        if topic == strongs or (re.sub(r"\D", "", topic) == digits and not topic[:1].isalpha()):
            return {
                "strongs": strongs,
                "lexeme": it.get("lexeme", ""),
                "translit": it.get("transliteration", ""),
                "short": _plain(it.get("short_definition", "")),
                "definition": _plain(it.get("definition", ""))[:450],
            }
    raise RuntimeError("no exact entry")


def get_words(words):
    """Keep a lexicon entry only if its sound matches the word the AI said (guards against wrong numbers)."""
    found = []
    for strongs, ai_translit in words:
        try:
            entry = fetch_lexicon(strongs)
        except Exception as e:  # noqa: BLE001
            print(f"[Berean] lexicon lookup failed for {strongs}: {e}")
            continue
        a, b = _norm(ai_translit), _norm(entry["translit"])
        if a and b and (a in b or b in a or difflib.SequenceMatcher(None, a, b).ratio() >= 0.55):
            found.append(entry)
        else:
            print(f"[Berean] lexicon mismatch for {strongs}: AI said {ai_translit!r}, lexicon has {entry['translit']!r}")
    return found


def show_lexicon(found):
    if not found:
        return
    with st.expander(f"📚 Original word from the lexicon ({len(found)})"):
        for e in found:
            st.markdown(f"**{e['strongs']} · {e['lexeme']} ({e['translit']})**")
            if e["short"]:
                st.markdown(e["short"])
            if e["definition"]:
                st.markdown(f"> {e['definition']}")
        st.caption("Lexicon data: Thayer's Greek and Brown-Driver-Briggs Hebrew definitions, via bolls.life.")


# ---------- Answer buttons: Listen, Copy, like / dislike, try again ----------
def action_buttons(text):
    """Free 'Listen' (phone voice) and 'Copy' buttons under an answer."""
    speak = re.sub(r"[*_#>`\[\]]", "", text)
    speak = re.sub(r"\s+", " ", speak).strip()
    p_speak = json.dumps(speak).replace("</", "<\\/")
    p_copy = json.dumps(text.strip()).replace("</", "<\\/")
    components.html(
        """
<style>
.row{display:flex;gap:8px;font-family:sans-serif}
.b{background:rgba(227,191,92,.13);border:1px solid rgba(227,191,92,.4);color:#E3BF5C;
border-radius:999px;padding:6px 14px;font-size:14px;cursor:pointer}
</style>
<div class="row"><button id="l" class="b">🔊 Listen</button><button id="c" class="b">📋 Copy</button></div>
<script>
const speakText = __SPEAK__;
const copyText = __COPY__;
const l = document.getElementById('l'), c = document.getElementById('c');
l.onclick = () => {
  const s = window.speechSynthesis;
  if (s.speaking) { s.cancel(); l.textContent = '🔊 Listen'; return; }
  const u = new SpeechSynthesisUtterance(speakText);
  u.onend = () => { l.textContent = '🔊 Listen'; };
  l.textContent = '⏹ Stop';
  s.speak(u);
};
c.onclick = () => {
  const done = () => { c.textContent = '✅ Copied'; setTimeout(() => { c.textContent = '📋 Copy'; }, 1500); };
  const fallback = () => {
    const ta = document.createElement('textarea');
    ta.value = copyText; document.body.appendChild(ta); ta.select();
    try { document.execCommand('copy'); done(); } catch (e) {}
    document.body.removeChild(ta);
  };
  if (navigator.clipboard && window.isSecureContext) {
    navigator.clipboard.writeText(copyText).then(done).catch(fallback);
  } else { fallback(); }
};
</script>""".replace("__SPEAK__", p_speak).replace("__COPY__", p_copy),
        height=44,
    )


def log_feedback(idx):
    """Write the like / dislike into the app logs (Manage app > logs) so you can see it."""
    val = st.session_state.get(f"fb_{idx}")
    msgs = st.session_state.messages
    q = msgs[idx - 1]["text"] if 0 < idx <= len(msgs) else ""
    a = msgs[idx]["text"] if idx < len(msgs) else ""
    mark = "LIKE" if val == 1 else "DISLIKE"
    print(f"[Berean][FEEDBACK] {mark} | question: {q[:200]!r} | answer: {a[:300]!r}")
    if val in (0, 1):
        save_feedback("up" if val == 1 else "down", a)


def regenerate():
    msgs = st.session_state.messages
    if msgs and msgs[-1]["role"] == "assistant":
        st.session_state.pop(f"fb_{len(msgs) - 1}", None)
        msgs.pop()
        st.session_state.pending = True


def show_followups(index, questions):
    if not questions:
        return
    st.caption("Tap to continue:")
    for i, q in enumerate(questions):
        st.button(q, key=f"fu_{index}_{i}", on_click=ask, args=(q,))


def answer_extras(idx, m, latest):
    """Everything shown under an answer."""
    show_verified(get_verified(m["text"]))
    show_lexicon(get_words(m.get("words", [])))
    if idx >= len(st.session_state.messages) - 8:
        action_buttons(m["text"])
    st.feedback("thumbs", key=f"fb_{idx}", on_change=log_feedback, args=(idx,))
    if latest:
        st.button("🔄 Try again", key=f"re_{idx}", on_click=regenerate)
        show_followups(idx, m.get("next", []))


me = user_avatar()
last = len(st.session_state.messages) - 1
for idx, m in enumerate(st.session_state.messages):
    if m["role"] == "user":
        with st.chat_message("user", avatar=me):
            safe = html.escape(m["text"])
            st.markdown(f'<span class="user-marker"></span>{safe}', unsafe_allow_html=True)
    else:
        with st.chat_message("assistant", avatar="📖"):
            st.markdown(m["text"])
        answer_extras(idx, m, idx == last)


def read_chat_value(v):
    """Return (text, audio) from the chat box, which may hold typed text and/or a voice recording."""
    if v is None:
        return None, None
    if isinstance(v, str):
        return v, None
    text = getattr(v, "text", None)
    audio = getattr(v, "audio", None)
    if hasattr(v, "get"):
        text = text or v.get("text")
        audio = audio or v.get("audio")
    return text, audio


try:
    typed = st.chat_input("Ask a question or just say hi...", accept_audio=True)  # mic beside send
except TypeError:  # older Streamlit without the built-in mic
    typed = st.chat_input("Ask a question or just say hi...")

text, audio = read_chat_value(typed)
if audio is not None:
    with st.spinner("Listening..."):
        spoken = transcribe(audio.getvalue())
    if spoken:
        text = spoken
    else:
        st.warning("I could not hear that clearly. Please try again.")
if text:
    ask(text)
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
            raw = generate(contents)
        if raw is None:
            clean, nexts, words = "The AI is very busy right now. Please wait a few seconds and ask again.", [], []
            st.markdown(clean)
        else:
            clean, nexts, words = split_extras(raw)
            st.write_stream(typewriter(clean))
    st.session_state.messages.append({"role": "assistant", "text": clean, "next": nexts, "words": words})
    st.session_state.pending = False
    new_idx = len(st.session_state.messages) - 1
    if raw is None:
        st.button("🔄 Try again", key=f"re_{new_idx}", on_click=regenerate)
    else:
        with st.spinner("Verifying verses..."):
            get_verified(clean)
            get_words(words)
        answer_extras(new_idx, st.session_state.messages[-1], True)
