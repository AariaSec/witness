"""Arena runner: drives `witness record` over a set of pre-built variant
directories and collects the resulting `run_id`s + bundles.

**Variant directory contract** (this is the interface the private scenario
generator — `witness-private/generator/gen_variants.py` — and this repo's
own test fixtures (`tests/fixtures/arena_variants/`) both implement; this
module never imports or depends on anything in `witness-private`):

```
<variants_dir>/<variant_id>/
    expected.json    # Expected, serialized — ground truth, written BEFORE
                      # any recording happens, derived from the variant's
                      # archetype definition alone (never copied from a run)
    cmd.json          # {"argv": ["python3", "-m", "witness.demo.sim_agent",
                      #           "--scenario", "exfil"]}  — the assistant
                      # command `witness record` spawns for this variant
```

`run_variants` calls the same `_run_record` orchestration function used by
`witness record` (the CLI) and `witness.demo.run_demo` — i.e. the full,
real recording pipeline (loopback listeners, ledger, detectors, actions,
signed receipt), not a second simulated mechanism. Variants run
**serially** (one `_run_record` call fully completes — listeners stopped,
ports released — before the next starts): this mirrors the architecture
doc's process-model note that arena disables parallel runs ("port
conflicts, timing noise"). The harness itself (`witness arena run` /
`witness arena score`) is the "separate process" in that same table — it
does not need to additionally shell out to a nested `witness record`
subprocess per variant to satisfy that framing.

Exceptions from `_run_record` or `build_bundle` (including
`BundleQuarantined` / `BundleChainInvalid`) are **not** swallowed here: a
broken variant should halt the arena run loudly rather than silently
produce a scores.json with a gap in it.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from witness.bundle import build_bundle
from witness.cli import _run_record
from witness.config import RecordConfig
from witness.models import FindingKind


class Expected(BaseModel):
    """Ground truth for one variant, written independently of any recorder
    run — derived from the archetype/seed definition that produced the
    variant, not from observing what the recorder actually finds."""

    model_config = ConfigDict(extra="forbid")

    malicious: bool
    expect_findings: list[FindingKind]
    stop_expected: bool


class ArenaRun(BaseModel):
    """One completed variant run: its ground truth plus where to find the
    resulting bundle."""

    model_config = ConfigDict(extra="forbid")

    variant_id: str
    run_id: str
    expected: Expected
    bundle: Path


def _load_expected(variant_dir: Path) -> Expected:
    data = json.loads((variant_dir / "expected.json").read_text(encoding="utf-8"))
    return Expected.model_validate(data)


def _load_argv(variant_dir: Path) -> list[str]:
    data = json.loads((variant_dir / "cmd.json").read_text(encoding="utf-8"))
    argv = data["argv"]
    if not isinstance(argv, list) or not all(isinstance(a, str) for a in argv):
        raise ValueError(f"{variant_dir}/cmd.json: 'argv' must be a list of strings")
    return list(argv)


def run_variants(variant_dirs: list[Path], out: Path, max_seconds: int = 120) -> list[ArenaRun]:
    """Run every variant in `variant_dirs` through the real recording
    pipeline, serially, and return one `ArenaRun` per variant in input
    order.

    `out/<variant_id>/lab/` is the per-variant lab dir the assistant
    command runs in; `out/<variant_id>/runs/<run_id>/` holds the ledger,
    receipt, and exported `bundle.jsonl`.
    """
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)

    results: list[ArenaRun] = []
    for raw_variant_dir in variant_dirs:
        variant_dir = Path(raw_variant_dir)
        variant_id = variant_dir.name
        expected = _load_expected(variant_dir)
        argv = _load_argv(variant_dir)

        variant_out = out / variant_id
        lab = variant_out / "lab"
        runs_dir = variant_out / "runs"

        config = RecordConfig(lab=lab, max_seconds=max_seconds)
        run_dir = _run_record(config, argv, runs_dir)

        bundle_path = run_dir / "bundle.jsonl"
        build_bundle(run_dir, bundle_path)

        results.append(
            ArenaRun(
                variant_id=variant_id,
                run_id=run_dir.name,
                expected=expected,
                bundle=bundle_path,
            )
        )

    return results


__all__ = ["ArenaRun", "Expected", "run_variants"]
