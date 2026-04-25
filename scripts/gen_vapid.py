"""Generate VAPID keys for Web Push.

Usage:
    docker compose exec -T api python -m scripts.gen_vapid

Outputs base64url-encoded public + private keys. Add to .env:
  VAPID_PUBLIC_KEY=...
  VAPID_PRIVATE_KEY=...
  VAPID_CONTACT_EMAIL=mailto:admin@yourdomain
"""
from __future__ import annotations

import base64

from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import (
    Encoding, PrivateFormat, PublicFormat, NoEncryption,
)


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def main() -> None:
    private_key = ec.generate_private_key(ec.SECP256R1())
    public_key = private_key.public_key()

    # 32-byte raw private value
    priv_int = private_key.private_numbers().private_value
    priv_bytes = priv_int.to_bytes(32, "big")

    # Uncompressed public point (65 bytes: 0x04 + X + Y)
    pub_bytes = public_key.public_bytes(
        Encoding.X962, PublicFormat.UncompressedPoint,
    )

    print("VAPID_PRIVATE_KEY=" + b64url(priv_bytes))
    print("VAPID_PUBLIC_KEY=" + b64url(pub_bytes))


if __name__ == "__main__":
    main()
