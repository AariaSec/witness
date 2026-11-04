"""Best-effort git-tree binding for a receipt (Receipt v0.2).

Walks a lab directory, computes a per-file sha256 digest for every regular
file present (a snapshot at receipt-signing time, not a strict pre/post
session diff — see `models.ReceiptBody.changed_file_digests`'s docstring
and `docs/ARCHITECTURE.md`'s "Receipt v0.2 / CI gate" section for why
that's still an honest coverage statement), and a sha256 "tree digest" of
the canonical, sorted `(relative_path, file_sha256)` pair list.

`git_commit_sha` is a SEPARATE, independent best-effort lookup: `git
rev-parse HEAD` against the lab directory. Most lab directories are
disposable tmp dirs that are never a git repository at all — this
degrades gracefully to `None` in that case, and NEVER raises or fails a
recording run. When the lab directory genuinely is a git working tree
(e.g. `record-claude --lab <a real checkout>`), this is the actual commit
the session's changes are bound to.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from witness.canon import canonical_json, sha256_hex

# Directories whose contents are never part of the attested file-digest
# snapshot: `.git/` is repository plumbing, not a session-authored file,
# and walking it on a large real checkout would be slow for no signal.
_EXCLUDED_DIR_NAMES = {".git"}


def compute_file_digests(root: Path) -> dict[str, str]:
    """Return `{relative_path: sha256_hex}` for every regular file under
    `root` (recursively), in sorted order. Returns `{}` if `root` doesn't
    exist. Never raises — a file that disappears or becomes unreadable
    between the `rglob` listing and the read (e.g. a concurrent writer) is
    silently skipped rather than failing the whole snapshot."""
    root = Path(root)
    digests: dict[str, str] = {}
    if not root.exists():
        return digests
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        rel_parts = p.relative_to(root).parts
        if _EXCLUDED_DIR_NAMES.intersection(rel_parts):
            continue
        try:
            data = p.read_bytes()
        except OSError:
            continue
        digests[str(p.relative_to(root))] = sha256_hex(data)
    return digests


def tree_digest_of(file_digests: dict[str, str]) -> str | None:
    """sha256 hex of the canonical, sorted `[relative_path, file_sha256]`
    pair list — the `ReceiptBody.git_tree_digest` value. Returns `None`
    for an empty snapshot (an empty lab directory has no tree to bind)."""
    if not file_digests:
        return None
    pairs = sorted(file_digests.items())
    return sha256_hex(canonical_json([list(pair) for pair in pairs]))


def git_commit_sha(root: Path) -> str | None:
    """Best-effort `git rev-parse HEAD` for `root`. Returns `None` if
    `root` isn't inside a git working tree, `git` isn't on PATH, or
    anything else goes wrong — never raises, never blocks a run."""
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    sha = result.stdout.strip()
    if not sha:
        return None
    return sha


__all__ = ["compute_file_digests", "git_commit_sha", "tree_digest_of"]
