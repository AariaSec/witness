"""Shared leak-scan logic: key whitelist, secret patterns, prose-length.

Used by both `witness.bundle` (refuses to emit a bundle containing a
violation) and `scripts/leakscan.py` (the standalone pre-commit / CI
entry point, and `make leakscan`). Keeping the logic in one place means
the bundle-time check and the pre-commit check can never silently drift.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

# Common secret-shaped patterns — intentionally broad (false positives are
# cheap here; false negatives are not).
_SECRET_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"AKIA[0-9A-Z]{16}"),  # AWS access key id
    re.compile(r"ASIA[0-9A-Z]{16}"),  # AWS temp access key id
    re.compile(r"sk-[A-Za-z0-9]{20,}"),  # OpenAI/Anthropic-style secret key
    re.compile(r"ghp_[A-Za-z0-9]{36}"),  # GitHub personal access token
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),  # other GitHub token prefixes
    re.compile(r"AIza[0-9A-Za-z_\-]{35}"),  # Google API key
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |)PRIVATE KEY-----"),
    re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),  # JWT
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),  # Slack token
    re.compile(r"Bearer [A-Za-z0-9._\-]{20,}"),
]

# A decoy value is allowed (and expected) anywhere — it is never real.
_DECOY_PATTERN = re.compile(r"^WITNESS-DECOY-[0-9a-f]{8}$")

# Dict fields whose own keys ARE content (relative file paths), not a
# fixed schema vocabulary the way `findings`'s keys (FindingKind values)
# are. The generic key-whitelist check below doesn't apply to these
# dicts' immediate children — but the keys are still scanned for
# secret-shaped / prose-like content, exactly like any other string.
_PATH_KEYED_FIELDS = {"changed_file_digests"}

_PROSE_LEN_LIMIT = 200
_PROSE_WORD_RE = re.compile(r"[A-Za-z]{2,}")


def load_allowed_keys(schemas_dir: Path | None = None) -> set[str]:
    if schemas_dir is None:
        schemas_dir = Path(__file__).resolve().parents[2] / "schemas"
    path = schemas_dir / "allowed_keys.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    keys = data.get("allowed_keys", [])
    return set(keys)


def looks_like_prose(value: str) -> bool:
    """A string over the length limit that also looks like natural-language
    prose (multiple word-like tokens), not e.g. a long digest or base64
    blob (those have no word boundaries worth calling 'words')."""
    if len(value) <= _PROSE_LEN_LIMIT:
        return False
    words = _PROSE_WORD_RE.findall(value)
    return len(words) >= 5


def contains_secret(value: str) -> str | None:
    """Return the matched pattern's text if `value` looks like a secret,
    else None. A well-formed decoy value is never flagged."""
    if _DECOY_PATTERN.match(value.strip()):
        return None
    for pattern in _SECRET_PATTERNS:
        m = pattern.search(value)
        if m:
            return m.group(0)
    return None


def scan_value(
    key_path: str,
    value: Any,
    allowed_keys: set[str],
    _parent_key: str | None = None,
) -> list[str]:
    """Recursively scan one JSON value, returning a list of violation
    descriptions (empty if clean).

    `_parent_key` is the dict key through which `value` was reached — used
    only to detect `_PATH_KEYED_FIELDS` (see module docstring), where
    `value` itself is a dict whose own keys are content (paths), not a
    fixed schema vocabulary to whitelist-check."""
    violations: list[str] = []
    if isinstance(value, dict):
        path_keyed = _parent_key in _PATH_KEYED_FIELDS
        for k, v in value.items():
            if path_keyed:
                # The key is data (a relative path), not a schema field
                # name — scan it like any other string value instead of
                # checking it against the key whitelist.
                secret = contains_secret(k)
                if secret is not None:
                    violations.append(
                        f"secret-shaped string at {key_path}.{k} (key): matched {secret[:12]}..."
                    )
                if looks_like_prose(k):
                    violations.append(f"prose-like string (>200 chars) at {key_path}.{k} (key)")
            elif k not in allowed_keys:
                violations.append(f"disallowed key {k!r} at {key_path}.{k}")
            violations.extend(scan_value(f"{key_path}.{k}", v, allowed_keys, _parent_key=k))
    elif isinstance(value, list):
        for i, item in enumerate(value):
            violations.extend(
                scan_value(f"{key_path}[{i}]", item, allowed_keys, _parent_key=_parent_key)
            )
    elif isinstance(value, str):
        secret = contains_secret(value)
        if secret is not None:
            violations.append(f"secret-shaped string at {key_path}: matched {secret[:12]}...")
        if looks_like_prose(value):
            violations.append(f"prose-like string (>200 chars) at {key_path}")
    return violations


def scan_record(record: dict[str, Any], allowed_keys: set[str] | None = None) -> list[str]:
    """Scan one already-parsed JSON record (one bundle.jsonl line)."""
    if allowed_keys is None:
        allowed_keys = load_allowed_keys()
    violations: list[str] = []
    for k, v in record.items():
        if k not in allowed_keys:
            violations.append(f"disallowed key {k!r} at $.{k}")
        violations.extend(scan_value(f"$.{k}", v, allowed_keys, _parent_key=k))
    return violations


def scan_text_blob(text: str) -> list[str]:
    """Scan arbitrary text (e.g. a staged file's contents) for secret
    patterns only — key-whitelisting doesn't apply outside JSONL records."""
    violations: list[str] = []
    for pattern in _SECRET_PATTERNS:
        for m in pattern.finditer(text):
            violations.append(f"secret-shaped string: matched {m.group(0)[:12]}...")
    return violations


__all__ = [
    "contains_secret",
    "load_allowed_keys",
    "looks_like_prose",
    "scan_record",
    "scan_text_blob",
    "scan_value",
]
