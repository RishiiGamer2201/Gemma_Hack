# Nyaya Navigator

An offline-first, multilingual legal-navigation prototype for the Build with Gemma
hackathon. The system is designed to confirm a citizen's facts, retrieve date-applicable
official law, verify claim-to-source support, and produce understandable next steps.

This is an informational prototype, not a lawyer and not a substitute for professional
legal advice.

## Current milestone

The first implementation milestone provides:

- typed legal-intake, evidence, answer, and verification models;
- a workflow state machine that blocks retrieval before user confirmation;
- date-aware IPC/BNS mapping primitives;
- dependency-light BM25 and hybrid retrieval interfaces;
- a localhost-only optional Ollama adapter;
- a command-line smoke-test application using a synthetic corpus;
- a reviewed official-source manifest and hostile-network downloader;
- receipt-verified local PDF extraction and deterministic section-aware JSONL builds;
- a strict offline Delhi DLSA finder with NALSA and Tele-Law fallbacks;
- validated evidence-preparation checklists for the three demo scenarios;
- deterministic English, Hindi, and Hinglish text intake with a hard confirmation gate;
- confirmed-facts safety and power routing with prompt-injection isolation;
- provenance-safe retrieval expansion, deduplication, filters, hashes, and debug traces.
- pinned offline English/Hindi ASR and English/Hindi image OCR adapters;
- a verified-evidence-only, visibly streamed Devil's Advocate workflow;
- page-level scan-review and OCR provenance in corpus builds.

The fixture corpus is deliberately synthetic and must never be used for real legal
answers. Official-source chunks remain marked `pending_human_review` until the corpus
audit in `IMPLEMENTATION_PLAN.md` is complete.

## Quick start

Python 3.11 or newer is required.

```powershell
python -m src.app --query "old section mapping"
python -m unittest discover -s tests -v
python scripts/download_official_sources.py --manifest config/official_sources.json --list
python scripts/download_official_snapshots.py --manifest config/official_web_sources.json --list
python scripts/build_corpus.py --manifest config/official_sources.json --raw-dir data/raw/official_law --output-dir data/processed/sections
python scripts/build_sankalan_candidates.py
python scripts/build_legal_aid_directory.py
python scripts/find_legal_aid.py --district "Rouse Avenue" --state Delhi
python scripts/get_evidence_checklist.py --template unpaid_wages
python scripts/process_text_intake.py --text "Mera rent deposit nahi mila" --domain tenancy_property --missing-fact "Incident date"
python scripts/route_safety.py --summary "My landlord has my deposit" --incident-date 2026-06-01 --jurisdiction Delhi --domain tenancy_property --party Tenant --party Landlord --confirmed-at 2026-07-13T02:30:00+05:30
python scripts/transcribe_audio.py --audio request.wav --model-path models/asr/faster-whisper-small --model-revision 536b0662742c02347bc0e980a01041f333bce120 --language hi --device cpu --compute-type int8
python scripts/extract_image_text.py --image notice.jpg --tessdata-dir models/ocr/tessdata --language eng+hin
```

Optional dependencies can later be installed with:

```powershell
uv sync --extra corpus --extra ui --extra retrieval --extra speech --extra ocr --extra dev
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
