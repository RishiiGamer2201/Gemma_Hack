"""Minimal localhost-only Ollama adapter using the Python standard library."""

from __future__ import annotations

import ipaddress
import json
import math
from collections.abc import Iterator, Mapping, Sequence
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


@dataclass(frozen=True, slots=True)
class OllamaStreamChunk:
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
        payload = self._generate_payload(
            model=model,
            prompt=prompt,
            stream=False,
            system=system,
            options=options,
            format=format,
            keep_alive=keep_alive,
            think=think,
        )
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

    def generate_stream(
        self,
        *,
        model: str,
        prompt: str,
        system: str | None = None,
        options: Mapping[str, Any] | None = None,
        format: str | Mapping[str, Any] | None = None,
        keep_alive: str | int | None = None,
        think: bool | None = None,
    ) -> Iterator[OllamaStreamChunk]:
        """Yield bounded NDJSON chunks from a loopback-only generation call."""
        payload = self._generate_payload(
            model=model,
            prompt=prompt,
            stream=True,
            system=system,
            options=options,
            format=format,
            keep_alive=keep_alive,
            think=think,
        )
        request = Request(
            self.base_url + "/api/generate",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json", "Accept": "application/x-ndjson"},
            method="POST",
        )
        total = 0
        saw_done = False
        try:
            with self._opener.open(request, timeout=self.timeout) as response:
                while True:
                    line = response.readline(self.max_response_bytes + 1)
                    if not line:
                        break
                    total += len(line)
                    if total > self.max_response_bytes:
                        raise OllamaError(
                            "response_too_large", "Ollama response exceeded the configured limit"
                        )
                    chunk = self._decode_object(line)
                    text = chunk.get("response")
                    done = chunk.get("done")
                    if not isinstance(text, str) or not isinstance(done, bool):
                        raise OllamaError(
                            "invalid_response", "Ollama returned an invalid stream chunk"
                        )
                    saw_done = saw_done or done
                    yield OllamaStreamChunk(
                        text=text,
                        model=str(chunk.get("model", model)),
                        done=done,
                        raw=chunk,
                    )
                    if done:
                        while trailing := response.readline(self.max_response_bytes + 1):
                            total += len(trailing)
                            if total > self.max_response_bytes:
                                raise OllamaError(
                                    "response_too_large",
                                    "Ollama response exceeded the configured limit",
                                )
                            if trailing.strip():
                                raise OllamaError(
                                    "invalid_response",
                                    "Ollama returned data after the final stream chunk",
                                )
                        break
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
        if not saw_done:
            raise OllamaError("invalid_response", "Ollama stream ended before a final chunk")

    @staticmethod
    def _generate_payload(
        *,
        model: str,
        prompt: str,
        stream: bool,
        system: str | None,
        options: Mapping[str, Any] | None,
        format: str | Mapping[str, Any] | None,
        keep_alive: str | int | None,
        think: bool | None,
    ) -> dict[str, Any]:
        if not model.strip():
            raise ValueError("model must not be empty")
        payload: dict[str, Any] = {"model": model, "prompt": prompt, "stream": stream}
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
        return payload

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

    def embed(
        self,
        *,
        model: str,
        inputs: Sequence[str],
        keep_alive: str | int | None = "10m",
    ) -> tuple[tuple[float, ...], ...]:
        """Return one embedding vector per input from the loopback-only runtime."""

        if not model.strip():
            raise ValueError("model must not be empty")
        texts = list(inputs)
        if not texts or any(not isinstance(text, str) for text in texts):
            raise ValueError("inputs must be a non-empty sequence of strings")

        payload: dict[str, Any] = {"model": model, "input": texts}
        if keep_alive is not None:
            payload["keep_alive"] = keep_alive
        response = self._post_json("/api/embed", payload)

        raw = response.get("embeddings")
        if not isinstance(raw, list) or len(raw) != len(texts):
            raise OllamaError(
                "invalid_response", "Ollama did not return one embedding per input"
            )
        vectors: list[tuple[float, ...]] = []
        for item in raw:
            if not isinstance(item, list) or not item:
                raise OllamaError("invalid_response", "Ollama returned an empty embedding")
            try:
                vector = tuple(float(value) for value in item)
            except (TypeError, ValueError) as exc:
                raise OllamaError(
                    "invalid_response", "Ollama returned a non-numeric embedding"
                ) from exc
            if any(not math.isfinite(value) for value in vector):
                raise OllamaError(
                    "invalid_response", "Ollama returned a non-finite embedding"
                )
            vectors.append(vector)
        dimensions = len(vectors[0])
        if any(len(vector) != dimensions for vector in vectors):
            raise OllamaError("invalid_response", "Ollama returned ragged embeddings")
        return tuple(vectors)

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
        return self._decode_object(body)

    @staticmethod
    def _decode_object(body: bytes) -> dict[str, Any]:
        try:
            decoded = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise OllamaError("invalid_response", "Ollama returned invalid JSON") from exc
        if not isinstance(decoded, dict):
            raise OllamaError("invalid_response", "Ollama returned a non-object response")
        if "error" in decoded:
            raise OllamaError("ollama_error", str(decoded["error"]))
        return decoded
