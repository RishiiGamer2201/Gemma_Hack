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

## Quick start — the app

Python 3.11+, Node 20+, and a local [Ollama](https://ollama.com/download) with
`gemma4:e4b-it-q4_K_M` and `embeddinggemma` pulled. The corpus, models, and indexes
are Git-ignored; build them with the pipeline commands below or copy them from a
prepared drive.

```powershell
# 1. Python environment and dependencies
uv sync --extra api --extra retrieval --extra ocr --extra speech --extra card --extra dev

# 2. Start the loopback-only API (127.0.0.1:8000)
python scripts/serve_api.py --port 8000

# 3. In a second terminal, the local React client (127.0.0.1:5173)
cd frontend
npm install
npm run dev
```

Open http://127.0.0.1:5173. The whole flow runs on device; disable Wi-Fi and it
still works. Set `NYAYA_USE_EMBEDDINGS=0` to fall back to lexical-only retrieval if
the embedding model is unavailable.

## Quick start — offline pipelines and CLIs

```powershell
python -m unittest discover -s tests -v
python scripts/build_corpus.py --manifest config/official_sources.json --raw-dir data/raw/official_law --output-dir data/processed/sections
python scripts/build_index.py            # precompute EmbeddingGemma vectors per domain
python scripts/build_legal_aid_directory.py
python scripts/find_legal_aid.py --district "Rouse Avenue" --state Delhi
python scripts/get_evidence_checklist.py --template unpaid_wages
python scripts/transcribe_audio.py --audio request.wav --model-path models/asr/faster-whisper-small --model-revision 536b0662742c02347bc0e980a01041f333bce120 --language hi --device cpu --compute-type int8
python scripts/extract_image_text.py --image notice.jpg --tessdata-dir models/ocr/tessdata --language eng+hin
```

Ollama is optional. When enabled, the adapter accepts only loopback hosts such as
`127.0.0.1` and `localhost`.

Speech and OCR model/runtime acquisition is documented in
`docs/asr_feasibility.md` and `docs/ocr_feasibility.md`. Runtime inference verifies
pinned local assets and does not download missing models.

## Safety boundaries

- Official government sources and effective dates outrank model memory.
- The user must confirm extracted facts before personalized legal information.
- Unsupported claims are removed, retried against retrieval, or refused.
- No case-outcome probabilities or fabricated confidence scores.
- Uploaded documents and transcripts are not persisted by default.
- The intended demo operates with network connectivity disabled.
