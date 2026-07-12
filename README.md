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
- a command-line smoke-test application using a synthetic corpus.

The fixture corpus is deliberately synthetic and must never be used for real legal
answers. Production ingestion of official statutes is tracked in
`IMPLEMENTATION_PLAN.md`.

## Quick start

Python 3.11 or newer is required.

```powershell
python -m src.app --query "old section mapping"
python -m unittest discover -s tests -v
```

Optional dependencies can later be installed with:

```powershell
uv sync --extra ui --extra retrieval --extra dev
```

Ollama is optional. When enabled, the adapter accepts only loopback hosts such as
`127.0.0.1` and `localhost`.

## Safety boundaries

- Official government sources and effective dates outrank model memory.
- The user must confirm extracted facts before personalized legal information.
- Unsupported claims are removed, retried against retrieval, or refused.
- No case-outcome probabilities or fabricated confidence scores.
- Uploaded documents and transcripts are not persisted by default.
- The intended demo operates with network connectivity disabled.
