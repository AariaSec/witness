"""Guards the sync `schemas/allowed_keys.yaml`'s own header comment
promises but didn't actually exist until this file: every `FindingKind`
value must be whitelisted, since it's used as a dynamic dict key under
`receipt.body.findings` and the leak-scanner checks keys recursively.

Found the hard way (2026-10-27): adding `FindingKind.credential_persist`
to models.py was NOT enough on its own -- `witness bundle` refused to
export a real run's bundle with `"disallowed key 'credential_persist'"`
until this file's own whitelist was separately updated. This test makes
that the loud, immediate failure the yaml comment already claimed existed.
"""

from __future__ import annotations

from witness.leakscan import load_allowed_keys
from witness.models import FindingKind


def test_every_finding_kind_is_in_the_allowed_keys_whitelist() -> None:
    allowed = load_allowed_keys()
    missing = {kind.value for kind in FindingKind} - allowed
    assert not missing, (
        f"FindingKind value(s) {missing!r} missing from "
        "schemas/allowed_keys.yaml's whitelist -- `witness bundle` will "
        "refuse to export any run whose findings include one of these."
    )
