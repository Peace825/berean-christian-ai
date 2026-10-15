import os
import streamlit as st
from google import genai
from google.genai import types

MODEL = "gemini-3.5-flash"  # if you ever get a model error, change this name

SYSTEM_PROMPT = """
You are Berean Christian AI. Your slogan: "Search the Scriptures. Know it's true." (Acts 17:11).

RULES:
1. BIBLE ONLY. Answer only from Scripture. Do not use outside books or other teachings.
   If a question is not about the Bible, faith, or Christian living, politely say:
   "I can only help with the Bible."
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
"""

st.set_page_config(page_title="Berean Christian AI", page_icon="📖")

st.title("📖 Berean Christian AI")
st.caption("*Search the Scriptures. Know it's true.*")
st.markdown("\"...searched the scriptures daily, whether those things were so.\" (Acts 17:11)")

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

if "messages" not in st.session_state:
    st.session_state.messages = []

with st.sidebar:
    st.header("Quick actions")
    if st.button("Give me a memory verse"):
        st.session_state.queued = "Give me a memory verse to learn today."
    if st.button("Quiz me on a verse"):
        st.session_state.queued = "Quiz me on a memory verse."
    if st.button("Clear chat"):
        st.session_state.messages = []
        st.rerun()
    st.caption("Berean Christian AI teaches from a Sabbath-keeping perspective.")

for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["text"])

typed = st.chat_input("Ask a Bible question...")
question = typed or st.session_state.pop("queued", None)

if question:
    st.session_state.messages.append({"role": "user", "text": question})
    with st.chat_message("user"):
        st.markdown(question)

    contents = [
        types.Content(
            role="user" if m["role"] == "user" else "model",
            parts=[types.Part(text=m["text"])],
        )
        for m in st.session_state.messages
    ]

    with st.chat_message("assistant"):
        try:
            response = client.models.generate_content(
                model=MODEL,
                contents=contents,
                config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT),
            )
            answer = response.text or "Sorry, I could not answer that. Please try again."
        except Exception as e:
            answer = f"Sorry, something went wrong. Please try again. ({e})"
        st.markdown(answer)

    st.session_state.messages.append({"role": "assistant", "text": answer})
