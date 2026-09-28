from __future__ import annotations

import socket
import ssl
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from typing import Any, Callable

DVCQG_HOST = "dichvucong.gov.vn"
DVCQG_PUBLIC_URL = "https://dichvucong.gov.vn/"


@dataclass(frozen=True)
class ConnectivityProbeResult:
    host: str
    url: str
    dns_addresses: tuple[str, ...]
    dns_elapsed_seconds: float
    https_elapsed_seconds: float | None
    http_status: int | None
    content_type: str | None
    bytes_read: int
    safe_to_review_for_reenable: bool
    stop_reason: str | None
    error_type: str | None
    error_message: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, file_pointer, code, message, headers, new_url):
        return None


def _open_once(request: urllib.request.Request, timeout: float):
    context = ssl.create_default_context()
    opener = urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=context),
        _NoRedirect(),
    )
    return opener.open(request, timeout=timeout)


def probe_dvcqg_connectivity(
    *,
    timeout_seconds: float = 20.0,
    resolver: Callable[..., Any] = socket.getaddrinfo,
    open_once: Callable[[urllib.request.Request, float], Any] = _open_once,
) -> ConnectivityProbeResult:
    dns_started = time.monotonic()
    try:
        infos = resolver(DVCQG_HOST, 443, type=socket.SOCK_STREAM)
        addresses = tuple(sorted({item[4][0] for item in infos}))
    except Exception as error:
        return ConnectivityProbeResult(
            host=DVCQG_HOST,
            url=DVCQG_PUBLIC_URL,
            dns_addresses=(),
            dns_elapsed_seconds=time.monotonic() - dns_started,
            https_elapsed_seconds=None,
            http_status=None,
            content_type=None,
            bytes_read=0,
            safe_to_review_for_reenable=False,
            stop_reason="dns-failure",
            error_type=type(error).__name__,
            error_message=str(error)[:500],
        )
    dns_elapsed = time.monotonic() - dns_started

    request = urllib.request.Request(
        DVCQG_PUBLIC_URL,
        method="GET",
        headers={
            "Accept": "text/html,application/xhtml+xml",
            "User-Agent": "qd766-connectivity-check/2.0 (+single-get; no-retry)",
        },
    )
    https_started = time.monotonic()
    try:
        with open_once(request, timeout_seconds) as response:
            status = response.status
            content_type = response.headers.get("Content-Type")
            sample = response.read(4096)
    except urllib.error.HTTPError as error:
        status = error.code
        content_type = error.headers.get("Content-Type") if error.headers else None
        sample = error.read(4096)
    except Exception as error:
        return ConnectivityProbeResult(
            host=DVCQG_HOST,
            url=DVCQG_PUBLIC_URL,
            dns_addresses=addresses,
            dns_elapsed_seconds=dns_elapsed,
            https_elapsed_seconds=time.monotonic() - https_started,
            http_status=None,
            content_type=None,
            bytes_read=0,
            safe_to_review_for_reenable=False,
            stop_reason="https-connection-failure",
            error_type=type(error).__name__,
            error_message=str(error)[:500],
        )

    lowered = sample.lower()
    rejection = b"request rejected" in lowered or b"access denied" in lowered
    if status in (403, 429):
        stop_reason = "access-or-rate-limit"
    elif status >= 500:
        stop_reason = "upstream-server-error"
    elif rejection:
        stop_reason = "rejection-response"
    else:
        stop_reason = None
    return ConnectivityProbeResult(
        host=DVCQG_HOST,
        url=DVCQG_PUBLIC_URL,
        dns_addresses=addresses,
        dns_elapsed_seconds=dns_elapsed,
        https_elapsed_seconds=time.monotonic() - https_started,
        http_status=status,
        content_type=content_type,
        bytes_read=len(sample),
        safe_to_review_for_reenable=stop_reason is None,
        stop_reason=stop_reason,
        error_type=None,
        error_message=None,
    )
