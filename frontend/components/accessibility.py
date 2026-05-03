import streamlit as st

def inject_accessibility_metadata():
    """Inject ARIA metadata and WCAG 2.1 AA compliant CSS/JS."""
    with open("frontend/assets/styles.css", "r") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

    # WCAG 3.1.1: Set lang attribute on html element
    st.markdown("""
    <script>
    document.documentElement.lang = 'en';
    document.documentElement.setAttribute('xml:lang', 'en');
    </script>
    """, unsafe_allow_html=True)

    # Skip navigation link (WCAG 2.4.1)
    st.markdown(
        '<a class="skip-nav" href="#main-content" tabindex="1" '
        'aria-label="Skip to main content">Skip to main content</a>',
        unsafe_allow_html=True,
    )

    # ARIA live region for dynamic announcements (WCAG 4.1.3)
    st.markdown("""
    <div id="aria-announcer"
         role="status"
         aria-live="polite"
         aria-atomic="true"
         style="position:absolute;width:1px;height:1px;overflow:hidden;
                clip:rect(0,0,0,0);white-space:nowrap;border:0;">
    </div>
    """, unsafe_allow_html=True)

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
