"""Ed25519 sign/verify for run receipts.

Private key lives at `~/.witness/keys/ed25519_private.pem`, mode 0600,
auto-created on first `witness record` (or explicit `witness keygen`).
The public key travels inside every `ReceiptBody` (and the `Manifest`),
so a receipt is self-verifiable without any external key distribution —
exactly what the console needs to verify client-side with no backend.
"""

from __future__ import annotations

import base64
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from witness.canon import canonical_json
from witness.models import Receipt, ReceiptBody


class Signer:
    """Loads (or creates) an Ed25519 keypair and signs `ReceiptBody` objects."""

    def __init__(self, private_key: Ed25519PrivateKey) -> None:
        self._private_key = private_key

    @classmethod
    def load_or_create(cls, keydir: Path) -> Signer:
        keydir = Path(keydir)
        keydir.mkdir(parents=True, exist_ok=True)
        priv_path = keydir / "ed25519_private.pem"

        if priv_path.exists():
            data = priv_path.read_bytes()
            private_key = serialization.load_pem_private_key(data, password=None)
            if not isinstance(private_key, Ed25519PrivateKey):
                raise ValueError(f"{priv_path} does not contain an Ed25519 private key")
        else:
            private_key = Ed25519PrivateKey.generate()
            pem = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
            priv_path.write_bytes(pem)
            priv_path.chmod(0o600)

            pub_path = keydir / "ed25519_public.pem"
            pub_pem = private_key.public_key().public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )
            pub_path.write_bytes(pub_pem)

        return cls(private_key)

    @property
    def public_key_b64(self) -> str:
        raw = self._private_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        return base64.b64encode(raw).decode("ascii")

    def sign(self, body: ReceiptBody) -> Receipt:
        sig_bytes = self._private_key.sign(canonical_json(body.canonical_payload()))
        sig = base64.b64encode(sig_bytes).decode("ascii")
        return Receipt(body=body, sig=sig)


def verify_receipt(r: Receipt) -> bool:
    """Verify `r.sig` over the canonical JSON of `r.body` (via
    `ReceiptBody.canonical_payload()` — NOT a raw `model_dump`, so a
    pre-v0.2 receipt round-tripped through the current schema still
    reproduces the exact bytes it was originally signed over; see that
    method's docstring) using the public key embedded in `r.body.pubkey`.
    Returns False on any malformed input — never raises."""
    try:
        pub_raw = base64.b64decode(r.body.pubkey, validate=True)
        public_key = Ed25519PublicKey.from_public_bytes(pub_raw)
        sig_bytes = base64.b64decode(r.sig, validate=True)
        public_key.verify(sig_bytes, canonical_json(r.body.canonical_payload()))
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False


__all__ = ["Signer", "verify_receipt"]
