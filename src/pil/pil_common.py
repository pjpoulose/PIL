#!/usr/bin/env python3
"""Shared config + helpers for the PIL (Personal Instagram Library) skill.

Config resolution order:
  1. PIL_CONFIG env var (path to a JSON config file)
  2. ./pil.config.json (current working directory)
  3. ~/.config/pil/pil.config.json

Config keys: {"account_id": "<instagram user_fbid>", "data_dir": "<dir for pil.sqlite>"}
data_dir defaults to ~/.local/share/pil when absent.
"""
import json
import os
import sqlite3

def _find_schema():
    """Locate schema.sql: installed package data first, repo checkout fallback."""
    try:
        from importlib.resources import files
        cand = files("pil") / "data" / "schema.sql"
        if cand.is_file():
            return str(cand)
    except Exception:
        pass
    # repo checkout fallback (src/pil -> repo root)
    here = os.path.dirname(os.path.abspath(__file__))
    for cand in (
        os.path.join(here, "data", "schema.sql"),
        os.path.abspath(os.path.join(here, "..", "..", "schema.sql")),
    ):
        if os.path.isfile(cand):
            return cand
    raise SystemExit("PIL schema.sql not found (looked in package data and repo root).")


SCHEMA_PATH = _find_schema()


def load_config():
    path = os.environ.get("PIL_CONFIG")
    candidates = [path] if path else []
    candidates += [
        os.path.join(os.getcwd(), "pil.config.json"),
        os.path.expanduser("~/.config/pil/pil.config.json"),
    ]
    cfg = {}
    for c in candidates:
        if c and os.path.exists(c):
            try:
                with open(c) as f:
                    cfg = json.load(f)
            except json.JSONDecodeError as e:
                raise SystemExit(f"PIL config is not valid JSON: {c}\n{e}")
            break
    data_dir = os.path.expanduser(cfg.get("data_dir") or "~/.local/share/pil")
    os.makedirs(data_dir, exist_ok=True)
    return {
        "account_id": cfg.get("account_id") or os.environ.get("PIL_ACCOUNT_ID"),
        "data_dir": data_dir,
        "db_path": os.path.join(data_dir, "pil.sqlite"),
        "config": cfg,  # full raw config (e.g. "publish" section); never logged
    }


def db_connect(cfg, read_only=False):
    """Connect to the PIL database, applying schema.sql on first creation.

    read_only=True opens with SQLite URI mode=ro: the connection cannot write,
    used by the MCP server to guarantee read-only access.
    """
    db_path = cfg["db_path"]
    fresh = not os.path.exists(db_path)
    if read_only:
        db = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    else:
        db = sqlite3.connect(db_path)
    if fresh:
        with open(SCHEMA_PATH) as f:
            db.executescript(f.read())
        db.commit()
    db.row_factory = sqlite3.Row
    return db


def require_account(cfg):
    acct = cfg.get("account_id")
    if not acct or acct == "YOUR_INSTAGRAM_USER_FBID":
        raise SystemExit(
            "PIL account_id is not configured.\n"
            "Run `instagram-cli accounts` to find your user_fbid, then copy "
            "pil.config.example.json to pil.config.json and set account_id."
        )
    return acct
