# -*- coding: utf-8 -*-
"""
storage.py — persistence for the whole workspace
================================================
One place where every app reads and writes durable state, so app #3 and #4
don't each invent their own scheme.

Railway's container filesystem is EPHEMERAL: anything written outside a mounted
volume disappears on the next deploy or restart. This module therefore writes
to DATA_DIR, which on Railway must point at a mounted volume (e.g. /data).
Locally it falls back to ./.localdata so the app runs unchanged off-Railway.

Two kinds of state, deliberately stored differently:
  - JSON  — small structured things (events). Human-readable and debuggable.
  - Parquet — the weekly stock dataframe. 15k rows compress to ~1MB and reload
    in a fraction of the time it takes to re-parse the source Excel.

Every write is atomic (temp file + os.replace, which is atomic on POSIX), so a
crash or a redeploy mid-write can never leave a half-written file behind.

Swapping to SQLite or Postgres later means rewriting this file only — the apps
call load_json / save_json / save_dataframe and know nothing about the backend.
"""

import json
import os
import shutil
import tempfile
from datetime import datetime

import pandas as pd

# Railway: set DATA_DIR to the volume mount path (e.g. /data).
DEFAULT_DIR = os.environ.get("DATA_DIR", "/data")
FALLBACK_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".localdata")

_resolved_dir = None
_last_error = None


# ─────────────────────────────────────────────
# LOCATION
# ─────────────────────────────────────────────

def _writable(path):
    """True if we can actually create and write files in `path`."""
    try:
        os.makedirs(path, exist_ok=True)
        probe = os.path.join(path, ".write_probe")
        with open(probe, "w") as fh:
            fh.write("ok")
        os.remove(probe)
        return True
    except Exception as exc:
        global _last_error
        _last_error = f"{type(exc).__name__}: {exc}"
        return False


def data_dir():
    """Resolve the storage directory once per process.

    Prefers DATA_DIR (the Railway volume). Falls back to a local folder so the
    app still runs when no volume is attached — but see is_persistent(): the
    fallback does NOT survive a redeploy.
    """
    global _resolved_dir
    if _resolved_dir is not None:
        return _resolved_dir
    if _writable(DEFAULT_DIR):
        _resolved_dir = DEFAULT_DIR
    else:
        os.makedirs(FALLBACK_DIR, exist_ok=True)
        _resolved_dir = FALLBACK_DIR
    return _resolved_dir


def is_persistent():
    """True when writing to the configured DATA_DIR (i.e. a real volume).

    False means we fell back to container-local disk, which Railway wipes on
    every deploy. The UI surfaces this so nobody trusts storage that isn't
    actually durable.
    """
    return data_dir() == DEFAULT_DIR


def storage_status():
    """Human-readable status for the UI."""
    return {
        "dir": data_dir(),
        "persistent": is_persistent(),
        "error": _last_error,
    }


def _path(name, ext):
    safe = "".join(c for c in str(name) if c.isalnum() or c in "-_")
    return os.path.join(data_dir(), f"{safe}.{ext}")


# ─────────────────────────────────────────────
# ATOMIC WRITE
# ─────────────────────────────────────────────

def _atomic_write(path, write_fn):
    """Write via a temp file in the same directory, then rename over the target.

    os.replace is atomic on POSIX, so readers see either the old file or the
    new one — never a truncated one.
    """
    directory = os.path.dirname(path)
    fd, tmp = tempfile.mkstemp(dir=directory, suffix=".tmp")
    os.close(fd)
    try:
        write_fn(tmp)
        os.replace(tmp, path)
        return True
    except Exception:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


# ─────────────────────────────────────────────
# JSON
# ─────────────────────────────────────────────

def save_json(namespace, data):
    """Persist a JSON-serialisable object. Returns True on success."""
    path = _path(namespace, "json")

    def _write(tmp):
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)

    try:
        _atomic_write(path, _write)
        return True
    except Exception as exc:
        global _last_error
        _last_error = f"save_json({namespace}): {exc}"
        return False


def load_json(namespace, default=None):
    """Read a JSON object back. Returns `default` if absent or unreadable."""
    path = _path(namespace, "json")
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception as exc:
        global _last_error
        _last_error = f"load_json({namespace}): {exc}"
        return default


# ─────────────────────────────────────────────
# DATAFRAMES
# ─────────────────────────────────────────────

def save_dataframe(name, df, meta=None):
    """Persist a dataframe as parquet, plus a small JSON sidecar of metadata.

    The sidecar records the original filename and upload time so the UI can
    tell the planner what they are looking at after a refresh.
    """
    path = _path(name, "parquet")

    def _write(tmp):
        df.to_parquet(tmp, index=False)

    try:
        _atomic_write(path, _write)
    except Exception as exc:
        global _last_error
        _last_error = f"save_dataframe({name}): {exc}"
        return False

    info = dict(meta or {})
    info.update({
        "saved_at": datetime.now().isoformat(timespec="seconds"),
        "rows": int(len(df)),
    })
    save_json(f"{name}_meta", info)
    return True


def load_dataframe(name):
    """Read a dataframe back, or None if it isn't there / can't be read."""
    path = _path(name, "parquet")
    if not os.path.exists(path):
        return None
    try:
        return pd.read_parquet(path)
    except Exception as exc:
        global _last_error
        _last_error = f"load_dataframe({name}): {exc}"
        return None


def dataframe_meta(name):
    return load_json(f"{name}_meta", None)


# ─────────────────────────────────────────────
# HOUSEKEEPING
# ─────────────────────────────────────────────

def delete(namespace):
    """Remove everything stored under a namespace."""
    removed = False
    for ext in ("json", "parquet"):
        path = _path(namespace, ext)
        if os.path.exists(path):
            try:
                os.remove(path)
                removed = True
            except OSError:
                pass
    meta = _path(f"{namespace}_meta", "json")
    if os.path.exists(meta):
        try:
            os.remove(meta)
        except OSError:
            pass
    return removed


def usage():
    """Total bytes stored, for the sidebar readout."""
    total = 0
    try:
        for entry in os.scandir(data_dir()):
            if entry.is_file():
                total += entry.stat().st_size
    except OSError:
        pass
    return total


def wipe_all():
    """Delete everything. Used by the sidebar reset button."""
    try:
        shutil.rmtree(data_dir(), ignore_errors=True)
        os.makedirs(data_dir(), exist_ok=True)
        return True
    except Exception:
        return False
