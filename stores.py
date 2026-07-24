# -*- coding: utf-8 -*-
"""
stores.py — Store codes + OMS generation engine
================================================
Pure Python, no AI. Instant OMS generation with smart warnings.
"""

import re
import pandas as pd
from datetime import datetime

# ─────────────────────────────────────────────
# STORE CODES
# ─────────────────────────────────────────────

STORE_CODES = {
    # Australia
    "L32": {"name": "SYDNEY BONDI", "city": "BOND JUNCTION", "country": "AUSTRALIA"},
    "L14": {"name": "BRISBANE", "city": "BRISBANE", "country": "AUSTRALIA"},
    "L12": {"name": "MELBOURNE COLLINS ST", "city": "MELBOURNE", "country": "AUSTRALIA"},
    "L26": {"name": "MELBOURNE CROWN", "city": "MELBOURNE", "country": "AUSTRALIA"},
    "L30": {"name": "MELBOURNE CHADSTONE", "city": "MELBOURNE", "country": "AUSTRALIA"},
    "L47": {"name": "MELBOURNE DAVID JONES", "city": "MELBOURNE", "country": "AUSTRALIA"},
    "L24": {"name": "PERTH RAINE SQUARE", "city": "PERTH", "country": "AUSTRALIA"},
    "L16": {"name": "PACIFIC FAIR", "city": "SURFERS PARADISE", "country": "AUSTRALIA"},
    "AUZ": {"name": "ECOM AUSTRALIA", "city": "SYDNEY", "country": "AUSTRALIA"},
    "L08": {"name": "SYDNEY GEORGE ST", "city": "SYDNEY", "country": "AUSTRALIA"},
    "L28": {"name": "SYDNEY ROCKS DFS", "city": "SYDNEY", "country": "AUSTRALIA"},
    "L42": {"name": "SYDNEY DAVID JONES", "city": "SYDNEY", "country": "AUSTRALIA"},
    "L45": {"name": "SYDNEY AIRPORT", "city": "SYDNEY", "country": "AUSTRALIA"},
    "L36": {"name": "AUSTRALIA CS", "city": "DIGITAL", "country": "AUSTRALIA"},
    # Guam
    "N53": {"name": "GUAM DFS", "city": "GUAM", "country": "GUAM"},
    # India
    "Y04": {"name": "BANGALORE", "city": "BANGALORE", "country": "INDIA"},
    "Y11": {"name": "MUMBAI JIO WORLD", "city": "BOMBAY", "country": "INDIA"},
    "Y03": {"name": "NEW DELHI 2", "city": "NEW DELHI", "country": "INDIA"},
    "Y10": {"name": "CSC IN ECOM", "city": "NEW DELHI", "country": "INDIA"},
    # Indonesia
    "N61": {"name": "INDONESIA CTS", "city": "JAKARTA", "country": "INDONESIA"},
    "N63": {"name": "LV JAKARTA PLAZA INDONESIA", "city": "JAKARTA", "country": "INDONESIA"},
    "N64": {"name": "LV JAKARTA PLAZA SENAYAN", "city": "JAKARTA", "country": "INDONESIA"},
    "NB6": {"name": "LV JAKARTA PACIFIC PLACE", "city": "JAKARTA", "country": "INDONESIA"},
    "NM3": {"name": "CSC ID ECOM", "city": "JAKARTA", "country": "INDONESIA"},
    # Malaysia
    "N68": {"name": "KUALALUMPUR PAVILION", "city": "KUALA LUMPUR", "country": "MALAYSIA"},
    "N69": {"name": "KUALA LUMPUR KLCC", "city": "KUALA LUMPUR", "country": "MALAYSIA"},
    "NF5": {"name": "KUALA LUMPUR GARDENS", "city": "KUALA LUMPUR", "country": "MALAYSIA"},
    "NYE": {"name": "KUALA LUMPUR TRX", "city": "KUALA LUMPUR", "country": "MALAYSIA"},
    "NM2": {"name": "MALAYSIA CS", "city": "DIGITAL", "country": "MALAYSIA"},
    # New Zealand
    "X06": {"name": "AUCKLAND QUEEN ST", "city": "AUCKLAND", "country": "NEW ZEALAND"},
    "X38": {"name": "AUCKLAND NEW MARKET", "city": "AUCKLAND", "country": "NEW ZEALAND"},
    "X10": {"name": "QUEENSTOWN", "city": "QUEENSTOWN", "country": "NEW ZEALAND"},
    "XM1": {"name": "NEW ZEALAND CS", "city": "DIGITAL", "country": "NEW ZEALAND"},
    # Philippines
    "NAD": {"name": "CEBU", "city": "CEBU", "country": "PHILIPPINES"},
    "N02": {"name": "MANILA GREENBELT", "city": "MANILA", "country": "PHILIPPINES"},
    "NG8": {"name": "CSC PH ECOM", "city": "MANILA", "country": "PHILIPPINES"},
    "NN5": {"name": "MANILA SOLAIRE", "city": "MANILA", "country": "PHILIPPINES"},
    # Singapore
    "N71": {"name": "SGP WAREHOUSE", "city": "SINGAPORE", "country": "SINGAPORE"},
    "N74": {"name": "SGP NGEE ANN CITY", "city": "SINGAPORE", "country": "SINGAPORE"},
    "NC3": {"name": "SGP ION", "city": "SINGAPORE", "country": "SINGAPORE"},
    "NF2": {"name": "SGP MARINA BAY", "city": "SINGAPORE", "country": "SINGAPORE"},
    "NQ6": {"name": "CHANGI AIRPORT T3", "city": "SINGAPORE", "country": "SINGAPORE"},
    "NX6": {"name": "CHANGI AIRPORT T1", "city": "SINGAPORE", "country": "SINGAPORE"},
    "NM4": {"name": "SINGAPORE CS", "city": "DIGITAL", "country": "SINGAPORE"},
    "N7X": {"name": "WH CARNET", "city": "SINGAPORE", "country": "SINGAPORE"},
    "SG11": {"name": "REPAIR CENTER", "city": "SINGAPORE", "country": "SINGAPORE"},
    "N65": {"name": "BLOCK LOCATION", "city": "SINGAPORE", "country": "SINGAPORE"},
    # Thailand
    "N79": {"name": "BANGKOK EMPORIUM", "city": "BANGKOK", "country": "THAILAND"},
    "NAB": {"name": "LV BANGKOK CHIDLOM", "city": "BANGKOK", "country": "THAILAND"},
    "NAM": {"name": "LV BANGKOK THE PLACE", "city": "BANGKOK", "country": "THAILAND"},
    "NG6": {"name": "WOMEN BANGKOK PARAGON", "city": "BANGKOK", "country": "THAILAND"},
    "NVJ": {"name": "LV BANGKOK ICONSIAM", "city": "BANGKOK", "country": "THAILAND"},
    "NX8": {"name": "LV BANGKOK SUVARNABHUMI AIRPORT", "city": "BANGKOK", "country": "THAILAND"},
    "NYF": {"name": "MEN BANGKOK PARAGON", "city": "BANGKOK", "country": "THAILAND"},
    "THW": {"name": "THAILAND WAREHOUSE", "city": "BANGKOK", "country": "THAILAND"},
    "NVQ": {"name": "LV PHUKET FLORESTA", "city": "PHUKET", "country": "THAILAND"},
    "NM1": {"name": "THAILAND CS", "city": "DIGITAL", "country": "THAILAND"},
    # Vietnam
    "NXD": {"name": "LV HANOI INTL CENTRE", "city": "HANOI", "country": "VIETNAM"},
    "N46": {"name": "HO CHI MINH", "city": "HO-CHI-MINH", "country": "VIETNAM"},
    "NM6": {"name": "CSC VN ECOM", "city": "HO-CHI-MINH", "country": "VIETNAM"},
    # Central / Other
    "DEC": {"name": "CENTRAL RDC", "city": "PARIS", "country": "DERET"},
    "LOG": {"name": "CENTRAL RDC", "city": "CERGY", "country": "CERGY"},
    "P9J": {"name": "HWJ CENTRAL ADHOC SHIPMENT", "city": "CERGY", "country": "CERGY"},
    "SCL": {"name": "CENTRAL RDC ADHOC SHIPMENT", "city": "GENEVA", "country": "GENEVA"},
    "JWC": {"name": "CENTRAL JWL", "city": "", "country": "CENTRAL"},
    "V99": {"name": "TOKYO MISATO WH", "city": "TOKYO", "country": "JAPAN"},
    # Doha
    "P71": {"name": "DOHA", "city": "DOHA", "country": "DOHA"},
    "P73": {"name": "DOHA", "city": "DOHA", "country": "DOHA"},
    "P74": {"name": "DOHA", "city": "DOHA", "country": "DOHA"},
    "P75": {"name": "DOHA", "city": "DOHA", "country": "DOHA"},
    "P76": {"name": "DOHA", "city": "DOHA", "country": "DOHA"},
    # Hong Kong
    "NF8": {"name": "NORTH ASIA RDC", "city": "HONG KONG", "country": "HONG KONG"},
    "N49": {"name": "NORTH ASIA RDC", "city": "HONG KONG", "country": "HONG KONG"},
}

# ─────────────────────────────────────────────
# STORE NAME ALIASES (for natural language)
# ─────────────────────────────────────────────

STORE_ALIASES = {
    # Singapore shortcuts
    "ION": "NC3", "NGEE ANN": "N74", "NGEE ANN CITY": "N74",
    "MARINA BAY": "NF2", "MBS": "NF2", "MARINA BAY SANDS": "NF2",
    "CHANGI T3": "NQ6", "CHANGI T1": "NX6",
    "SGP WAREHOUSE": "N71", "WAREHOUSE": "N71",
    # Indonesia shortcuts
    "PLAZA INDONESIA": "N63", "PI": "N63",
    "PLAZA SENAYAN": "N64", "PACIFIC PLACE": "NB6",
    # Malaysia shortcuts
    "PAVILION": "N68", "KLCC": "N69", "GARDENS": "NF5", "TRX": "NYE",
    # Thailand shortcuts
    "EMPORIUM": "N79", "CHIDLOM": "NAB", "ICONSIAM": "NVJ",
    "PARAGON": "NG6", "PARAGON WOMEN": "NG6", "PARAGON MEN": "NYF",
    "SUVARNABHUMI": "NX8", "FLORESTA": "NVQ", "PHUKET": "NVQ",
    # Australia shortcuts
    "GEORGE ST": "L08", "BONDI": "L32", "CHADSTONE": "L30",
    "COLLINS ST": "L12", "CROWN": "L26", "PACIFIC FAIR": "L16",
    # Philippines shortcuts
    "GREENBELT": "N02", "SOLAIRE": "NN5", "CEBU": "NAD",
    # NZ shortcuts
    "QUEEN ST": "X06",
    # Other
    "GUAM": "N53", "BANGALORE": "Y04",
    "MUMBAI": "Y11", "JIO WORLD": "Y11",
    "NEW DELHI": "Y03",
}


def resolve_store(text):
    """Resolve store code or name to a valid store code.
    Returns (code, store_info) or (None, None)."""
    t = text.upper().strip()

    # Direct code match
    if t in STORE_CODES:
        return t, STORE_CODES[t]

    # Alias match (exact)
    if t in STORE_ALIASES:
        code = STORE_ALIASES[t]
        return code, STORE_CODES[code]

    # Partial alias match
    for alias, code in sorted(STORE_ALIASES.items(), key=lambda x: -len(x[0])):
        if t == alias or alias in t or t in alias:
            return code, STORE_CODES[code]

    # Partial name match
    for code, info in STORE_CODES.items():
        if t in info["name"] or info["name"] in t:
            return code, info

    return None, None


# ─────────────────────────────────────────────
# OMS INTENT DETECTION
# ─────────────────────────────────────────────

OMS_KEYWORDS = ['OMS', 'TRANSFER ORDER', 'SEND TO', 'SHIP TO', 'MOVE TO']

def is_oms_request(question):
    """Check if the user is asking for OMS generation."""
    q = ' '.join(question.upper().split())  # normalize newlines/whitespace
    return any(kw in q for kw in OMS_KEYWORDS)


# ─────────────────────────────────────────────
# OMS PARSER (from natural language)
# ─────────────────────────────────────────────

def parse_oms_request(question, df):
    """Parse an OMS request from natural language.

    Returns dict with:
        - success: bool
        - orders: list of order dicts
        - warnings: list of warning strings
        - errors: list of error strings
        - summary: human-readable summary
    """
    q = ' '.join(question.upper().split())  # normalize newlines/whitespace
    all_skus_in_data = set(df['SKU'].str.upper().unique())
    store_code_set = set(STORE_CODES.keys())

    # ── Find destination store(s) ──
    destinations = []

    # Try "to <store>" pattern — match codes after "to"
    to_patterns = re.findall(r'\bTO\s+([A-Z0-9]{2,4})\b', q)
    for tp in to_patterns:
        code, info = resolve_store(tp)
        if code and code != "N71":
            if code not in [d[0] for d in destinations]:
                destinations.append((code, info))

    # Try alias matches in full text if none found
    if not destinations:
        for alias, code in sorted(STORE_ALIASES.items(), key=lambda x: -len(x[0])):
            if alias in q and code != "N71":
                info = STORE_CODES[code]
                if code not in [d[0] for d in destinations]:
                    destinations.append((code, info))
                    break

    # ── Find SKUs ──
    candidates = re.findall(r'\b([A-Z0-9][A-Z0-9]{3,9})\b', q)
    found_skus = []
    for c in candidates:
        if c in all_skus_in_data and c not in store_code_set:
            if c not in found_skus:
                found_skus.append(c)

    # ── Find quantity ──
    qty = 1
    qty_match = re.search(r'\bQTY\s*(\d+)\b', q) or re.search(r'\b(\d+)\s*(?:UNITS?|PCS?|PIECES?|EACH)\b', q)
    if qty_match:
        qty = int(qty_match.group(1))

    # ── Validate ──
    errors = []
    warnings = []

    if not destinations:
        errors.append("❌ No destination store found. Use a store code or name (e.g. 'to NC3' or 'to Ion').")
        return {"success": False, "orders": [], "warnings": [], "errors": errors, "summary": ""}

    if not found_skus:
        errors.append("❌ No valid SKUs found in your message.")
        return {"success": False, "orders": [], "warnings": [], "errors": errors, "summary": ""}

    # ── Build orders with validation ──
    orders = []
    today = datetime.now().strftime('%d%m%y')
    n71_stock = df[df['LOCATION'].str.upper() == 'N71'].copy()

    for dest_code, dest_info in destinations:
        for sku in found_skus:
            # Check warehouse stock
            wh_rows = n71_stock[n71_stock['SKU'].str.upper() == sku]
            wh_qty = int(wh_rows['STOCK_ON_HAND'].sum()) if len(wh_rows) > 0 else 0

            # Check logistic status
            sku_rows = df[df['SKU'].str.upper() == sku]
            status = ""
            if len(sku_rows) > 0 and 'LOGISTIC_STATUS' in sku_rows.columns:
                status = str(sku_rows.iloc[0].get('LOGISTIC_STATUS', '')).upper()

            # Warnings
            if wh_qty == 0:
                warnings.append(f"⚠️ {sku}: 0 units at N71 warehouse")
            elif qty > wh_qty:
                warnings.append(f"⚠️ {sku}: only {wh_qty} at N71, sending {qty}")

            if 'PRODUCTION STOPPED' in status:
                warnings.append(f"⚠️ {sku}: Production Stopped")
            elif 'RETRIEVAL' in status:
                warnings.append(f"⚠️ {sku}: Under Retrieval — should not ship")

            order_name = f"SGTO{dest_code}{today}"
            orders.append({
                "ORDERNAME": order_name,
                "TYPE": "TS",
                "RELEASE_TYPE": "RT",
                "SHIP_FROM": "N71",
                "SHIP_TO": dest_code,
                "SKU": sku,
                "QTY": qty,
                "STOCK_CAT": "AVA",
                "STORAGE_LOC": "1100",
                "ALLOCATION_TYPE": "BCO",
                "ALLOCATION_PRIORITY": "0",
                "SPLIT_STRATEGY": "SPL",
                "MOT": "",
                "PRODUCT_FLAG": "",
                "START_DATE": "",
                "ANTICIPATION_DATE": "",
                "RELEASE_DATE": "",
                "SHIP_DATE": "",
                "EXPIRATION_DATE": "20261010",
            })

    # ── Summary ──
    dest_strs = [f"{c} ({i['name']})" for c, i in destinations]
    summary = f"✅ OMS: {len(orders)} line(s) — {', '.join(found_skus)} → {', '.join(dest_strs)}"

    return {
        "success": True,
        "orders": orders,
        "warnings": warnings,
        "errors": [],
        "summary": summary,
    }


def generate_oms_csv(orders):
    """Generate CSV string from orders list."""
    if not orders:
        return None

    cols = ["ORDERNAME", "TYPE", "RELEASE_TYPE", "SHIP_FROM", "SHIP_TO", "SKU", "QTY",
            "STOCK_CAT", "STORAGE_LOC", "ALLOCATION_TYPE", "ALLOCATION_PRIORITY",
            "SPLIT_STRATEGY", "MOT", "PRODUCT_FLAG", "START_DATE", "ANTICIPATION_DATE",
            "RELEASE_DATE", "SHIP_DATE", "EXPIRATION_DATE"]

    lines = [",".join(cols)]
    for o in orders:
        lines.append(",".join(str(o.get(c, "")) for c in cols))

    return "\n".join(lines)


# ─────────────────────────────────────────────
# SR (STORE REVERSE)
# ─────────────────────────────────────────────

from datetime import timedelta

SR_KEYWORDS = ['STORE REVERSE', ' SR ']


def is_sr_request(question):
    """Check if user is asking for SR generation."""
    q = f" {' '.join(question.upper().split())} "  # normalize newlines/whitespace
    if ' SR ' in q:
        return True
    if 'STORE REVERSE' in q:
        return True
    return False


def parse_sr_request(question, df):
    """Parse a Store Reverse request from natural language.

    New format: OMS-style CSV, reversed direction.
    SHIP_FROM = source store, SHIP_TO = always N71.
    ORDERNAME = {store}SR{DDMMYY}
    EXPIRATION_DATE = today + 4 days.
    """
    q = ' '.join(question.upper().split())  # normalize newlines/whitespace
    all_skus_in_data = set(df['SKU'].str.upper().unique())
    store_code_set = set(STORE_CODES.keys())

    # ── Find source store(s) ──
    sources = []

    # "from <store>" pattern
    from_patterns = re.findall(r'\bFROM\s+([A-Z0-9]{2,4})\b', q)
    for fp in from_patterns:
        code, info = resolve_store(fp)
        if code and code != "N71":
            if code not in [s[0] for s in sources]:
                sources.append((code, info))

    # Bare store codes in message
    if not sources:
        candidates = re.findall(r'\b([A-Z0-9]{2,4})\b', q)
        for c in candidates:
            if c in store_code_set and c != "N71" and c not in all_skus_in_data:
                info = STORE_CODES[c]
                if c not in [s[0] for s in sources]:
                    sources.append((c, info))

    # Alias match
    if not sources:
        for alias, code in sorted(STORE_ALIASES.items(), key=lambda x: -len(x[0])):
            if alias in q and code != "N71":
                info = STORE_CODES[code]
                if code not in [s[0] for s in sources]:
                    sources.append((code, info))
                    break

    # ── Find SKUs ──
    candidates = re.findall(r'\b([A-Z0-9][A-Z0-9]{3,9})\b', q)
    found_skus = []
    for c in candidates:
        if c in all_skus_in_data and c not in store_code_set:
            if c not in found_skus:
                found_skus.append(c)

    # ── Find quantity ──
    qty = 1
    qty_match = re.search(r'\bQTY\s*(\d+)\b', q) or re.search(r'\b(\d+)\s*(?:UNITS?|PCS?|PIECES?|EACH)\b', q)
    if qty_match:
        qty = int(qty_match.group(1))

    # ── Validate ──
    errors = []
    warnings = []

    if not sources:
        errors.append("❌ No source store found. Use: 'sr from NG6 for Q03024'")
        return {"success": False, "orders": [], "warnings": [], "errors": errors, "summary": ""}

    if not found_skus:
        errors.append("❌ No valid SKUs found in your message.")
        return {"success": False, "orders": [], "warnings": [], "errors": errors, "summary": ""}

    # ── Build orders (OMS-style CSV, reversed) ──
    orders = []
    now = datetime.now()
    today_ddmmyy = now.strftime('%d%m%y')
    expiration = (now + timedelta(days=4)).strftime('%Y%m%d')  # SR expiration: today + 4 days
    oms_expiration = "20261010"  # OMS leg expiration (matches standard OMS)

    # Indonesia retail stores route through N61 hub: store → N61 (SR), then N61 → N71 (OMS)
    INDONESIA_HUB_STORES = {"N63", "N64", "NB6"}

    # Precompute uppercase columns ONCE (avoids repeated .str.upper() on 8k rows)
    sku_upper = df['SKU'].str.upper()
    loc_upper = df['LOCATION'].str.upper()
    has_status = 'LOGISTIC_STATUS' in df.columns

    # Build per-SKU lookup: stock by (location, sku) and status by sku
    status_by_sku = {}
    if has_status:
        for sku in found_skus:
            srows = df[sku_upper == sku]
            if len(srows) > 0:
                status_by_sku[sku] = str(srows.iloc[0].get('LOGISTIC_STATUS', '')).upper()

    for source_code, source_info in sources:
        order_name = f"{source_code}SR{today_ddmmyy}"
        is_indonesia = source_code in INDONESIA_HUB_STORES
        sr_ship_to = "N61" if is_indonesia else "N71"
        indonesia_legs = []  # SKUs needing the N61 → N71 OMS leg

        for sku in found_skus:
            # Check stock at source (using precomputed masks)
            mask = (loc_upper == source_code) & (sku_upper == sku)
            source_qty = int(df.loc[mask, 'STOCK_ON_HAND'].sum()) if mask.any() else 0

            if source_qty == 0:
                warnings.append(f"⚠️ {sku}: 0 units at {source_code}")
            elif qty > source_qty:
                warnings.append(f"⚠️ {sku}: only {source_qty} at {source_code}, pulling {qty}")

            if 'RETRIEVAL' in status_by_sku.get(sku, ''):
                warnings.append(f"⚠️ {sku}: Under Retrieval")

            # SR leg: source → N61 (Indonesia) or → N71 (everyone else)
            orders.append({
                "ORDERNAME": order_name,
                "TYPE": "TS",
                "RELEASE_TYPE": "",
                "SHIP_FROM": source_code,
                "SHIP_TO": sr_ship_to,
                "SKU": sku,
                "QTY": qty,
                "STOCK_CAT": "AVA",
                "STORAGE_LOC": "",
                "ALLOCATION_TYPE": "",
                "ALLOCATION_PRIORITY": "",
                "SPLIT_STRATEGY": "SPL",
                "MOT": "",
                "PRODUCT_FLAG": "",
                "START_DATE": "",
                "ANTICIPATION_DATE": "",
                "RELEASE_DATE": "",
                "SHIP_DATE": "",
                "EXPIRATION_DATE": expiration,
            })

            if is_indonesia:
                indonesia_legs.append(sku)

        # Indonesia: add OMS leg(s) N61 → N71 (one per SKU, shared order name)
        if indonesia_legs:
            oms_order_name = f"N61TON71{today_ddmmyy}"
            for sku in indonesia_legs:
                orders.append({
                    "ORDERNAME": oms_order_name,
                    "TYPE": "TS",
                    "RELEASE_TYPE": "RT",
                    "SHIP_FROM": "N61",
                    "SHIP_TO": "N71",
                    "SKU": sku,
                    "QTY": qty,
                    "STOCK_CAT": "AVA",
                    "STORAGE_LOC": "1100",
                    "ALLOCATION_TYPE": "BCO",
                    "ALLOCATION_PRIORITY": "0",
                    "SPLIT_STRATEGY": "SPL",
                    "MOT": "",
                    "PRODUCT_FLAG": "",
                    "START_DATE": "",
                    "ANTICIPATION_DATE": "",
                    "RELEASE_DATE": "",
                    "SHIP_DATE": "",
                    "EXPIRATION_DATE": oms_expiration,
                })

    # ── Summary ──
    source_strs = [f"{c} ({i['name']})" for c, i in sources]
    has_id = any(c in {"N63", "N64", "NB6"} for c, i in sources)
    dest_note = " (via N61 → N71)" if has_id else " → N71"
    summary = f"✅ SR: {len(orders)} line(s) — {', '.join(found_skus)} | {', '.join(source_strs)}{dest_note}"

    return {
        "success": True,
        "orders": orders,
        "warnings": warnings,
        "errors": [],
        "summary": summary,
    }


def generate_sr_csv(orders):
    """Generate CSV string from SR orders list (OMS-style format)."""
    if not orders:
        return None

    cols = ["ORDERNAME", "TYPE", "RELEASE_TYPE", "SHIP_FROM", "SHIP_TO", "SKU", "QTY",
            "STOCK_CAT", "STORAGE_LOC", "ALLOCATION_TYPE", "ALLOCATION_PRIORITY",
            "SPLIT_STRATEGY", "MOT", "PRODUCT_FLAG", "START_DATE", "ANTICIPATION_DATE",
            "RELEASE_DATE", "SHIP_DATE", "EXPIRATION_DATE"]

    lines = [",".join(cols)]
    for o in orders:
        lines.append(",".join(str(o.get(c, "")) for c in cols))

    return "\n".join(lines)


# ─────────────────────────────────────────────
# SR EMAIL TEMPLATE
# ─────────────────────────────────────────────

STORE_CONTACTS = {
    "L12": ["nicholas.mcpherson@louisvuitton.com"],
    "L45": ["luz-karime.caro@louisvuitton.com"],
    "L08": ["wen.zhang@louisvuitton.com", "jahmila.gensen@louisvuitton.com"],
    "X38": ["ruby.ho@louisvuitton.com", "kiran.vibhute@louisvuitton.com", "sarah.lee@louisvuitton.com"],
    "N63": ["treacia.tjahyadi@louisvuitton.com", "desyana.wang@louisvuitton.com", "stephanie.kosetio@louisvuitton.com", "yassir.mutaqin@louisvuitton.com"],
    "N64": ["ayu.lestari@louisvuitton.com", "melasari.isawan@louisvuitton.com", "donia.felicia@louisvuitton.com"],
    "NB6": ["jennifer.budiman@louisvuitton.com", "andina.octavia@louisvuitton.com"],
    "NXD": ["thuan.nguyen@louisvuitton.com", "tram.nguyenbao@louisvuitton.com"],
    "N46": ["thao.phung@louisvuitton.com"],
    "N53": ["sharon-ann.gray@louisvuitton.com"],
    "Y11": ["karthick.p@louisvuitton.com"],
    "N02": ["nikita.tarasov@louisvuitton.com"],
    "NQ6": ["jonathan.jong@louisvuitton.com", "elaine.soh@louisvuitton.com", "Lee.nicole@louisvuitton.com", "Noor-Jannah.nasir@louisvuitton.com"],
    "NX6": ["jonathan.jong@louisvuitton.com", "elaine.soh@louisvuitton.com", "weng-chung.ng@louisvuitton.com", "lennette.law@louisvuitton.com"],
    "NC3": ["sophie.zhou@louisvuitton.com", "ruppert.foo@louisvuitton.com", "mannde.wong@louisvuitton.com"],
    "N74": ["vivian.chia@louisvuitton.com", "vianney.oh@louisvuitton.com", "rathika.sundaram@louisvuitton.com", "darryl.khoo@louisvuitton.com", "sherry.li@louisvuitton.com"],
    "NF2": ["zoe.hsieh@louisvuitton.com", "phiqa.asari@louisvuitton.com", "juanjuan.jiang@louisvuitton.com"],
    "N69": ["carynne.tan@louisvuitton.com"],
    "NF5": ["kelvin.gan@louisvuitton.com"],
    "NYE": ["delong.tirapong@louisvuitton.com"],
    "N68": ["kristopher.toon@louisvuitton.com", "robin.koh@louisvuitton.com"],
    "NG6": ["patnaree.kritthipongsagul@louisvuitton.com"],
    "NAM": ["thanakorn.kaenchan@louisvuitton.com", "thanatchaphat.sajjaruk@louisvuitton.com"],
    "NVJ": ["munchusa.supasalingkarn@louisvuitton.com", "putthipong.sitthikulkiet@louisvuitton.com"],
    "NVQ": ["pintira.kittiratanasombat@louisvuitton.com"],
    "NX8": ["benjaporn.klongkarnngern@louisvuitton.com"],
    "NAB": ["yui.ngamying@louisvuitton.com"],
    "NYF": ["patnaree.kritthipongsagul@louisvuitton.com"],
}


def generate_sr_email(orders, df):
    """Generate email template for SR notification.

    Returns dict per source store with: to, cc, subject, body (HTML table).
    Email table columns: SKU, SKU DESCRIPTION, QTY, FROM, TO, DUE DATE.
    DUE DATE = expiration date (today + 4 days).
    """
    if not orders:
        return []

    # Exclude hub OMS legs (N61→N71, RELEASE_TYPE=RT) — stores only get notified of their SR action
    orders = [o for o in orders if o.get("RELEASE_TYPE", "") != "RT"]
    if not orders:
        return []

    # Precompute SKU → (description, universe) lookup ONCE (avoids repeated full-column str.upper())
    all_skus = {o["SKU"].upper() for o in orders}
    sku_info = {}
    sku_upper_col = df['SKU'].str.upper()
    for sku in all_skus:
        rows = df[sku_upper_col == sku]
        if len(rows) > 0:
            desc = str(rows.iloc[0].get('SKU_DESCRIPTION', ''))
            uni = str(rows.iloc[0].get('UNIVERSE', '')).upper() if 'UNIVERSE' in rows.columns else ''
            sku_info[sku] = (desc, uni)
        else:
            sku_info[sku] = ('', '')

    # Group orders by source store (SHIP_FROM)
    by_store = {}
    for o in orders:
        src = o["SHIP_FROM"]
        if src not in by_store:
            by_store[src] = []
        by_store[src].append(o)

    emails = []
    for store_code, store_orders in by_store.items():
        # To
        to = f"store_{store_code}@louisvuitton.com"

        # CC
        cc_list = STORE_CONTACTS.get(store_code, [])
        cc = "; ".join(cc_list)

        # Detect universe from SKUs (using precomputed lookup)
        universes = set()
        for o in store_orders:
            u = sku_info.get(o["SKU"].upper(), ('', ''))[1]
            if 'JEWELRY' in u:
                universes.add('Fine Jewelry')
            elif 'WATCH' in u:
                universes.add('Watches')

        if not universes:
            universe_str = "HJW"
        else:
            universe_str = " and ".join(sorted(universes))

        # Subject
        subject = f"{universe_str} SR ({store_code})"

        # Due date = expiration (YYYYMMDD → readable)
        exp = store_orders[0]["EXPIRATION_DATE"]
        try:
            exp_dt = datetime.strptime(str(exp), '%Y%m%d')
            due_str = exp_dt.strftime('%-d %b %Y')
            due_cell = exp_dt.strftime('%d/%m/%Y')
        except Exception:
            due_str = str(exp)
            due_cell = str(exp)

        # HTML table rows (using precomputed descriptions)
        table_rows_html = ""
        for o in store_orders:
            desc = sku_info.get(o["SKU"].upper(), ('', ''))[0]
            table_rows_html += f"""<tr>
<td style="border:1px solid #8db4e2;padding:4px 8px;font-size:11pt;">{o['SKU']}</td>
<td style="border:1px solid #8db4e2;padding:4px 8px;font-size:11pt;">{desc}</td>
<td style="border:1px solid #8db4e2;padding:4px 8px;font-size:11pt;text-align:center;">{o['QTY']}</td>
<td style="border:1px solid #8db4e2;padding:4px 8px;font-size:11pt;text-align:center;">{o['SHIP_FROM']}</td>
<td style="border:1px solid #8db4e2;padding:4px 8px;font-size:11pt;text-align:center;">{o['SHIP_TO']}</td>
<td style="border:1px solid #8db4e2;padding:4px 8px;font-size:11pt;text-align:center;">{due_cell}</td>
</tr>"""

        body_html = f"""<div style="font-family:Calibri,Arial,sans-serif;font-size:11pt;color:#333;">
Dear Team,<br><br>
The following SR has been uploaded. Please complete it by <b style="color:red;">{due_str}</b>.<br><br><br>
<table style="border-collapse:collapse;">
<tr>
<th style="border:1px solid #8db4e2;padding:4px 8px;background:#4472C4;color:white;font-size:11pt;">SKU</th>
<th style="border:1px solid #8db4e2;padding:4px 8px;background:#4472C4;color:white;font-size:11pt;">SKU DESCRIPTION</th>
<th style="border:1px solid #8db4e2;padding:4px 8px;background:#4472C4;color:white;font-size:11pt;">QTY</th>
<th style="border:1px solid #8db4e2;padding:4px 8px;background:#4472C4;color:white;font-size:11pt;">FROM</th>
<th style="border:1px solid #8db4e2;padding:4px 8px;background:#4472C4;color:white;font-size:11pt;">TO</th>
<th style="border:1px solid #8db4e2;padding:4px 8px;background:#4472C4;color:white;font-size:11pt;">DUE DATE</th>
</tr>
{table_rows_html}
</table>
<br>Thank you!
</div>"""

        emails.append({
            "to": to,
            "cc": cc,
            "subject": subject,
            "body_html": body_html,
            "store_code": store_code,
        })

    return emails




# ─────────────────────────────────────────────
# PR (PRODUCT REQUEST)
# ─────────────────────────────────────────────

PR_KEYWORDS = [' PR ']


def is_pr_request(question):
    """Check if user is asking for PR generation."""
    q = f" {' '.join(question.upper().split())} "
    if ' PR ' in q:
        return True
    if 'PRODUCT REQUEST' in q:
        return True
    return False


def parse_pr_request(question, df):
    """Parse a Product Request (store-to-store transfer) from natural language.

    Format: pr [destination] from [source] for [SKUs]
    Example: pr NC3 from NF2 for Q1TC10 Q03000

    OMS-style CSV. SHIP_FROM = source store, SHIP_TO = destination store.
    ORDERNAME = {source}TO{dest}{DDMONYY}  e.g. NF2TONC302JUNE26
    EXPIRATION_DATE = today + 5 days.
    """
    q = ' '.join(question.upper().split())
    all_skus_in_data = set(df['SKU'].str.upper().unique())
    store_code_set = set(STORE_CODES.keys())

    # ââ Find destination store (after "pr", before "from") ââ
    destination = None
    dest_info = None
    pr_match = re.search(r'\bPR\s+([A-Z0-9]{2,4})\b', q)
    if pr_match:
        code, info = resolve_store(pr_match.group(1))
        if code:
            destination = code
            dest_info = info
    if not destination:
        to_patterns = re.findall(r'\bTO\s+([A-Z0-9]{2,4})\b', q)
        for tp in to_patterns:
            code, info = resolve_store(tp)
            if code:
                destination = code
                dest_info = info
                break

    # ââ Find source store (after "from") ââ
    source = None
    source_info = None
    from_patterns = re.findall(r'\bFROM\s+([A-Z0-9]{2,4})\b', q)
    for fp in from_patterns:
        code, info = resolve_store(fp)
        if code and code != destination:
            source = code
            source_info = info
            break

    # ââ Find SKUs ââ
    candidates = re.findall(r'\b([A-Z0-9][A-Z0-9]{3,9})\b', q)
    found_skus = []
    for c in candidates:
        if c in all_skus_in_data and c not in store_code_set:
            if c not in found_skus:
                found_skus.append(c)

    # ââ Find quantity ââ
    qty = 1
    qty_match = re.search(r'\bQTY\s*(\d+)\b', q) or re.search(r'\b(\d+)\s*(?:UNITS?|PCS?|PIECES?|EACH)\b', q)
    if qty_match:
        qty = int(qty_match.group(1))

    # ââ Validate ââ
    errors = []
    warnings = []
    if not destination:
        errors.append("\u274c No destination store found. Use: 'pr NC3 from NF2 for Q1TC10'")
        return {"success": False, "orders": [], "warnings": [], "errors": errors, "summary": ""}
    if not source:
        errors.append("\u274c No source store found. Use: 'pr NC3 from NF2 for Q1TC10'")
        return {"success": False, "orders": [], "warnings": [], "errors": errors, "summary": ""}
    if not found_skus:
        errors.append("\u274c No valid SKUs found in your message.")
        return {"success": False, "orders": [], "warnings": [], "errors": errors, "summary": ""}

    # ââ Build orders (OMS-style CSV, store-to-store) ââ
    orders = []
    now = datetime.now()
    order_date = now.strftime('%d%B%y').upper()   # e.g. 02JUNE26
    order_name = f"{source}TO{destination}{order_date}"
    expiration = (now + timedelta(days=5)).strftime('%Y%m%d')

    # Precompute uppercase columns once
    sku_upper = df['SKU'].str.upper()
    loc_upper = df['LOCATION'].str.upper()

    for sku in found_skus:
        mask = (loc_upper == source) & (sku_upper == sku)
        source_qty = int(df.loc[mask, 'STOCK_ON_HAND'].sum()) if mask.any() else 0
        if source_qty == 0:
            warnings.append(f"\u26a0\ufe0f {sku}: 0 units at {source}")
        elif qty > source_qty:
            warnings.append(f"\u26a0\ufe0f {sku}: only {source_qty} at {source}, requesting {qty}")

        orders.append({
            "ORDERNAME": order_name,
            "TYPE": "TS",
            "RELEASE_TYPE": "",
            "SHIP_FROM": source,
            "SHIP_TO": destination,
            "SKU": sku,
            "QTY": qty,
            "STOCK_CAT": "AVA",
            "STORAGE_LOC": "",
            "ALLOCATION_TYPE": "",
            "ALLOCATION_PRIORITY": "",
            "SPLIT_STRATEGY": "SPL",
            "MOT": "",
            "PRODUCT_FLAG": "",
            "START_DATE": "",
            "ANTICIPATION_DATE": "",
            "RELEASE_DATE": "",
            "SHIP_DATE": "",
            "EXPIRATION_DATE": expiration,
        })

    # ââ Summary ââ
    dest_name = dest_info['name'] if dest_info else destination
    src_name = source_info['name'] if source_info else source
    summary = f"\u2705 PR: {len(orders)} line(s) \u2014 {', '.join(found_skus)} | {source} ({src_name}) \u2192 {destination} ({dest_name})"

    return {
        "success": True,
        "orders": orders,
        "warnings": warnings,
        "errors": [],
        "summary": summary,
    }


def generate_pr_csv(orders):
    """Generate CSV string from PR orders list (OMS-style format)."""
    if not orders:
        return None

    cols = ["ORDERNAME", "TYPE", "RELEASE_TYPE", "SHIP_FROM", "SHIP_TO", "SKU", "QTY",
            "STOCK_CAT", "STORAGE_LOC", "ALLOCATION_TYPE", "ALLOCATION_PRIORITY",
            "SPLIT_STRATEGY", "MOT", "PRODUCT_FLAG", "START_DATE", "ANTICIPATION_DATE",
            "RELEASE_DATE", "SHIP_DATE", "EXPIRATION_DATE"]

    lines = [",".join(cols)]
    for o in orders:
        lines.append(",".join(str(o.get(c, "")) for c in cols))

    return "\n".join(lines)


def generate_pr_email(orders, df):
    """Generate email template for PR notification.

    Goes to the source store (SHIP_FROM). Shows FROM source TO destination.
    Email table columns: SKU, SKU DESCRIPTION, QTY, FROM, TO, DUE DATE.
    DUE DATE = expiration date (today + 5 days).
    """
    if not orders:
        return []

    # Precompute SKU → (description, universe) lookup once
    all_skus = {o["SKU"].upper() for o in orders}
    sku_info = {}
    sku_upper_col = df['SKU'].str.upper()
    for sku in all_skus:
        rows = df[sku_upper_col == sku]
        if len(rows) > 0:
            desc = str(rows.iloc[0].get('SKU_DESCRIPTION', ''))
            uni = str(rows.iloc[0].get('UNIVERSE', '')).upper() if 'UNIVERSE' in rows.columns else ''
            sku_info[sku] = (desc, uni)
        else:
            sku_info[sku] = ('', '')

    # Group orders by source store (SHIP_FROM)
    by_store = {}
    for o in orders:
        src = o["SHIP_FROM"]
        by_store.setdefault(src, []).append(o)

    emails = []
    for store_code, store_orders in by_store.items():
        to = f"store_{store_code}@louisvuitton.com"
        cc_list = STORE_CONTACTS.get(store_code, [])
        cc = "; ".join(cc_list)

        # Universe detection
        universes = set()
        for o in store_orders:
            u = sku_info.get(o["SKU"].upper(), ('', ''))[1]
            if 'JEWELRY' in u:
                universes.add('Fine Jewelry')
            elif 'WATCH' in u:
                universes.add('Watches')
        universe_str = " and ".join(sorted(universes)) if universes else "HJW"

        # Destination (SHIP_TO) — same for all lines in a PR
        dest_code = store_orders[0]["SHIP_TO"]
        subject = f"{universe_str} Store Transfer ({store_code} → {dest_code})"

        # Due date = expiration
        exp = store_orders[0]["EXPIRATION_DATE"]
        try:
            exp_dt = datetime.strptime(str(exp), '%Y%m%d')
            due_str = exp_dt.strftime('%-d %b %Y')
            due_cell = exp_dt.strftime('%d/%m/%Y')
        except Exception:
            due_str = str(exp)
            due_cell = str(exp)

        # Table rows
        table_rows_html = ""
        for o in store_orders:
            desc = sku_info.get(o["SKU"].upper(), ('', ''))[0]
            table_rows_html += f"""<tr>
<td style="border:1px solid #8db4e2;padding:4px 8px;font-size:11pt;">{o['SKU']}</td>
<td style="border:1px solid #8db4e2;padding:4px 8px;font-size:11pt;">{desc}</td>
<td style="border:1px solid #8db4e2;padding:4px 8px;font-size:11pt;text-align:center;">{o['QTY']}</td>
<td style="border:1px solid #8db4e2;padding:4px 8px;font-size:11pt;text-align:center;">{o['SHIP_FROM']}</td>
<td style="border:1px solid #8db4e2;padding:4px 8px;font-size:11pt;text-align:center;">{o['SHIP_TO']}</td>
<td style="border:1px solid #8db4e2;padding:4px 8px;font-size:11pt;text-align:center;">{due_cell}</td>
</tr>"""

        body_html = f"""<div style="font-family:Calibri,Arial,sans-serif;font-size:11pt;color:#333;">
Dear Team,<br><br>
The following store transfer has been requested. Please complete it by <b style="color:red;">{due_str}</b>.<br><br><br>
<table style="border-collapse:collapse;">
<tr>
<th style="border:1px solid #8db4e2;padding:4px 8px;background:#4472C4;color:white;font-size:11pt;">SKU</th>
<th style="border:1px solid #8db4e2;padding:4px 8px;background:#4472C4;color:white;font-size:11pt;">SKU DESCRIPTION</th>
<th style="border:1px solid #8db4e2;padding:4px 8px;background:#4472C4;color:white;font-size:11pt;">QTY</th>
<th style="border:1px solid #8db4e2;padding:4px 8px;background:#4472C4;color:white;font-size:11pt;">FROM</th>
<th style="border:1px solid #8db4e2;padding:4px 8px;background:#4472C4;color:white;font-size:11pt;">TO</th>
<th style="border:1px solid #8db4e2;padding:4px 8px;background:#4472C4;color:white;font-size:11pt;">DUE DATE</th>
</tr>
{table_rows_html}
</table>
<br>Thank you!
</div>"""

        emails.append({
            "to": to,
            "cc": cc,
            "subject": subject,
            "body_html": body_html,
            "store_code": store_code,
        })

    return emails


# ─────────────────────────────────────────────
# BLOCK
# ─────────────────────────────────────────────

def is_block_request(question):
    """Check if user is asking for a Block. Requires 'block ... as ...' pattern."""
    q = f" {' '.join(question.upper().split())} "
    return bool(re.search(r'\bBLOCK\b', q)) and bool(re.search(r'\bAS\b', q))


def parse_block_request(question, df):
    """Parse a Block request from natural language.

    Format: block [SKUs] as [ordername]
    Example: block Q96413 Q03000 as PHcarnet

    OMS-style CSV. SHIP_FROM=N71, SHIP_TO=N65. Dates hardcoded.
    ORDERNAME = exactly what the user types after "as" (case preserved).
    """
    original = ' '.join(question.split())  # normalize whitespace, preserve case
    all_skus_in_data = set(df['SKU'].str.upper().unique())
    store_code_set = set(STORE_CODES.keys())

    # Extract order name: everything after "as" (case-insensitive), preserve original case
    m = re.search(r'\bas\b', original, re.IGNORECASE)
    order_name = original[m.end():].strip() if m else ""

    # Find SKUs only in the region BEFORE "as"
    sku_region = (original[:m.start()] if m else original).upper()
    candidates = re.findall(r'\b([A-Z0-9][A-Z0-9]{3,9})\b', sku_region)
    found_skus = []
    for c in candidates:
        if c in all_skus_in_data and c not in store_code_set:
            if c not in found_skus:
                found_skus.append(c)

    # Validate
    errors = []
    warnings = []
    if not order_name:
        errors.append("❌ No order name found. Use: 'block Q96413 as PHcarnet'")
        return {"success": False, "orders": [], "warnings": [], "errors": errors, "summary": ""}
    if not found_skus:
        errors.append("❌ No valid SKUs found in your message.")
        return {"success": False, "orders": [], "warnings": [], "errors": errors, "summary": ""}

    # Build orders (exact template format, only SKU + ORDERNAME vary)
    sku_upper = df['SKU'].str.upper()
    loc_upper = df['LOCATION'].str.upper()
    orders = []
    for sku in found_skus:
        mask = (loc_upper == 'N71') & (sku_upper == sku)
        n71_qty = int(df.loc[mask, 'STOCK_ON_HAND'].sum()) if mask.any() else 0
        if n71_qty == 0:
            warnings.append(f"⚠️ {sku}: 0 units at N71")

        orders.append({
            "ORDERNAME": order_name,
            "TYPE": "TS",
            "RELEASE_TYPE": "RT",
            "SHIP_FROM": "N71",
            "SHIP_TO": "N65",
            "SKU": sku,
            "QTY": 1,
            "STOCK_CAT": "",
            "STORAGE_LOC": "",
            "ALLOCATION_TYPE": "BCO",
            "ALLOCATION_PRIORITY": "0",
            "SPLIT_STRATEGY": "SPL",
            "MOT": "",
            "PRODUCT_FLAG": "",
            "START_DATE": "",
            "ANTICIPATION_DATE": "20290505",
            "RELEASE_DATE": "20290505",
            "SHIP_DATE": "",
            "EXPIRATION_DATE": "20290630",
        })

    summary = f"✅ Block: {len(orders)} line(s) — {', '.join(found_skus)} → N65 (order {order_name})"
    return {"success": True, "orders": orders, "warnings": warnings, "errors": [], "summary": summary}


def generate_block_csv(orders):
    """Generate CSV string from Block orders list (OMS-style format)."""
    if not orders:
        return None

    cols = ["ORDERNAME", "TYPE", "RELEASE_TYPE", "SHIP_FROM", "SHIP_TO", "SKU", "QTY",
            "STOCK_CAT", "STORAGE_LOC", "ALLOCATION_TYPE", "ALLOCATION_PRIORITY",
            "SPLIT_STRATEGY", "MOT", "PRODUCT_FLAG", "START_DATE", "ANTICIPATION_DATE",
            "RELEASE_DATE", "SHIP_DATE", "EXPIRATION_DATE"]

    lines = [",".join(cols)]
    for o in orders:
        lines.append(",".join(str(o.get(c, "")) for c in cols))

    return "\n".join(lines)
