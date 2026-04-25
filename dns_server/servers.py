"""asyncio DNS listeners (UDP + TCP) and a DoH HTTP endpoint."""
from __future__ import annotations

import asyncio
import base64
from typing import Optional

import structlog
from aiohttp import web

from .resolver import Resolver

log = structlog.get_logger()


class UDPServer(asyncio.DatagramProtocol):
    def __init__(self, resolver: Resolver):
        self._resolver = resolver
        self._transport: Optional[asyncio.DatagramTransport] = None

    def connection_made(self, transport):
        self._transport = transport

    def datagram_received(self, data: bytes, addr):
        asyncio.create_task(self._handle(data, addr))

    async def _handle(self, data: bytes, addr):
        client_ip = addr[0] if addr else None
        try:
            result = await self._resolver.resolve(data, client_ip=client_ip)
            if self._transport and result.wire:
                self._transport.sendto(result.wire, addr)
        except Exception as exc:
            log.exception("udp_handler_error", error=str(exc))


async def start_udp(resolver: Resolver, host: str, port: int):
    loop = asyncio.get_running_loop()
    transport, _protocol = await loop.create_datagram_endpoint(
        lambda: UDPServer(resolver), local_addr=(host, port),
    )
    log.info("udp_listening", host=host, port=port)
    return transport


async def start_tcp(resolver: Resolver, host: str, port: int):
    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        peer = writer.get_extra_info("peername")
        client_ip = peer[0] if peer else None
        try:
            while True:
                # TCP DNS: 2-byte length prefix
                length_bytes = await reader.readexactly(2)
                length = int.from_bytes(length_bytes, "big")
                wire = await reader.readexactly(length)
                result = await resolver.resolve(wire, client_ip=client_ip)
                if result.wire:
                    writer.write(len(result.wire).to_bytes(2, "big") + result.wire)
                    await writer.drain()
        except asyncio.IncompleteReadError:
            pass
        except Exception as exc:
            log.warning("tcp_handler_error", error=str(exc))
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

    server = await asyncio.start_server(handle, host=host, port=port)
    log.info("tcp_listening", host=host, port=port)
    return server


def build_doh_app(resolver: Resolver, doh_tokens: dict[str, int]) -> web.Application:
    """RFC 8484 DNS-over-HTTPS. application/dns-message body, either POST raw
    or GET with ?dns=<base64url>. Nginx fronts this on 443.

    Two URL forms:
      /dns-query                  anonymous query (user_id=None)
      /dns-query/<token>          per-user query — token resolves to user_id,
                                  bound to the resulting block_event.
    `doh_tokens` is a shared dict mutated by the refresh loop.
    """

    async def _process(request: web.Request, token: str | None) -> web.Response:
        client_ip = (
            request.headers.get("X-Real-IP")
            or request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
            or (request.remote or "")
        )
        user_id = doh_tokens.get(token) if token else None

        if request.method == "POST":
            if request.headers.get("Content-Type") != "application/dns-message":
                return web.Response(status=415, text="unsupported media type")
            wire = await request.read()
        else:
            raw = request.query.get("dns")
            if not raw:
                return web.Response(status=400, text="missing dns param")
            try:
                wire = base64.urlsafe_b64decode(_pad_b64(raw))
            except Exception:
                return web.Response(status=400, text="bad base64")

        if not wire:
            return web.Response(status=400, text="empty query")

        result = await resolver.resolve(
            wire, client_ip=client_ip or None, user_id=user_id,
        )
        return web.Response(
            body=result.wire, content_type="application/dns-message",
        )

    async def handle_anon(request: web.Request) -> web.StreamResponse:
        return await _process(request, None)

    async def handle_with_token(request: web.Request) -> web.StreamResponse:
        token = request.match_info.get("token")
        return await _process(request, token)

    async def health(_: web.Request) -> web.Response:
        return web.json_response({"status": "ok"})

    app = web.Application()
    app.router.add_route("GET", "/dns-query", handle_anon)
    app.router.add_route("POST", "/dns-query", handle_anon)
    app.router.add_route("GET", "/dns-query/{token}", handle_with_token)
    app.router.add_route("POST", "/dns-query/{token}", handle_with_token)
    app.router.add_route("GET", "/health", health)
    return app


def _pad_b64(s: str) -> str:
    return s + "=" * (-len(s) % 4)


async def start_doh(
    resolver: Resolver,
    host: str,
    port: int,
    doh_tokens: dict[str, int],
) -> web.AppRunner:
    app = build_doh_app(resolver, doh_tokens)
    runner = web.AppRunner(app, access_log=None)
    await runner.setup()
    site = web.TCPSite(runner, host=host, port=port)
    await site.start()
    log.info("doh_listening", host=host, port=port)
    return runner
