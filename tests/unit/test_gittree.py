"""`witness.gittree`: per-file digest snapshot, tree digest, best-effort
git commit sha lookup."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from witness.canon import sha256_hex
from witness.gittree import compute_file_digests, git_commit_sha, tree_digest_of

pytestmark = pytest.mark.skipif(
    subprocess.run(["git", "--version"], capture_output=True).returncode != 0,
    reason="no `git` on PATH",
)


def test_compute_file_digests_empty_dir_is_empty(tmp_path: Path) -> None:
    assert compute_file_digests(tmp_path) == {}


def test_compute_file_digests_nonexistent_dir_is_empty(tmp_path: Path) -> None:
    assert compute_file_digests(tmp_path / "does_not_exist") == {}


def test_compute_file_digests_matches_sha256_of_contents(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_bytes(b"hello")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "b.txt").write_bytes(b"world")

    digests = compute_file_digests(tmp_path)

    assert digests == {
        "a.txt": sha256_hex(b"hello"),
        "sub/b.txt": sha256_hex(b"world"),
    }


def test_compute_file_digests_excludes_dot_git(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_bytes(b"hello")
    git_dir = tmp_path / ".git" / "objects"
    git_dir.mkdir(parents=True)
    (git_dir / "pack-internal").write_bytes(b"not a real file content should never be hashed")

    digests = compute_file_digests(tmp_path)

    assert list(digests) == ["a.txt"]


def test_tree_digest_of_empty_is_none() -> None:
    assert tree_digest_of({}) is None


def test_tree_digest_of_is_deterministic_regardless_of_dict_order() -> None:
    d1 = {"a.txt": "1" * 64, "b.txt": "2" * 64}
    d2 = {"b.txt": "2" * 64, "a.txt": "1" * 64}
    assert tree_digest_of(d1) == tree_digest_of(d2)


def test_tree_digest_of_changes_when_a_digest_changes() -> None:
    d1 = {"a.txt": "1" * 64}
    d2 = {"a.txt": "2" * 64}
    assert tree_digest_of(d1) != tree_digest_of(d2)


def test_git_commit_sha_none_outside_a_repo(tmp_path: Path) -> None:
    assert git_commit_sha(tmp_path) is None


def test_git_commit_sha_real_repo(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    env_kwargs = dict(cwd=repo, capture_output=True, text=True, check=True)
    subprocess.run(["git", "init", "-q"], **env_kwargs)
    subprocess.run(["git", "config", "user.email", "test@example.com"], **env_kwargs)
    subprocess.run(["git", "config", "user.name", "Test"], **env_kwargs)
    (repo / "f.txt").write_text("content")
    subprocess.run(["git", "add", "f.txt"], **env_kwargs)
    subprocess.run(["git", "commit", "-q", "-m", "init"], **env_kwargs)

    sha = git_commit_sha(repo)

    assert sha is not None
    assert len(sha) in (40, 64)
    assert all(c in "0123456789abcdef" for c in sha)


def test_git_commit_sha_never_raises_when_git_binary_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If `git` isn't on PATH at all, `subprocess.run` raises `OSError`
    (`FileNotFoundError`) — must degrade to `None`, never propagate."""

    def _raise(*args: object, **kwargs: object) -> None:
        raise FileNotFoundError("no such file: git")

    monkeypatch.setattr(subprocess, "run", _raise)
    assert git_commit_sha(tmp_path) is None
