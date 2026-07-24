# -*- coding: utf-8 -*-
"""
event_app.py — Event Management UI
==================================
Streamlit layer only. All logic lives in events.py; all document formats
live in stores.py. Nothing here builds a CSV row or decides a status.

Reads the FULL uploaded dataframe, deliberately ignoring the Stock Report's
sidebar filters — an event plan must see every location, not the subset the
planner happens to be looking at.
"""

import io
from datetime import date, datetime, timedelta

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

import events as ev
from stores import STORE_CODES

EVENT_CSS = """
<style>
    .ev-brief {
        border-radius: 8px; padding: 0.7rem 0.9rem; margin-bottom: 0.6rem;
        font-size: 0.85rem; line-height: 1.5; border-left: 4px solid;
    }
    .ev-brief h4 { margin: 0 0 0.35rem 0; font-size: 0.95rem; }
    .ev-brief ul { margin: 0.4rem 0 0 0; padding-left: 1.1rem; }
    .ev-brief li { margin-bottom: 0.15rem; }
    .ev-ontrack  { background: #f0f5ef; border-color: #1a7a5a; color: #1d3d31; }
    .ev-urgent   { background: #fff8e6; border-color: #e8a820; color: #6b5a1e; }
    .ev-critical { background: #fff1e6; border-color: #e07020; color: #7a3d12; }
    .ev-overdue  { background: #fef0f0; border-color: #d32f2f; color: #8a1f1f; }

    .ev-action {
        background: #f5f0ff; border-left: 3px solid #6b3fa0;
        border-radius: 8px; padding: 0.5rem 0.75rem;
        margin-bottom: 0.3rem; font-size: 0.82rem;
    }
    .ev-action .cmd {
        font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
        font-size: 0.75rem; color: #4a2d70; display: block; margin-top: 3px;
    }
    .ev-empty {
        color: #999; text-align: center; padding: 2rem 1rem;
        font-size: 0.85rem; line-height: 1.6;
    }
</style>
"""

URGENCY_CLASS = {
    "ON TRACK": "ev-ontrack", "URGENT": "ev-urgent",
    "CRITICAL": "ev-critical", "OVERDUE": "ev-overdue",
}


# ─────────────────────────────────────────────
# STATE
# ─────────────────────────────────────────────

def init_state():
    for key, default in [
        ("ev_events", []),          # list of event dicts
        ("ev_active_id", None),     # currently open event
        ("ev_route", "SR"),         # SR (via N71) or PR (direct store-to-store)
        ("ev_results", {}),         # action label -> run_action() result
        ("ev_editing", False),      # show the edit form
    ]:
        if key not in st.session_state:
            st.session_state[key] = default


def _active_event():
    for e in st.session_state.ev_events:
        if e["id"] == st.session_state.ev_active_id:
            return e
    return None


def _store_options():
    """Store codes a venue could plausibly be.

    Excludes the warehouse, the block location, the repair centre and the
    RDCs — none of those are places an event happens. Singapore first.
    """
    opts = [(c, i) for c, i in STORE_CODES.items()
            if c not in ev.NON_SOURCE_LOCATIONS]
    opts.sort(key=lambda x: (x[1].get("country", "") != "SINGAPORE",
                             x[1].get("country", ""), x[0]))
    return [f"{c} — {i['name']}" for c, i in opts]


# ─────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────

def render_event_sidebar(df):
    """Event picker + create/import. Called from inside the sidebar context.

    Calls init_state() because this runs BEFORE render_event_app() in main().
    init_state is idempotent, so calling it from both entry points is safe.
    """
    init_state()
    st.divider()
    st.markdown("**Events**")

    evts = st.session_state.ev_events
    if evts:
        labels = []
        for e in evts:
            days, urgency = ev.event_urgency(e)
            labels.append(f"{e['name']} · {e['event_date']} · {urgency}")
        ids = [e["id"] for e in evts]
        idx = ids.index(st.session_state.ev_active_id) if st.session_state.ev_active_id in ids else 0
        pick = st.selectbox("Open event", labels, index=idx, label_visibility="collapsed")
        chosen = ids[labels.index(pick)]
        if chosen != st.session_state.ev_active_id:
            st.session_state.ev_active_id = chosen
            st.session_state.ev_results = {}
            st.session_state.ev_editing = False
            st.rerun()
    else:
        st.caption("No events yet.")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("New", use_container_width=True):
            st.session_state.ev_active_id = None
            st.session_state.ev_editing = True
            st.session_state.ev_results = {}
            st.rerun()
    with c2:
        if evts and st.button("Edit", use_container_width=True):
            st.session_state.ev_editing = True
            st.rerun()

    if evts:
        st.download_button(
            "Save events file",
            data=ev.events_to_json(evts),
            file_name=f"hjw_events_{datetime.now().strftime('%Y%m%d')}.json",
            mime="application/json",
            use_container_width=True,
            key="ev_dl_events",
        )

    up = st.file_uploader("Load events file", type=["json"], key="ev_import",
                          label_visibility="collapsed")
    if up is not None:
        try:
            loaded = ev.events_from_json(up.getvalue().decode("utf-8"))
            existing = {e["id"] for e in st.session_state.ev_events}
            added = [e for e in loaded if e["id"] not in existing]
            if added:
                st.session_state.ev_events.extend(added)
                st.session_state.ev_active_id = added[0]["id"]
                st.rerun()
        except Exception as exc:
            st.error(f"Could not read that file: {exc}")


# ─────────────────────────────────────────────
# EVENT FORM
# ─────────────────────────────────────────────

def render_event_form(df):
    """Create or edit an event."""
    event = _active_event() if st.session_state.ev_active_id else None
    is_new = event is None

    st.markdown("#### " + ("New event" if is_new else f"Edit — {event['name']}"))

    name = st.text_input("Event name", value="" if is_new else event["name"],
                         placeholder="e.g. Manila Private Salon")

    default_date = (date.today() + timedelta(days=21) if is_new
                    else datetime.strptime(event["event_date"], "%Y-%m-%d").date())
    event_date = st.date_input("Event date", value=default_date)
    st.caption(f"Everything must be ready to send by "
               f"**{(event_date - timedelta(days=ev.READY_LEAD_DAYS)).strftime('%d %b %Y')}** "
               f"({ev.READY_LEAD_DAYS} days before).")

    venue_type = st.radio(
        "Venue", ["store", "block"],
        index=0 if is_new or event["venue_type"] == "store" else 1,
        format_func=lambda v: "Store code" if v == "store" else "Block (N71 → N65)",
        horizontal=True,
    )

    venue_code, block_name = "", ""
    if venue_type == "store":
        opts = _store_options()
        default_idx = 0
        if not is_new and event.get("venue_code"):
            for i, o in enumerate(opts):
                if o.startswith(event["venue_code"]):
                    default_idx = i
                    break
        venue_code = st.selectbox("Venue store", opts, index=default_idx).split(" — ")[0]
    else:
        block_name = st.text_input(
            "Block order name", value="" if is_new else event.get("block_name", ""),
            placeholder="e.g. PHcarnet",
            help="Used verbatim as ORDERNAME in the block CSV. Case is preserved.")

    existing_skus = "" if is_new else "\n".join(event["skus"])
    sku_text = st.text_area("SKUs", value=existing_skus, height=160,
                            placeholder="Paste your SKU list — one per line, or comma separated.")

    known, unknown = ev.parse_sku_list(sku_text, df)
    if known or unknown:
        msg = f"{len(known)} SKU(s) matched"
        if unknown:
            msg += f" · {len(unknown)} not in this file: {', '.join(unknown[:8])}"
            if len(unknown) > 8:
                msg += f" +{len(unknown) - 8} more"
        st.caption(msg)

    c1, c2 = st.columns([1, 1])
    with c1:
        if st.button("Save event", type="primary", use_container_width=True):
            draft = ev.new_event(name, event_date, venue_type, venue_code,
                                 block_name, known + unknown)
            problems = ev.validate_event(draft)
            if problems:
                for p in problems:
                    st.error(p)
            else:
                if is_new:
                    st.session_state.ev_events.append(draft)
                    st.session_state.ev_active_id = draft["id"]
                else:
                    draft["id"] = event["id"]
                    draft["created"] = event.get("created", draft["created"])
                    for i, e in enumerate(st.session_state.ev_events):
                        if e["id"] == event["id"]:
                            st.session_state.ev_events[i] = draft
                st.session_state.ev_editing = False
                st.session_state.ev_results = {}
                st.rerun()
    with c2:
        if st.button("Cancel", use_container_width=True):
            st.session_state.ev_editing = False
            st.rerun()

    if not is_new:
        if st.button("Delete this event"):
            st.session_state.ev_events = [
                e for e in st.session_state.ev_events if e["id"] != event["id"]]
            st.session_state.ev_active_id = (
                st.session_state.ev_events[0]["id"] if st.session_state.ev_events else None)
            st.session_state.ev_editing = False
            st.rerun()


# ─────────────────────────────────────────────
# EMAIL CARD
# ─────────────────────────────────────────────

def render_email_card(em):
    """Blue email bubble with a copy-as-rich-text button.

    Mirrors the chat email card in app.py. Worth pulling both into a shared
    ui module the next time either one is touched.
    """
    body = em["body_html"]
    components.html(f"""
<div style="background:#f0f4ff;border-left:3px solid #2962ff;border-radius:8px;
     font-family:'DM Sans',Calibri,Arial,sans-serif;overflow:hidden;">
    <div style="padding:8px 10px;font-size:12px;color:#444;border-bottom:1px solid #c8d6f0;">
        <div style="margin-bottom:2px;"><b style="color:#2962ff;">To:</b> {em['to']}</div>
        <div style="margin-bottom:2px;"><b style="color:#2962ff;">CC:</b> {em['cc']}</div>
        <div><b style="color:#2962ff;">Subject:</b> {em['subject']}</div>
    </div>
    <div style="padding:8px 10px;position:relative;">
        <div id="emailBody">{body}</div>
        <button onclick="copyEmail()" id="copyBtn" style="
            position:absolute;top:6px;right:6px;background:#2962ff;color:white;
            border:none;border-radius:4px;padding:3px 10px;font-size:11px;cursor:pointer;">
            Copy</button>
    </div>
</div>
<script>
function copyEmail() {{
    const body = document.getElementById('emailBody').innerHTML;
    const blob = new Blob([body], {{type: 'text/html'}});
    navigator.clipboard.write([new ClipboardItem({{'text/html': blob}})]).then(() => {{
        document.getElementById('copyBtn').textContent = 'Copied';
        setTimeout(() => {{ document.getElementById('copyBtn').textContent = 'Copy'; }}, 2000);
    }}).catch(() => {{
        const range = document.createRange();
        range.selectNodeContents(document.getElementById('emailBody'));
        const sel = window.getSelection();
        sel.removeAllRanges(); sel.addRange(range);
        document.getElementById('copyBtn').textContent = 'Selected — Ctrl+C';
        setTimeout(() => {{ document.getElementById('copyBtn').textContent = 'Copy'; }}, 2000);
    }});
}}
</script>
""", height=195 + body.count('<tr>') * 30)


# ─────────────────────────────────────────────
# MAIN RENDER
# ─────────────────────────────────────────────

def render_event_app(df):
    """Entry point. `df` is the FULL dataframe, not the filtered view."""
    init_state()
    st.markdown(EVENT_CSS, unsafe_allow_html=True)

    if st.session_state.ev_editing or (not st.session_state.ev_events):
        st.markdown("""
        <div class="app-header"><h1>Event Management</h1></div>
        """, unsafe_allow_html=True)
        if not st.session_state.ev_events and not st.session_state.ev_editing:
            st.caption("Paste a SKU list and this page will tell you what to send, "
                       "what to pull back, and what is stuck.")
        render_event_form(df)
        return

    event = _active_event()
    if event is None:
        st.session_state.ev_active_id = st.session_state.ev_events[0]["id"]
        st.rerun()

    lines = ev.analyse_event(event, df)
    brief = ev.build_brief(event, lines)

    venue_label = (f"{event['venue_code']} ({STORE_CODES.get(event['venue_code'], {}).get('name', '')})"
                   if event["venue_type"] == "store" else f"Block '{event['block_name']}'")

    st.markdown(f"""
    <div class="app-header">
        <h1>{event['name']}</h1>
        <span class="stats">
            {venue_label} &nbsp;|&nbsp; Event {event['event_date']} &nbsp;|&nbsp;
            Ready by {ev.ready_by_date(event).strftime('%d %b %Y')} &nbsp;|&nbsp;
            {brief['total']} SKUs (${brief['value']:,.0f})
        </span>
    </div>
    """, unsafe_allow_html=True)

    col_left, col_right = st.columns([3, 2])

    # ═══ LEFT: brief + status table ═══
    with col_left:
        cls = URGENCY_CLASS.get(brief["urgency"], "ev-ontrack")
        bullets = "".join(f"<li>{a}</li>" for a in brief["actions"])
        st.markdown(f"""
        <div class="ev-brief {cls}">
            <h4>{brief['urgency']} — {brief['headline']}</h4>
            <ul>{bullets}</ul>
        </div>
        """, unsafe_allow_html=True)

        table = ev.lines_to_dataframe(lines)
        if len(table):
            st.dataframe(
                table,
                use_container_width=True, hide_index=True, height=430,
                column_config={
                    "FRP": st.column_config.NumberColumn("FRP", format="$%d"),
                    "FREE_N71": st.column_config.NumberColumn("Free N71", format="%d"),
                    "TRANSIT_N71": st.column_config.NumberColumn("Transit", format="%d"),
                },
                key="ev_table",
            )
            buf = io.BytesIO()
            table.to_excel(buf, index=False, engine="openpyxl")
            st.download_button(
                "Download plan",
                data=buf.getvalue(),
                file_name=f"event_{event['name'].replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="ev_dl_plan",
            )

    # ═══ RIGHT: actions ═══
    with col_right:
        st.markdown("**Actions**")

        if event["venue_type"] == "store":
            route = st.radio(
                "Recovery route", ["SR", "PR"],
                index=0 if st.session_state.ev_route == "SR" else 1,
                format_func=lambda r: ("Pull to N71 first (SR)" if r == "SR"
                                       else "Store to store (PR)"),
                horizontal=True, label_visibility="collapsed",
            )
            if route != st.session_state.ev_route:
                st.session_state.ev_route = route
                st.session_state.ev_results = {}
                st.rerun()
        else:
            route = "SR"

        actions = ev.plan_actions(event, lines, route=route)

        if not actions:
            st.markdown('<div class="ev-empty">Nothing to generate — every SKU is '
                        'either already at the venue or waiting on stock.</div>',
                        unsafe_allow_html=True)

        for i, action in enumerate(actions):
            st.markdown(f"""
            <div class="ev-action">
                <b>{action['label']}</b><br>
                <span style="color:#666;">{action['detail']}</span>
                <span class="cmd">{action['command']}</span>
            </div>
            """, unsafe_allow_html=True)

            key = f"{action['kind']}::{action['label']}"
            if st.button(f"Generate {action['kind']}", key=f"ev_gen_{i}",
                         use_container_width=True):
                st.session_state.ev_results[key] = ev.run_action(action, df)
                st.rerun()

            result = st.session_state.ev_results.get(key)
            if result:
                if result["ok"]:
                    st.success(result["summary"])
                    for w in result["warnings"]:
                        st.warning(w)
                    if result["csv"]:
                        st.download_button(
                            f"Download {action['kind']} CSV",
                            data=result["csv"], file_name=result["filename"],
                            mime="text/csv", use_container_width=True,
                            key=f"ev_dl_{i}",
                        )
                    for em in result["emails"]:
                        render_email_card(em)
                else:
                    for err in result["errors"]:
                        st.error(err)
