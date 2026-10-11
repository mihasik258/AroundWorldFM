import asyncio
import ipaddress
import socket
from typing import Any
from urllib.parse import urlsplit

import httpx

from app.core.config import settings

USER_AGENT = "AroundFM/2.1 (+https://github.com/mihasik258/AroundWorldFM)"


class UnsafeURLError(ValueError):
    pass


def validate_http_url(url: str) -> str:
    parts = urlsplit(url.strip())
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise UnsafeURLError("URL must be http(s)")
    if parts.username or parts.password:
        raise UnsafeURLError("URL must not contain credentials")
    return url.strip()


def optional_http_url(value: object) -> str | None:
    if not value:
        return None
    try:
        return validate_http_url(str(value))
    except UnsafeURLError:
        return None


def _is_public(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return ip.is_global and not ip.is_multicast


async def ensure_public_host(host: str, port: int | None) -> None:
    if settings.ALLOW_PRIVATE_STREAM_HOSTS:
        return
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None:
        if not _is_public(literal):
            raise UnsafeURLError("Host is not public")
        return
    loop = asyncio.get_running_loop()
    try:
        infos = await loop.getaddrinfo(host, port or 443, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise UnsafeURLError("Host does not resolve") from exc
    if not infos or any(not _is_public(ipaddress.ip_address(info[4][0])) for info in infos):
        raise UnsafeURLError("Host is not public")


async def _guard_request(request: httpx.Request) -> None:
    if request.url.scheme not in ("http", "https"):
        raise UnsafeURLError("URL must be http(s)")
    await ensure_public_host(request.url.host, request.url.port)


def outbound_client(timeout: float | httpx.Timeout, **kwargs: Any) -> httpx.AsyncClient:
    headers = {"User-Agent": USER_AGENT, **kwargs.pop("headers", {})}
    return httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=True,
        max_redirects=5,
        trust_env=False,
        headers=headers,
        event_hooks={"request": [_guard_request]},
        **kwargs,
    )
