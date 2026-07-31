# -*- coding: utf-8 -*-
"""
auth.py — shared-password gate
==============================
Call require_auth() as the FIRST thing in main(), before any widget renders.
On failure it calls st.stop(), so nothing below it executes — no sidebar, no
file uploader, no chat, no cached data.

Scope, stated plainly: this is one shared credential. It stops crawlers and
anyone who stumbles onto the URL, which is the realistic exposure for a public
Railway hostname. It does NOT give per-person accounts, an audit trail, or
revocation. When someone else needs access — or IT asks where the data lives —
the answer is st.login() OIDC against the corporate tenant, not this.

The password comes from APP_PASSWORD (Railway → Variables), or st.secrets when
running on Streamlit Cloud. If neither is set the app stays open and shows a
warning: locking the planner out of their own deploy over a missing env var
would be worse than the exposure, and the warning is loud enough to notice.
"""

import hmac
import os

import streamlit as st

ENV_VAR = "APP_PASSWORD"
STATE_KEY = "_auth_ok"

LOGIN_CSS = """
<style>
    #MainMenu, footer, header { visibility: hidden; }
    .auth-wrap { max-width: 380px; margin: 12vh auto 0 auto; text-align: center; }
    .auth-wrap h2 {
        font-family: 'DM Sans', sans-serif; color: #1a1a2e;
        font-size: 1.35rem; font-weight: 600; margin-bottom: 0.15rem;
    }
    .auth-wrap p { color: #8a8f98; font-size: 0.85rem; margin-bottom: 1.2rem; }
</style>
"""


def _expected_password():
    """Read the configured password from the environment or st.secrets."""
    pw = os.environ.get(ENV_VAR)
    if pw:
        return pw
    try:
        return st.secrets.get(ENV_VAR)      # Streamlit Cloud
    except Exception:
        return None


def require_auth():
    """Block the app until the correct password is entered.

    Returns True when authenticated. Otherwise renders the login screen and
    stops the script.
    """
    expected = _expected_password()

    # Not configured — open, but say so.
    if not expected:
        if not st.session_state.get("_auth_warned"):
            st.session_state["_auth_warned"] = True
        st.warning(
            f"No {ENV_VAR} set — this app is publicly accessible to anyone with the URL. "
            f"Set {ENV_VAR} in Railway → Variables to enable the password gate.",
            icon="⚠️",
        )
        return True

    if st.session_state.get(STATE_KEY):
        return True

    st.markdown(LOGIN_CSS, unsafe_allow_html=True)
    st.markdown("""
    <div class="auth-wrap">
        <h2>HJW Tracker</h2>
        <p>South Asia Pacific</p>
    </div>
    """, unsafe_allow_html=True)

    left, mid, right = st.columns([1, 2, 1])
    with mid:
        entered = st.text_input("Password", type="password",
                                label_visibility="collapsed",
                                placeholder="Password", key="_auth_input")
        if st.button("Enter", use_container_width=True, type="primary", key="_auth_btn"):
            # compare_digest rather than == : constant time, no early exit on
            # the first differing character.
            if hmac.compare_digest(str(entered), str(expected)):
                st.session_state[STATE_KEY] = True
                # Don't leave the password sitting in session state.
                st.session_state.pop("_auth_input", None)
                st.rerun()
            else:
                st.error("Incorrect password.")

    st.stop()


def logout():
    st.session_state.pop(STATE_KEY, None)
