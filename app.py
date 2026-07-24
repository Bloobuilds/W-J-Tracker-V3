# -*- coding: utf-8 -*-
"""
HJW Tracker v2
===============
Stock report + AI chat (stock questions only) + instant OMS generation (Python).
"""

import streamlit as st
import pandas as pd
import os
import io
import re
from datetime import datetime
from stores import (STORE_CODES, is_oms_request, parse_oms_request, generate_oms_csv,
                    is_sr_request, parse_sr_request, generate_sr_csv, generate_sr_email,
                    is_pr_request, parse_pr_request, generate_pr_csv, generate_pr_email,
                    is_block_request, parse_block_request, generate_block_csv)
from event_app import render_event_app, render_event_sidebar

# Apps available in the switcher. Only the selected one renders — Streamlit
# executes every branch it is given, so this must stay a dispatch, not tabs.
APPS = ["Stock Report", "Event Management"]

# ─────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="HJW Tracker",
    page_icon=":gem:",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────
# STYLING
# ─────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap');
    .stApp { font-family: 'DM Sans', sans-serif; }
    .block-container { padding-top: 1rem; }

    .chat-user {
        background: #e8ecf1; border-left: 3px solid #1a1a2e;
        padding: 0.5rem 0.8rem; border-radius: 8px;
        margin-bottom: 0.35rem; font-size: 0.83rem; line-height: 1.45;
    }
    .chat-ai {
        background: #f0f5ef; border-left: 3px solid #1a7a5a;
        padding: 0.5rem 0.8rem; border-radius: 8px;
        margin-bottom: 0.35rem; font-size: 0.83rem; line-height: 1.45;
    }
    .chat-oms {
        background: #f5f0ff; border-left: 3px solid #6b3fa0;
        padding: 0.5rem 0.8rem; border-radius: 8px;
        margin-bottom: 0.35rem; font-size: 0.83rem; line-height: 1.45;
    }
    .chat-warn {
        background: #fff8e6; border-left: 3px solid #e8a820;
        padding: 0.5rem 0.8rem; border-radius: 8px;
        margin-bottom: 0.35rem; font-size: 0.83rem; line-height: 1.45;
    }
    .chat-err {
        background: #fef0f0; border-left: 3px solid #d32f2f;
        padding: 0.5rem 0.8rem; border-radius: 8px;
        margin-bottom: 0.35rem; font-size: 0.83rem; line-height: 1.45;
    }
    .chat-email {
        background: #f0f4ff; border-left: 3px solid #2962ff;
        padding: 0.6rem 0.8rem; border-radius: 8px;
        margin-bottom: 0.35rem; font-size: 0.82rem; line-height: 1.5;
    }
    .chat-email .email-field {
        font-size: 0.78rem; color: #444; margin-bottom: 2px;
    }
    .chat-email .email-field b { color: #2962ff; }
    .chat-email .email-body {
        margin-top: 6px; padding-top: 6px;
        border-top: 1px solid #c8d6f0;
    }

    .filter-banner {
        display: flex; align-items: center; justify-content: space-between;
        background: #fff8e6; border: 1px solid #e8d48b;
        border-radius: 8px; padding: 0.45rem 0.8rem;
        margin-bottom: 0.5rem; font-size: 0.82rem;
    }
    .filter-banner .label { color: #6b5a1e; font-weight: 600; }
    .filter-banner .stats { color: #888; font-size: 0.78rem; }

    .app-header {
        display: flex; align-items: baseline; gap: 0.8rem;
        margin-bottom: 0.6rem; padding-bottom: 0.4rem;
        border-bottom: 2px solid #1a1a2e;
    }
    .app-header h1 { margin: 0; font-size: 1.3rem; color: #1a1a2e; }
    .app-header .stats { font-size: 0.78rem; color: #666; }

    /* Hide Streamlit running/loading indicators */
    div[data-testid="stStatusWidget"] { display: none !important; }
    .stDeployButton { display: none !important; }
    #MainMenu { display: none !important; }
    header[data-testid="stHeader"] { background: transparent; }

    .thinking-bubble {
        background: #f0f5ef; border-left: 3px solid #1a7a5a;
        padding: 0.5rem 0.8rem; border-radius: 8px;
        margin-bottom: 0.35rem; font-size: 0.83rem;
        color: #888; font-style: italic;
    }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# COLUMN DEFINITIONS
# ─────────────────────────────────────────────

PRIMARY_COLS = [
    'SKU', 'SKU_DESCRIPTION', 'SKU_GROUP', 'UNIVERSE', 'COUNTRY', 'LOCATION',
    'STOCK_ON_HAND', 'TRANSIT', 'PICKING', 'RESERVATION',
    'AUTOREP_MAX', 'CLIENT_ORDER_STOCK', 'PENDING_ORDER_DETAIL',
]

EXTRA_COLS = [
    'SEGMENT', 'SUB_DEPARTMENT', 'FAMILY', 'THEME', 'SUB_THEME',
    'GENDER', 'LOGISTIC_STATUS', 'VALIDATED_FRP', 'SKU_LONG_CODE', 'SIZE',
    'STOCK_VALUE', 'TRANSIT_VALUE', 'TOTAL_UNITS',
]


# ─────────────────────────────────────────────
# DATA LOADING
# ─────────────────────────────────────────────

def load_and_process(uploaded_file):
    if uploaded_file is None:
        return None
    df = pd.read_excel(uploaded_file, header=0)
    num_cols = ['VALIDATED_FRP', 'STOCK_ON_HAND', 'TRANSIT', 'PICKING',
                'RESERVATION', 'CLIENT_ORDER_STOCK', 'PENDING_ORDER_DETAIL', 'AUTOREP_MAX']
    for col in num_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    df['STOCK_VALUE'] = df.get('VALIDATED_FRP', 0) * df.get('STOCK_ON_HAND', 0)
    df['TRANSIT_VALUE'] = df.get('VALIDATED_FRP', 0) * df.get('TRANSIT', 0)
    df['TOTAL_UNITS'] = (
        df.get('STOCK_ON_HAND', 0) + df.get('TRANSIT', 0)
        + df.get('PICKING', 0) + df.get('RESERVATION', 0)
    )
    for col in ['UNIVERSE', 'SEGMENT', 'SUB_DEPARTMENT', 'FAMILY', 'THEME', 'SUB_THEME']:
        if col in df.columns:
            df[col] = df[col].fillna('UNKNOWN')
    return df


# ─────────────────────────────────────────────
# SYSTEM PROMPT (stock analysis only — no OMS)
# ─────────────────────────────────────────────

SYSTEM_PROMPT = """You are an inventory analyst for a luxury brand's High Jewelry & Watches (HJW) division in Asia Pacific.

## DATA COLUMNS:
- SKU / SKU_DESCRIPTION / SKU_GROUP: Product identifiers
- UNIVERSE: "FINE JEWELRY" or "WATCHES"
- COUNTRY / LOCATION: Market and store code
- SEGMENT: CORE, PREMIUM, HIGH END, EXCEPTIONAL
- FAMILY: Product type (FINE EARRINGS, FINE RING, WATCHES, etc.)
- THEME / SUB_THEME: Collection (e.g. MONOGRAM FLOWER / COLOR BLOSSOM)
- LOGISTIC_STATUS: "DISTRIBUTION - NIP (CEN)" = active | "PRODUCTION STOPPED (CEN)" = discontinued | "RETRIEVAL (CEN)" = recalled
- VALIDATED_FRP: Retail price
- STOCK_ON_HAND / TRANSIT / PICKING / RESERVATION / AUTOREP_MAX / CLIENT_ORDER_STOCK / PENDING_ORDER_DETAIL
- TOTAL_UNITS: Stock + Transit + Picking + Reservation

## BUSINESS TERMS:
- OMS (Order Management System): Transfer order from N71 warehouse to a store. Used to send stock out.
- SR (Store Reverse): Transfer order from a store BACK to the N71 warehouse in Singapore. Used to pull stock back.
- Rebalance: Moving stock between stores to meet demand. Usually SR from one store to N71, then OMS from N71 to the requesting store.
- N71: The Singapore central warehouse. All stock flows through here.
- BCO: Allocation type for store orders.
- NIP: "New In Production" — active item being distributed.
- FRP: Full Retail Price.

## STORE LOCATIONS:
SINGAPORE: N71 (Warehouse), N74 (Ngee Ann City), NC3 (ION Orchard), NF2 (Marina Bay Sands), NQ6 (Changi T3), NX6 (Changi T1), NM4 (Digital CS)
AUSTRALIA: L08 (Sydney George St), L32 (Sydney Bondi), L12 (Melbourne Collins St), L26 (Melbourne Crown), L30 (Chadstone), L47 (David Jones Melb), L14 (Brisbane), L24 (Perth), L16 (Pacific Fair), L42 (David Jones Syd), L45 (Sydney Airport), L28 (Rocks DFS), AUZ (Ecom), L36 (CS)
INDONESIA: N63 (Plaza Indonesia, Jakarta), N64 (Plaza Senayan, Jakarta), NB6 (Pacific Place, Jakarta), N61 (CTS), NM3 (Ecom)
MALAYSIA: N68 (Pavilion, KL), N69 (KLCC, KL), NF5 (Gardens, KL), NYE (TRX, KL), NM2 (CS)
THAILAND: N79 (Emporium, Bangkok), NAB (Chidlom, Bangkok), NAM (The Place, Bangkok), NG6 (Paragon Women, Bangkok), NYF (Paragon Men, Bangkok), NVJ (ICONSIAM, Bangkok), NX8 (Suvarnabhumi Airport), NVQ (Floresta, Phuket), THW (Warehouse), NM1 (CS)
VIETNAM: NXD (Hanoi), N46 (Ho Chi Minh), NM6 (Ecom)
PHILIPPINES: N02 (Greenbelt, Manila), NN5 (Solaire, Manila), NAD (Cebu), NG8 (Ecom)
INDIA: Y04 (Bangalore), Y11 (Mumbai Jio World), Y03 (New Delhi), Y10 (Ecom)
NEW ZEALAND: X06 (Auckland Queen St), X38 (Auckland Newmarket), X10 (Queenstown), XM1 (CS)
GUAM: N53 (DFS)

## STORE ALIASES (common names):
ION = NC3, MBS / Marina Bay = NF2, Ngee Ann = N74, Plaza Indonesia / PI = N63, Plaza Senayan = N64, Pacific Place = NB6, Pavilion = N68, KLCC = N69, Gardens = NF5, TRX = NYE, Emporium = N79, Chidlom = NAB, ICONSIAM = NVJ, Paragon = NG6, Floresta / Phuket = NVQ, Greenbelt = N02, Solaire = NN5, George St = L08, Bondi = L32, Chadstone = L30, Collins St = L12, Crown = L26

## RESPONSE RULES:
1. Be concise. 2-3 sentences max.
2. DO NOT include any tables. The user sees data in the main table.
3. Brief overview: units, locations, risks.
4. Don't introduce yourself.
5. Use specific numbers with $ and commas.
6. Items with TOTAL_UNITS = 0 are never shown.
7. If asked about a store (e.g. "what is N63"), give the store name, city, and country.
8. If asked about a business term (e.g. "what is SR"), explain it in the context of this business.
9. When PRE-COMPUTED FACTS are provided, use those exact numbers — never recalculate from rows.
10. If RECENT CONVERSATION is provided, use it to resolve follow-ups like "what about Malaysia?" or "only the rings from those".
11. If an ACTIVE FILTER is noted, remember your numbers reflect only that subset.

## TABLE FILTER (REQUIRED):
Every response MUST include a [TABLE_FILTER] block.

[TABLE_FILTER]
column:value,column:value
[/TABLE_FILTER]

Rules:
- Use | for OR: FAMILY:FINE EARRINGS|FINE RING
- Use >0 or =0 for numeric: STOCK_ON_HAND>0
- For general/overview questions: [TABLE_FILTER]ALL[/TABLE_FILTER]
- When asked about a specific store/location: filter to that LOCATION code

Examples:
- "Color Blossom in Singapore" → [TABLE_FILTER]SUB_THEME:COLOR BLOSSOM,COUNTRY:SINGAPORE[/TABLE_FILTER]
- "SKU Q03789" → [TABLE_FILTER]SKU:Q03789[/TABLE_FILTER]
- "Location L08" → [TABLE_FILTER]LOCATION:L08[/TABLE_FILTER]
- "What's at Plaza Indonesia" → [TABLE_FILTER]LOCATION:N63[/TABLE_FILTER]
- "Show everything" → [TABLE_FILTER]ALL[/TABLE_FILTER]
"""


# ─────────────────────────────────────────────
# CONTEXT BUILDER
# ─────────────────────────────────────────────

def extract_relevant_rows(question, df):
    q = question.upper().strip()
    matched = pd.DataFrame()
    store_code_set = set(STORE_CODES.keys())

    for sku in re.findall(r'\b([A-Z0-9][A-Z0-9]{3,9})\b', q):
        if sku in store_code_set:
            continue
        hits = df[df['SKU'].str.upper() == sku]
        if len(hits) > 0:
            matched = pd.concat([matched, hits])

    match_configs = [
        ('COUNTRY', df['COUNTRY'].unique()),
        ('LOCATION', df['LOCATION'].unique()),
        ('THEME', df['THEME'].unique()),
        ('SUB_THEME', df['SUB_THEME'].unique()),
        ('FAMILY', df['FAMILY'].unique()),
        ('SEGMENT', df['SEGMENT'].unique()),
        ('UNIVERSE', ['FINE JEWELRY', 'WATCHES']),
        ('GENDER', ['WOMEN', 'MEN', 'UNISEX']),
    ]
    for col, values in match_configs:
        for val in values:
            val_str = str(val).upper()
            if val_str in q and len(val_str) >= 3:
                hits = df[df[col].str.upper() == val_str]
                matched = pd.concat([matched, hits.head(100)])

    skip = {'WHAT', 'WHERE', 'WHICH', 'SHOW', 'FIND', 'GIVE', 'LIST', 'TELL',
            'HAVE', 'DOES', 'MANY', 'MUCH', 'THAT', 'THIS', 'THEM', 'FROM',
            'WITH', 'ABOUT', 'STOCK', 'ITEMS', 'TOTAL', 'VALUE', 'EXPORT',
            'DOWNLOAD', 'PLEASE', 'COULD', 'WOULD', 'THERE', 'THEIR', 'WANT',
            'NEED', 'LIKE', 'ALSO', 'EACH', 'SOME', 'MORE', 'INTO', 'ZERO',
            'LOCATION', 'COUNTRY', 'STORE', 'STORES', 'SEND', 'SHIP', 'TRANSFER',
            'ORDER', 'CREATE', 'MAKE'}
    for word in [w for w in q.split() if len(w) >= 4 and w not in skip]:
        hits = df[df['SKU_DESCRIPTION'].str.upper().str.contains(word, na=False)]
        if 0 < len(hits) <= 100:
            matched = pd.concat([matched, hits])

    return matched.drop_duplicates() if len(matched) > 0 else matched


def detect_question_intent(question):
    """Detect analytical intent to select the right context rows."""
    q = question.upper()
    intents = set()
    if any(w in q for w in ['DEAD STOCK', 'DEADSTOCK', 'DISCONTINUED', 'PRODUCTION STOPPED', 'STOPPED']):
        intents.add('dead_stock')
    if any(w in q for w in ['EXPENSIVE', 'HIGHEST VALUE', 'TOP VALUE', 'MOST VALUABLE', 'PRICIEST', 'HIGH VALUE']):
        intents.add('high_value')
    if any(w in q for w in ['LOW STOCK', 'LAST UNIT', 'ONLY 1', 'ONE UNIT', 'RUNNING OUT', 'ALMOST OUT', 'REPLENISH']):
        intents.add('low_stock')
    if any(w in q for w in ['TRANSIT', 'INCOMING', 'ON THE WAY', 'ARRIVING']):
        intents.add('transit')
    if any(w in q for w in ['SLOW MOV', 'NOT SELLING', 'SITTING', 'AGING', 'OLD STOCK']):
        intents.add('high_value')  # best proxy we have without sales data
    if any(w in q for w in ['CHEAP', 'LOWEST VALUE', 'LEAST EXPENSIVE']):
        intents.add('low_value')
    return intents


def build_aggregates(filtered_df):
    """Pre-compute exact numbers so the AI never has to do math."""
    lines = ["\nPRE-COMPUTED FACTS (use these exact numbers, do not recalculate):"]

    in_stock = filtered_df[filtered_df['STOCK_ON_HAND'] > 0]
    lines.append(f"- Total stock on hand: {filtered_df['STOCK_ON_HAND'].sum():,.0f} units, value ${filtered_df['STOCK_VALUE'].sum():,.0f}")
    lines.append(f"- Total in transit: {filtered_df['TRANSIT'].sum():,.0f} units (${filtered_df['TRANSIT_VALUE'].sum():,.0f})")
    lines.append(f"- SKUs with stock: {in_stock['SKU'].nunique():,} | Locations with stock: {in_stock['LOCATION'].nunique()}")

    if 'LOGISTIC_STATUS' in filtered_df.columns:
        dead = filtered_df[filtered_df['LOGISTIC_STATUS'].str.contains('STOPPED', case=False, na=False)]
        dead_in_stock = dead[dead['STOCK_ON_HAND'] > 0]
        lines.append(f"- Dead stock (production stopped, units>0): {dead_in_stock['STOCK_ON_HAND'].sum():,.0f} units, value ${dead_in_stock['STOCK_VALUE'].sum():,.0f}, {dead_in_stock['SKU'].nunique()} SKUs")

    # Low stock: active SKUs with total 1 unit across all locations
    sku_totals = in_stock.groupby('SKU')['STOCK_ON_HAND'].sum()
    lines.append(f"- SKUs with only 1 unit total: {(sku_totals == 1).sum()}")

    # Top 5 by value
    if len(in_stock) > 0:
        top = in_stock.nlargest(5, 'STOCK_VALUE')[['SKU', 'STOCK_VALUE']]
        top_str = ", ".join(f"{r.SKU} (${r.STOCK_VALUE:,.0f})" for r in top.itertuples())
        lines.append(f"- Top 5 rows by stock value: {top_str}")

    return "\n".join(lines)


def build_context(question, df, filtered_df, filter_note=None):
    parts = [
        f"DATASET: {len(df):,} rows | {df['SKU'].nunique():,} SKUs",
        f"Countries: {sorted(df['COUNTRY'].unique().tolist())}",
    ]

    # D. Active filter awareness
    if filter_note:
        parts.append(f"ACTIVE FILTER: The user is currently viewing a FILTERED subset: {filter_note}. "
                     f"All numbers below reflect only this subset. Mention this if relevant.")
    parts.append(f"Filtered view: {len(filtered_df):,} rows")

    # B. Pre-computed aggregates (exact math done in Python)
    parts.append(build_aggregates(filtered_df))

    parts.append(f"\nBY COUNTRY:")
    parts.append(filtered_df.groupby('COUNTRY').agg(
        Locs=('LOCATION', 'nunique'), SKUs=('SKU', 'nunique'),
        Stock=('STOCK_ON_HAND', 'sum'), Transit=('TRANSIT', 'sum'),
    ).to_string())

    cols = ['SKU', 'SKU_DESCRIPTION', 'COUNTRY', 'LOCATION', 'FAMILY',
            'THEME', 'SUB_THEME', 'STOCK_ON_HAND', 'TRANSIT', 'PICKING',
            'RESERVATION', 'AUTOREP_MAX', 'LOGISTIC_STATUS', 'VALIDATED_FRP']
    avail = [c for c in cols if c in filtered_df.columns]

    # C. Intent-based row selection
    intents = detect_question_intent(question)
    intent_rows = pd.DataFrame()
    in_stock = filtered_df[filtered_df['STOCK_ON_HAND'] > 0]

    if 'dead_stock' in intents and 'LOGISTIC_STATUS' in filtered_df.columns:
        dead = in_stock[in_stock['LOGISTIC_STATUS'].str.contains('STOPPED', case=False, na=False)]
        intent_rows = pd.concat([intent_rows, dead.nlargest(40, 'STOCK_VALUE')])
    if 'high_value' in intents:
        intent_rows = pd.concat([intent_rows, in_stock.nlargest(40, 'STOCK_VALUE')])
    if 'low_value' in intents:
        intent_rows = pd.concat([intent_rows, in_stock.nsmallest(40, 'STOCK_VALUE')])
    if 'low_stock' in intents:
        sku_totals = in_stock.groupby('SKU')['STOCK_ON_HAND'].sum()
        low_skus = sku_totals[sku_totals == 1].index
        intent_rows = pd.concat([intent_rows, in_stock[in_stock['SKU'].isin(low_skus)].head(40)])
    if 'transit' in intents:
        intent_rows = pd.concat([intent_rows, filtered_df[filtered_df['TRANSIT'] > 0].head(40)])

    # Keyword-matched rows (existing logic)
    relevant = extract_relevant_rows(question, filtered_df)

    combined = pd.concat([intent_rows, relevant]).drop_duplicates() if len(intent_rows) > 0 or len(relevant) > 0 else pd.DataFrame()

    if len(combined) > 0:
        combined = combined.head(80)
        parts.append(f"\nRELEVANT ROWS ({len(combined)}, selected for this question):")
        parts.append(combined[avail].to_string(index=False))
    else:
        parts.append(f"\nSAMPLE (30 rows):")
        parts.append(filtered_df[avail].head(30).to_string(index=False))

    context = "\n".join(parts)
    if len(context) > 30000:
        context = context[:30000] + "\n[truncated]"
    return context


# ─────────────────────────────────────────────
# GEMINI API
# ─────────────────────────────────────────────

def get_api_key():
    try:
        return st.secrets["GEMINI_API_KEY"]
    except Exception:  # no secrets.toml on Railway → fall back to env var
        pass
    key = os.environ.get("GEMINI_API_KEY", "")
    if key:
        return key
    return st.session_state.get("gemini_key", "")


def build_chat_history_text(chat_history, max_exchanges=3):
    """Build recent Q&A history for conversation memory (last N user/assistant pairs)."""
    # Collect only user and assistant messages (skip oms/warn/error/email)
    relevant = [m for m in chat_history if m.get("role") in ("user", "assistant")]
    # Take the last max_exchanges*2 messages, excluding the current question (already removed by caller)
    recent = relevant[-(max_exchanges * 2):]
    if not recent:
        return ""
    lines = ["\n--- RECENT CONVERSATION (for context; the user may refer back to it) ---"]
    for m in recent:
        who = "User" if m["role"] == "user" else "You (AI)"
        content = str(m.get("content", ""))[:400]  # cap each message
        lines.append(f"{who}: {content}")
    return "\n".join(lines)


def detect_stock_summary_request(question, df):
    """Detect 'how much stock in X' queries. Returns (scope_type, scope_value) or None.

    scope_type: 'location', 'country', or 'all'
    """
    q = ' '.join(question.upper().split())
    triggers = ['HOW MUCH STOCK', 'HOW MANY UNITS', 'HOW MANY ITEMS', 'HOW MANY PIECES',
                'TOTAL STOCK', 'STOCK VALUE', 'INVENTORY VALUE', 'HOW MUCH INVENTORY',
                'TOTAL INVENTORY', 'TOTAL VALUE']
    if not any(t in q for t in triggers):
        return None

    # Look for a location code
    for token in re.findall(r'\b([A-Z0-9]{2,4})\b', q):
        if token in STORE_CODES:
            return ('location', token)

    # Try store aliases (e.g. "ION", "PLAZA INDONESIA")
    from stores import STORE_ALIASES
    for alias, acode in sorted(STORE_ALIASES.items(), key=lambda x: -len(x[0])):
        if alias in q:
            return ('location', acode)

    # Look for a country
    for country in df['COUNTRY'].dropna().unique():
        if str(country).upper() in q:
            return ('country', str(country).upper())

    return ('all', None)


def build_stock_summary(scope_type, scope_value, filtered):
    """Build instant stock summary response + filtered df."""
    if scope_type == 'location':
        subset = filtered[filtered['LOCATION'].str.upper() == scope_value]
        info = STORE_CODES.get(scope_value, {})
        label = f"{scope_value} ({info.get('name', '')})" if info else scope_value
    elif scope_type == 'country':
        subset = filtered[filtered['COUNTRY'].str.upper() == scope_value]
        label = scope_value.title()
    else:
        subset = filtered
        label = "All locations"

    in_stock = subset[subset['STOCK_ON_HAND'] > 0]
    units = int(subset['STOCK_ON_HAND'].sum())
    value = subset['STOCK_VALUE'].sum()
    skus = in_stock['SKU'].nunique()
    transit = int(subset['TRANSIT'].sum())

    if units == 0 and transit == 0:
        return f"❌ No stock found at {label}.", subset

    msg = f"**{label}**: {units:,} units across {skus:,} SKUs — total value ${value:,.0f}."
    if transit > 0:
        msg += f" Plus {transit:,} in transit."
    return msg, subset[subset['TOTAL_UNITS'] > 0]


def ask_gemini_stream(question, context, history_text=""):
    """Generator yielding text chunks from Gemini (streaming)."""
    api_key = get_api_key()
    if not api_key:
        yield "**API key not found.** Add GEMINI_API_KEY to Streamlit secrets.\n\n[TABLE_FILTER]ALL[/TABLE_FILTER]"
        return

    try:
        import google.generativeai as genai
    except ImportError:
        yield "**Missing package:** google-generativeai\n\n[TABLE_FILTER]ALL[/TABLE_FILTER]"
        return

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-3.5-flash")
        prompt = f"{SYSTEM_PROMPT}\n\n--- DATA ---\n{context}{history_text}\n\n--- CURRENT QUESTION ---\n{question}"
        response = model.generate_content(
            prompt,
            generation_config={"max_output_tokens": 1500, "temperature": 0.3},
            stream=True,
        )
        got_text = False
        for chunk in response:
            try:
                if chunk.text:
                    got_text = True
                    yield chunk.text
            except (ValueError, AttributeError):
                continue
        if not got_text:
            yield "**No response.** Try rephrasing.\n\n[TABLE_FILTER]ALL[/TABLE_FILTER]"

    except Exception as e:
        msg = str(e)
        if "401" in msg or "403" in msg:
            yield f"**Invalid API key.** {msg}\n\n[TABLE_FILTER]ALL[/TABLE_FILTER]"
        elif "429" in msg:
            yield f"**Rate limit.** Wait and retry.\n\n[TABLE_FILTER]ALL[/TABLE_FILTER]"
        elif "404" in msg:
            yield f"**Model not found.** {msg}\n\n[TABLE_FILTER]ALL[/TABLE_FILTER]"
        else:
            yield f"**Error:** {msg}\n\n[TABLE_FILTER]ALL[/TABLE_FILTER]"


def ask_gemini(question, context, history_text=""):
    api_key = get_api_key()
    if not api_key:
        return "**API key not found.** Add GEMINI_API_KEY to Streamlit secrets.\n\n[TABLE_FILTER]ALL[/TABLE_FILTER]"

    try:
        import google.generativeai as genai
    except ImportError:
        return "**Missing package:** google-generativeai\n\n[TABLE_FILTER]ALL[/TABLE_FILTER]"

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-3.5-flash")
        prompt = f"{SYSTEM_PROMPT}\n\n--- DATA ---\n{context}{history_text}\n\n--- CURRENT QUESTION ---\n{question}"
        response = model.generate_content(
            prompt,
            generation_config={"max_output_tokens": 1500, "temperature": 0.3},
        )
        if response and response.text:
            return response.text
        if response.prompt_feedback:
            return f"**Blocked:** {response.prompt_feedback}\n\n[TABLE_FILTER]ALL[/TABLE_FILTER]"
        return "**No response.** Try rephrasing.\n\n[TABLE_FILTER]ALL[/TABLE_FILTER]"

    except Exception as e:
        msg = str(e)
        if "401" in msg or "403" in msg:
            return f"**Invalid API key.** {msg}\n\n[TABLE_FILTER]ALL[/TABLE_FILTER]"
        elif "429" in msg:
            return f"**Rate limit.** Wait and retry.\n\n[TABLE_FILTER]ALL[/TABLE_FILTER]"
        elif "404" in msg:
            return f"**Model not found.** {msg}\n\n[TABLE_FILTER]ALL[/TABLE_FILTER]"
        return f"**Error:** {msg}\n\n[TABLE_FILTER]ALL[/TABLE_FILTER]"


# ─────────────────────────────────────────────
# TABLE FILTER PARSER
# ─────────────────────────────────────────────

def parse_table_filter(response_text, df):
    match = re.search(r'\[TABLE_FILTER\]\s*\n?(.*?)\n?\s*\[/TABLE_FILTER\]', response_text, re.DOTALL)
    if not match:
        return df, "all data"
    filter_str = match.group(1).strip()
    if filter_str.upper() == 'ALL':
        return df, "all data"

    mask = pd.Series([True] * len(df), index=df.index)
    desc_parts = []

    for part in filter_str.split(','):
        part = part.strip()
        if not part:
            continue
        gt = re.match(r'(\w+)>(\d+\.?\d*)', part)
        eq = re.match(r'(\w+)=(\d+\.?\d*)', part)
        colon = re.match(r'(\w+):(.+)', part)

        if gt:
            col, val = gt.group(1), float(gt.group(2))
            if col in df.columns:
                mask &= df[col] > val
                desc_parts.append(f"{col}>{val:.0f}")
        elif eq:
            col, val = eq.group(1), float(eq.group(2))
            if col in df.columns:
                mask &= df[col] == val
                desc_parts.append(f"{col}={val:.0f}")
        elif colon:
            col, values = colon.group(1).strip(), colon.group(2).strip()
            if col not in df.columns:
                continue
            if '|' in values:
                vlist = [v.strip().upper() for v in values.split('|')]
                mask &= df[col].astype(str).str.upper().isin(vlist)
                desc_parts.append(f"{col}: {'/'.join(vlist)}")
            else:
                mask &= df[col].astype(str).str.upper() == values.upper()
                desc_parts.append(f"{col}: {values}")

    result = df[mask]
    desc = " + ".join(desc_parts) if desc_parts else "all data"
    if len(result) == 0:
        return df, "no matches (showing all)"
    return result, desc


def clean_response(text):
    return re.sub(r'\[TABLE_FILTER\].*?\[/TABLE_FILTER\]', '', text, flags=re.DOTALL).strip()


def detect_skus_in_question(question, df):
    q = question.upper().strip()
    all_skus = set(df['SKU'].str.upper().unique())
    store_code_set = set(STORE_CODES.keys())
    candidates = re.findall(r'\b([A-Z0-9][A-Z0-9]{3,9})\b', q)
    return [c for c in candidates if c in all_skus and c not in store_code_set]


# ─────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────

def render_upload():
    """Shared across every app: the weekly file. Called inside the sidebar.

    Re-uploading a different file now replaces the loaded data. Previously this
    only ran when nothing was loaded, so the second upload of a session was
    silently ignored until the browser was refreshed.
    """
    st.markdown("### HJW Tracker")
    uploaded = st.file_uploader("Upload tracker", type=["xlsx", "xls", "csv"],
                                label_visibility="collapsed", key="tracker_upload")
    if uploaded:
        sig = (uploaded.name, uploaded.size)
        if sig != st.session_state.get("upload_sig"):
            with st.spinner("Loading..."):
                st.session_state.df = load_and_process(uploaded)
                st.session_state.upload_sig = sig
                st.session_state.chat_history = []
                st.session_state.ai_filter_df = None
                st.session_state.ai_filter_desc = None
                st.session_state.oms_csv = None
                st.session_state.sr_csv = None
                st.session_state.pr_csv = None
                st.session_state.block_csv = None
                st.session_state.ev_results = {}   # event plans re-run on new data
            st.rerun()

    df = st.session_state.df
    if df is not None:
        st.caption(f"{len(df):,} rows | {df['SKU'].nunique():,} SKUs")


def render_stock_filters(df):
    """Stock Report filters. Returns the hard-filtered dataframe."""
    with st.sidebar:
        st.markdown("**Filters**")

        universes = sorted(df['UNIVERSE'].unique().tolist())
        sel_universe = st.multiselect("Universe", universes, default=universes)
        countries = sorted(df['COUNTRY'].unique().tolist())
        sel_country = st.multiselect("Country", countries, default=countries)
        avail_locs = sorted(df[df['COUNTRY'].isin(sel_country)]['LOCATION'].unique().tolist())
        sel_location = st.multiselect("Location", avail_locs, default=avail_locs)
        segments = sorted(df['SEGMENT'].unique().tolist())
        sel_segment = st.multiselect("Segment", segments, default=segments)
        families = sorted(df['FAMILY'].unique().tolist())
        sel_family = st.multiselect("Family", families, default=families)
        statuses = sorted(df['LOGISTIC_STATUS'].unique().tolist())
        sel_status = st.multiselect("Logistic Status", statuses, default=statuses)

    mask = (
        df['UNIVERSE'].isin(sel_universe) &
        df['COUNTRY'].isin(sel_country) &
        df['LOCATION'].isin(sel_location) &
        df['SEGMENT'].isin(sel_segment) &
        df['FAMILY'].isin(sel_family) &
        df['LOGISTIC_STATUS'].isin(sel_status)
    )
    return df[mask].copy()


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    for key, default in [
        ("df", None), ("chat_history", []),
        ("ai_filter_df", None), ("ai_filter_desc", None),
        ("show_extra_cols", False), ("oms_csv", None), ("sr_csv", None), ("pr_csv", None), ("block_csv", None),
        ("pending_question", None), ("upload_sig", None),
    ]:
        if key not in st.session_state:
            st.session_state[key] = default

    with st.sidebar:
        render_upload()

    df = st.session_state.df

    if df is None:
        st.markdown("""
        <div style="text-align:center; padding:4rem 2rem; max-width:500px; margin:auto;">
            <h2 style="color:#1a1a2e;">HJW Tracker</h2>
            <p style="color:#666;">Upload your tracker Excel in the sidebar.</p>
        </div>
        """, unsafe_allow_html=True)
        return

    with st.sidebar:
        st.divider()
        app_choice = st.radio("App", APPS, label_visibility="collapsed", key="app_choice")
        st.divider()

    # Only the selected app renders. Each owns its own sidebar section.
    if app_choice == "Stock Report":
        filtered = render_stock_filters(df)
        render_stock_report(df, filtered)
    else:
        with st.sidebar:
            render_event_sidebar(df)
        render_event_app(df)


def render_stock_report(df, filtered):
    """Render the Stock Report."""

    # Determine table data
    if st.session_state.ai_filter_df is not None:
        table_data = st.session_state.ai_filter_df
        filter_desc = st.session_state.ai_filter_desc
        is_ai_filtered = True
    else:
        table_data = filtered
        filter_desc = None
        is_ai_filtered = False

    # Always hide zero total_units
    table_data = table_data[table_data['TOTAL_UNITS'] > 0]

    # Stats
    stock_units = table_data['STOCK_ON_HAND'].sum()
    stock_val = table_data['STOCK_VALUE'].sum()
    transit_units = table_data['TRANSIT'].sum()

    # Header
    st.markdown(f"""
    <div class="app-header">
        <h1>Stock Report</h1>
        <span class="stats">
            {len(table_data):,} rows &nbsp;|&nbsp;
            {table_data['SKU'].nunique():,} SKUs &nbsp;|&nbsp;
            Stock: {stock_units:,.0f} units (${stock_val:,.0f}) &nbsp;|&nbsp;
            Transit: {transit_units:,.0f}
        </span>
    </div>
    """, unsafe_allow_html=True)

    col_stock, col_ai = st.columns([3, 2])

    # ═══ LEFT: STOCK TABLE ═══════════════════
    with col_stock:

        if is_ai_filtered:
            bc1, bc2, bc3 = st.columns([5, 2, 1])
            with bc1:
                st.markdown(f"""
                <div class="filter-banner">
                    <span>
                        <span class="label">AI Filter:</span> {filter_desc}
                        &nbsp;&nbsp;
                        <span class="stats">{len(table_data):,} rows | {stock_units:,.0f} units</span>
                    </span>
                </div>
                """, unsafe_allow_html=True)
            with bc2:
                buf = io.BytesIO()
                table_data.to_excel(buf, index=False, engine='openpyxl')
                st.download_button(
                    f"Export ({len(table_data)})",
                    data=buf.getvalue(),
                    file_name=f"hjw_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            with bc3:
                if st.button("Clear", type="secondary"):
                    st.session_state.ai_filter_df = None
                    st.session_state.ai_filter_desc = None
                    st.session_state.oms_csv = None
                    st.session_state.sr_csv = None
                    st.session_state.pr_csv = None
                    st.session_state.block_csv = None
                    st.rerun()

        sc1, sc2 = st.columns([4, 1])
        with sc1:
            search = st.text_input("Search", placeholder="Type to search...", label_visibility="collapsed")
        with sc2:
            show_extra = st.checkbox("Extra cols", value=st.session_state.show_extra_cols, key="extra_toggle")
            st.session_state.show_extra_cols = show_extra

        if search:
            term = search.upper().strip()
            text_cols = table_data.select_dtypes(include='object').columns
            smask = table_data[text_cols].apply(
                lambda c: c.astype(str).str.upper().str.contains(term, na=False)
            ).any(axis=1)
            display_data = table_data[smask]
            st.caption(f"{len(display_data):,} results for \"{search}\"")
        else:
            display_data = table_data

        avail_primary = [c for c in PRIMARY_COLS if c in display_data.columns]
        if show_extra:
            avail_extra = [c for c in EXTRA_COLS if c in display_data.columns]
            show_cols = avail_primary + avail_extra
        else:
            show_cols = avail_primary

        # Build column_config for fast client-side formatting (avoids slow pandas Styler)
        col_config = {}
        for c in show_cols:
            if c in ['VALIDATED_FRP', 'STOCK_VALUE', 'TRANSIT_VALUE']:
                col_config[c] = st.column_config.NumberColumn(c, format="$%d")
            elif c in ['STOCK_ON_HAND', 'TRANSIT', 'PICKING', 'RESERVATION',
                        'AUTOREP_MAX', 'CLIENT_ORDER_STOCK', 'PENDING_ORDER_DETAIL', 'TOTAL_UNITS']:
                col_config[c] = st.column_config.NumberColumn(c, format="%d")

        display_data = display_data.copy()
        display_data['_sg_sort'] = display_data['COUNTRY'].apply(lambda x: 0 if str(x).upper() == 'SINGAPORE' else 1)
        display_data = display_data.sort_values(['_sg_sort', 'COUNTRY', 'LOCATION', 'SKU']).drop(columns=['_sg_sort'])

        table_view = display_data[show_cols]
        event = st.dataframe(
            table_view,
            use_container_width=True,
            height=600,
            column_config=col_config,
            hide_index=True,
            on_select="rerun",
            selection_mode=["multi-column", "multi-cell"],
            key="stock_table",
        )

        # ── Excel-style status bar (bottom of table) ──
        sel = getattr(event, "selection", None)
        sel_cells = list(getattr(sel, "cells", []) or []) if sel else []
        sel_rows = list(getattr(sel, "rows", []) or []) if sel else []
        sel_cols = list(getattr(sel, "columns", []) or []) if sel else []

        status = None
        money_cols = {'VALIDATED_FRP', 'STOCK_VALUE', 'TRANSIT_VALUE'}

        if sel_cells:
            # Drag-selected cells: aggregate numeric values like Excel (Average | Count | Sum)
            values, any_money = [], False
            for cell in sel_cells:
                try:
                    r, c = int(cell[0]), cell[1]
                    v = pd.to_numeric(table_view.iloc[r][c], errors='coerce')
                    if pd.notna(v):
                        values.append(float(v))
                        if c in money_cols:
                            any_money = True
                except Exception:
                    continue
            if values:
                fmt = (lambda x: f"${x:,.0f}") if any_money else (lambda x: f"{x:,.2f}".rstrip('0').rstrip('.'))
                status = (f"Average: <b>{fmt(sum(values)/len(values))}</b> &nbsp;|&nbsp; "
                          f"Count: <b>{len(sel_cells)}</b> &nbsp;|&nbsp; "
                          f"Sum: <b>{fmt(sum(values))}</b>")
            else:
                status = f"Count: <b>{len(sel_cells)}</b>"

        elif sel_rows:
            # Whole rows selected: summarize the key numeric columns
            subset = table_view.iloc[sel_rows]
            parts = [f"Count: <b>{len(sel_rows)}</b> rows"]
            for c in ['STOCK_ON_HAND', 'STOCK_VALUE', 'TRANSIT']:
                if c in subset.columns:
                    vals = pd.to_numeric(subset[c], errors='coerce')
                    s = vals.sum()
                    parts.append(f"{c} Sum: <b>{'$' if c in money_cols else ''}{s:,.0f}</b>")
            status = " &nbsp;|&nbsp; ".join(parts)

        elif sel_cols:
            # Whole columns selected: sum each numeric column over all visible rows
            parts = []
            for c in sel_cols:
                if c in table_view.columns:
                    vals = pd.to_numeric(table_view[c], errors='coerce')
                    if vals.notna().any():
                        s, a = vals.sum(), vals.mean()
                        p = '$' if c in money_cols else ''
                        parts.append(f"{c} — Sum: <b>{p}{s:,.0f}</b> · Avg: {p}{a:,.1f}")
            if parts:
                status = f"Count: <b>{len(table_view):,}</b> rows &nbsp;|&nbsp; " + " &nbsp;|&nbsp; ".join(parts)

        if status:
            st.markdown(
                f"""<div style="background:#f8f9fa; border:1px solid #d9dee3; border-radius:0 0 8px 8px;
                border-top:none; padding:0.35rem 0.9rem; font-size:0.8rem; color:#1a1a2e;
                text-align:right; margin-top:-0.6rem;">{status}</div>""",
                unsafe_allow_html=True,
            )

        if not is_ai_filtered:
            csv = display_data[show_cols].to_csv(index=False)
            st.download_button(
                "Download CSV", data=csv,
                file_name=f"hjw_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                mime="text/csv",
            )

    # ═══ RIGHT: AI CHAT ══════════════════════
    with col_ai:
        st.markdown("**Ask AI**")

        chat_box = st.container(height=580)
        with chat_box:
            if not st.session_state.chat_history:
                st.markdown("""
                <div style="color:#999; padding:0.8rem; text-align:center; font-size:0.82rem; line-height:1.6;">
                    Ask me anything — the table updates to match.<br><br>
                    <b>Stock:</b><br>
                    <em>"What Color Blossom do we have in Singapore?"</em><br><br>
                    <b>OMS:</b><br>
                    <em>"OMS to Ion for Q1TC10"</em><br><br>
                    <b>SR:</b><br>
                    <em>"SR from NN5 for Q05911"</em><br><br>
                    <b>PR:</b><br>
                    <em>"PR NC3 from NF2 for Q1TC10"</em><br><br>
                    <b>Block:</b><br>
                    <em>"Block Q96413 as PHcarnet"</em><br><br>
                    <b>Find:</b><br>
                    <em>"Find Q03000 E3PG21"</em>
                </div>
                """, unsafe_allow_html=True)

            for msg in st.session_state.chat_history:
                role = msg["role"]
                content = msg.get("content", "")
                if role == "user":
                    st.markdown(f'<div class="chat-user"><strong>You:</strong><br>{content}</div>', unsafe_allow_html=True)
                elif role == "oms":
                    st.markdown(f'<div class="chat-oms">{content}</div>', unsafe_allow_html=True)
                elif role == "warn":
                    st.markdown(f'<div class="chat-warn">{content}</div>', unsafe_allow_html=True)
                elif role == "error":
                    st.markdown(f'<div class="chat-err">{content}</div>', unsafe_allow_html=True)
                elif role == "email":
                    em_to = msg.get("to", "")
                    em_cc = msg.get("cc", "")
                    em_subj = msg.get("subject", "")
                    em_body = msg.get("body_html", "")
                    import streamlit.components.v1 as components
                    components.html(f"""
<div style="background:#f0f4ff;border-left:3px solid #2962ff;border-radius:8px;font-family:'DM Sans',Calibri,Arial,sans-serif;overflow:hidden;">
    <div style="padding:8px 10px;font-size:12px;color:#444;border-bottom:1px solid #c8d6f0;">
        <div style="margin-bottom:2px;"><b style="color:#2962ff;">To:</b> {em_to}</div>
        <div style="margin-bottom:2px;"><b style="color:#2962ff;">CC:</b> {em_cc}</div>
        <div><b style="color:#2962ff;">Subject:</b> {em_subj}</div>
    </div>
    <div style="padding:8px 10px;position:relative;">
        <div id="emailBody">{em_body}</div>
        <button onclick="copyEmail()" id="copyBtn" style="
            position:absolute;top:6px;right:6px;
            background:#2962ff;color:white;border:none;border-radius:4px;
            padding:3px 10px;font-size:11px;cursor:pointer;
        ">📋 Copy</button>
    </div>
</div>
<script>
function copyEmail() {{
    const body = document.getElementById('emailBody').innerHTML;
    const blob = new Blob([body], {{type: 'text/html'}});
    const item = new ClipboardItem({{'text/html': blob}});
    navigator.clipboard.write([item]).then(() => {{
        document.getElementById('copyBtn').textContent = '✅ Copied!';
        setTimeout(() => {{ document.getElementById('copyBtn').textContent = '📋 Copy'; }}, 2000);
    }}).catch(() => {{
        const range = document.createRange();
        range.selectNodeContents(document.getElementById('emailBody'));
        const sel = window.getSelection();
        sel.removeAllRanges();
        sel.addRange(range);
        document.getElementById('copyBtn').textContent = '📋 Selected — Ctrl+C';
        setTimeout(() => {{ document.getElementById('copyBtn').textContent = '📋 Copy'; }}, 2000);
    }});
}}
</script>
""", height=195 + em_body.count('<tr>') * 30)
                else:
                    st.markdown(f'<div class="chat-ai"><strong>AI:</strong><br>{content}</div>', unsafe_allow_html=True)

            # ── Process pending question (runs AFTER messages are visible) ──
            if st.session_state.pending_question:
                pq = st.session_state.pending_question
                st.session_state.pending_question = None

                # Check 1: OMS request?
                if is_oms_request(pq):
                    result = parse_oms_request(pq, df)
                    if result["success"]:
                        st.session_state.oms_csv = generate_oms_csv(result["orders"])
                        st.session_state.chat_history.append({
                            "role": "oms", "content": result["summary"]
                        })
                        if result["warnings"]:
                            st.session_state.chat_history.append({
                                "role": "warn", "content": "\n".join(result["warnings"])
                            })
                        oms_skus = list(set(o["SKU"] for o in result["orders"]))
                        sku_mask = filtered['SKU'].str.upper().isin(oms_skus)
                        st.session_state.ai_filter_df = filtered[sku_mask]
                        st.session_state.ai_filter_desc = f"OMS: {', '.join(oms_skus)}"
                    else:
                        for err in result["errors"]:
                            st.session_state.chat_history.append({"role": "error", "content": err})
                    st.rerun()

                # Check 2: SR (Store Reverse)?
                elif is_sr_request(pq):
                    result = parse_sr_request(pq, df)
                    if result.get("needs_counter"):
                        st.session_state.chat_history.append({
                            "role": "error", "content": "❌ Set the SR starting order number in the sidebar first."
                        })
                    elif result["success"]:
                        st.session_state.sr_csv = generate_sr_csv(result["orders"])
                        st.session_state.chat_history.append({
                            "role": "oms", "content": result["summary"]
                        })
                        if result["warnings"]:
                            st.session_state.chat_history.append({
                                "role": "warn", "content": "\n".join(result["warnings"])
                            })
                        # Generate email templates
                        sr_emails = generate_sr_email(result["orders"], df)
                        for em in sr_emails:
                            st.session_state.chat_history.append({
                                "role": "email",
                                "to": em["to"],
                                "cc": em["cc"],
                                "subject": em["subject"],
                                "body_html": em["body_html"],
                            })
                        sr_skus = list(set(o["SKU"] for o in result["orders"]))
                        sku_mask = filtered['SKU'].str.upper().isin(sr_skus)
                        st.session_state.ai_filter_df = filtered[sku_mask]
                        st.session_state.ai_filter_desc = f"SR: {', '.join(sr_skus)}"
                    else:
                        for err in result["errors"]:
                            st.session_state.chat_history.append({"role": "error", "content": err})
                    st.rerun()

                # Check 3: PR (Product Request)?
                elif is_pr_request(pq):
                    result = parse_pr_request(pq, df)
                    if result["success"]:
                        st.session_state.pr_csv = generate_pr_csv(result["orders"])
                        st.session_state.chat_history.append({
                            "role": "oms", "content": result["summary"]
                        })
                        if result["warnings"]:
                            st.session_state.chat_history.append({
                                "role": "warn", "content": "\n".join(result["warnings"])
                            })
                        # Generate email template
                        pr_emails = generate_pr_email(result["orders"], df)
                        for em in pr_emails:
                            st.session_state.chat_history.append({
                                "role": "email",
                                "to": em["to"],
                                "cc": em["cc"],
                                "subject": em["subject"],
                                "body_html": em["body_html"],
                            })
                        pr_skus = list(set(o["SKU"] for o in result["orders"]))
                        sku_mask = filtered['SKU'].str.upper().isin(pr_skus)
                        st.session_state.ai_filter_df = filtered[sku_mask]
                        st.session_state.ai_filter_desc = f"PR: {', '.join(pr_skus)}"
                    else:
                        for err in result["errors"]:
                            st.session_state.chat_history.append({"role": "error", "content": err})
                    st.rerun()

                # Check 4: Block?
                elif is_block_request(pq):
                    result = parse_block_request(pq, df)
                    if result["success"]:
                        st.session_state.block_csv = generate_block_csv(result["orders"])
                        st.session_state.chat_history.append({
                            "role": "oms", "content": result["summary"]
                        })
                        if result["warnings"]:
                            st.session_state.chat_history.append({
                                "role": "warn", "content": "\n".join(result["warnings"])
                            })
                        block_skus = list(set(o["SKU"] for o in result["orders"]))
                        sku_mask = filtered['SKU'].str.upper().isin(block_skus)
                        st.session_state.ai_filter_df = filtered[sku_mask]
                        st.session_state.ai_filter_desc = f"Block: {', '.join(block_skus)}"
                    else:
                        for err in result["errors"]:
                            st.session_state.chat_history.append({"role": "error", "content": err})
                    st.rerun()

                # Check 5: "find" + SKUs → instant Python lookup
                elif 'FIND' in pq.upper():
                    found_skus = detect_skus_in_question(pq, filtered)
                    if found_skus:
                        sku_mask = filtered['SKU'].str.upper().isin(found_skus)
                        matched = filtered[sku_mask]
                        matched_with_stock = matched[matched['TOTAL_UNITS'] > 0]

                        # Build quick summary
                        total_stock = int(matched_with_stock['STOCK_ON_HAND'].sum())
                        total_transit = int(matched_with_stock['TRANSIT'].sum())
                        n_locs = matched_with_stock['LOCATION'].nunique()
                        n_found = matched_with_stock['SKU'].nunique()
                        n_requested = len(found_skus)

                        # Country breakdown
                        by_country = matched_with_stock.groupby('COUNTRY')['STOCK_ON_HAND'].sum()
                        by_country = by_country[by_country > 0].sort_values(ascending=False)
                        country_str = ", ".join(f"{c}: {int(v)}" for c, v in by_country.items())

                        # Missing SKUs
                        found_upper = set(matched['SKU'].str.upper().unique())
                        missing = [s for s in found_skus if s not in found_upper]

                        summary = f"Found {n_found}/{n_requested} SKUs — {total_stock} units on hand across {n_locs} locations"
                        if total_transit > 0:
                            summary += f", {total_transit} in transit"
                        summary += f". {country_str}."
                        if missing:
                            summary += f"\n❌ Not found: {', '.join(missing)}"

                        st.session_state.ai_filter_df = filtered[sku_mask]
                        st.session_state.ai_filter_desc = f"SKU: {', '.join(found_skus)}"
                        st.session_state.chat_history.append({
                            "role": "assistant", "content": summary
                        })
                    else:
                        st.session_state.chat_history.append({
                            "role": "error", "content": "❌ No valid SKUs found in your message."
                        })
                    st.rerun()

                # Check 6: Instant stock summary ("how much stock in N71")
                elif detect_stock_summary_request(pq, df) is not None and not detect_skus_in_question(pq, df):
                    scope_type, scope_value = detect_stock_summary_request(pq, df)
                    msg, subset = build_stock_summary(scope_type, scope_value, filtered)
                    st.session_state.chat_history.append({
                        "role": "assistant", "content": msg
                    })
                    if len(subset) > 0:
                        st.session_state.ai_filter_df = subset
                        if scope_type == 'location':
                            st.session_state.ai_filter_desc = f"LOCATION: {scope_value}"
                        elif scope_type == 'country':
                            st.session_state.ai_filter_desc = f"COUNTRY: {scope_value}"
                    st.rerun()

                # Check 7: AI for everything else (streaming)
                else:
                    # D. Tell the AI about the active AI filter (if any)
                    active_filter_note = st.session_state.ai_filter_desc if st.session_state.ai_filter_df is not None else None
                    context = build_context(pq, df, filtered, filter_note=active_filter_note)
                    # A. Conversation memory: last 3 exchanges (excluding the current question)
                    history_text = build_chat_history_text(st.session_state.chat_history[:-1])

                    # Stream the response into a live bubble
                    stream_box = st.empty()
                    raw = ""
                    for chunk in ask_gemini_stream(pq, context, history_text=history_text):
                        raw += chunk
                        # Hide the TABLE_FILTER block while streaming
                        display_text = re.split(r'\[TABLE_FILTER', raw)[0]
                        stream_box.markdown(
                            f'<div class="chat-ai"><strong>AI:</strong><br>{display_text}▌</div>',
                            unsafe_allow_html=True,
                        )
                    stream_box.empty()

                    mentioned_skus = detect_skus_in_question(pq, filtered)
                    if mentioned_skus:
                        sku_mask = filtered['SKU'].str.upper().isin(mentioned_skus)
                        st.session_state.ai_filter_df = filtered[sku_mask]
                        st.session_state.ai_filter_desc = f"SKU: {', '.join(mentioned_skus)}"
                    else:
                        ai_f, desc = parse_table_filter(raw, filtered)
                        st.session_state.ai_filter_df = ai_f
                        st.session_state.ai_filter_desc = desc

                    st.session_state.chat_history.append({
                        "role": "assistant", "content": clean_response(raw)
                    })
                    st.rerun()

        # Download buttons
        if st.session_state.oms_csv:
            today = datetime.now().strftime('%d%m%y')
            st.download_button(
                "📋 Download OMS",
                data=st.session_state.oms_csv,
                file_name=f"OMS_{today}.csv",
                mime="text/csv",
                use_container_width=True,
            )

        if st.session_state.sr_csv:
            today = datetime.now().strftime('%d%m%y')
            st.download_button(
                "🔄 Download SR",
                data=st.session_state.sr_csv,
                file_name=f"SR_{today}.csv",
                mime="text/csv",
                use_container_width=True,
            )

        if st.session_state.pr_csv:
            today = datetime.now().strftime('%d%m%y')
            st.download_button(
                "📦 Download PR",
                data=st.session_state.pr_csv,
                file_name=f"PR_{today}.csv",
                mime="text/csv",
                use_container_width=True,
            )

        if st.session_state.block_csv:
            today = datetime.now().strftime('%d%m%y')
            st.download_button(
                "🔒 Download Block",
                data=st.session_state.block_csv,
                file_name=f"BLOCK_{today}.csv",
                mime="text/csv",
                use_container_width=True,
            )

        # Input
        question = st.chat_input("Ask, find, OMS, SR, PR, or Block...")

        if question:
            st.session_state.chat_history.append({"role": "user", "content": question})
            st.session_state.pending_question = question
            st.rerun()

        if st.session_state.chat_history:
            if st.button("Clear chat", type="secondary", use_container_width=True):
                st.session_state.chat_history = []
                st.session_state.ai_filter_df = None
                st.session_state.ai_filter_desc = None
                st.session_state.oms_csv = None
                st.session_state.sr_csv = None
                st.session_state.pr_csv = None
                st.session_state.block_csv = None
                st.session_state.pending_question = None
                st.rerun()


if __name__ == "__main__":
    main()
