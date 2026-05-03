"""
frontend/streamlit_app.py
──────────────────────────
Election Guide Assistant – Streamlit UI

WCAG 2.1 AA compliant frontend refactored into modular components.
"""

from __future__ import annotations

import os
import uuid
from typing import Any

import requests
import streamlit as st

# Import components
from components.accessibility import inject_accessibility_metadata, render_accessibility_info
from components.language_selector import render_language_selector
from components.chat_interface import render_message

# ── Page Config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="🗳️ Election Guide Assistant",
    page_icon="🗳️",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Get Help": "https://eci.gov.in",
        "Report a bug": None,
        "About": (
            "Election Guide Assistant – AI-powered voter education platform. "
            "Built with Google Gemini 1.5 Flash, FastAPI, and Streamlit."
        ),
    },
)

inject_accessibility_metadata()

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

# ── Session State ─────────────────────────────────────────────────────────────
if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = []
if "user_id" not in st.session_state:
    st.session_state.user_id = "anonymous"
if "message_index" not in st.session_state:
    st.session_state.message_index = 0
if "selected_language" not in st.session_state:
    st.session_state.selected_language = "English"

# ── Helper Functions ──────────────────────────────────────────────────────────

def translate_text(text: str, target_lang: str) -> str:
    """Translate text via backend translation endpoint."""
    if target_lang == "en" or not text:
        return text
    try:
        resp = requests.post(
            f"{BACKEND_URL}/api/translate",
            json={"text": text, "target_language": target_lang},
            timeout=5,
        )
        if resp.status_code == 200:
            return resp.json().get("translated", text)
    except Exception:
        pass
    return text

def send_query(query: str) -> dict[str, Any] | None:
    """Send a query to the FastAPI backend and return the response."""
    lang_code = st.session_state.get("lang_code", "en")
    try:
        resp = requests.post(
            f"{BACKEND_URL}/api/chat",
            json={
                "query": query,
                "conversation_id": st.session_state.conversation_id,
                "user_id": st.session_state.user_id,
                "language": lang_code,
            },
            timeout=30,
        )
        if resp.status_code == 200:
            return resp.json()
        else:
            detail = resp.json().get("detail", "Unknown error")
            st.error(f"⚠️ {detail}")
            return None
    except Exception as exc:
        st.error(f"❌ Connection error: {exc}")
        return None

def send_feedback(message_index: int, feedback: str, comment: str = "") -> None:
    """Send user feedback to the backend."""
    try:
        requests.post(
            f"{BACKEND_URL}/api/feedback",
            json={
                "conversation_id": st.session_state.conversation_id,
                "message_index": message_index,
                "feedback": feedback,
                "comment": comment or None,
            },
            timeout=5,
        )
    except Exception:
        pass

# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## 🗳️ Election Guide")
    st.markdown("---")

    st.markdown("### 📋 Quick Topics")
    quick_questions = {
        "📅 Registration deadlines": "When is the voter registration deadline?",
        "🪪 ID requirements": "What ID do I need to vote?",
        "📮 Vote by mail": "How do I vote by mail or absentee?",
        "🏛️ Find polling place": "How do I find my polling place?",
        "📞 Voter Helpline 1950": "How do I contact the Voter Helpline at 1950?",
    }
    for label, query in quick_questions.items():
        if st.button(label, use_container_width=True):
            st.session_state["pending_query"] = query
            st.rerun()

    st.markdown("---")
    
    st.session_state["lang_code"] = render_language_selector()

    st.markdown("#### 🔍 Text Size")
    font_size = st.slider("Font size", 14, 22, 16, 1)
    st.markdown(f"<style>.bot-bubble, .user-bubble {{ font-size: {font_size}px !important; }}</style>", unsafe_allow_html=True)

    if st.button("🗑️ Clear Conversation", use_container_width=True):
        st.session_state.messages = []
        st.session_state.conversation_id = str(uuid.uuid4())
        st.session_state.message_index = 0
        st.rerun()

    st.markdown("---")
    render_accessibility_info()
    
    st.page_link("pages/accessibility_statement.py", label="♿ Accessibility Statement", icon="♿")

    st.markdown('<div style="font-size:0.75em; color:#64748b; text-align:center;">🔒 Policy-compliant AI<br>Powered by Google Gemini 1.5 Flash</div>', unsafe_allow_html=True)

# ── Main UI ───────────────────────────────────────────────────────────────────

st.markdown('<div class="hero-header" role="banner"><h1 style="color:white; font-size:2em; margin:0;" id="main-content">🗳️ Election Guide Assistant</h1><p style="color:#bfdbfe; margin:6px 0 0;">AI-powered voter education • WCAG 2.1 AA</p></div>', unsafe_allow_html=True)

st.markdown('<div class="disclaimer-bar" role="alert" aria-live="assertive" aria-atomic="true">🤖 <strong>AI Assistant Notice:</strong> This assistant provides educational information only. For authoritative guidance, contact the <strong>Voter Helpline: 1950</strong> or visit <a href="https://eci.gov.in" target="_blank" style="color:#6ee7b7;">eci.gov.in</a>.</div>', unsafe_allow_html=True)

# Chat history
chat_container = st.container()
with chat_container:
    if not st.session_state.messages:
        st.info("👋 Hello! I'm your Election Guide Assistant. Ask me anything about voter registration, ID requirements, or how to vote. Call **1950** for urgent help.", icon="🗳️")
    else:
        st.markdown('<div role="list" aria-label="Conversation history">', unsafe_allow_html=True)
        for idx, msg in enumerate(st.session_state.messages):
            render_message(msg, idx, send_feedback)
        st.markdown("</div>", unsafe_allow_html=True)

# Input logic
def process_message(query: str):
    st.session_state.messages.append({"role": "user", "content": query})
    with st.spinner("🔍 Researching..."):
        response = send_query(query)
    if response:
        msg_data = response["message"]
        content = translate_text(msg_data["simplified"], st.session_state["lang_code"])
        st.session_state.messages.append({
            "role": "assistant",
            "content": content,
            "sources": msg_data.get("sources", []),
            "intent": msg_data.get("intent", "other"),
            "safety_passed": msg_data.get("safety_passed", True),
            "latency_ms": msg_data.get("latency_ms", 0),
            "reading_level": msg_data.get("reading_level", ""),
        })
        st.session_state.message_index += 1
    st.rerun()

if "pending_query" in st.session_state:
    process_message(st.session_state.pop("pending_query"))

st.markdown("---")
with st.form(key="chat_form", clear_on_submit=True):
    col1, col2 = st.columns([8, 1])
    user_input = col1.text_input("Ask about elections…", placeholder="e.g. How do I register to vote?", label_visibility="collapsed")
    submitted = col2.form_submit_button("Send 🚀", use_container_width=True)

if submitted and user_input.strip():
    process_message(user_input.strip())

# Footer
st.markdown('<div style="text-align:center; color:#64748b; font-size:0.8em;" role="contentinfo">🤖 AI-generated educational content. Always verify with your local election office.<br>📞 <strong>Voter Helpline: 1950</strong> • <a href="https://eci.gov.in" target="_blank" style="color:#3b82f6;">eci.gov.in</a></div>', unsafe_allow_html=True)
