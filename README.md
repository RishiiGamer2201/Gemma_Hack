# Nyaya Navigator

An offline-first, multilingual legal-navigation prototype for the Build with Gemma
hackathon. The system is designed to confirm a citizen's facts, retrieve date-applicable
official law, verify claim-to-source support, and produce understandable next steps.

This is an informational prototype, not a lawyer and not a substitute for professional
legal advice.

## Current milestone

The system now runs end to end, on device: a citizen describes a situation in
English, Hindi, or Hinglish (typed or spoken), confirms the extracted facts, and —
for a case that is not routed to a human or refused — receives a plain-language
answer in which every legal claim has been independently verified against retrieved
official law, or the answer is withheld.

Working components:

- typed legal-intake, evidence, answer, and verification models with a workflow
  state machine that blocks retrieval before explicit user confirmation;
- deterministic English/Hindi/Hinglish text intake and offline voice transcription
  behind that same confirmation gate;
- domain-scoped hybrid retrieval (dependency-free BM25 fused with local
  EmbeddingGemma vectors) over 6,845 reviewed official-law chunks;
- a grounded drafter and an **independent claim-level verifier**: the verifier sees
  only a claim and the excerpts it cites, and a claim naming a provision its sources
  do not contain is rejected deterministically before the model is even consulted;
- confirmed-facts safety and power routing that refuses outcome predictions and
  routes urgent cases to human help before any model call;
- a visibly streamed Devil's Advocate stress test over a verified answer;
- a Rights Card generator whose every line is sourced and whose QR links only to an
  official government URL;
- a strict offline Delhi DLSA finder (NALSA 15100 / Tele-Law 14454 fallbacks),
  evidence checklists, IPC/BNS temporal-mapping primitives, and a Delhi Rent Control
  applicability gate;
- a loopback-only FastAPI layer and a local React client over all of the above.

Official-source chunks remain marked `pending_human_review`, several central acts
carry an unverified-commencement warning that is displayed on every citation, and
the IPC/BNS mapping catalogue is intentionally empty until a human reviewer approves
entries. See `IMPLEMENTATION_PLAN.md` for the audited status of every item.

## Setup — fresh clone, step by step

Everything runs on your own machine. Follow the steps in order; each says what it is
for so you can stop at the level you need.

### 0. Prerequisites

Install these first:

| Tool | Version | Notes |
|---|---|---|
| Python | 3.11 or 3.12 | 3.13 also works. Avoid 3.14 for now. |
| [uv](https://docs.astral.sh/uv/getting-started/installation/) | latest | Python package manager used here. `pip` works too — see the note in step 2. |
| Node.js | 20+ | Only for the web UI. |
| [Ollama](https://ollama.com/download) | latest | Runs the local model. |

### 1. Clone

```powershell
git clone https://github.com/RishiiGamer2201/Gemma_Hack.git
cd Gemma_Hack
```

### 2. Install Python dependencies

```powershell
uv sync --extra api --extra ocr --extra speech --extra card --extra dev
```

This creates a `.venv` and installs everything for the API, OCR, voice, Rights Card,
and tests. `uv run <command>` then runs inside that environment.

> **Do not add `--extra retrieval`** — there is no such extra. The semantic search
> uses EmbeddingGemma through Ollama and needs no extra Python library. (An older
> command that included `--extra retrieval` fails with an "unsatisfiable
> requirements" resolver error; that extra was removed.)

Lighter installs, if you do not need everything:

```powershell
uv sync --extra api --extra card --extra dev   # text-only app + tests (no voice/OCR)
```

Prefer plain `pip`? `python -m venv .venv`, activate it, then
`pip install -e ".[api,ocr,speech,card,dev]"`.

### 3. Pull the local model

```powershell
ollama pull gemma4:e4b-it-q4_K_M   # the answering model
ollama pull embeddinggemma         # semantic retrieval (skip only if using NYAYA_USE_EMBEDDINGS=0)
```

Keep `ollama serve` running (the Ollama app starts it for you on Windows/macOS).

### 4. Get the legal corpus

The app answers from ~6,845 reviewed official-law chunks. That data is **Git-ignored**
(it is large and rebuilt from official PDFs), so a fresh clone has none yet. Choose one:

- **Copy from a teammate** — the fastest path. Copy the whole `data/` (and `models/`
  if you want voice/OCR) folder from someone who has already built it.
- **Build it yourself** — download the official PDFs, then chunk them:

  ```powershell
  uv sync --extra corpus                                   # adds the PDF reader
  uv run python scripts/download_official_sources.py --manifest config/official_sources.json
  uv run python scripts/build_corpus.py --manifest config/official_sources.json --raw-dir data/raw/official_law --output-dir data/processed/sections
  uv run python scripts/build_index.py                     # precompute EmbeddingGemma vectors
  ```

Without a corpus the server still starts, but `/api/health` reports
`corpus_loaded: false` and answers cannot be produced.

### 5. Run the app

```powershell
# Terminal 1 — loopback-only API on 127.0.0.1:8000
uv run python scripts/serve_api.py --port 8000

# Terminal 2 — local React client on 127.0.0.1:5173
cd frontend
npm install
npm run dev
```

Open **http://127.0.0.1:5173**. The whole flow runs on device — disable Wi-Fi and it
still works. Set `NYAYA_USE_EMBEDDINGS=0` before starting the API to fall back to
lexical-only retrieval if you skipped `embeddinggemma`.

### 6. Verify it works

```powershell
uv run python -m pytest            # the full test suite should pass
curl http://127.0.0.1:8000/api/health
```

A healthy server returns `corpus_loaded: true` with a chunk count once step 4 is done.

## Offline pipelines and CLIs

```powershell
uv run python scripts/find_legal_aid.py --district "Rouse Avenue" --state Delhi
uv run python scripts/get_evidence_checklist.py --template unpaid_wages
uv run python scripts/transcribe_audio.py --audio request.wav --model-path models/asr/faster-whisper-small --model-revision 536b0662742c02347bc0e980a01041f333bce120 --language hi --device cpu --compute-type int8
uv run python scripts/extract_image_text.py --image notice.jpg --tessdata-dir models/ocr/tessdata --language eng+hin
```

Voice (`speech` extra) and OCR (`ocr` extra) also need pinned local model/binary
assets; acquisition is documented in `docs/asr_feasibility.md` and
`docs/ocr_feasibility.md`. Runtime inference verifies those pinned assets and does not
download missing models.

## Troubleshooting

- **`uv sync` fails with "requirements are unsatisfiable" / sentence-transformers vs
  tokenizers** — you used `--extra retrieval`. Remove it; use the step 2 command.
- **`/api/health` shows `corpus_loaded: false`** — do step 4 (copy or build `data/`).
- **`VIRTUAL_ENV ... does not match` warning from uv** — harmless; uv uses the
  project's `.venv`. Prefix commands with `uv run` and ignore it.
- **The model call errors or times out** — confirm `ollama serve` is running and both
  models from step 3 are pulled (`ollama list`).

## Safety boundaries

- Official government sources and effective dates outrank model memory.
- The user must confirm extracted facts before personalized legal information.
- Unsupported claims are removed, retried against retrieval, or refused.
- No case-outcome probabilities or fabricated confidence scores.
- Uploaded documents and transcripts are not persisted by default.
- The intended demo operates with network connectivity disabled.
