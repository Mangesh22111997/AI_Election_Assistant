import streamlit as st

def get_reading_badge(reading_level: str) -> str:
    """Map reading level string to an accessible badge."""
    badges = {
        "Easy": "✅ Easy to Read",
        "Moderate": "📖 Moderate Level",
        "Advanced": "📚 Advanced Level",
        "Complex": "⚠️ Complex",
    }
    for key, label in badges.items():
        if key.lower() in reading_level.lower():
            return f'<span class="reading-badge" aria-label="Reading level: {label}">{label}</span>'
    return ""

def render_message(msg: dict, idx: int, on_feedback: callable):
    """Render a single chat message with ARIA attributes."""
    role = msg["role"]

    if role == "user":
        st.markdown(
            f'<div class="user-bubble" role="listitem" aria-label="Your message">👤 {msg["content"]}</div>',
            unsafe_allow_html=True,
        )
    else:
        reading_badge = get_reading_badge(msg.get("reading_level", ""))
        st.markdown(
            f'<div class="bot-bubble" role="listitem" aria-label="Assistant response" '
            f'aria-live="polite" aria-atomic="true">🗳️ {msg["content"]}{reading_badge}</div>',
            unsafe_allow_html=True,
        )

        # Sources panel
        if msg.get("sources"):
            with st.expander("📚 View Sources", expanded=False):
                st.markdown('<ul role="list" style="list-style:none;padding:0;">', unsafe_allow_html=True)
                for src in msg["sources"]:
                    st.markdown(
                        f'<li style="margin-bottom:4px;"><span class="source-badge" role="note" aria-label="Source citation">📄 {src}</span></li>',
                        unsafe_allow_html=True,
                    )
                st.markdown('</ul>', unsafe_allow_html=True)

        # Safety + intent + latency indicators
        safety_icon = "✅" if msg.get("safety_passed", True) else "❌"
        intent = msg.get("intent", "other")
        latency = msg.get("latency_ms", 0)
        reading_level = msg.get("reading_level", "")
        caption_parts = [
            f"{safety_icon} Safety check",
            f"🎯 Intent: {intent.replace('_', ' ').title()}",
            f"⚡ {latency}ms",
        ]
        if reading_level:
            caption_parts.append(f"📖 {reading_level}")
        st.caption(" | ".join(caption_parts))

        # Feedback buttons
        col1, col2, col3 = st.columns([1, 1, 8])
        with col1:
            if st.button("👍", key=f"thumbs_up_{idx}", help="Mark as helpful"):
                on_feedback(idx, "helpful")
                st.toast("Thanks for your feedback! 🙏")
        with col2:
            if st.button("👎", key=f"thumbs_down_{idx}", help="Mark as not helpful"):
                on_feedback(idx, "not_helpful")
                st.toast("Thanks! We'll improve. 🙏")
