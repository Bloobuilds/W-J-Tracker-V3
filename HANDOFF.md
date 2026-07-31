# HJW TRACKER — SOUTH ASIA (COMPLETE HANDOFF)
Last updated: 24 July 2026. This doc + the code files are the full state of the project.
THE CODE IS THE SOURCE OF TRUTH — this doc describes it.

## What this is
A multi-app Streamlit workspace for a luxury brand's High Jewelry & Watches (HJW) division,
South Asia Pacific market (Singapore N71 warehouse). One user (supply chain planner) uploads
a weekly stock Excel; every app in the workspace reads that one file.

Apps currently in the switcher (sidebar radio, `APPS` in app.py):
1. **Stock Report** — view/filter stock, ask an AI questions, generate transfer documents
   (OMS / SR / PR / Block) with matching notification emails.
2. **Event Management** — track a pasted SKU list against an event date and venue; get a
   readiness brief and one-click document generation for whatever is missing.

## ARCHITECTURE RULE (read before adding app #3)
**Never use `st.tabs`.** Streamlit renders every tab body on every rerun whether visible or
not. That is what made the old Rebalance tab slow and why it was deleted. Apps are dispatched
with a sidebar radio in `main()` — only the selected branch executes.

Layering, which must be preserved:
- `stores.py` owns **every** CSV format, store code and email template. Single source of truth.
- `events.py` owns event logic. It does NOT build CSV rows — it builds command strings
  (`"sr from N63 for Q03039"`) and calls the stores.py parsers. Fixes to stores.py therefore
  propagate to Event Management for free.
- `event_app.py` is Streamlit only — no business logic.
- `app.py` holds the Stock Report UI, chat routing, Gemini client, and the app switcher.

## DEPLOYMENT (current: Railway)
- Hosted on **Railway**. GitHub repo → Railway auto-deploys on push.
- `Procfile` (required): `web: streamlit run app.py --server.port $PORT --server.address 0.0.0.0 --server.headless true`
- Environment variable in Railway → Variables: `GEMINI_API_KEY` (get_api_key() falls back from
  st.secrets to os.environ, so it works on both Streamlit Cloud and Railway).
- `.streamlit/config.toml` sets the navy theme (primaryColor #1a1a2e).
- `requests` was removed from requirements.txt on 24 Jul 2026 — it was a leftover from the
  deleted GitHub counter sync and is imported nowhere. `pyarrow` was added 27 Jul 2026 for
  parquet.

### PERSISTENCE (added 27 Jul 2026)
Data now survives refreshes AND redeploys, via a Railway **volume**. Railway's container
filesystem is ephemeral — anything written outside a mounted volume is wiped on every deploy.

**Required Railway setup:**
1. Create a volume, mount path `/data`.
2. Variables: `DATA_DIR=/data`, `APP_PASSWORD=<something>`, plus the existing `GEMINI_API_KEY`.
3. If the app can't write to the volume, set `RAILWAY_RUN_UID=0` — volumes mount as root and a
   non-root container user won't have write access.

`storage.py` is the single persistence layer for the whole workspace; apps call
`load_json`/`save_json`/`save_dataframe` and know nothing about the backend. Swapping to SQLite
or Postgres later means rewriting that one file. All writes are atomic (temp file + `os.replace`)
so a crash or redeploy mid-write can't leave a truncated file.

What is stored, under `DATA_DIR`:
- `stock_current.parquet` + `stock_current_meta.json` — the parsed weekly file. 15,412 rows =
  ~210KB parquet vs 1.28MB xlsx, and reloads in 0.05s vs 2.2s to re-parse the Excel (~42x).
  Saved on upload, restored once per session by `restore_stock()`.
- `events.json` — the event list, written by `event_app.persist_events()` after every mutation
  (create, edit, delete, import, inline table edit).

If `DATA_DIR` is unwritable the app falls back to `./.localdata` and shows a **warning in the
sidebar** — that fallback does NOT survive a redeploy. Never ignore that warning in production.

A guarded "Clear stored data" control sits in the sidebar footer (two-step confirm).

**Only the current week's file is kept** — each upload overwrites the last. Retaining snapshots
is the prerequisite for week-over-week diffing (see Roadmap).

### SECURITY
`auth.py` gates the app behind a shared password (`APP_PASSWORD`), checked with
`hmac.compare_digest` at the very top of `main()` before any widget renders. If `APP_PASSWORD`
is unset the app stays open and shows a warning — locking the planner out of their own deploy
over a missing env var would be worse, but never run production without it.

Scope: one shared credential stops crawlers and accidental discovery. It gives **no** per-person
accounts, audit trail, or revocation. When someone else needs access, or IT asks where the data
lives, the answer is `st.login()` OIDC against the corporate tenant — not this.

Still true regardless of the gate: an authenticated user can use the Gemini chat freely (your
key, your bill), extract every address in `STORE_CONTACTS` via a crafted SR, and read the store
taxonomy out of the system prompt. Now that data persists server-side, a visitor who gets past
the gate lands on populated data rather than an empty shell.

## FILES
- `app.py` — Stock Report UI, AI chat, message routing, table, app switcher, storage footer
- `stores.py` (~1,040 lines) — store codes, aliases, contacts, all document generators
- `events.py` — Event Management engine (pure Python, no Streamlit)
- `event_app.py` — Event Management UI
- `storage.py` — durable storage for every app (JSON + parquet on a Railway volume)
- `auth.py` — shared-password gate
- `requirements.txt`, `Procfile`, `.streamlit/config.toml`, `.gitignore`

## DATA
Weekly Excel upload. As of 24JULY.xlsx: **15,412 rows, 24 cols, 2,889 SKUs, 70 locations**
(the old handoff said ~8,000 rows — that was stale). Key columns: SKU, SKU_DESCRIPTION,
SKU_GROUP, UNIVERSE (FINE JEWELRY/WATCHES), COUNTRY, LOCATION, SEGMENT, FAMILY, THEME,
SUB_THEME, GENDER, LOGISTIC_STATUS, VALIDATED_FRP (retail price), STOCK_ON_HAND, TRANSIT,
PICKING, RESERVATION, AUTOREP_MAX, CLIENT_ORDER_STOCK, PENDING_ORDER_DETAIL, SIZE,
SKU_LONG_CODE, LAUNCH_DATE.
Computed on load: STOCK_VALUE = FRP×STOCK_ON_HAND, TRANSIT_VALUE, TOTAL_UNITS
(stock+transit+picking+reservation). Rows with TOTAL_UNITS=0 are always hidden in the table.
Unique key is SKU + LOCATION (verified: zero duplicates).
Table always sorts Singapore first, then country/location/SKU.

LOGISTIC_STATUS values: "DISTRIBUTION - NIP (CEN)"=active, "PRODUCTION STOPPED (CEN)"=discontinued,
"RETRIEVAL (CEN)"=recalled, **"INDUSTRIALISATION (CEN)"** (1 row — not yet in SYSTEM_PROMPT,
so the AI will improvise if asked about it).

### KNOWN DATA GAPS / BUGS
- **14 LOCATION codes in the data are missing from `STORE_CODES`**: L22, L40, L43, L46, L50,
  N82, NF6, NO2, NVF, NYA, NYC, SGZ, Y02, Y09. SR/PR/OMS involving these will fail at
  `resolve_store`. Note `NO2` vs the existing `N02` (Manila Greenbelt) — verify whether that
  is a source-system typo or a genuinely missing store.
- `LAUNCH_DATE` (YYYYMMDD ints, ~4,300 rows populated, contains future dates e.g. 20260918 on
  7 SKUs, and a 19000101 sentinel) is **used nowhere**. Best unexploited column in the file.
- `CLIENT_ORDER_STOCK` / `PENDING_ORDER_DETAIL` are populated on only 173 rows.
- **No ETA anywhere.** TRANSIT gives a count, never an arrival date. Any "when does it land"
  feature requires week-over-week snapshot diffing (see Roadmap).
- `resolve_store` over-matches short tokens: its final fallback `t in info["name"]` means
  "to the ..." resolves THE → NAM (LV BANGKOK THE PLACE). Same risk with the 2-char alias PI.
- `is_pr_request` does not require FROM, so "what is the PR process" routes into the PR parser
  and errors instead of reaching the AI.
- Dead code: `result.get("needs_counter")` in app.py's SR branch, unused `SR_KEYWORDS` /
  `PR_KEYWORDS`, and `detect_stock_summary_request` is called twice in the check-6 condition.

## APP 1 — STOCK REPORT

### UI LAYOUT
Left ~60%: search bar, Extra cols toggle, table, CSV download.
Right ~40%: Ask AI chat (580px box) + chat input + download buttons + Clear chat.
Sidebar: Excel upload, app switcher, then multiselect filters (Universe, Country, Location,
Segment, Family, Logistic Status). Sidebar filters HARD-filter both table and AI data.
AI filter banner (yellow) appears above table when a chat action filters it; Export + Clear.
Chat bubble colors: gray=user, green=AI, purple=OMS/SR/PR/Block confirmations, yellow=warnings,
red=errors, blue=email templates (with Copy button).
Custom CSS hides Streamlit's default loading animations; user message renders instantly,
processing runs AFTER chat renders (two-phase: pending_question → rerun → process → rerun).

### Table (st.dataframe) — Excel-like selection sums
- on_select="rerun", selection_mode=["multi-column","multi-cell"] (NO multi-row: user wanted
  no checkbox column).
- Drag cells → status bar bottom-right: "Average | Count | Sum". Money columns ($) formatted.
  Click a column header → whole-column Sum·Avg over visible rows.
- Number formatting via st.column_config (NOT pandas Styler — cost ~0.7s/render on 8k rows).
- NOTE: Streamlit has NO native per-column header filter. User explicitly rejected a filter
  expander panel and AgGrid. Do not re-suggest without new info.

### CHAT MESSAGE ROUTING (the core architecture)
Every chat message goes through this Python check chain in app.py. Only the LAST step calls AI.
All checks normalize whitespace/newlines before keyword matching (multi-line messages work).
1. **OMS** — keywords: OMS / TRANSFER ORDER / SEND TO / SHIP TO / MOVE TO
2. **SR** — " SR " as word, or STORE REVERSE
3. **PR** — " PR " as word (see bug above: FROM is not actually required)
4. **Block** — "block" + "as"
5. **Find** — "find" + valid SKUs → instant lookup summary
6. **Stock summary** — "how much stock/total stock/stock value/..." + optional location code /
   alias / country → instant Python totals. Skipped if the message contains SKUs.
7. **AI** — everything else → Gemini "gemini-3.5-flash", STREAMING word-by-word with ▌ cursor.

SKU detection (all parsers): regex `\b([A-Z0-9][A-Z0-9]{3,9})\b` matched against actual data
SKUs, excluding store codes. Quantity: "qty N" or "N units/pcs" (default 1).

### AI FEATURES
- Model: gemini-3.5-flash via google-generativeai. Streaming (ask_gemini_stream generator);
  non-streaming ask_gemini kept as fallback/unused.
- System prompt includes column definitions, business terms, all store codes + aliases,
  response rules (2-3 sentences, no tables, exact numbers).
- Conversation memory: last 3 user/assistant exchanges (oms/warn/email excluded; 400 char cap).
- Pre-computed facts: Python calculates totals, dead-stock value/SKUs, transit, single-unit SKU
  count, top-5 by value → injected as "PRE-COMPUTED FACTS (use these exact numbers)".
- Intent-based context: question classified (dead_stock/high_value/low_stock/transit/low_value)
  → the right 40 rows sent instead of a random sample. Cap 80 rows total.
- Every AI reply must end with [TABLE_FILTER]col:value,...[/TABLE_FILTER] (or ALL) → parsed by
  parse_table_filter() to filter the main table. SKUs in the question override with a direct
  SKU filter. TABLE_FILTER hidden from display during streaming.

## APP 2 — EVENT MANAGEMENT

### Concept
An event = name + start date (+ optional end date) + venue + pasted SKU list.
The start date is stored under the key **`event_date`** (not renamed, so events saved before
end dates existed still load); the optional end is `end_date`, "" when unset. All deadlines run
off the START date — stock has to be there for day one. `date_range_label()` renders
"28 Aug", "28–30 Aug", or "28 Aug – 2 Sep". Venue is either a **store code** (goods move
N71 → store, an OMS) or a **block** (goods move N71 → N65 under a custom ORDERNAME).
Deadline rule: everything must be ready to send `READY_LEAD_DAYS` (=7) before the event date.

### Statuses (events.py, worst-first — this order drives the brief and the table sort)
| Status | Meaning |
|---|---|
| BLOCKED | LOGISTIC_STATUS contains RETRIEVAL — must not ship |
| MISSING | SKU not in this week's file at all |
| NO STOCK | in the file, zero free units anywhere |
| ELSEWHERE | free units exist, but at the wrong location |
| COMMITTED | at N71 but all units picking/reserved |
| INBOUND | in transit to N71 (no ETA available — see data gaps) |
| READY | free at N71 |
| AT VENUE | already at the venue store, nothing to do |

"Free" = STOCK_ON_HAND − PICKING − RESERVATION, floored at 0.

### Sidebar
Events are an always-visible list (not a dropdown), sorted by start date ascending, so an
overdue event sorts to the top. Each row shows the name and the date range. The urgency word is
appended only when it is NOT "ON TRACK", so the list stays quiet until something needs
attention. Active event is the primary-styled button. On load the soonest event opens, not the
first created.

**No country flags in the UI.** They were tried and removed: flag emoji are pairs of
regional-indicator letters, and Windows renders them as the bare two-letter code — 🇸🇬 shows as
"SG" — so they read as noise. `COUNTRY_FLAGS` / `country_flag` / `store_flag` (stores.py) and
`event_flag` (events.py) are kept but unused; re-enabling is one line if the app is ever used
on macOS/iOS/Android, which render them properly. Do not re-add without checking the target
platform.

### Action planning
`plan_actions()` groups the analysis into runnable commands, `run_action()` executes them
through stores.py:
- READY + store venue → `oms to {venue} for {skus}`
- READY + block venue → `block {skus} as {block_name}`
- ELSEWHERE, route SR (default) → BOTH legs in one file:
  store venue → `sr from {src} for {skus} and send to {venue}`
  block venue → `sr from {src} for {skus} and block as {block_name}`
- ELSEWHERE, route PR → `pr {venue} from {src} for {skus}` (direct store-to-store)
Every action carries a **`doc`** field naming the document it produces ("OMS", "PR", "Block",
"SR + OMS", "SR + Block"). That drives the button ("Generate SR + OMS"), the download label and
the filename (`SR_OMS_310726.csv`) — so a two-leg action never claims to be just an SR.

The Route column offers SR/PR for store venues only. For a block venue it stays hidden and
everything routes via N71, because a block is by definition an N71→N65 movement — there is no
"direct to block" process. Revisit if that turns out to be wrong.
Source ranking: Singapore first, then most free units. `NON_SOURCE_LOCATIONS` excludes the
warehouse, block location, repair centre and RDCs. Ecom/CS locations are still selectable —
no policy decision has been made on those.

### Persistence
Events live in **session state only**, with Save/Load JSON buttons so the planner keeps their
own file. Nothing is written server-side — deliberately, because the volume/retention decision
is still open (see Security). Swapping in disk persistence touches only
`events_to_json`/`events_from_json` and the sidebar.

### Guards
- Block names containing " as " or a comma are rejected at save time (both break the
  block command or the CSV).
- N71 cannot be chosen as a venue.
- Blank event names are rejected.
- The event app reads the **full** dataframe, deliberately ignoring the Stock Report's sidebar
  filters — an event plan must see every location.

## DOCUMENT GENERATORS (stores.py) — all CSV with these 19 columns:
ORDERNAME,TYPE,RELEASE_TYPE,SHIP_FROM,SHIP_TO,SKU,QTY,STOCK_CAT,STORAGE_LOC,ALLOCATION_TYPE,
ALLOCATION_PRIORITY,SPLIT_STRATEGY,MOT,PRODUCT_FLAG,START_DATE,ANTICIPATION_DATE,RELEASE_DATE,
SHIP_DATE,EXPIRATION_DATE

**OMS** (N71 → store). Cmd: `oms to NC3 for Q03000` (aliases work: "to Ion")
Row: SGTO{dest}{DDMMYY},TS,RT,N71,{dest},{sku},{qty},AVA,1100,BCO,0,SPL,,,,,,,**20261010**
Warns: 0 stock at N71, qty>stock, production stopped, retrieval.

**SR** (store → N71). Cmd: `sr from NG6 for Q03024`
Row: {src}SR{DDMMYY},TS,,{src},N71,{sku},{qty},AVA,,,,SPL,,,,,,,{today+4 as YYYYMMDD}
**Indonesia hub rule**: sources N63/N64/NB6 generate TWO rows per SKU:
  1. {src}SR{DDMMYY}: src → **N61** (SR format, today+4)
  2. N61TON71{DDMMYY}: N61 → N71 (OMS format: RT,1100,BCO,0, expiration **20261010**)
SR auto-generates a notification email per source store (blue bubble, Copy button):
to store_{code}@louisvuitton.com, cc from STORE_CONTACTS, subject "{Universe} SR ({code})",
HTML table (blue #4472C4 header): SKU | SKU DESCRIPTION | QTY | FROM | TO | DUE DATE.
Email EXCLUDES the Indonesia N61→N71 leg (stores only see their own action).

**SR + ONWARD LEG** (added 31 Jul 2026). One file, two movements.
Cmd: `Q03039 sr from NF2 and send to N74` → SR leg NF2→N71, then OMS leg N71→N74
(ORDERNAME `SGTO{dest}{DDMMYY}`, RT/1100/BCO/0, expiration 20261010).
Cmd: `Q03039 sr from NF2 and block as PHcarnet` → SR leg, then the block row N71→N65.
Also callable directly: `parse_sr_request(q, df, forward_to="N74")` or `forward_block="PHcarnet"`
— Event Management uses that path. Markers recognised: SEND/SHIP/MOVE/OMS TO, optionally
prefixed AND/THEN. Destination resolves by code or alias. "send to N71" is treated as no
onward leg, since an SR already ends there.
Indonesia sources stack correctly: N63 + forward = 3 legs (N63→N61, N61→N71, N71→dest).
Email still goes to the source store only — the exclusion filter drops any RELEASE_TYPE=RT
leg, which covers both the hub leg and the new onward leg.
**ROUTING**: `is_sr_forward_request()` MUST be checked before OMS — "SEND TO" is an OMS
keyword, so app.py's check 1 reads `is_oms_request(pq) and not is_sr_forward_request(pq, df)`.
Without that exclusion the combined command is swallowed by the OMS parser.
Known edge: "sr ... send to N71" (redundant phrasing) still routes to OMS.

**PR** (store → store). Cmd: `pr NC3 from NF2 for Q1TC10`
Row: {src}TO{dest}{DDMONYY} (e.g. NF2TONC302JUNE26),TS,,{src},{dest},{sku},{qty},AVA,,,,SPL,,,,,,,{today+5}
PR email: to source store, subject "{Universe} Store Transfer ({src} → {dest})", same table.

**Block** (N71 → N65). Cmd: `block Q96413 Q03000 as PHcarnet`
ORDERNAME = EXACTLY what user typed after "as" (case preserved). All SKUs share it.
Row: {name},TS,RT,N71,N65,{sku},1,,,BCO,0,SPL,,,,20290505,20290505,,20290630 (dates hardcoded).
Detection needs both "block" AND "as" (so "what is block location" still goes to AI).

## STORES (stores.py)
- STORE_CODES: 67 locations, 12 countries. Warehouse=N71. Special SG: N7X (WH CARNET),
  SG11 (REPAIR CENTER), N65 (BLOCK LOCATION). Indonesia hub: N61. **14 codes present in the
  data are missing from this dict — see Known Data Gaps.**
- STORE_ALIASES: natural names (ION→NC3, PLAZA INDONESIA→N63, MBS→NF2, PAVILION→N68...).
- STORE_CONTACTS: cc emails per store. ~50 real addresses live in source. Moving these to a
  runtime config file is a standing recommendation — it keeps PII out of permanent git history
  and lets contacts be updated without a deploy.

## PERFORMANCE LESSONS (do not regress)
- NEVER use pandas Styler on the big table (0.7s/render) — use st.column_config.
- Precompute .str.upper() columns ONCE per parse, not per SKU (was the SR slowness bug).
- Whole-page reruns happen on every interaction; keep per-render work light.
- Big system prompt = slower Gemini; keep additions lean.
- Never `st.tabs`. See Architecture Rule.
- The Stock Report search re-scans every object column on every keystroke — next perf hotspot.

## HISTORY / DECISIONS (so you don't re-litigate)
- Streamlit Cloud → Railway (Procfile + env var pattern).
- Old SR format (W{week}_PR_JWL_{MMYY}_{counter} xlsx with GitHub-synced counter) was fully
  REPLACED by the CSV format above; counter/week/GitHub sync all removed.
- PR was originally an xlsx template; replaced by the CSV store-transfer format above.
- OMS expiration was 20260404 → 20260707 → now 20261010.
- A Rebalance tab was built then REMOVED entirely (tabs render both panes every rerun).
- Excel-like features: filter expander → rejected; AgGrid header filters → reverted;
  final solution = native multi-cell selection sums (Streamlit ≥1.59), no row checkboxes.
- Sales/aging/cost columns identified as the dataset's biggest gaps; no sales feed exists.
- 24 Jul 2026: single-app → multi-app workspace. Event Management added. `render_sidebar` split
  into `render_upload` + `render_stock_filters`. Re-upload bug fixed (previously the second
  upload of a session was ignored until refresh; now keyed on filename+size).
- 27 Jul 2026: persistence + auth. `storage.py` (volume-backed JSON + parquet) and `auth.py`
  (shared password) added. Events and the weekly stock file now survive refresh and redeploy.
  Per-SKU notes and per-row SR/PR route overrides added to the event model. Fixed: the `New`
  event button was unusable (the sidebar picker reassigned the active event and cancelled the
  draft); the venue dropdown offered N65/N7X/SG11/RDCs as venues and defaulted to N65, the
  block location; `select_dtypes(include="object")` in the table search would silently match
  nothing once pandas removes the str-under-object fallback.
- 31 Jul 2026: SR with an onward leg (SR+OMS / SR+Block in one file); Event Management's SR
  route now generates both legs instead of leaving the OMS to be done by hand. Event dropdown
  replaced by a date-sorted always-visible list. Fixed: a comma in a block ORDERNAME produced a
  20-column row against a 19-column header — silently malformed CSV, in BOTH the new combined
  command and the pre-existing standalone `block` command; now rejected with a clear error.
  Added warnings for an unresolved onward destination and for source == destination.
- 31 Jul 2026 (later): events gained an optional end date; sidebar dots replaced by venue
  country flags with the urgency word shown only when not ON TRACK; action buttons and
  filenames now name the actual document ("Generate SR + OMS"); event name threaded into SR/PR
  notification emails; email sign-off changed to "Thank you for your support!".
- Country flags in the event list: added then removed same day — they render as "SG"/"ID" text
  on Windows. Helpers kept, UI usage removed. Don't re-litigate without a non-Windows client.
- User prefers: talk/plan first before building; concise chat replies; instant Python over AI
  wherever deterministic.

## KNOWN LIMITATIONS
- Two browser tabs open at once = last-write-wins on the events file.
- Only the current week's stock file is retained; each upload overwrites the last.
- Railway won't mount one volume to two deployments at once, so redeploys now have a brief
  window of downtime.
- AI chat sends up to ~80 data rows to Google's Gemini API.
- No header-based column filtering (Streamlit limitation).
- No tests; parsers share duplicated extraction logic (refactor candidate).
- Sorting the table clears cell selections (Streamlit behavior).
- The Event brief refreshes on open/upload only. A real scheduled daily push needs a separate
  Railway cron service — Streamlit only runs while a browser session is open.

## ROADMAP / NEXT
1. **Week-over-week snapshot diffing.** Keep each weekly upload (currently only the latest is
   retained); arrival at N71 = TRANSIT 1→0 while STOCK_ON_HAND 0→1. Turns INBOUND from "1
   coming, no idea when" into "arrived Tuesday", and finally gives an aging signal. The volume
   and auth groundwork is now in place — this needs a retention policy and a snapshot namespace.
2. Add the 14 missing store codes; resolve the NO2/N02 question.
3. Surface LAUNCH_DATE — a launch calendar is directly useful to event planning.
4. Cross-app AI ("which event SKUs do we actually have stock for") once each app exposes a
   clean summary interface.
