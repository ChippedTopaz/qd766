#!/usr/bin/env python3
"""Very small, read-only connectivity diagnostic for DVCQG.

No POST is made. The script checks DNS/HTTPS connectivity to the public host
and records timing/status only. It is intentionally lightweight and safe.
"""
from __future__ import annotations

import socket
import ssl
import sys
import time
import urllib.error
import urllib.request

HOST = "dichvucong.gov.vn"
URL = "https://dichvucong.gov.vn/"


def main() -> int:
    print(f"DNS {HOST}")
    t0 = time.monotonic()
    try:
        infos = socket.getaddrinfo(HOST, 443, type=socket.SOCK_STREAM)
        addresses = sorted({item[4][0] for item in infos})
        print(f"DNS OK | {len(addresses)} address(es) | {', '.join(addresses[:10])}")
    except Exception as exc:
        print(f"DNS ERROR: {exc}")
        return 1
    print(f"DNS elapsed: {time.monotonic() - t0:.2f}s")

    print(f"HTTPS GET {URL}")
    t1 = time.monotonic()
    request = urllib.request.Request(
        URL,
        method="GET",
        headers={"User-Agent": "Mozilla/5.0 (compatible; qd766-connectivity-check/1.0)"},
    )
    try:
        with urllib.request.urlopen(request, timeout=20, context=ssl.create_default_context()) as response:
            sample = response.read(256)
            print(f"HTTPS OK | status={response.status} | content-type={response.headers.get('Content-Type','')} | bytes-read={len(sample)}")
    except urllib.error.HTTPError as exc:
        print(f"HTTPS REACHED HOST | HTTP {exc.code} | content-type={exc.headers.get('Content-Type','')}")
    except urllib.error.URLError as exc:
        print(f"HTTPS NETWORK ERROR: {exc}")
        return 2
    except Exception as exc:
        print(f"HTTPS ERROR: {exc}")
        return 3
    print(f"HTTPS elapsed: {time.monotonic() - t1:.2f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
