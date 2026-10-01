"""Sequential, checkpointed collection of QĐ766 evaluation datasets."""

from __future__ import annotations

import hashlib
import json
import os
import random
import shutil
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Protocol

from .normalization import METRIC_GROUPS
from .periods import PeriodSelection, build_evaluation_payload
from .snapshot import GROUP_ORDER, UNSUPPORTED_BY_SCOPE, period_dict

API_ROOT = "https://dichvucong.gov.vn/api/v1/reporting/evaluation"


@dataclass(frozen=True)
class PlannedRequest:
    group: str
    url: str
    payload: dict[str, object]
    outputFile: str


@dataclass(frozen=True)
class TransportResponse:
    status: int
    body: bytes
    contentType: str | None = None


class Transport(Protocol):
    def post_json(self, url: str, payload: dict[str, object]) -> TransportResponse: ...


class CollectionError(RuntimeError):
    pass


class SafetyStop(CollectionError):
    """A server signal that requires operator review instead of retrying."""


class RateLimitStop(SafetyStop):
    pass


class TransportFailure(CollectionError):
    pass


class UrllibTransport:
    """Minimal live transport; collection policy remains in ``collect_snapshot``."""

    def __init__(self, timeout_seconds: float = 45.0):
        self.timeout_seconds = timeout_seconds

    def post_json(self, url: str, payload: dict[str, object]) -> TransportResponse:
        request = urllib.request.Request(
            url,
            data=json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"),
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "qd766-research/1.0 (+sequential; contact repository owner)",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                return TransportResponse(
                    status=response.status,
                    body=response.read(),
                    contentType=response.headers.get("Content-Type"),
                )
        except urllib.error.HTTPError as error:
            return TransportResponse(
                status=error.code,
                body=error.read(),
                contentType=error.headers.get("Content-Type") if error.headers else None,
            )
        except urllib.error.URLError as error:
            raise TransportFailure(f"Network transport failed: {error.reason}") from error


class BrowserTransport:
    """Same-origin transport for DVCQG hosts that reject non-browser TLS clients.

    The browser is started once for a short sequential collection run and is
    closed explicitly by the caller. It does not retry, rotate identities, or
    bypass an HTTP/WAF rejection returned by the source.
    """

    SOURCE_URL = "https://dichvucong.gov.vn/danh-gia-chat-luong-phuc-vu"
    WINDOWS_BROWSER_PATHS = (
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    )

    def __init__(self, timeout_seconds: float = 45.0):
        self.timeout_seconds = timeout_seconds
        self._process = None
        self._socket = None
        self._profile_path = None
        self._message_id = 0

    def __enter__(self) -> "BrowserTransport":
        try:
            from websockets.sync.client import connect
        except ImportError as error:
            raise TransportFailure("WebSocket support is not installed") from error
        executable_path = next(
            (path for path in self.WINDOWS_BROWSER_PATHS if os.path.isfile(path)),
            None,
        )
        if executable_path is None:
            raise TransportFailure("Chrome or Edge is not installed")
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
                probe.bind(("127.0.0.1", 0))
                port = probe.getsockname()[1]
            self._profile_path = tempfile.mkdtemp(prefix="qd766-browser-")
            self._process = subprocess.Popen(
                [
                    executable_path,
                    "--headless=new",
                    "--disable-gpu",
                    "--disable-background-networking",
                    "--no-first-run",
                    "--no-default-browser-check",
                    "--remote-allow-origins=*",
                    f"--remote-debugging-port={port}",
                    f"--user-data-dir={self._profile_path}",
                    "about:blank",
                ],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            targets_url = f"http://127.0.0.1:{port}/json/list"
            deadline = time.monotonic() + min(self.timeout_seconds, 15)
            targets = None
            while time.monotonic() < deadline:
                if self._process.poll() is not None:
                    raise RuntimeError("browser exited during startup")
                try:
                    with urllib.request.urlopen(targets_url, timeout=1) as response:
                        targets = json.loads(response.read())
                    if targets:
                        break
                except (OSError, ValueError):
                    time.sleep(0.2)
            if not targets:
                raise RuntimeError("browser debugging endpoint did not start")
            websocket_url = next(
                target["webSocketDebuggerUrl"]
                for target in targets
                if target.get("type") == "page"
            )
            self._socket = connect(
                websocket_url,
                open_timeout=min(self.timeout_seconds, 10),
                close_timeout=2,
                max_size=32 * 1024 * 1024,
            )
            self._command("Page.enable")
            self._command("Page.navigate", {"url": self.SOURCE_URL})
            deadline = time.monotonic() + self.timeout_seconds
            while time.monotonic() < deadline:
                state = self._evaluate(
                    "({origin: location.origin, ready: document.readyState})"
                )
                if (
                    state.get("origin") == "https://dichvucong.gov.vn"
                    and state.get("ready") in {"interactive", "complete"}
                ):
                    time.sleep(1.5)
                    break
                time.sleep(0.25)
            else:
                raise RuntimeError("DVCQG page did not become ready")
        except Exception as error:
            self.close()
            raise TransportFailure(f"Browser transport startup failed: {error}") from error
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()

    def close(self) -> None:
        if self._socket is not None:
            try:
                self._socket.close()
            except Exception:
                pass
            self._socket = None
        if self._process is not None:
            try:
                self._process.terminate()
                self._process.wait(timeout=5)
            except Exception:
                try:
                    self._process.kill()
                except Exception:
                    pass
            self._process = None
        if self._profile_path is not None:
            shutil.rmtree(self._profile_path, ignore_errors=True)
            self._profile_path = None

    def _command(self, method: str, params: dict | None = None) -> dict:
        if self._socket is None:
            raise TransportFailure("Browser transport is not open")
        self._message_id += 1
        message_id = self._message_id
        self._socket.send(
            json.dumps({"id": message_id, "method": method, "params": params or {}})
        )
        while True:
            message = json.loads(self._socket.recv(timeout=self.timeout_seconds))
            if message.get("id") != message_id:
                continue
            if "error" in message:
                raise TransportFailure(
                    f"Browser command {method} failed: {message['error']}"
                )
            return message.get("result", {})

    def _evaluate(self, expression: str) -> object:
        result = self._command(
            "Runtime.evaluate",
            {
                "expression": expression,
                "awaitPromise": True,
                "returnByValue": True,
            },
        )
        if result.get("exceptionDetails"):
            description = (
                result.get("result", {}).get("description")
                or result["exceptionDetails"].get("text")
            )
            raise TransportFailure(f"Browser script failed: {description}")
        return result.get("result", {}).get("value")

    def post_json(self, url: str, payload: dict[str, object]) -> TransportResponse:
        if self._socket is None:
            raise TransportFailure("Browser transport is not open")
        try:
            arguments = json.dumps(
                {
                    "url": url,
                    "payload": payload,
                    "timeoutMs": int(self.timeout_seconds * 1000),
                },
                ensure_ascii=False,
            )
            expression = """
                (async ({url, payload, timeoutMs}) => {
                  const controller = new AbortController();
                  const timer = setTimeout(() => controller.abort(), timeoutMs);
                  try {
                    const response = await fetch(url, {
                      method: 'POST',
                      credentials: 'include',
                      headers: {
                        'Accept': 'application/json, text/plain, */*',
                        'Content-Type': 'application/json'
                      },
                      body: JSON.stringify(payload),
                      signal: controller.signal
                    });
                    return {
                      status: response.status,
                      contentType: response.headers.get('content-type'),
                      body: await response.text()
                    };
                  } finally {
                    clearTimeout(timer);
                  }
                })(__ARGS__)
                """.replace("__ARGS__", arguments)
            result = self._evaluate(expression)
        except Exception as error:
            if isinstance(error, TransportFailure):
                raise
            raise TransportFailure(f"Browser transport failed: {error}") from error
        if not isinstance(result, dict):
            raise TransportFailure("Browser transport returned an invalid result")
        return TransportResponse(
            status=int(result["status"]),
            body=str(result["body"]).encode("utf-8"),
            contentType=result.get("contentType"),
        )


def plan_evaluation_requests(
    period: PeriodSelection,
    root_department_id: str,
    formality_id: str | None = None,
) -> list[PlannedRequest]:
    scope = "formality" if formality_id else "all"
    unsupported = UNSUPPORTED_BY_SCOPE[scope]
    plan = []
    for group in GROUP_ORDER:
        if group in unsupported:
            continue
        payload = build_evaluation_payload(
            group, period, root_department_id, formality_id
        )
        plan.append(
            PlannedRequest(
                group=group,
                url=f"{API_ROOT}/{group}",
                payload=payload,
                outputFile=f"{group}.json",
            )
        )
    return plan


def _write_json(path: Path, value: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def _manifest_template(
    plan: list[PlannedRequest], period: PeriodSelection, scope: str
) -> dict:
    return {
        "schemaVersion": 1,
        "status": "collecting",
        "period": period_dict(period),
        "scope": scope,
        "expectedGroups": [request.group for request in plan],
        "captures": [],
        "failure": None,
    }


def _validate_response(
    request: PlannedRequest, response: TransportResponse
) -> dict:
    try:
        envelope = json.loads(response.body)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CollectionError(f"Invalid JSON for {request.group}") from error
    if envelope.get("code") != "OK" or not isinstance(envelope.get("data"), dict):
        raise CollectionError(f"Unexpected response envelope for {request.group}")
    data = envelope["data"]
    if request.group in METRIC_GROUPS:
        root_key, children_key = "overview", "evaluation"
    else:
        root_key, children_key = "parent", "children"
    if not isinstance(data.get(root_key), dict) or not isinstance(
        data.get(children_key), list
    ):
        raise CollectionError(f"Unexpected response schema for {request.group}")
    expected_root = request.payload.get("rootDepartmentId")
    if data[root_key].get("departmentId") != expected_root:
        raise CollectionError(f"Wrong root department for {request.group}")
    if not all(isinstance(child, dict) and child.get("departmentId") for child in data[children_key]):
        raise CollectionError(f"Invalid child identity for {request.group}")
    return envelope


def collect_snapshot(
    plan: list[PlannedRequest],
    *,
    period: PeriodSelection,
    output_dir: Path,
    transport: Transport,
    minimum_delay_seconds: float = 1.0,
    jitter_seconds: float = 0.25,
    max_retries: int = 2,
    sleeper: Callable[[float], None] = time.sleep,
    random_value: Callable[[], float] = random.random,
) -> dict:
    """Collect one snapshot sequentially and checkpoint after every response.

    A previously complete directory is immutable. An incomplete directory can
    resume only captures whose file hash still matches its manifest entry.
    """

    if not plan:
        raise ValueError("plan must contain at least one request")
    if minimum_delay_seconds < 0 or jitter_seconds < 0 or max_retries < 0:
        raise ValueError("delay, jitter and retry values must be non-negative")

    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "manifest.json"
    scope = "formality" if any(
        "formalityId" in request.payload or "formalityID" in request.payload
        for request in plan
    ) else "all"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("status") == "complete":
            raise CollectionError("Refusing to overwrite a complete snapshot")
        if manifest.get("expectedGroups") != [request.group for request in plan]:
            raise CollectionError("Existing manifest does not match the request plan")
    else:
        manifest = _manifest_template(plan, period, scope)
        _write_json(manifest_path, manifest)

    completed = {capture["group"]: capture for capture in manifest["captures"]}
    for request_index, request in enumerate(plan):
        existing = completed.get(request.group)
        destination = output_dir / request.outputFile
        if existing:
            if not destination.exists():
                raise CollectionError(f"Missing checkpoint file for {request.group}")
            digest = hashlib.sha256(destination.read_bytes()).hexdigest()
            if digest != existing["sha256"]:
                raise CollectionError(f"Checkpoint hash changed for {request.group}")
            continue

        response = None
        for attempt in range(max_retries + 1):
            try:
                response = transport.post_json(request.url, request.payload)
            except TransportFailure as error:
                if attempt == max_retries:
                    manifest["status"] = "failed"
                    manifest["failure"] = {
                        "group": request.group,
                        "httpStatus": None,
                        "reason": "transport-retry-limit",
                    }
                    _write_json(manifest_path, manifest)
                    raise CollectionError(
                        f"Transport failed for {request.group} after retries"
                    ) from error
                sleeper(minimum_delay_seconds + jitter_seconds * random_value())
                continue
            if response.status in (403, 429):
                manifest["status"] = "halted"
                manifest["failure"] = {
                    "group": request.group,
                    "httpStatus": response.status,
                    "reason": "access-or-rate-limit",
                }
                _write_json(manifest_path, manifest)
                raise RateLimitStop(
                    f"Stopped on HTTP {response.status} for {request.group}"
                )
            content_type = (response.contentType or "").lower()
            rejection_body = response.body[:4096].lower()
            if (
                "text/html" in content_type
                or b"request rejected" in rejection_body
                or b"access denied" in rejection_body
            ):
                manifest["status"] = "halted"
                manifest["failure"] = {
                    "group": request.group,
                    "httpStatus": response.status,
                    "reason": "rejection-or-html-response",
                }
                _write_json(manifest_path, manifest)
                raise SafetyStop(
                    f"Stopped on rejection/HTML response for {request.group}"
                )
            if response.status in (200, 201):
                break
            if attempt == max_retries:
                manifest["status"] = "failed"
                manifest["failure"] = {
                    "group": request.group,
                    "httpStatus": response.status,
                    "reason": "retry-limit",
                }
                _write_json(manifest_path, manifest)
                raise CollectionError(
                    f"HTTP {response.status} for {request.group} after retries"
                )
            sleeper(minimum_delay_seconds + jitter_seconds * random_value())

        assert response is not None
        try:
            _validate_response(request, response)
        except CollectionError as error:
            reason = (
                "invalid-json"
                if str(error).startswith("Invalid JSON")
                else "unexpected-response"
            )
            manifest["status"] = "failed"
            manifest["failure"] = {
                "group": request.group,
                "httpStatus": response.status,
                "reason": reason,
            }
            _write_json(manifest_path, manifest)
            raise

        temporary = destination.with_suffix(destination.suffix + ".tmp")
        temporary.write_bytes(response.body)
        temporary.replace(destination)
        capture = {
            "group": request.group,
            "method": "POST",
            "url": request.url,
            "payload": request.payload,
            "httpStatus": response.status,
            "contentType": response.contentType,
            "capturedAt": datetime.now(timezone.utc).isoformat(),
            "file": request.outputFile,
            "bytes": len(response.body),
            "sha256": hashlib.sha256(response.body).hexdigest(),
            "verification": "json-envelope-schema-and-root-verified",
        }
        manifest["captures"].append(capture)
        manifest["failure"] = None
        _write_json(manifest_path, manifest)
        if request_index < len(plan) - 1:
            sleeper(minimum_delay_seconds + jitter_seconds * random_value())

    loaded = {capture["group"] for capture in manifest["captures"]}
    expected = set(manifest["expectedGroups"])
    manifest["status"] = "complete" if loaded == expected else "incomplete"
    manifest["failure"] = None
    _write_json(manifest_path, manifest)
    return manifest
