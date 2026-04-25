"""/api/setup/* — per-platform instructions + iOS profile download."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response

from ..deps import get_cfg
from ..ios_profile import build_mobileconfig
from ..models import SetupResponse

router = APIRouter()


@router.get("/setup/ios")
async def setup_ios(
    cfg=Depends(get_cfg),
    token: str | None = Query(None, description="Optional DoH token for per-user DNS"),
) -> Response:
    """Download Apple Configuration Profile (.mobileconfig)."""
    body = build_mobileconfig(cfg.dns_hostname, cfg.profile_org, cfg.profile_identifier, doh_token=token)
    filename = f"{cfg.profile_org.lower()}-dns.mobileconfig"
    return Response(
        content=body,
        media_type="application/x-apple-aspen-config",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/setup/android", response_model=SetupResponse)
async def setup_android(cfg=Depends(get_cfg)) -> SetupResponse:
    return SetupResponse(
        platform="android",
        dns_hostname=cfg.dns_hostname,
        block_page_ip=cfg.block_page_ip,
        steps=[
            "Open Settings → Network & internet (or Connections).",
            "Tap Private DNS.",
            "Select 'Private DNS provider hostname'.",
            f"Enter: {cfg.dns_hostname}",
            "Tap Save. Protection is active immediately.",
        ],
        notes=[
            "Requires Android 9 (Pie) or newer.",
            "No app installation needed.",
            "Works on any network — WiFi or mobile data.",
        ],
    )


@router.get("/setup/desktop", response_model=SetupResponse)
async def setup_desktop(cfg=Depends(get_cfg)) -> SetupResponse:
    return SetupResponse(
        platform="desktop",
        dns_hostname=cfg.dns_hostname,
        block_page_ip=cfg.block_page_ip,
        steps=[
            "Windows: Settings → Network & Internet → your connection → "
            "Edit DNS → Manual → IPv4 → Preferred DNS = the ScamLens server IP.",
            "macOS: System Settings → Network → your interface → Details → "
            "DNS → + → enter the ScamLens server IP.",
            "Linux (NetworkManager): nmcli con mod <conn> ipv4.dns <server-ip>; "
            "nmcli con up <conn>.",
            "Linux (systemd-resolved): edit /etc/systemd/resolved.conf, "
            "DNS=<server-ip>, then: systemctl restart systemd-resolved.",
        ],
        notes=[
            "For DoH on desktop, use Firefox Network Settings → Enable DNS over "
            f"HTTPS → Custom → https://{cfg.dns_hostname}/dns-query.",
            "Chrome/Edge: chrome://settings/security → Use secure DNS → Custom.",
        ],
    )
