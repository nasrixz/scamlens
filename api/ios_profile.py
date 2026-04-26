"""Apple Configuration Profile builder for DNS-over-HTTPS / DNS-over-TLS.

Used by both the FastAPI `/api/setup/ios` endpoint and the standalone CLI
(`scripts/generate_ios_profile.py`). Produces a plist .mobileconfig. Signing
is optional — see `sign_profile()` (requires openssl at runtime).

Spec refs:
- Apple: Configuration Profile Reference → DNS Settings payload
  (PayloadType = com.apple.dnsSettings.managed).
- DoH: DNSProtocol = HTTPS, ServerURL required.
- DoT: DNSProtocol = TLS, ServerName required, ServerAddresses recommended.
"""
from __future__ import annotations

import plistlib
import subprocess
import tempfile
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional


Protocol = Literal["HTTPS", "TLS"]


@dataclass
class ProfileSpec:
    org: str
    identifier: str                     # reverse-dns base, e.g. com.scamlens.dns
    dns_hostname: str                   # DoH/DoT server hostname
    protocol: Protocol = "HTTPS"
    doh_path: str = "/dns-query"        # appended to https://<host> for DoH
    doh_token: str = ""                 # optional token for per-user DoH
    server_addresses: list[str] = field(default_factory=list)  # IPv4/IPv6 fallback (DoT)
    prohibited_domains: list[str] = field(default_factory=list)  # bypass list (captive portals, local TLDs)
    allow_removal: bool = True
    # Deterministic UUIDs for reproducible builds. Namespaced UUID5 against
    # identifier — so same org+identifier always produces the same profile
    # UUID, which lets iOS recognize re-installs as upgrades instead of dupes.
    uuid_namespace: Optional[str] = None


def build_profile(spec: ProfileSpec) -> bytes:
    display_name = f"{spec.org} Protection"
    description = _describe(spec)

    profile_uuid, payload_uuid = _uuids(spec)
    payload_identifier = f"{spec.identifier}.dns.{payload_uuid.lower()}"
    top_identifier = f"{spec.identifier}.profile.{profile_uuid.lower()}"

    dns_settings: dict = {"DNSProtocol": spec.protocol}
    if spec.protocol == "HTTPS":
        host = f"{spec.doh_token}.{spec.dns_hostname}" if spec.doh_token else spec.dns_hostname
        dns_settings["ServerURL"] = f"https://{host}{spec.doh_path}"
    else:  # TLS
        dns_settings["ServerName"] = spec.dns_hostname
    if spec.server_addresses:
        dns_settings["ServerAddresses"] = spec.server_addresses
    if spec.prohibited_domains:
        dns_settings["ProhibitedDNSDomains"] = spec.prohibited_domains

    payload = {
        "PayloadDescription": description,
        "PayloadDisplayName": f"{display_name} DNS",
        "PayloadIdentifier": payload_identifier,
        "PayloadType": "com.apple.dnsSettings.managed",
        "PayloadUUID": profile_uuid_dashed(payload_uuid),
        "PayloadVersion": 1,
        "DNSSettings": dns_settings,
    }

    profile = {
        "PayloadContent": [payload],
        "PayloadDescription": description,
        "PayloadDisplayName": display_name,
        "PayloadIdentifier": top_identifier,
        "PayloadOrganization": spec.org,
        "PayloadRemovalDisallowed": not spec.allow_removal,
        "PayloadType": "Configuration",
        "PayloadUUID": profile_uuid_dashed(profile_uuid),
        "PayloadVersion": 1,
    }
    return plistlib.dumps(profile, fmt=plistlib.FMT_XML)


def sign_profile(unsigned: bytes, cert_pem: Path, key_pem: Path) -> bytes:
    """Produce a CMS-signed profile using openssl smime.

    Apple accepts signed .mobileconfig; install UI shows 'Verified' when the
    signer chains to a trusted root. Unsigned profiles still install but show
    a 'Not Signed' warning.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        (tmp / "unsigned").write_bytes(unsigned)
        signed_path = tmp / "signed"
        subprocess.run(
            [
                "openssl", "smime", "-sign",
                "-signer", str(cert_pem),
                "-inkey", str(key_pem),
                "-in", str(tmp / "unsigned"),
                "-out", str(signed_path),
                "-outform", "DER",
                "-nodetach",
            ],
            check=True,
        )
        return signed_path.read_bytes()


def build_mobileconfig(dns_hostname: str, org: str, identifier: str, doh_token: str | None = None) -> bytes:
    """Backwards-compatible wrapper used by the API for the common DoH case."""
    spec = ProfileSpec(org=org, identifier=identifier, dns_hostname=dns_hostname, doh_token=doh_token or "")
    return build_profile(spec)


# ---- internals ----------------------------------------------------------

def _describe(spec: ProfileSpec) -> str:
    if spec.protocol == "HTTPS":
        return f"Configures DNS-over-HTTPS to {spec.dns_hostname}"
    return f"Configures DNS-over-TLS to {spec.dns_hostname}"


def _uuids(spec: ProfileSpec) -> tuple[str, str]:
    ns = uuid.uuid5(uuid.NAMESPACE_DNS, spec.uuid_namespace or spec.identifier)
    token_part = f":{spec.doh_token}" if spec.doh_token else ""
    profile_uuid = uuid.uuid5(ns, f"profile:{spec.dns_hostname}:{spec.protocol}{token_part}").hex.upper()
    payload_uuid = uuid.uuid5(ns, f"payload:{spec.dns_hostname}:{spec.protocol}{token_part}").hex.upper()
    return profile_uuid, payload_uuid


def profile_uuid_dashed(h: str) -> str:
    """Return 8-4-4-4-12 UUID formatted from a hex string."""
    h = h.upper()
    return f"{h[0:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"
