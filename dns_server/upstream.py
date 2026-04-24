"""Forward DNS queries to upstream resolver over UDP, TCP fallback on truncation."""
from __future__ import annotations

import asyncio
import socket
from typing import Optional

import structlog

log = structlog.get_logger()


class UpstreamResolver:
    def __init__(self, primary: str, fallback: str, timeout: float = 3.0):
        self._servers = [primary, fallback]
        self._timeout = timeout

    async def query(self, wire: bytes) -> Optional[bytes]:
        for server in self._servers:
            try:
                answer = await asyncio.wait_for(
                    self._udp_query(wire, server), timeout=self._timeout
                )
                if answer and _is_truncated(answer):
                    return await asyncio.wait_for(
                        self._tcp_query(wire, server), timeout=self._timeout
                    )
                if answer:
                    return answer
            except asyncio.TimeoutError:
                log.warning("upstream_timeout", server=server)
            except Exception as exc:
                log.warning("upstream_error", server=server, error=str(exc))
        return None

    async def _udp_query(self, wire: bytes, server: str) -> Optional[bytes]:
        loop = asyncio.get_running_loop()
        fut: asyncio.Future[bytes] = loop.create_future()

        class _Proto(asyncio.DatagramProtocol):
            def datagram_received(self, data, addr):
                if not fut.done():
                    fut.set_result(data)

            def error_received(self, exc):
                if not fut.done():
                    fut.set_exception(exc)

        transport, _ = await loop.create_datagram_endpoint(
            _Proto, remote_addr=(server, 53), family=socket.AF_INET,
        )
        try:
            transport.sendto(wire)
            return await fut
        finally:
            transport.close()

    async def _tcp_query(self, wire: bytes, server: str) -> Optional[bytes]:
        reader, writer = await asyncio.open_connection(server, 53)
        try:
            # TCP DNS: 2-byte length prefix
            writer.write(len(wire).to_bytes(2, "big") + wire)
            await writer.drain()
            length_bytes = await reader.readexactly(2)
            length = int.from_bytes(length_bytes, "big")
            return await reader.readexactly(length)
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass


def _is_truncated(wire: bytes) -> bool:
    """TC flag = bit 1 of byte 2 of the DNS header flags field."""
    if len(wire) < 4:
        return False
    flags = (wire[2] << 8) | wire[3]
    return bool(flags & 0x0200)
