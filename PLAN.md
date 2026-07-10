# Build Plan — Track 1: Multilingual AI Legal Assistant

**Team:** Judge My Win · **Hackathon:** Build with Gemma – AIMS DTU, 15 July 2026
**Concept:** *"Nyaya in your pocket, in your language, on your device"* — voice-first, on-device legal assistant grounded in BNS-era Indian law with verbatim citations.

**Team roles:**
| Member | Owns |
|---|---|
| Member A | Model pipeline (Gemma 4, Ollama, audio/image) — Phase 1 |
| Member B | Data + RAG (corpus, embeddings, retrieval) — Phase 2 (see [DATASET.md](DATASET.md)) |
| Member C | App UI + function-calling tools — Phase 3 |
| Member D | Writeup, pitch deck, demo video — Phase 5 (starts day 1, full-time) |

---

## Phase 0 — Lock the Concept (Today, 10 July)

- [ ] Agree on final concept and name for the assistant (e.g., "NyayaSathi", "Adhikar", "Kanoon Dost")
- [ ] Pick demo languages: **Hindi + English** (add one regional language only if Phase 1 tests go well)
- [ ] Pick 3 demo scenarios (these drive corpus, tools, and pitch):
  - [ ] Scenario 1: "My landlord won't return my security deposit" (civil / rent law)
  - [ ] Scenario 2: "Explain this FIR / legal notice" — photo intake (BNS criminal law)
  - [ ] Scenario 3: "My employer hasn't paid my wages for 2 months" (labour law)
- [ ] Each member confirms their role and reads [RESEARCH.md](RESEARCH.md)
- [ ] Create Kaggle accounts for all members; confirm event registration status

## Phase 1 — Validate the Model Pipeline (10–11 July) ⚠️ GO/NO-GO

> Highest-risk phase. Do this before building anything else.

- [ ] Install [Ollama](https://ollama.com/download) on the demo laptop
- [ ] Pull Gemma 4 E4B: `ollama pull gemma4:e4b` (~3 GB quantized)
- [ ] **Test 1 — Hindi text:** ask a legal question in Hindi, judge fluency and correctness of register
- [ ] **Test 2 — Audio input:** speak a legal problem in Hindi; verify Gemma 4 E4B's native audio understanding
- [ ] **Test 3 — Image input:** photo of a printed legal notice / FIR; verify it reads and explains it
- [ ] **Test 4 — Function calling:** define a dummy `search_law` JSON tool; verify E4B calls it correctly
- [ ] Measure tokens/sec on demo laptop (CPU vs GPU); decide if E4B is fast enough live
- [ ] **Fallback decisions (only if a test fails):**
  - [ ] Hindi weak → try `gemma4:12b`, or route through [IndicTrans2](https://github.com/AI4Bharat/IndicTrans2) translation
  - [ ] Audio weak → front with [IndicConformer ASR](https://github.com/AI4Bharat/IndicConformerASR) (30M params, on-device)
  - [ ] Laptop too slow → borrow a GPU laptop, or demo on Kaggle GPU notebook with local-first framing
- [ ] Record short screen captures of successful tests (reusable in demo video)

## Phase 2 — Data + RAG (11–12 July)

> Full download instructions in [DATASET.md](DATASET.md)

- [ ] Download bare acts needed by the 3 scenarios (BNS, BNSS, Consumer Protection Act, Delhi Rent Act, Payment of Wages Act)
- [ ] Download NALSA legal-aid info + DLSA contact directory (for the `find_legal_aid` tool)
- [ ] Write chunker: split acts **by section**, keep metadata `{act, section_no, title, text}`
- [ ] Build embeddings + vector store (ChromaDB or FAISS; embedder: [InLegalBERT](https://huggingface.co/law-ai/InLegalBERT) or `sentence-transformers/all-MiniLM-L6-v2` as a simpler fallback)
- [ ] Build `search_law(query) -> [sections]` retrieval function; test on all 3 scenarios
- [ ] Verify retrieved sections are **BNS (2023), not IPC** for criminal queries
- [ ] Spot-check 10 queries: retrieval hit-rate ≥ 8/10 before wiring to the model

## Phase 3 — App + Function Calling (12–13 July)

- [ ] Scaffold app: **Streamlit or Gradio**, single-page chat UI
- [ ] Wire chat → Ollama (OpenAI-compatible API at `localhost:11434`)
- [ ] Add mic input (browser audio → Gemma 4 native audio, or ASR fallback)
- [ ] Add photo upload → Gemma 4 image input
- [ ] Implement tools via Gemma 4 function calling:
  - [ ] `search_law(query)` — RAG retrieval from Phase 2
  - [ ] `find_legal_aid(district)` — NALSA/DLSA lookup
  - [ ] `draft_document(type, facts)` — complaint / RTI / legal-aid application template
- [ ] **Citation UI:** every answer renders the verbatim section text + act name in an expandable box
- [ ] **Safety layer:** system prompt with "legal information, not legal advice" framing; low-confidence → recommend Tele-Law (call 14454) / nearest DLSA
- [ ] Language toggle or auto-detect for Hindi/English responses
- [ ] End-to-end test: all 3 demo scenarios pass, voice-in → cited answer out

## Phase 4 — Integration + Rehearsal (13–14 July)

- [ ] Full dry run on the actual demo laptop, **offline (Wi-Fi off)** — the offline demo is a pitch moment
- [ ] Time the demo: target ≤ 4 minutes for all 3 scenarios
- [ ] Prepare printed props: a fake FIR / legal notice to photograph live
- [ ] Freeze code by evening of 14 July; tag `v1.0` on GitHub
- [ ] Backup plan: screen-recorded video of the full demo in case of live failure
- [ ] Charge everything; export the Ollama model + venv to a second laptop as hardware backup

## Phase 5 — Writeup + Pitch (10–14 July, parallel, Member D full-time)

- [ ] Draft the writeup (Kaggle format) with this skeleton:
  - [ ] **The human story:** one named persona (e.g., a domestic worker in Bawana with a wage dispute)
  - [ ] **The problem:** >50% of Indians with legal problems get no representation; language + cost + awareness barriers ([RESEARCH.md](RESEARCH.md) has all stats + sources)
  - [ ] **Why now:** IPC→BNS transition (July 2024) — even lawyers are confused; no citizen tool is BNS-current
  - [ ] **Why Gemma 4 specifically:** native audio+image on-device, 140+ languages, function calling, privacy by construction
  - [ ] **The honesty slide:** legal AI hallucinates 1-in-6 (Stanford) → our grounding: verbatim citations + human routing
  - [ ] **Architecture diagram** (voice/photo → Gemma 4 E4B → RAG → cited answer → tools)
  - [ ] **Impact & roadmap:** 22 scheduled languages, WhatsApp channel, DLSA partnership
- [ ] Build pitch deck (≤ 8 slides matching writeup skeleton)
- [ ] Record 2–3 min demo video
- [ ] Rehearse pitch twice with full team; prep answers for likely judge questions:
  - [ ] "Why not just use ChatGPT?" → privacy, offline, cost, on-device is the track premise
  - [ ] "What if it gives wrong legal advice?" → grounding + citations + human routing + disclaimer
  - [ ] "How is this different from Jugalbandi?" → on-device, legal reasoning not scheme lookup, BNS-current, citations

## Hackathon Day — 15 July, 10 AM–6 PM, AB-3 DTU

- [ ] Arrive early; test venue Wi-Fi and power; run smoke test of full demo
- [ ] Final polish only — no new features after 2 PM
- [ ] Submit writeup + code on Kaggle before deadline
- [ ] Deliver pitch; capture judge feedback in this repo afterwards
