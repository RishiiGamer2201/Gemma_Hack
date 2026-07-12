"""Minimal localhost-only Ollama adapter using the Python standard library."""

from __future__ import annotations

import ipaddress
import json
from collections.abc import Mapping
from dataclasses import dataclass
from http.client import HTTPException
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


class OllamaError(RuntimeError):
    """Structured failure from local runtime validation or communication."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status: int | None = None,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status = status
        self.details = dict(details or {})

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": str(self),
            "status": self.status,
            "details": self.details,
        }


@dataclass(frozen=True, slots=True)
class OllamaResponse:
    text: str
    model: str
    done: bool
    raw: Mapping[str, Any]


class _NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        return None


def _validate_local_base_url(base_url: str) -> str:
    parsed = urlparse(base_url)
    if parsed.scheme != "http":
        raise OllamaError("invalid_endpoint", "Ollama endpoint must use local HTTP")
    if parsed.username or parsed.password:
        raise OllamaError("invalid_endpoint", "Ollama endpoint must not contain credentials")
    if parsed.query or parsed.fragment:
        raise OllamaError("invalid_endpoint", "Ollama endpoint must not contain query data")
    hostname = parsed.hostname
    if hostname is None:
        raise OllamaError("invalid_endpoint", "Ollama endpoint requires a host")
    if hostname.casefold() != "localhost":
        try:
            if not ipaddress.ip_address(hostname).is_loopback:
                raise OllamaError(
                    "remote_endpoint_blocked", "Only loopback Ollama endpoints are allowed"
                )
        except ValueError as exc:
            raise OllamaError(
                "remote_endpoint_blocked", "Only localhost or loopback IPs are allowed"
            ) from exc
    if parsed.path not in {"", "/"}:
        raise OllamaError("invalid_endpoint", "Ollama base URL must not include a path")
    try:
        port = parsed.port
    except ValueError as exc:
        raise OllamaError("invalid_endpoint", "Ollama endpoint has an invalid port") from exc
    if port is None:
        raise OllamaError("invalid_endpoint", "Ollama endpoint requires an explicit port")
    return base_url.rstrip("/")


class OllamaClient:
    """Optional local client; constructing it performs no I/O."""

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:11434",
        *,
        timeout: float = 60.0,
        max_response_bytes: int = 16 * 1024 * 1024,
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        if max_response_bytes <= 0:
            raise ValueError("max_response_bytes must be positive")
        self.base_url = _validate_local_base_url(base_url)
        self.timeout = float(timeout)
        self.max_response_bytes = max_response_bytes
        # Ignore environment proxies and reject redirects so a local service cannot
        # bounce a request to a remote host.
        self._opener = build_opener(ProxyHandler({}), _NoRedirects())

    def generate(
        self,
        *,
        model: str,
        prompt: str,
        system: str | None = None,
        options: Mapping[str, Any] | None = None,
        format: str | Mapping[str, Any] | None = None,
        keep_alive: str | int | None = None,
        think: bool | None = None,
    ) -> OllamaResponse:
        if not model.strip():
            raise ValueError("model must not be empty")
        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "stream": False,
        }
        if system is not None:
            payload["system"] = system
        if options is not None:
            payload["options"] = dict(options)
        if format is not None:
            payload["format"] = format
        if keep_alive is not None:
            payload["keep_alive"] = keep_alive
        if think is not None:
            payload["think"] = think
        response = self._post_json("/api/generate", payload)
        text = response.get("response")
        if not isinstance(text, str):
            raise OllamaError("invalid_response", "Ollama response did not contain generated text")
        done = response.get("done")
        if not isinstance(done, bool):
            raise OllamaError("invalid_response", "Ollama response did not contain a boolean done")
        return OllamaResponse(
            text=text,
            model=str(response.get("model", model)),
            done=done,
            raw=response,
        )

    def version(self) -> str:
        """Return the version reported by the loopback-only runtime."""
        response = self._get_json("/api/version")
        version = response.get("version")
        if not isinstance(version, str) or not version.strip():
            raise OllamaError("invalid_response", "Ollama response did not contain a version")
        return version.strip()

    def list_models(self) -> tuple[dict[str, Any], ...]:
        """Return installed model metadata from the local runtime."""
        response = self._get_json("/api/tags")
        models = response.get("models")
        if not isinstance(models, list) or not all(isinstance(item, dict) for item in models):
            raise OllamaError("invalid_response", "Ollama response did not contain a model list")
        return tuple(models)

    def _get_json(self, path: str) -> dict[str, Any]:
        request = Request(
            self.base_url + path,
            headers={"Accept": "application/json"},
            method="GET",
        )
        return self._open_json(request)

    def _post_json(self, path: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        request = Request(
            self.base_url + path,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        return self._open_json(request)

    def _open_json(self, request: Request) -> dict[str, Any]:
        try:
            with self._opener.open(request, timeout=self.timeout) as response:
                declared_length = response.headers.get("Content-Length")
                if declared_length:
                    try:
                        parsed_length = int(declared_length)
                    except ValueError as exc:
                        raise OllamaError(
                            "invalid_response", "Ollama returned an invalid Content-Length"
                        ) from exc
                    if parsed_length < 0:
                        raise OllamaError(
                            "invalid_response", "Ollama returned an invalid Content-Length"
                        )
                    if parsed_length > self.max_response_bytes:
                        raise OllamaError(
                            "response_too_large",
                            "Ollama response exceeded the configured limit",
                        )
                body = response.read(self.max_response_bytes + 1)
        except OllamaError:
            raise
        except HTTPError as exc:
            error_body = exc.read(4096).decode("utf-8", errors="replace")
            raise OllamaError(
                "http_error",
                f"Local Ollama returned HTTP {exc.code}",
                status=exc.code,
                details={"body": error_body},
            ) from exc
        except (URLError, TimeoutError, OSError, HTTPException) as exc:
            raise OllamaError(
                "connection_error",
                "Could not reach the local Ollama runtime",
                details={"reason": str(exc)},
            ) from exc
        if len(body) > self.max_response_bytes:
            raise OllamaError("response_too_large", "Ollama response exceeded the configured limit")
        try:
            decoded = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise OllamaError("invalid_response", "Ollama returned invalid JSON") from exc
        if not isinstance(decoded, dict):
            raise OllamaError("invalid_response", "Ollama returned a non-object response")
        if "error" in decoded:
            raise OllamaError("ollama_error", str(decoded["error"]))
        return decoded
