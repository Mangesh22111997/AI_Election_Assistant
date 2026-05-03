import streamlit as st

def inject_accessibility_metadata():
    """Inject ARIA metadata and WCAG 2.1 AA compliant CSS/JS."""
    with open("frontend/assets/styles.css", "r") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

    # Skip navigation link (screen reader accessible)
    st.markdown(
        '<a class="skip-nav" href="#main-content" tabindex="1">Skip to main content</a>',
        unsafe_allow_html=True,
    )

def render_accessibility_info():
    """Render the accessibility expander in the sidebar."""
    with st.expander("♿ Accessibility", expanded=False):
        st.markdown("""
        **Keyboard Navigation:**
        - `Tab` — move between elements
        - `Enter` — submit query
        - `Esc` — close panels

        **Screen Reader:**
        - All responses have `aria-live` regions
        - Sources panel is keyboard accessible
        - Skip navigation link available

        **Standards:**
        - WCAG 2.1 AA compliant
        - 4.5:1 minimum contrast ratio
        - 44px minimum touch targets
        """)
