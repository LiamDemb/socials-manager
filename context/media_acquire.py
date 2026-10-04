"""Allowlisted asset acquisition. No arbitrary manual-URL previews."""
import ipaddress
import socket
from urllib.parse import urlparse

from .media_config import LIMITS, QUOTAS

PRIVATE_NETS = (
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
)


def assert_public_http_url(url: str) -> str:
    parsed = urlparse(url or "")
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError("rejected_url")
    host = parsed.hostname.strip("[]")
    if host in ("localhost",):
        raise ValueError("rejected_private_target")
    try:
        infos = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80))
    except socket.gaierror as exc:
        raise ValueError("unresolved_host") from exc
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if any(ip in net for net in PRIVATE_NETS) or ip.is_loopback or ip.is_link_local:
            raise ValueError("rejected_private_target")
    return url


def sniff_image_mime(data: bytes) -> str | None:
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"GIF87a") or data.startswith(b"GIF89a"):
        return "image/gif"
    if len(data) >= 12 and data[4:8] == b"ftyp":
        return "video/mp4"
    return None


def reject_extension_mismatch(declared_ext: str, data: bytes) -> str | None:
    mime = sniff_image_mime(data)
    if mime is None:
        return "invalid_mime"
    ext = (declared_ext or "").lower().lstrip(".")
    if ext in ("jpg", "jpeg") and mime != "image/jpeg":
        return "invalid_mime"
    if ext == "png" and mime != "image/png":
        return "invalid_mime"
    return None


def acquisition_limits() -> dict:
    return {
        "per_input_bytes": QUOTAS["transient_per_input_bytes"],
        "timeout_seconds": LIMITS["acquire_timeout_seconds"],
        "retries": LIMITS["network_retries"],
    }
