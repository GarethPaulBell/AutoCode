"""Persistence helpers for the AutoCode DB.

This module provides a small, testable API for saving and loading the in-memory
CodeDatabase instance. The functions are intentionally small and accept the
DB object to keep them independent of the original module's global state.
"""
from __future__ import annotations

import pickle
from typing import Optional

DB_PATH = "code_db.pkl"


def save_db(db, path: str | None = None):
    """Serialize the provided DB object to disk.

    Args:
        db: the CodeDatabase instance to serialize.
        path: optional path to write the file. If None, uses DB_PATH.
    """
    p = path or DB_PATH
    with open(p, "wb") as f:
        pickle.dump(db, f)


def load_db(path: str | None = None):
    """Load a CodeDatabase instance from disk.

    Returns the loaded object or None if file not present.
    """
    p = path or DB_PATH
    try:
        with open(p, "rb") as f:
            obj = pickle.load(f)
            return obj
    except FileNotFoundError:
        return None
    except Exception:
        # If loading fails, surface the exception to caller
        raise
