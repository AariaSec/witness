"""Arena: scenario-generation + scoring harness (G-Arena).

`witness.arena.runner.run_variants` drives the real recording pipeline
over a set of variant directories; `witness.arena.score.score` turns the
results into an honest `scores.json`. See `runner.py` for the variant
directory contract. The frozen rule set that *generates* variants lives
in the private companion repo (`witness-private/generator/`) — this
package never imports it and must be fully testable without it (see
`tests/fixtures/arena_variants/`).
"""

from __future__ import annotations

from witness.arena.runner import ArenaRun, Expected, run_variants
from witness.arena.score import PerRun, Scores, score

__all__ = ["ArenaRun", "Expected", "PerRun", "Scores", "run_variants", "score"]
