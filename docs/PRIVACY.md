# What stays on the device

Nyaya Navigator is offline by construction. This document states exactly what data
exists, where it lives, and what leaves the machine — which is nothing.

## Nothing leaves the device

Every inference endpoint is loopback-only. `src/config.py` rejects any Ollama URL
whose host is not `127.0.0.1`, `localhost`, or `::1`, and the Ollama adapter
(`src/agents/ollama.py`) additionally strips proxy handlers and refuses redirects, so
a local service cannot bounce a request to a remote host. The embedding runtime uses
the same client, so retrieval never sends corpus or query text off the machine.

The corpus downloader and snapshot tools (`src/corpus/`) are the only components that
open outbound connections, and they run at build time against an explicit per-source
HTTPS allowlist with redirects disabled. They are never invoked while answering a
user. The intended demo runs with Wi-Fi disabled.

The browser client ships a Content-Security-Policy of `default-src 'self'` with
`connect-src 'self'`, uses a system font stack, and loads no remote script, font, or
image. `tests/test_offline.py` asserts the offline guards; the frontend has no
`localStorage`, `sessionStorage`, or cookies.

## What is held, and for how long

| Data | Where | Lifetime |
|---|---|---|
| Typed situation, confirmed facts | Process memory only | The request; never written to disk |
| Uploaded image / audio / PDF | Process memory only | Decoded in memory, never spooled to a temp file |
| OCR / ASR transcript | Process memory only | Returned to the caller; not persisted |
| Generated answer, verdicts | Process memory only | The response; not persisted |
| Official corpus, embeddings cache | `data/processed`, `data/indexes` | Build artifacts; contain no user data |

Uploads stay in RAM for their whole lifetime: the API raises Starlette's multipart
spool bound above the image-size limit so a part is never rolled over to a temporary
file, and the OCR path rejects a mutable buffer to prevent aliasing. No case narrative,
document, or transcript is logged; `tests/test_offline.py` asserts that no confirmed
fact reaches the application log.

## What the user controls

The web client offers an explicit "start over" / clear-session control that discards
the current facts and answer from memory. Because nothing was persisted, clearing the
session leaves nothing behind.

## What is not private

Only the build-time corpus acquisition touches the network, and only against official
government hosts. The processed corpus and the embedding cache are ordinary files on
disk; they hold public statute text and vectors of it, never anything a user typed.
