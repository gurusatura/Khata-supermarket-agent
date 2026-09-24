"""
services/memory.py — Nebula Supermarket Ops Agent
==================================================
Stage 10: Persistent Memory & Preferences
Stores simple key-value preferences in the database so they survive 
across Telegram sessions (unlike LLM context windows).

Note: preferences.value is JSONB in Supabase, so we use json.dumps/loads
to store plain strings correctly (e.g. "Tamil" → '"Tamil"').
"""

import json
from services.db import get_connection

def set_preference(key: str, value) -> None:
    """
    Saves or updates a preference.
    Value can be any JSON-serializable type: str, int, bool, dict, list.
    Uses UPSERT (ON CONFLICT) to update if the key already exists.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO preferences (key, value)
                VALUES (%s, %s::jsonb)
                ON CONFLICT (key) DO UPDATE 
                SET value = EXCLUDED.value, updated_at = NOW();
            """, (key, json.dumps(value)))
            conn.commit()

def get_preference(key: str, default=None):
    """
    Retrieves a preference by key. Returns the default if not found.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT value FROM preferences WHERE key = %s;", (key,))
            row = cur.fetchone()
            return row[0] if row else default


def get_all_preferences() -> dict:
    """
    Retrieves all non-ephemeral store preferences (excludes active_sale_id).
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT key, value FROM preferences WHERE key NOT LIKE 'active_sale_id:%';")
            rows = cur.fetchall()
            return {r[0]: r[1] for r in rows}

