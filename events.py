# -*- coding: utf-8 -*-
"""
events.py — Event Management engine
===================================
Pure Python. No Streamlit, no AI, no document formats of its own.

An "event" is a named SKU list with a date and a venue. The venue is either
a store code (goods ship N71 -> store, an OMS) or a block (goods ship
N71 -> N65 under a custom order name, a Block).

This module works out, for each SKU, whether it is ready to send, on its way,
sitting in the wrong place, or a problem. It then builds the *command string*
for the action needed and hands it to stores.py, which owns every CSV format
and the store-notification emails. That delegation is deliberate: the
Indonesia hub rule, the warning text and the email templates exist once, in
stores.py, and this module inherits fixes to them for free.

Readiness deadline: everything must be sendable READY_LEAD_DAYS before the
event date.
"""

import re
import json
import uuid
from datetime import datetime, date, timedelta

import pandas as pd

from stores import (
    STORE_CODES, store_flag,
    parse_oms_request, generate_oms_csv,
    parse_sr_request, generate_sr_csv, generate_sr_email,
    parse_pr_request, generate_pr_csv, generate_pr_email,
    parse_block_request, generate_block_csv,
)

WAREHOUSE = "N71"
BLOCK_LOCATION = "N65"
READY_LEAD_DAYS = 7

# Locations that are not real selling stores and should never be proposed as
# an SR source for an event.
NON_SOURCE_LOCATIONS = {"N71", "N65", "N7X", "SG11", "THW", "DEC", "LOG",
                        "P9J", "SCL", "JWC", "V99", "NF8", "N49"}

# ─────────────────────────────────────────────
# STATUSES
# ─────────────────────────────────────────────
# Ordered worst-first. This ordering drives the brief and the sort in the UI.

STATUS_BLOCKED   = "BLOCKED"     # under retrieval — must not ship
STATUS_MISSING   = "MISSING"     # SKU not present anywhere in the file
STATUS_NOSTOCK   = "NO STOCK"    # in the file, but zero units anywhere
STATUS_ELSEWHERE = "ELSEWHERE"   # units exist, but at the wrong location
STATUS_COMMITTED = "COMMITTED"   # at N71 but picking/reserved against something else
STATUS_INBOUND   = "INBOUND"     # in transit to N71
STATUS_READY     = "READY"       # free at N71, send it
STATUS_AT_VENUE  = "AT VENUE"    # already at the venue store, nothing to do

STATUS_ORDER = [
    STATUS_BLOCKED, STATUS_MISSING, STATUS_NOSTOCK, STATUS_ELSEWHERE,
    STATUS_COMMITTED, STATUS_INBOUND, STATUS_READY, STATUS_AT_VENUE,
]

# Statuses that need the planner to do something before the deadline.
ACTIONABLE = {STATUS_BLOCKED, STATUS_MISSING, STATUS_NOSTOCK,
              STATUS_ELSEWHERE, STATUS_COMMITTED, STATUS_READY}

STATUS_EMOJI = {
    STATUS_BLOCKED: "🚫", STATUS_MISSING: "❓", STATUS_NOSTOCK: "❌",
    STATUS_ELSEWHERE: "🔄", STATUS_COMMITTED: "🔒", STATUS_INBOUND: "🚚",
    STATUS_READY: "✅", STATUS_AT_VENUE: "🏬",
}


# ─────────────────────────────────────────────
# SKU LIST PARSING
# ─────────────────────────────────────────────

def parse_sku_list(text, df):
    """Parse a pasted SKU list.

    Accepts anything a planner is likely to paste: one per line, comma
    separated, space separated, tab separated, or an Excel column paste.
    Case-insensitive, order-preserving, de-duplicated.

    Returns (known, unknown) — both lists of uppercase strings.
    """
    if not text or not str(text).strip():
        return [], []

    tokens = [t.strip().upper() for t in re.split(r'[\s,;]+', str(text)) if t.strip()]

    known_skus = set(df['SKU'].astype(str).str.upper().unique())
    store_codes = set(STORE_CODES.keys())

    known, unknown, seen = [], [], set()
    for t in tokens:
        if t in seen:
            continue
        seen.add(t)
        if t in store_codes:      # planner pasted a store code by accident
            continue
        if t in known_skus:
            known.append(t)
        else:
            unknown.append(t)
    return known, unknown


# ─────────────────────────────────────────────
# EVENT MODEL
# ─────────────────────────────────────────────

def new_event(name, event_date, venue_type, venue_code="", block_name="", skus=None,
              end_date=None):
    """Create an event dict.

    venue_type: 'store' -> venue_code is a store code (OMS destination)
                'block' -> block_name is the ORDERNAME used by the Block flow
    event_date: start date — datetime.date or 'YYYY-MM-DD'
    end_date:   optional last day. The key stays "event_date" for the start so
                events saved before end dates existed still load.

    Deadlines run off the START date: stock has to be there for day one.
    """
    if isinstance(event_date, str):
        event_date = datetime.strptime(event_date, "%Y-%m-%d").date()
    if isinstance(end_date, str) and end_date:
        end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
    return {
        "id": f"evt_{uuid.uuid4().hex[:8]}",
        "name": (name or "").strip(),
        "event_date": event_date.isoformat(),
        "end_date": end_date.isoformat() if end_date else "",
        "venue_type": venue_type,
        "venue_code": (venue_code or "").upper().strip(),
        "block_name": (block_name or "").strip(),
        "skus": list(skus or []),
        "notes_by_sku": {},      # sku -> planner's own note
        "route_by_sku": {},      # sku -> "SR" or "PR" override for recovery
        "created": datetime.now().isoformat(timespec="seconds"),
        "notes": "",
    }


def validate_event(event):
    """Return a list of problems with an event definition. Empty list = valid."""
    problems = []
    if not event.get("name", "").strip():
        problems.append("Event needs a name.")
    if event.get("venue_type") == "store":
        code = event.get("venue_code", "").upper()
        if not code:
            problems.append("Pick a venue store.")
        elif code not in STORE_CODES:
            problems.append(f"'{code}' is not a known store code.")
        elif code == WAREHOUSE:
            problems.append("N71 is the warehouse, not a venue.")
    elif event.get("venue_type") == "block":
        bn = event.get("block_name", "").strip()
        if not bn:
            problems.append("Block needs an order name.")
        elif re.search(r'\bas\b', bn, re.IGNORECASE):
            problems.append("Block name cannot contain the word 'as' — it breaks the block command.")
        elif "," in bn:
            problems.append("Block name cannot contain a comma — it breaks the CSV.")
    else:
        problems.append("Venue must be a store or a block.")
    end = event.get("end_date")
    if end:
        try:
            if datetime.strptime(end, "%Y-%m-%d").date() < \
               datetime.strptime(event["event_date"], "%Y-%m-%d").date():
                problems.append("End date is before the start date.")
        except (ValueError, KeyError):
            problems.append("End date is not a valid date.")
    if not event.get("skus"):
        problems.append("Event has no SKUs.")
    return problems


def date_range_label(event):
    """Compact date label: '28 Aug', '28–30 Aug', or '28 Aug – 2 Sep'."""
    try:
        start = datetime.strptime(event["event_date"], "%Y-%m-%d").date()
    except (ValueError, KeyError):
        return event.get("event_date", "?")
    end_raw = event.get("end_date")
    if not end_raw or end_raw == event["event_date"]:
        return start.strftime("%d %b")
    try:
        end = datetime.strptime(end_raw, "%Y-%m-%d").date()
    except ValueError:
        return start.strftime("%d %b")
    if (start.year, start.month) == (end.year, end.month):
        return f"{start.strftime('%d')}–{end.strftime('%d %b')}"
    return f"{start.strftime('%d %b')} – {end.strftime('%d %b')}"


def event_flag(event):
    """Flag of the venue's country. Blocks sit at N65, which is Singapore."""
    if event.get("venue_type") == "store" and event.get("venue_code"):
        return store_flag(event["venue_code"])
    return store_flag(BLOCK_LOCATION)


def ready_by_date(event):
    """The date everything must be ready to send by."""
    ed = datetime.strptime(event["event_date"], "%Y-%m-%d").date()
    return ed - timedelta(days=READY_LEAD_DAYS)


def event_urgency(event, today=None):
    """Return (days_until_ready_by, label). Negative days = past the deadline."""
    today = today or date.today()
    days = (ready_by_date(event) - today).days
    if days < 0:
        label = "OVERDUE"
    elif days <= 2:
        label = "CRITICAL"
    elif days <= 6:
        label = "URGENT"
    else:
        label = "ON TRACK"
    return days, label


# ─────────────────────────────────────────────
# ANALYSIS
# ─────────────────────────────────────────────

def _free_units(row):
    """Units genuinely available: on hand minus what is already spoken for."""
    on_hand = float(row.get('STOCK_ON_HAND', 0) or 0)
    picking = float(row.get('PICKING', 0) or 0)
    reserved = float(row.get('RESERVATION', 0) or 0)
    return max(0.0, on_hand - picking - reserved)


def analyse_event(event, df):
    """Work out the state of every SKU in the event.

    Returns a list of line dicts, one per SKU, each with:
        sku, description, universe, segment, frp, status, free_at_n71,
        transit_to_n71, at_venue, sources (list), note
    """
    if df is None or len(df) == 0:
        return []

    venue = event.get("venue_code", "").upper() if event.get("venue_type") == "store" else None

    # Precompute uppercase columns ONCE — the whole file is ~15k rows and this
    # runs on every rerun.
    work = df.copy()
    work['_SKU_U'] = work['SKU'].astype(str).str.upper()
    work['_LOC_U'] = work['LOCATION'].astype(str).str.upper()
    for c in ['STOCK_ON_HAND', 'TRANSIT', 'PICKING', 'RESERVATION', 'VALIDATED_FRP']:
        if c in work.columns:
            work[c] = pd.to_numeric(work[c], errors='coerce').fillna(0)
        else:
            work[c] = 0

    lines = []
    for sku in event.get("skus", []):
        rows = work[work['_SKU_U'] == sku]

        if len(rows) == 0:
            lines.append({
                "sku": sku, "description": "", "universe": "", "segment": "",
                "frp": 0.0, "status": STATUS_MISSING, "free_at_n71": 0,
                "transit_to_n71": 0, "at_venue": 0, "sources": [],
                "note": "Not in this week's file at all.",
                "user_note": event.get("notes_by_sku", {}).get(sku, ""),
                "route": event.get("route_by_sku", {}).get(sku, "SR"),
            })
            continue

        first = rows.iloc[0]
        desc = str(first.get('SKU_DESCRIPTION', '') or '')
        universe = str(first.get('UNIVERSE', '') or '')
        segment = str(first.get('SEGMENT', '') or '')
        frp = float(first.get('VALIDATED_FRP', 0) or 0)
        status_text = str(first.get('LOGISTIC_STATUS', '') or '').upper()

        n71_rows = rows[rows['_LOC_U'] == WAREHOUSE]
        free_n71 = int(sum(_free_units(r) for _, r in n71_rows.iterrows()))
        transit_n71 = int(n71_rows['TRANSIT'].sum()) if len(n71_rows) else 0
        on_hand_n71 = int(n71_rows['STOCK_ON_HAND'].sum()) if len(n71_rows) else 0

        at_venue = 0
        if venue:
            v_rows = rows[rows['_LOC_U'] == venue]
            at_venue = int(sum(_free_units(r) for _, r in v_rows.iterrows()))

        # Candidate source stores for an SR — real stores, holding free units,
        # that are not the warehouse or the venue itself.
        sources = []
        for _, r in rows.iterrows():
            loc = r['_LOC_U']
            if loc in NON_SOURCE_LOCATIONS or loc == venue:
                continue
            free = int(_free_units(r))
            if free > 0:
                info = STORE_CODES.get(loc, {})
                sources.append({
                    "code": loc,
                    "name": info.get("name", loc),
                    "country": info.get("country", str(r.get('COUNTRY', '')) or ''),
                    "free": free,
                    "known": loc in STORE_CODES,
                })
        # Prefer Singapore (a same-country pull is fastest), then most stock.
        sources.sort(key=lambda s: (s["country"] != "SINGAPORE", -s["free"], s["code"]))

        # ── Decide the status ──
        note = ""
        if 'RETRIEVAL' in status_text:
            status = STATUS_BLOCKED
            note = "Under retrieval — must not ship."
        elif at_venue > 0:
            status = STATUS_AT_VENUE
            note = f"{at_venue} already at {venue}."
        elif free_n71 > 0:
            status = STATUS_READY
            note = f"{free_n71} free at N71."
        elif on_hand_n71 > 0:
            status = STATUS_COMMITTED
            note = f"{on_hand_n71} at N71 but all picking/reserved."
        elif transit_n71 > 0:
            status = STATUS_INBOUND
            note = f"{transit_n71} in transit to N71 — no ETA in this file."
        elif sources:
            best = sources[0]
            status = STATUS_ELSEWHERE
            note = f"{best['free']} at {best['code']} ({best['name']})."
        else:
            status = STATUS_NOSTOCK
            note = "In the file, but no free units anywhere."

        if 'PRODUCTION STOPPED' in status_text and status not in (STATUS_BLOCKED,):
            note += " Production stopped — no replacement available."

        lines.append({
            "sku": sku, "description": desc, "universe": universe,
            "segment": segment, "frp": frp, "status": status,
            "free_at_n71": free_n71, "transit_to_n71": transit_n71,
            "at_venue": at_venue, "sources": sources, "note": note,
            "user_note": event.get("notes_by_sku", {}).get(sku, ""),
            "route": event.get("route_by_sku", {}).get(sku, "SR"),
        })

    lines.sort(key=lambda l: (STATUS_ORDER.index(l["status"]), -l["frp"]))
    return lines


# ─────────────────────────────────────────────
# BRIEF
# ─────────────────────────────────────────────

def build_brief(event, lines, today=None):
    """Build the daily/on-upload brief for one event.

    Returns a dict — the UI decides how to render it. No formatting decisions
    beyond the sentence text itself.
    """
    today = today or date.today()
    days, urgency = event_urgency(event, today)
    counts = {s: 0 for s in STATUS_ORDER}
    for l in lines:
        counts[l["status"]] += 1

    venue_label = (event["venue_code"] if event.get("venue_type") == "store"
                   else f"Block '{event.get('block_name', '')}'")

    total = len(lines)
    settled = counts[STATUS_READY] + counts[STATUS_AT_VENUE]

    if days < 0:
        deadline_line = f"Ready-by date passed {abs(days)} day(s) ago."
    elif days == 0:
        deadline_line = "Everything must be ready to send today."
    else:
        deadline_line = f"{days} day(s) until the ready-by date ({ready_by_date(event).strftime('%d %b %Y')})."

    headline = (f"{settled}/{total} settled for {event['name']} → {venue_label} "
                f"({date_range_label(event)}). {deadline_line}")

    actions = []
    if counts[STATUS_BLOCKED]:
        actions.append(f"{counts[STATUS_BLOCKED]} under retrieval — pull from the event list or replace.")
    if counts[STATUS_MISSING]:
        actions.append(f"{counts[STATUS_MISSING]} not found in this file — check the SKU or the extract.")
    if counts[STATUS_NOSTOCK]:
        actions.append(f"{counts[STATUS_NOSTOCK]} with no free units anywhere — escalate.")
    if counts[STATUS_ELSEWHERE]:
        actions.append(f"{counts[STATUS_ELSEWHERE]} sitting at other stores — raise SRs now so they land before the deadline.")
    if counts[STATUS_COMMITTED]:
        actions.append(f"{counts[STATUS_COMMITTED]} at N71 but already picking/reserved — confirm they are free.")
    if counts[STATUS_INBOUND]:
        actions.append(f"{counts[STATUS_INBOUND]} in transit to N71 — hold, and re-check on next week's upload.")
    if counts[STATUS_READY]:
        actions.append(f"{counts[STATUS_READY]} free at N71 — ready to send to {venue_label}.")
    if not actions:
        actions.append("Nothing outstanding.")

    return {
        "headline": headline,
        "urgency": urgency,
        "days_to_ready": days,
        "counts": counts,
        "actions": actions,
        "total": total,
        "settled": settled,
        "value": sum(l["frp"] for l in lines),
    }


# ─────────────────────────────────────────────
# ACTION PLANNING
# ─────────────────────────────────────────────
# Every action is expressed as a command string for stores.py. Nothing here
# builds a CSV row — that stays in one place.

def plan_actions(event, lines):
    """Turn the analysis into concrete, runnable commands.

    Recovery route is per SKU (`event["route_by_sku"]`, default "SR"):
      SR — pull to N71 first, the documented process
      PR — ship store-to-store directly, faster, only valid for a store venue
    Lines are grouped by (source store, route), so one event can do both.

    Returns a list of dicts: {kind, label, command, skus, detail}
    """
    actions = []
    is_store_venue = event.get("venue_type") == "store"

    # ── Send what is ready ──
    ready = [l["sku"] for l in lines if l["status"] == STATUS_READY]
    if ready:
        if not is_store_venue:
            actions.append({
                "kind": "BLOCK", "doc": "Block",
                "label": f"Block {len(ready)} SKU(s) → N65 as '{event['block_name']}'",
                "command": f"block {' '.join(ready)} as {event['block_name']}",
                "skus": ready,
                "detail": f"N71 → {BLOCK_LOCATION}",
            })
        else:
            dest = event["venue_code"]
            actions.append({
                "kind": "OMS", "doc": "OMS",
                "label": f"OMS {len(ready)} SKU(s) → {dest}",
                "command": f"oms to {dest} for {' '.join(ready)}",
                "skus": ready,
                "detail": f"N71 → {dest}",
            })

    # ── Recover what is elsewhere, grouped by (source store, route) ──
    grouped = {}
    for l in lines:
        if l["status"] != STATUS_ELSEWHERE or not l["sources"]:
            continue
        src = l["sources"][0]["code"]
        # PR is only meaningful when there is a store to ship to.
        route = l.get("route", "SR")
        if route == "PR" and not is_store_venue:
            route = "SR"
        grouped.setdefault((src, route), []).append(l["sku"])

    for (src, route), skus in sorted(grouped.items()):
        name = STORE_CODES.get(src, {}).get("name", src)
        if route == "PR":
            dest = event["venue_code"]
            actions.append({
                "kind": "PR", "doc": "PR",
                "label": f"PR {len(skus)} SKU(s) {src} → {dest}",
                "command": f"pr {dest} from {src} for {' '.join(skus)}",
                "skus": skus,
                "detail": f"{src} ({name}) → {dest}, direct store transfer",
            })
        elif is_store_venue:
            # One file, both legs: src → N71 (SR), then N71 → venue (OMS).
            dest = event["venue_code"]
            actions.append({
                "kind": "SR", "doc": "SR + OMS",
                "label": f"SR + OMS {len(skus)} SKU(s) {src} → {dest}",
                "command": f"sr from {src} for {' '.join(skus)} and send to {dest}",
                "skus": skus,
                "detail": f"{src} ({name}) → N71 → {dest}, both legs in one file",
            })
        else:
            # Block venue: src → N71 (SR), then N71 → N65 under the block name.
            actions.append({
                "kind": "SR", "doc": "SR + Block",
                "label": f"SR + Block {len(skus)} SKU(s) from {src}",
                "command": (f"sr from {src} for {' '.join(skus)} "
                            f"and block as {event['block_name']}"),
                "skus": skus,
                "detail": f"{src} ({name}) → N71 → {BLOCK_LOCATION}, both legs in one file",
            })

    return actions


def run_action(action, df, event_name=None):
    """Execute one planned action through the stores.py engine.

    event_name, when given, is threaded into the notification emails so the
    store can see which event the request belongs to.

    Returns {ok, summary, warnings, errors, csv, filename, emails}
    """
    kind = action["kind"]
    cmd = action["command"]
    doc = action.get("doc", kind)

    if kind == "OMS":
        res = parse_oms_request(cmd, df)
        csv = generate_oms_csv(res["orders"]) if res["success"] else None
        emails = []
    elif kind == "SR":
        res = parse_sr_request(cmd, df)
        csv = generate_sr_csv(res["orders"]) if res["success"] else None
        emails = generate_sr_email(res["orders"], df, event_name) if res["success"] else []
    elif kind == "PR":
        res = parse_pr_request(cmd, df)
        csv = generate_pr_csv(res["orders"]) if res["success"] else None
        emails = generate_pr_email(res["orders"], df, event_name) if res["success"] else []
    elif kind == "BLOCK":
        res = parse_block_request(cmd, df)
        csv = generate_block_csv(res["orders"]) if res["success"] else None
        emails = []
    else:
        return {"ok": False, "summary": "", "warnings": [],
                "errors": [f"Unknown action type {kind}"], "csv": None,
                "filename": "", "emails": []}

    return {
        "ok": bool(res.get("success")),
        "summary": res.get("summary", ""),
        "warnings": res.get("warnings", []),
        "errors": res.get("errors", []),
        "csv": csv,
        "filename": f"{doc.replace(' + ', '_').replace(' ', '')}_"
                    f"{datetime.now().strftime('%d%m%y')}.csv",
        "emails": emails,
    }


# ─────────────────────────────────────────────
# EXPORT / IMPORT
# ─────────────────────────────────────────────
# Events live in session state for now. Export gives the planner a file they
# own, so nothing is lost on refresh, without committing to server-side
# storage before that decision is made.

def events_to_json(events):
    return json.dumps(events, indent=2)


def events_from_json(text):
    data = json.loads(text)
    if isinstance(data, dict):
        data = [data]
    out = []
    for e in data:
        if not isinstance(e, dict) or "skus" not in e:
            continue
        e.setdefault("id", f"evt_{uuid.uuid4().hex[:8]}")
        e.setdefault("name", "Untitled event")
        e.setdefault("venue_type", "store")
        e.setdefault("venue_code", "")
        e.setdefault("block_name", "")
        e.setdefault("notes", "")
        e.setdefault("notes_by_sku", {})
        e.setdefault("route_by_sku", {})
        e.setdefault("end_date", "")
        out.append(e)
    return out


ROUTE_CHOICES = ["SR", "PR"]


def lines_to_dataframe(lines):
    """Flatten the analysis for the editable plan table.

    Column order matters: the two editable columns (ROUTE, NOTES) sit at the
    right so the read-only status columns stay stable while typing.
    """
    if not lines:
        return pd.DataFrame(columns=["STATUS", "SKU", "DESCRIPTION", "SEGMENT",
                                     "FRP", "FREE_N71", "TRANSIT_N71",
                                     "BEST_SOURCE", "DETAIL", "ROUTE", "NOTES"])
    return pd.DataFrame([{
        "STATUS": f"{STATUS_EMOJI.get(l['status'], '')} {l['status']}",
        "SKU": l["sku"],
        "DESCRIPTION": l["description"],
        "SEGMENT": l["segment"],
        "FRP": l["frp"],
        "FREE_N71": l["free_at_n71"],
        "TRANSIT_N71": l["transit_to_n71"],
        "BEST_SOURCE": l["sources"][0]["code"] if l["sources"] else "",
        "DETAIL": l["note"],
        "ROUTE": l.get("route", "SR"),
        "NOTES": l.get("user_note", ""),
    } for l in lines])


# ─────────────────────────────────────────────
# MUTATIONS
# ─────────────────────────────────────────────
# The plan table is editable. These apply the edits back onto the event dict,
# which is what gets serialised into the events file — so notes, route choices
# and removals all survive a save/load round trip.

def remove_skus(event, skus):
    """Drop SKUs from the event, along with their notes and route overrides."""
    drop = {s.upper() for s in skus}
    event["skus"] = [s for s in event["skus"] if s not in drop]
    for s in drop:
        event.get("notes_by_sku", {}).pop(s, None)
        event.get("route_by_sku", {}).pop(s, None)
    return event


def add_skus(event, skus, df):
    """Append SKUs to the event. Returns (added, rejected)."""
    known = set(df['SKU'].astype(str).str.upper().unique())
    added, rejected = [], []
    for s in skus:
        s = str(s).strip().upper()
        if not s or s in event["skus"]:
            continue
        if s in known:
            event["skus"].append(s)
            added.append(s)
        else:
            rejected.append(s)
    return added, rejected


def set_note(event, sku, note):
    event.setdefault("notes_by_sku", {})
    note = (note or "").strip()
    if note:
        event["notes_by_sku"][sku.upper()] = note
    else:
        event["notes_by_sku"].pop(sku.upper(), None)
    return event


def set_route(event, sku, route):
    event.setdefault("route_by_sku", {})
    route = (route or "SR").upper()
    if route not in ROUTE_CHOICES:
        route = "SR"
    if route == "SR":
        event["route_by_sku"].pop(sku.upper(), None)   # SR is the default
    else:
        event["route_by_sku"][sku.upper()] = route
    return event


def apply_table_edits(event, editor_state, display_skus, df):
    """Apply st.data_editor changes onto the event.

    editor_state is the dict Streamlit puts in session_state for a keyed
    data_editor: {"edited_rows": {row: {col: val}}, "deleted_rows": [row],
    "added_rows": [{col: val}]}. Row numbers are positions in the frame that
    was handed to the editor, so `display_skus` maps them back to SKUs.

    Returns (changed: bool, messages: list[str]).
    """
    if not editor_state:
        return False, []

    changed, messages = False, []

    # ── Deletions ──
    deleted = editor_state.get("deleted_rows") or []
    drop = [display_skus[i] for i in deleted if 0 <= i < len(display_skus)]
    if drop:
        remove_skus(event, drop)
        changed = True
        messages.append(f"Removed {', '.join(drop)}.")

    # ── Cell edits ──
    for row, edits in (editor_state.get("edited_rows") or {}).items():
        try:
            idx = int(row)
        except (TypeError, ValueError):
            continue
        if not (0 <= idx < len(display_skus)):
            continue
        sku = display_skus[idx]
        if sku in drop:
            continue
        if "NOTES" in edits:
            set_note(event, sku, edits["NOTES"])
            changed = True
        if "ROUTE" in edits:
            set_route(event, sku, edits["ROUTE"])
            changed = True

    # ── Added rows ──
    new_skus = [r.get("SKU") for r in (editor_state.get("added_rows") or []) if r.get("SKU")]
    if new_skus:
        added, rejected = add_skus(event, new_skus, df)
        if added:
            changed = True
            messages.append(f"Added {', '.join(added)}.")
        if rejected:
            messages.append(f"Not in this file, ignored: {', '.join(rejected)}.")

    return changed, messages
