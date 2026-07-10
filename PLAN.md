# Build Plan — Track 1: Multilingual AI Legal Assistant

**Team:** Judge My Win · **Hackathon:** Build with Gemma – AIMS DTU, 15 July 2026
**Concept:** *"Nyaya in your pocket, in your language, on your device"* — voice-first, on-device legal assistant grounded in BNS-era Indian law with verbatim citations, a **verifier agent** that checks every claim, and a **Devil's Advocate mode** that argues the other side.

> Updated 11 July after [FULL_REVIEW.md](FULL_REVIEW.md) (team ideation doc + IEEE papers) and [SENIOR_REVIEW.md](SENIOR_REVIEW.md). Feature set below is **locked** — additions only if a phase finishes early.

**Team roles:**
| Member | Owns |
|---|---|
| Member A | Model pipeline (Gemma 4, Ollama, audio/image) — Phase 1 |
| Member B | Data + RAG (corpus, embeddings, retrieval, eval set) — Phase 2 (see [DATASET.md](DATASET.md)) |
| Member C | App UI + agent pipeline + tools — Phase 3 |
| Member D | Writeup, pitch deck, demo video — Phase 5 (starts day 1, full-time) |

## 🔒 Locked feature set (MVP + three wows)

**Base pipeline (MVP):** cited answers · voice input (Hindi/English) · photo intake (FIR/notice/rent paper) · `search_law` · `find_legal_aid` · `draft_document` · "legal information, not legal advice" framing + human routing.

**The three wows:**
1. **Verifier agent with visible trace** (technical wow) — Intake → Classifier → Researcher (RAG) → Strategist → Drafter → Verifier; agent trace shown in a debug panel. The Verifier checks every claim against retrieved law and flags anything unsupported — it doubles as the explainability panel.
2. **Devil's Advocate mode** (demo wow) — same model, 3 sequential role prompts: build the case → opposing counsel attacks it (gets a *summary*, not chat history) → advocate shores up weaknesses. Stream tokens with stage labels ("⚖️ Opposing counsel is reviewing your case…").
3. **Rights Card generator** (shareable wow) — pocket "know your rights" image card in the user's language with section numbers + helplines + **QR code linking to the bare act on India Code**.

**Prompt-level freebies (near-zero build cost):**
- **Confirmation loop** — restate the user's situation and ask "correct?" before advising.
- **BNS↔IPC time-awareness** — ask "before or after 1 July 2024?"; map old IPC sections to BNS via a small table.
- **Urgency/safety triage** — DV/arrest/eviction/deadline cases → safety resources + human routing *first*.
- **"What happens if I do nothing"** — consequences grounded only in statutory deadlines we can cite.
- Negotiation escalation kit (polite message → firm letter → legal notice) as three `draft_document` templates.
- Simple/Detailed mode toggle (system-prompt switch) — only if time allows.

**❌ Explicitly rejected (know why, for judges):** lawyer-facing courtroom diarization (off-track) · Whisper+pyannote (Gemma 4 has native audio) · Qwen or any non-Gemma model (disqualifying) · outcome statistics / case-strength percentages (fabrication risk — our whole thesis) · blockchain layer (audits documents, not advice — see JusticeAI in [RELATED_WORK.md](RELATED_WORK.md)) · GRPO post-training (roadmap, not a 1-day activity).

---

## Phase 0 — Concept Lock ✅ (done 10–11 July)

- [x] Concept, tagline, and track locked
- [x] Demo languages: **Hindi + English**
- [x] 3 demo scenarios locked:
  - [x] Scenario 1: "My landlord won't return my security deposit" (civil/rent/consumer)
  - [x] Scenario 2: "Explain this FIR / legal notice" — photo intake (BNS criminal law)
  - [x] Scenario 3: "My employer hasn't paid my wages" (labour law)
- [x] Research corpus complete: [RESEARCH.md](RESEARCH.md), [SENIOR_REVIEW.md](SENIOR_REVIEW.md), [RELATED_WORK.md](RELATED_WORK.md), [FULL_REVIEW.md](FULL_REVIEW.md)
- [ ] Pick the assistant's name (e.g., "NyayaSathi", "Adhikar", "Kanoon Dost")
- [ ] Everyone reads FULL_REVIEW.md Part C (the locked-scope table)
- [ ] **Find and read the "Legal Buddy" Gemma 4 Challenge submission** — closest competitor; rehearse our differentiation (citizen voice-first UX, BNS mapping, verifier agent, legal-aid routing)
- [ ] Kaggle accounts + event registration confirmed for all four

## Phase 1 — Validate the Model Pipeline (11–12 July) ⚠️ GO/NO-GO

> Highest-risk phase. Do this before building anything else.
> ⚠️ Model name is **`gemma4:e4b`** — the team doc's `gemma3:4b` references are stale (Gemma 3 4B had no audio/image). Same 8 GB VRAM conclusion holds: E4B ≈ 3 GB at Q4.

- [ ] Install [Ollama](https://ollama.com/download) on the demo laptop
- [ ] Pull Gemma 4 E4B: `ollama pull gemma4:e4b`
- [ ] **Test 1 — Hindi text:** legal question in Hindi; judge fluency and register
- [ ] **Test 2 — Audio input:** speak a legal problem in Hindi (native Gemma 4 audio)
- [ ] **Test 3 — Image input:** photo of a printed legal notice / FIR; verify it reads and explains
- [ ] **Test 4 — Function calling:** dummy `search_law` JSON tool; verify correct calls
- [ ] **Test 5 — Role prompts:** quick Devil's-Advocate dry run (3 sequential calls, same model) — verify the adversary actually argues the other side
- [ ] Measure tokens/sec (CPU vs GPU); sequential-call latency budget for Devil's Advocate (2–3× a normal answer — plan streamed stage labels)
- [ ] **Fallbacks (only if a test fails):**
  - [ ] Hindi weak → try `gemma4:12b`, or route through [IndicTrans2](https://github.com/AI4Bharat/IndicTrans2)
  - [ ] Audio weak → [IndicConformer ASR](https://github.com/AI4Bharat/IndicConformerASR) (30M params, on-device)
  - [ ] Laptop too slow → borrow GPU laptop, or Kaggle GPU notebook with local-first framing
- [ ] Record screen captures of successful tests (reusable in demo video)

## Phase 2 — Data + RAG + Eval Set (12 July)

> Full download instructions in [DATASET.md](DATASET.md)

- [ ] Download bare acts for the 3 scenarios (BNS, BNSS, Consumer Protection Act, Delhi Rent Act, Payment of Wages Act, LSA Act)
- [ ] **NEW: Constitution of India** ([legislative.gov.in](https://legislative.gov.in/constitution-of-india/)) — top retrieval-priority tier
- [ ] **NEW: Hindi versions of core acts** ([legislative.gov.in important legislations](https://legislative.gov.in/important-legislations/)) — grounded Hindi citations without a translation step
- [ ] NALSA legal-aid eligibility + Delhi DLSA contacts CSV + Tele-Law 14454 (for `find_legal_aid`)
- [ ] Chunk by **section**, metadata `{act, section_no, title, text, language, priority}` — **priority tiers: 1 = Constitution, 2 = BNS/BNSS/BSA/CPC/Contract Act, 3 = other acts**; rank retrieved citations by tier
- [ ] Embeddings + vector store (ChromaDB/FAISS; [InLegalBERT](https://huggingface.co/law-ai/InLegalBERT) or MiniLM fallback)
- [ ] **NEW: BNS↔IPC mapping table** (~50 most-cited sections) for the converter feature
- [ ] **NEW: limitation-period table** for the 3 demo scenarios (consumer complaint: 2 years; wage claims; notice reply windows) — powers "what happens if I do nothing" with citable deadlines
- [ ] Verify criminal-law retrieval returns **BNS (2023), not IPC**
- [ ] **NEW: eval set (LexiServe-style, for the writeup):** 30–50 labeled queries → measure (a) legal-domain classification accuracy, (b) Top-K retrieval accuracy, vs a naive keyword-search baseline. Optional extra queries from the akshatgupta7 Kaggle dataset — **Constitution subset only** (IPC/CrPC pairs reference repealed law)
- [ ] Spot-check: retrieval hit-rate ≥ 8/10 before wiring to the model

## Phase 3 — Agent Pipeline + App + Tools (12–13 July)

- [ ] Scaffold app: **Streamlit or Gradio**, single-page chat UI
- [ ] Wire chat → Ollama (OpenAI-compatible API at `localhost:11434`)
- [ ] Mic input (Gemma 4 native audio; ASR fallback) + photo upload (native image)
- [ ] **Agent pipeline (one loaded model, role prompts in sequence):**
  - [ ] Intake agent — extracts facts, runs the **confirmation loop** ("So you're saying… correct?")
  - [ ] Classifier — legal domain + **"before or after 1 July 2024?"** when criminal
  - [ ] Researcher — calls `search_law` (RAG, priority-ranked)
  - [ ] Strategist — options incl. the other side's likely argument; protective tone for weaker party; **urgency/safety triage first** for DV/arrest/eviction
  - [ ] Drafter — `draft_document`: complaint, legal-aid application, RTI, + **escalation kit** (message → letter → legal notice)
  - [ ] **Verifier — checks every claim against retrieved sections; flags unsupported claims; low confidence → recommend Tele-Law (14454) / nearest DLSA**
  - [ ] **Debug panel showing the live agent trace** (= explainability panel)
- [ ] **Devil's Advocate mode:** 3 sequential calls (advocate → opposing counsel on a case *summary* with a tight adversarial prompt → advocate rebuts); streamed stage labels
- [ ] **Rights Card generator:** image card (Pillow/HTML-to-image) — situation, key sections, helplines, **QR to India Code** (`qrcode` lib)
- [ ] Tools via Gemma 4 function calling: `search_law(query)` · `find_legal_aid(district)` · `draft_document(type, facts)`
- [ ] **Citation UI:** every answer renders verbatim section text + act name in an expandable box
- [ ] Language toggle/auto-detect (Hindi/English); Simple/Detailed toggle if time allows
- [ ] End-to-end test: all 3 demo scenarios pass voice-in → verified, cited answer out

## Phase 4 — Integration + Rehearsal (13–14 July)

- [ ] Full dry run on the demo laptop, **offline (Wi-Fi off)** — the offline demo is a pitch moment
- [ ] Rehearse the **Devil's Advocate moment** and the **verifier catching an unsupported claim live** — these two make the demo memorable
- [ ] Time the demo: ≤ 4 minutes for 3 scenarios + one wow each
- [ ] Printed props: fake FIR / legal notice to photograph live
- [ ] Run the eval set; record the numbers for the writeup
- [ ] Freeze code by evening of 14 July; tag `v1.0` on GitHub
- [ ] Backup: screen-recorded full demo video; export Ollama model + venv to a second laptop; charge everything

## Phase 5 — Writeup + Pitch (11–14 July, parallel, Member D full-time)

- [ ] Draft the writeup (Kaggle format):
  - [ ] **Human story:** one named persona (e.g., a domestic worker in Bawana with a wage dispute)
  - [ ] **Problem:** >50% with legal problems get no representation; **1 legal-aid clinic per 163 villages; ~16 lakh aided vs ~80% eligible** (JusticeAI intro stats — verify primary sources); language/cost/awareness barriers
  - [ ] **Why now:** IPC→BNS transition (1 July 2024) — even lawyers are relearning; no citizen tool is BNS-current
  - [ ] **Why Gemma 4:** native audio+image on-device, 140+ languages, function calling, privacy by construction
  - [ ] **The honesty slide:** legal AI hallucinates 1-in-6 (Stanford) + **png2 exhibit** ("Section 247A of the Constitution" — doesn't exist) → our answer: RAG + verifier agent + verbatim citations + human routing
  - [ ] **Related work + positioning table** from [RELATED_WORK.md](RELATED_WORK.md) (JusticeAI, LexiServe, Mina — all cloud, pre-2024 law, text-only; we're on-device, multimodal, BNS-current, citation-grounded)
  - [ ] **Eval numbers** from Phase 2 (classification + Top-K retrieval vs keyword baseline)
  - [ ] **Architecture diagram** (voice/photo → agent pipeline → verified cited answer → tools)
  - [ ] **Roadmap slide:** 22 scheduled languages · WhatsApp channel · DLSA partnership · state-specific acts · case timeline builder · panchayat bridge mode · GRPO reasoning refinement (Tunix recipe) · lawyer mode
- [ ] Pitch deck (≤ 8 slides matching the skeleton) + 2–3 min demo video
- [ ] Rehearse judge Q&A:
  - [ ] "Why not ChatGPT?" → privacy, offline, cost; on-device is the track premise
  - [ ] "Wrong legal advice?" → verifier + citations + confirmation loop + human routing + disclaimer
  - [ ] "vs Jugalbandi?" → on-device, legal reasoning not scheme lookup, BNS-current, citations
  - [ ] "vs Legal Buddy?" → citizen voice-first UX, BNS↔IPC mapping, verifier agent, legal-aid routing
  - [ ] "Why no blockchain?" → it audits documents, not advice; our verifier audits the advice itself

## Hackathon Day — 15 July, 10 AM–6 PM, AB-3 DTU

- [ ] Arrive early; venue Wi-Fi/power check; full offline smoke test
- [ ] Final polish only — no new features after 2 PM
- [ ] Submit writeup + code on Kaggle before deadline
- [ ] Deliver pitch; capture judge feedback in this repo afterwards
