"""Small helper for creating structured error dictionaries used across AutoCode.

Provide consistent, user-friendly error payloads with optional suggested actions and traceback.
"""
from typing import Optional, Dict


def make_error(error_type: str, message: str, suggested_action: Optional[str] = None, traceback: Optional[str] = None) -> Dict:
    payload = {
        "success": False,
        "error_type": error_type,
        "message": message,
    }
    if suggested_action:
        payload["suggested_action"] = suggested_action
    if traceback:
        payload["traceback"] = traceback
    return payload
