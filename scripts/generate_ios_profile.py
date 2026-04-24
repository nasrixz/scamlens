#!/usr/bin/env python3
"""Generate an iOS/macOS Configuration Profile for DNS-over-HTTPS or DoT.

Usage:
    # Unsigned DoH profile (most common)
    python scripts/generate_ios_profile.py \\
        --org ScamLens \\
        --identifier com.scamlens.dns \\
        --dns-hostname dns.scamlens.example.com \\
        --out dist/scamlens.mobileconfig

    # DoT with IP fallbacks
    python scripts/generate_ios_profile.py \\
        --protocol TLS --dns-hostname dns.scamlens.example.com \\
        --server-ip 203.0.113.10 --server-ip 2001:db8::10 \\
        --org ScamLens --identifier com.scamlens.dns \\
        --out dist/scamlens-dot.mobileconfig

    # Signed profile
    python scripts/generate_ios_profile.py ... \\
        --sign-cert certs/fullchain.pem --sign-key certs/privkey.pem

    # Exempt a local corp suffix from DoH (captive portals, .local, etc.)
    python scripts/generate_ios_profile.py ... \\
        --prohibited example.corp --prohibited local

Install on device: open the resulting .mobileconfig in Safari on iPhone /
iPad, or double-click on macOS. System Settings → General → VPN & Device
Management → install.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running as `python scripts/generate_ios_profile.py` from the repo root
# (imports the API module) or as a standalone file (falls back to local copy).
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

try:
    from api.ios_profile import ProfileSpec, build_profile, sign_profile
except ImportError:  # standalone usage outside the repo
    print("error: run from repo root so api/ios_profile.py is importable", file=sys.stderr)
    sys.exit(2)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate iOS/macOS DNS profile")
    p.add_argument("--org", required=True, help="Organization name (shown in Settings)")
    p.add_argument("--identifier", required=True,
                   help="Reverse-DNS identifier (e.g. com.scamlens.dns)")
    p.add_argument("--dns-hostname", required=True,
                   help="Hostname of the DoH/DoT server")
    p.add_argument("--protocol", choices=["HTTPS", "TLS"], default="HTTPS",
                   help="HTTPS (DoH) or TLS (DoT). Default: HTTPS")
    p.add_argument("--doh-path", default="/dns-query",
                   help="URL path for DoH. Default: /dns-query")
    p.add_argument("--server-ip", action="append", default=[], metavar="IP",
                   help="Server IP (repeat flag for multiple). Required for DoT, optional for DoH.")
    p.add_argument("--prohibited", action="append", default=[], metavar="DOMAIN",
                   help="Domain excluded from encrypted DNS (repeat flag for multiple)")
    p.add_argument("--no-removal", action="store_true",
                   help="Prevent user from removing the profile without a passcode")
    p.add_argument("--sign-cert", type=Path, help="X.509 cert PEM for signing")
    p.add_argument("--sign-key", type=Path, help="Private key PEM for signing")
    p.add_argument("--out", type=Path, required=True, help="Output .mobileconfig path")
    return p.parse_args()


def main() -> int:
    args = _parse_args()
    if args.protocol == "TLS" and not args.server_ip:
        print("error: --server-ip required for DoT (--protocol TLS)", file=sys.stderr)
        return 2
    if bool(args.sign_cert) != bool(args.sign_key):
        print("error: --sign-cert and --sign-key must be used together", file=sys.stderr)
        return 2

    spec = ProfileSpec(
        org=args.org,
        identifier=args.identifier,
        dns_hostname=args.dns_hostname,
        protocol=args.protocol,
        doh_path=args.doh_path,
        server_addresses=args.server_ip,
        prohibited_domains=args.prohibited,
        allow_removal=not args.no_removal,
    )
    profile = build_profile(spec)
    if args.sign_cert:
        profile = sign_profile(profile, args.sign_cert, args.sign_key)
        print("[scamlens] profile signed with", args.sign_cert, file=sys.stderr)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(profile)
    print(f"[scamlens] wrote {args.out} ({len(profile)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
