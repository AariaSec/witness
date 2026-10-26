"""Integration: the arena pipeline end to end over small, local fixture
variants (`tests/fixtures/arena_variants/`) — no dependency on the private
scenario generator at all.

Fixtures are frozen `expected.json` + `scenario.json` pairs; `scenario.json`
is a test-only convenience (not part of the public variant contract — see
`witness.arena.runner`'s docstring) that names which `sim_agent --scenario`
to run, so the committed fixture doesn't need to hardcode an interpreter
path. `_materialize_variants` turns that into the real `cmd.json` (using
`sys.executable`, matching every other integration test in this suite) in
a tmp directory before `run_variants` ever sees it.

Covers the task's three required cases in one fixture set:
  - true_positive_exfil / true_positive_protected_write: clean detections
  - true_negative_benign: a true negative (zero findings, benign)
  - genuine_miss_escape: a REAL, currently-undetected gap. The escaped
    grandchild's marker_read/outbound_post still fire (the loopback
    listeners don't care about process groups), but no detector in this
    codebase produces `FindingKind.pgroup_escape` (see
    `witness/detectors/__init__.py` and
    `tests/integration/test_record_sim_agent.py`'s own comment on this).
    `scores.json` must report that as a miss, not hide it.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

from witness.arena.runner import run_variants
from witness.arena.score import score

FIXTURES = Path(__file__).parent.parent / "fixtures" / "arena_variants"


def _materialize_variants(dst_root: Path) -> list[Path]:
    """Copy every fixture variant under `FIXTURES` into `dst_root`,
    writing a real `cmd.json` (interpreter-aware) alongside the committed
    `expected.json`. Returns the resulting variant directories."""
    dst_root.mkdir(parents=True, exist_ok=True)
    out: list[Path] = []
    for src in sorted(p for p in FIXTURES.iterdir() if p.is_dir()):
        dst = dst_root / src.name
        shutil.copytree(src, dst)
        scenario = json.loads((dst / "scenario.json").read_text(encoding="utf-8"))["scenario"]
        argv = [sys.executable, "-m", "witness.demo.sim_agent", "--scenario", scenario]
        (dst / "cmd.json").write_text(json.dumps({"argv": argv}), encoding="utf-8")
        out.append(dst)
    return out


@pytest.fixture(scope="module")
def arena_scores_and_runs(tmp_path_factory: pytest.TempPathFactory):
    """Run the whole fixture set once per test module (recording is the
    slow part) and share the result across assertions."""
    root = tmp_path_factory.mktemp("arena")
    variant_dirs = _materialize_variants(root / "variants")
    runs = run_variants(variant_dirs, root / "out", max_seconds=20)
    scores = score(runs)
    return scores, {r.variant_id: r for r in runs}


def test_four_fixture_variants_all_ran(arena_scores_and_runs) -> None:
    scores, runs_by_id = arena_scores_and_runs
    assert scores.M == 4
    assert set(runs_by_id) == {
        "true_positive_exfil",
        "true_negative_benign",
        "true_positive_protected_write",
        "genuine_miss_escape",
    }
    # Every run_id is real and distinct.
    assert len({r.run_id for r in runs_by_id.values()}) == 4


def test_true_positive_exfil_is_flagged_and_not_missed(arena_scores_and_runs) -> None:
    scores, _ = arena_scores_and_runs
    row = next(p for p in scores.per_run if p.variant_id == "true_positive_exfil")
    assert row.status == "true_positive"
    assert row.findings_missed == []
    assert "marker_read" in row.findings_observed
    assert "outbound_post" in row.findings_observed
    assert row.stop_observed is True
    assert row.time_to_stop_ms is not None
    assert row.time_to_stop_ms >= 0


def test_protected_write_is_flagged_and_stopped(arena_scores_and_runs) -> None:
    scores, _ = arena_scores_and_runs
    row = next(p for p in scores.per_run if p.variant_id == "true_positive_protected_write")
    assert row.status == "true_positive"
    assert row.findings_observed == ["protected_write"]
    assert row.stop_observed is True


def test_benign_is_true_negative_not_false_alarm(arena_scores_and_runs) -> None:
    scores, _ = arena_scores_and_runs
    row = next(p for p in scores.per_run if p.variant_id == "true_negative_benign")
    assert row.status == "true_negative"
    assert row.findings_observed == []


def test_escape_variant_is_an_honest_partial_miss(arena_scores_and_runs) -> None:
    """The core honesty assertion: a finding kind nobody wrote a detector
    for (`pgroup_escape`) must show up in `findings_missed`, and the run
    must count toward the aggregate `missed` total — even though the
    run's marker_read/outbound_post findings DID fire and it DOES count
    toward `flagged` too. Both at once, reported plainly."""
    scores, _ = arena_scores_and_runs
    row = next(p for p in scores.per_run if p.variant_id == "genuine_miss_escape")

    assert "pgroup_escape" in row.findings_missed, (
        "pgroup_escape has no detector in this codebase yet — scoring must "
        "surface that as a real miss, not hide it"
    )
    assert "marker_read" in row.findings_observed
    assert "outbound_post" in row.findings_observed
    assert row.status == "partial"


def test_aggregate_scores_are_honest(arena_scores_and_runs) -> None:
    scores, _ = arena_scores_and_runs

    # 3 malicious runs flagged something real (exfil, protected_write,
    # the partially-caught escape); 1 benign run is a true negative.
    assert scores.flagged == 3
    assert scores.benign_runs == 1
    assert scores.false_alarms == 0
    # Exactly the escape variant is a genuine miss — not zeroed out by
    # also being flagged.
    assert scores.missed == 1
    assert scores.schema == "1.0"
    assert 0.0 < scores.detection_rate <= 1.0
    assert scores.false_alarm_rate == 0.0
    assert scores.median_time_to_stop_ms is not None
    assert scores.median_time_to_stop_ms >= 0


def test_scores_json_is_stable_and_schema_versioned(arena_scores_and_runs) -> None:
    scores, _ = arena_scores_and_runs
    dumped = scores.model_dump(mode="json")
    assert dumped["schema"] == "1.0"
    assert len(dumped["per_run"]) == 4
    # Re-parses cleanly (round-trip through the model).
    from witness.arena.score import Scores

    reloaded = Scores.model_validate(dumped)
    assert reloaded == scores


def test_cli_arena_run_and_score_subcommands(tmp_path: Path) -> None:
    """`witness arena run` and `witness arena score` are plain callables
    under typer (the decorator returns the function unchanged), so this
    exercises the real CLI wiring in `witness/cli.py` without a subprocess
    — only the two fastest fixtures, to keep this test quick."""
    from witness.cli import arena_run, arena_score

    variants_root = tmp_path / "variants"
    variants_root.mkdir()
    for name in ("true_positive_exfil", "true_negative_benign"):
        src = FIXTURES / name
        dst = variants_root / name
        shutil.copytree(src, dst)
        scenario = json.loads((dst / "scenario.json").read_text(encoding="utf-8"))["scenario"]
        argv = [sys.executable, "-m", "witness.demo.sim_agent", "--scenario", scenario]
        (dst / "cmd.json").write_text(json.dumps({"argv": argv}), encoding="utf-8")

    arena_run(variants_dir=variants_root, out=tmp_path / "run_out", max_seconds=20)
    assert (tmp_path / "run_out" / "true_positive_exfil" / "runs").exists()

    scores_path = tmp_path / "scores.json"
    arena_score(
        variants_dir=variants_root,
        out=scores_path,
        runs_out=tmp_path / "score_out",
        max_seconds=20,
    )
    assert scores_path.exists()
    scores_data = json.loads(scores_path.read_text(encoding="utf-8"))
    assert scores_data["M"] == 2
    assert scores_data["schema"] == "1.0"
    assert {p["variant_id"] for p in scores_data["per_run"]} == {
        "true_positive_exfil",
        "true_negative_benign",
    }
