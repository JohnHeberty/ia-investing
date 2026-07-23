from __future__ import annotations

import hashlib
import json

SENSITIVE_ARGUMENT_KEYS = frozenset({"password", "secret", "token", "api_key", "authorization", "cookie"})


def canonical_hash(payload: dict[str, object]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


def sanitize_tool_payload(value: object, *, key: str = "") -> object:
    if key.lower() in SENSITIVE_ARGUMENT_KEYS:
        return "[REDACTED]"
    if isinstance(value, dict):
        return {str(item_key): sanitize_tool_payload(item, key=str(item_key)) for item_key, item in value.items()}
    if isinstance(value, list):
        return [sanitize_tool_payload(item) for item in value]
    if isinstance(value, str) and len(value) > 4_000:
        return value[:4_000] + "…[TRUNCATED]"
    return value
