import streamlit as st

LANGUAGE_OPTIONS = {
    "English": "en",
    "हिन्दी (Hindi)": "hi",
    "मराठी (Marathi)": "mr",
    "தமிழ் (Tamil)": "ta",
}

def render_language_selector():
    """Render the language selector in the sidebar."""
    st.markdown("### ⚙️ Settings")
    selected_lang = st.selectbox(
        "🌐 Language",
        list(LANGUAGE_OPTIONS.keys()),
        index=0,
        key="lang_selector",
        help="Select your preferred language for responses",
    )
    st.session_state.selected_language = selected_lang
    lang_code = LANGUAGE_OPTIONS[selected_lang]
    if lang_code != "en":
        st.markdown(
            f'<div class="lang-badge" aria-label="Selected language">🌐 Translating to {selected_lang}</div>',
            unsafe_allow_html=True,
        )
    return lang_code
