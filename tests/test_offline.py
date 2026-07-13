"""The app must work with the network off. These are the regression guards.

The demo runs with Wi-Fi disabled, and the privacy claim is that a citizen's legal
problem never leaves their machine. Both properties are easy to break by accident —
one CDN font, one analytics snippet, one library that phones home — so they are
asserted here rather than left to a manual check.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from src.agents.ollama import OllamaClient, OllamaError

FRONTEND = Path("frontend/src")
INDEX_HTML = Path("frontend/index.html")

# Hosts that may appear as *data* the API supplies (an official source URL rendered
# as a link the user clicks) but must never be fetched by the app itself.
_DATA_ONLY_HOSTS = ("indiacode.nic.in", "gov.in", "nic.in", "tele-law.in")

# Strings that are documentation or schema identifiers, never network calls.
_ALLOWED_LITERALS = ("w3.org", "reactjs.org", "127.0.0.1", "localhost")


def _sources() -> list[Path]:
    if not FRONTEND.is_dir():
        pytest.skip("the frontend is not present")
    return [
        path
        for path in FRONTEND.rglob("*")
        if path.suffix in {".ts", ".tsx", ".css"} and path.is_file()
    ]


def test_the_client_never_fetches_a_remote_host() -> None:
    """No fetch/import/asset may point anywhere but the loopback backend."""

    offenders: list[str] = []
    for path in _sources():
        text = path.read_text(encoding="utf-8")
        # Only flag a remote URL inside an actual request or asset reference.
        for match in re.finditer(
            r"""(?:fetch|import|src\s*=|href\s*=|url\()\s*\(?["'`](https?://[^"'`)]+)""",
            text,
        ):
            url = match.group(1)
            if any(allowed in url for allowed in _ALLOWED_LITERALS):
                continue
            if any(host in url for host in _DATA_ONLY_HOSTS):
                continue
            offenders.append(f"{path}: {url}")
    assert not offenders, "remote request in the client: " + "; ".join(offenders)


def test_no_analytics_telemetry_or_remote_fonts() -> None:
    banned = (
        "googletagmanager",
        "google-analytics",
        "gtag(",
        "fonts.googleapis",
        "fonts.gstatic",
        "cdn.jsdelivr",
        "unpkg.com",
        "cdnjs.cloudflare",
        "sentry",
        "posthog",
        "mixpanel",
    )
    for path in [*_sources(), INDEX_HTML]:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8").lower()
        for needle in banned:
            assert needle not in text, f"{path} references {needle}"


def test_the_content_security_policy_forbids_remote_connections() -> None:
    if not INDEX_HTML.is_file():
        pytest.skip("index.html is not present")
    html = INDEX_HTML.read_text(encoding="utf-8")

    assert "Content-Security-Policy" in html
    # Even if a remote request were introduced later, the browser must refuse it.
    assert "default-src 'self'" in html
    assert "connect-src 'self'" in html


def test_no_browser_storage_persists_a_citizens_case() -> None:
    """Nothing about the case may survive the tab, not even in localStorage."""

    for path in _sources():
        text = path.read_text(encoding="utf-8")
        for api in ("localStorage", "sessionStorage", "document.cookie", "indexedDB"):
            assert api not in text, f"{path} uses {api}"


def test_the_model_client_refuses_any_non_loopback_host() -> None:
    """Inference is where user facts would leak. Only loopback is reachable."""

    for url in (
        "http://example.com:11434",
        "http://10.0.0.5:11434",
        "http://169.254.169.254:11434",  # cloud metadata endpoint
        "http://[2001:db8::1]:11434",
    ):
        with pytest.raises(OllamaError):
            OllamaClient(url)

    for url in ("http://127.0.0.1:11434", "http://localhost:11434", "http://[::1]:11434"):
        assert OllamaClient(url).base_url.startswith("http://")


def test_nothing_in_the_serving_path_logs_a_citizens_case() -> None:
    """A log line is a copy. The case must not end up in one.

    There is no application logging in the request path, and the server's access log
    is off, so no case fact reaches a log file. Assert it rather than rely on it
    staying true.
    """

    serving = [
        Path("src/api/app.py"),
        Path("src/api/state.py"),
        Path("src/pipeline.py"),
        Path("src/agents/drafter.py"),
        Path("src/agents/verifier.py"),
        Path("src/agents/researcher.py"),
    ]
    for path in serving:
        if not path.is_file():
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            for call in ("logger.", "logging.", "print("):
                assert call not in stripped, f"{path}:{number} logs in the serving path"

    launcher = Path("scripts/serve_api.py")
    if launcher.is_file():
        # Uvicorn's access log records every request line. Off.
        assert "access_log=False" in launcher.read_text(encoding="utf-8")
