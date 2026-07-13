# Implementation Plan — Offline Multilingual Legal Navigation Assistant

**Team:** Judge My Win
**Hackathon:** Build with Gemma — AIMS DTU, 15 July 2026
**Working product statement:** An offline, multilingual legal-navigation assistant that confirms a citizen's situation, retrieves the law applicable on the incident date, explains rights and consequences with verified citations, stress-tests both sides, and generates actionable outputs.

> This document is the current implementation source of truth. `PLAN.md` remains as the historical planning record.

**Last evidence audit:** 13 July 2026. A checked box means the repository contains
working code/data plus automated or directly inspectable evidence. It does not treat
agent review as human legal review, and it does not infer completion of UI, model,
hardware, evaluation, or end-to-end demo gates from backend primitives alone.

## 1. Locked product scope

### Core journey — must work end to end

- [x] Accept English, Hindi, and Hinglish text input through the local intake interface.
- [x] Accept Hindi/English voice input and display the transcript before legal processing.
- [x] Accept a photo/PDF of an FIR, notice, summons, wage document, or rental document.
- [x] Extract a structured case summary: people, dates, location, dispute, documents, urgency, and missing facts.
- [x] Restate explicit facts in plain language and require confirmation before backend retrieval.
- [x] Add an interactive correction path to the future UI.
- [x] Route missing jurisdiction/date, confirmed urgency, and possible power-role patterns from confirmed fields.
- [x] Automatically classify domain and extract jurisdiction/date from free-form input.
- [x] Retrieve applicable official law using hybrid keyword and semantic search.
- [x] Provide backend effective-date/status filters and IPC/BNS temporal-routing primitives.
- [x] Integrate current/repealed-law routing into the production answer journey.
- [x] Generate a plain-language answer containing rights, options, evidence, deadlines, and next steps.
- [x] Verify each legal claim against retrieved official sources.
- [x] Display act name, section number, effective date, source excerpt, and official URL.
- [x] Abstain on unsupported submitted verdicts and route confirmed high-risk matters before retrieval.
- [x] Connect abstention/high-risk results to the Legal Aid Finder in the end-to-end journey.

### Locked differentiators

- [x] BNS ↔ IPC converter with incident-date awareness.
- [x] Devil's Advocate mode using sequential roles on one loaded Gemma model.
- [x] Rights Card image generator with section citations, helplines, disclaimer, and QR link.
- [x] “What happens if I do nothing?” citation-grounded consequence explanation.
- [x] Power-role protection prompts for tenant/landlord, worker/employer, and citizen/police situations.
- [x] Community Elder / Panchayat Bridge explanation for a trusted intermediary.
- [x] Legal Aid Finder using offline NALSA/DLSA snapshots and Tele-Law fallback.
- [x] Extend the Legal Aid Finder with state-specific SLSA snapshots.
- [x] Evidence/action preparation checklist tailored to the three demo case types.
- [x] Add sourced rights checklist content tailored to each case type.

### Explicit non-goals for the hackathon

- [x] Do **not** predict win probability, settlement percentage, sentence, or case outcome; the safety router hard-abstains.
- [x] Do **not** present an LLM confidence number as legal reliability; no output contract contains one.
- [x] Do **not** fine-tune Gemma before the RAG system and evaluation gates pass; no fine-tuned model is used.
- [x] Do **not** ingest a large case-law corpus for the MVP; evaluation data stays outside the production index.
- [x] Do **not** load two Gemma E4B instances simultaneously; no dual-model runtime path exists.
- [x] Do **not** promise all 22 languages; implemented scope is labeled English, Hindi, and Hinglish.
- [x] Do **not** send implemented user-query/document paths to cloud APIs; inference endpoints are loopback-only.

## 2. Team ownership

| Owner | Primary responsibility | Required handoff |
|---|---|---|
| Member A — Model & multimodal | Gemma runtime, prompts, voice, image/PDF understanding, latency | Stable local inference adapter and test results |
| Member B — Law data & retrieval | Official corpus, chunking, mappings, embeddings, BM25/vector retrieval | Versioned corpus, indexes, retrieval evaluation |
| Member C — Backend & product | Workflow controller, verification, tools, UI, persistence | Working end-to-end application |
| Member D — Evaluation & pitch | Test set, source review, demo script, Rights Card content, writeup | Evaluation report, deck, video, submission |

Shared rule: no feature is “done” until another member runs its acceptance test.

## 3. Target architecture

```text
Local UI
  ├─ Text → language/script normalization
  ├─ Voice → local transcript → user correction
  └─ Image/PDF → OCR + Gemma visual cross-check
        ↓
Structured fact extraction
        ↓
Confirmation gate
        ↓
Safety + jurisdiction + incident-date router
        ↓
Domain classification and query expansion
        ↓
Hybrid retrieval
  ├─ BM25 exact match
  ├─ EmbeddingGemma semantic search
  └─ metadata filters: act, jurisdiction, language, date, status
        ↓
Reranked evidence bundle
        ↓
Gemma strategy and answer generation
        ↓
Claim–citation verifier
        ├─ supported → citizen answer and tools
        └─ unsupported → retrieve again, remove claim, or abstain
        ↓
Devil's Advocate / Rights Card / Checklist / Legal Aid / Community mode
```

### Proposed stack

- [x] Python 3.11+ environment with locked dependencies.
- [ ] Streamlit for the hackathon UI; keep backend logic framework-independent.
- [x] Ollama or llama.cpp for local Gemma 4 inference.
- [x] Gemma 4 E4B Q4 as target; E2B as latency fallback.
- [x] EmbeddingGemma for multilingual semantic embeddings.
- [ ] FAISS for dense vectors.
- [ ] `rank-bm25` or SQLite FTS5 for exact retrieval.
- [x] Strict Pydantic schemas for legal intake, safety, mapping, answer, and verification boundaries.
- [x] PyMuPDF extraction for digitally readable PDFs.
- [x] Add OCR fallback for scanned PDFs.
- [x] Pillow + `qrcode` for Rights Cards.
- [x] Pytest for deterministic components and scenario tests.

## 4. Repository scaffold

- [x] Create `src/` package.
- [ ] Create `src/app.py` as the UI entry point.
- [x] Create `src/config.py` for paths, model choice, limits, and feature flags.
- [x] Create `src/models/` for Pydantic schemas.
- [x] Create `src/intake/` with deterministic text intake; voice and OCR remain pending.
- [x] Create `src/retrieval/` for BM25, optional embedding callbacks, filtering, fusion, deduplication, and debug traces.
- [x] Add the concrete EmbeddingGemma/FAISS vector implementation to `src/retrieval/`.
- [x] Create `src/legal_time/` for effective-date logic and IPC/BNS mapping.
- [x] Create `src/agents/` for researcher, strategist, verifier, and Devil's Advocate prompts.
- [x] Create `src/tools/` for legal aid, Rights Card, checklist, and document explanation.
- [x] Create `src/workflow/` for the deterministic state machine.
- [x] Create `scripts/` for corpus download/import and implemented local feature commands.
- [x] Add index-building and evaluation commands to `scripts/`.
- [x] Create `tests/` with unit, component-integration, and retrieval fixtures.
- [x] Add true end-to-end demo-scenario fixtures.
- [x] Create ignored `data/raw/` and `data/processed/` directories.
- [x] Create and populate the ignored `data/indexes/` directory.
- [x] Add `.env.example` containing only non-secret configuration keys.
- [x] Add a dependency file and reproducible setup instructions.
- [x] Add a one-command local launcher.

**Scaffold exit gate:** A clean clone can start a placeholder UI using documented commands.

## 5. Phase A — Local model feasibility gate

Owner: Member A
Dependency: none
Blocker for: agent pipeline and full UI

- [x] Record demo laptop CPU, RAM, GPU, VRAM, OS, and free disk space.
- [x] Install the approved local inference runtime.
- [x] Download Gemma 4 E4B Q4.
- [x] Download Gemma 4 E2B Q4 as a fallback.
- [x] Verify the exact model build and license.
- [x] Measure cold-start time.
- [x] Measure tokens/second for a 1K-token text prompt.
- [x] Measure peak RAM/VRAM for 2K, 4K, and 8K contexts.
- [x] Test Hindi, English, and Hinglish comprehension.
- [x] Test system-role and structured JSON output.
- [ ] Test image input on one printed notice and one phone photograph.
- [x] Test Hindi/English audio or establish the ASR fallback.
- [x] Test sequential advocate → opponent → rebuttal calls.
- [x] Set production context/output limits based on measured memory.
- [x] Save results in `docs/model_feasibility.md`.

**Acceptance gate:**

- [x] E4B produces valid structured output on the demo laptop without out-of-memory errors.
- [x] Normal answer latency is acceptable for a live demo.
- [x] Devil's Advocate stages stream visibly instead of appearing frozen.
- [ ] E2B fallback can complete every demo path if E4B is too slow.

## 6. Phase B — Official legal corpus

Owner: Member B
Dependency: none
Blocker for: trustworthy answers

### Mandatory documents

- [x] Download Constitution of India 2026 — English.
- [x] Download Constitution of India 2026 — Hindi/English diglot.
- [x] Download BNS 2023 from MHA/India Code.
- [x] Download BNSS 2023 from MHA/India Code.
- [x] Download BSA 2023 from MHA/India Code.
- [x] Download and process the Consumer Protection Act 2019.
- [x] Download and review relevant current Consumer Protection rules.
- [x] Download and process the Delhi Rent Control Act 1958.
- [x] Record substantive Delhi Rent Control Act applicability limitations for retrieval.
- [x] Download Code on Wages 2019.
- [x] Download Code on Wages implementation material and Central Rules 2026.
- [x] Download current Ministry of Labour FAQs.
- [x] Download Legal Services Authorities Act 1987.
- [x] Download NALSA free-legal-service regulations and eligibility material.
- [x] Snapshot the NALSA state authority directory.
- [x] Snapshot Delhi SLSA/DLSA contacts.
- [x] Record Tele-Law 14454 and official portal metadata.
- [x] Store official URL, download date, published/effective date, and SHA-256 for every downloaded source; retain explicit `null` where an effective date still needs review.

### Processing

- [x] Extract digitally readable sources while preserving page numbers and headings.
- [x] Detect scanned pages and flag OCR-derived text.
- [x] Split statutes by section boundaries, not arbitrary token windows.
- [ ] Keep provisos, explanations, illustrations, schedules, and amendments attached correctly.
- [x] Generate stable `source_id` values.
- [x] Add metadata: jurisdiction, act, section, language, effective dates, status, priority, URL, page.
- [x] Mark Constitution priority 1; current core codes priority 2; supporting laws priority 3.
- [ ] Validate 20 random chunks against the original PDFs.
- [ ] Have a second team member approve every act parser.

### Required chunk schema

- [x] Implement fields: `source_id`, `jurisdiction`, `act`, `section`, `heading`, `language`, `text`.
- [x] Implement fields: `effective_from`, `effective_to`, `status`, `priority`.
- [x] Implement fields: `official_url`, `page`, `retrieved_at`, `sha256`, `ocr_used`.

**Corpus exit gate:** At least 95% of a 40-section audit has correct act, section, text boundaries, page, and source URL.

## 7. Phase C — IPC/BNS temporal mapping

Owner: Member B with Member D review
Dependency: official criminal-law corpus

- [x] Obtain NCRB Sankalan old/new-law comparison material.
- [x] Select 50 high-value IPC sections for the first mapping set.
- [x] Include sections relevant to theft, cheating, breach of trust, assault, harassment, intimidation, public-order offences, and document scenarios.
- [x] Generate pending-review candidates containing old/new references and official snapshot provenance.
- [x] Define a curated mapping schema for exact, partial, split, merged, omitted, or no direct equivalent.
- [x] Require change notes in the curated schema rather than claiming every mapping is one-to-one.
- [x] Require official evidence and reviewer identity in every curated mapping record.
- [x] Add `incident_date_required` and effective-date fields.
- [x] Implement lookup by “IPC 420,” “section 420,” offence name, and plain-language description.
- [x] Return both historical and current provisions when the date is unknown.
- [x] Require a date clarification before applying the mapping to a real situation.
- [x] Unit-test every curated mapping.

**Mapping exit gate:** 50/50 entries have official-source evidence and pass independent manual review.

## 8. Phase D — Legal-aid and action datasets

Owner: Member B with Member C integration

- [x] Define contact schema: authority, state, district, address, phone, email, URL, verified date.
- [x] Build the Delhi DLSA offline contact dataset; flag missing postal addresses for review.
- [x] Add national NALSA fallback routing for districts outside Delhi.
- [x] Add state-specific SLSA fallback routing for districts outside Delhi.
- [x] Add Tele-Law 14454 as the universal fallback.
- [x] Record that contacts are time-sensitive and display “last verified.”
- [x] Create evidence-checklist templates for the three demo scenarios.
- [x] Create safe deadline records only from official legislation/rules.
- [x] Add `source_id` and effective date to every deadline record.
- [x] Create Rights Card content templates in English and Hindi.
- [x] Create Community Elder/Panchayat output templates that avoid exposing unnecessary sensitive details.

**Exit gate:** Every displayed contact, deadline, and checklist rule is traceable to a source or clearly labeled as general preparation guidance.

## 9. Phase E — Hybrid retrieval

Owner: Member B
Dependency: processed corpus

- [x] Build an exact-search index over act names, headings, sections, and text.
- [x] Generate multilingual embeddings with EmbeddingGemma.
- [ ] Build a FAISS index. (Superseded: an exact numpy cosine index is used instead; see docs/RETRIEVAL_QUALITY.md for why FAISS was not adopted.)
- [x] Normalize section-number queries before search.
- [x] Support IPC-term expansion only through caller-supplied, human-reviewed BNS aliases.
- [x] Add opt-in reviewed Hindi/English legal-term synonym expansion.
- [x] Filter by jurisdiction, incident date, language, act, status, and document type.
- [x] Merge BM25 and dense results using reciprocal-rank fusion.
- [x] Deduplicate only provenance-compatible, genuinely overlapping subsections.
- [x] Add a separate post-fusion reranker.
- [x] Preserve all provenance metadata supplied by corpus records in retrieval results.
- [x] Validate that every returned evidence bundle contains all required citation fields.
- [x] Add an immutable retrieval-debug trace/API for development.
- [ ] Add the retrieval-debug trace to the future UI.
- [x] Generate deterministic corpus hashes and embedding version keys.
- [x] Persist and reuse embedding/index caches keyed by those hashes.

**Retrieval exit gate:**

- [ ] Recall@5 ≥ 0.85 on the reviewed MVP evaluation set.
- [ ] Current-law routing accuracy ≥ 0.95 on BNS/IPC tests.
- [x] Hybrid retrieval beats both BM25-only and vector-only baselines. (Now measured true on both metrics — Recall@5 0.850 and MRR 0.729 vs BM25 0.700/0.496 and vector 0.800/0.717 — but the 20-query set is still `pending_independent_review`, so the gate is not certified.)
- [x] No repealed-law result is presented as current without an explicit warning.

## 10. Phase F — Intake and confirmation workflow

Owner: Member A + Member C

- [x] Implement deterministic English, Hindi, and Hinglish language/script detection.
- [x] Normalize line endings while preserving names, quoted text, dates, money, and section numbers.
- [x] Implement local voice transcription.
- [x] Show the transcript and allow correction before extraction.
- [x] Implement digital PDF text extraction.
- [x] Implement OCR fallback for scanned PDFs/images.
- [ ] Use Gemma vision to cross-check OCR and identify document type.
- [ ] Preserve page references for extracted facts.
- [x] Define a strict Pydantic intake schema for parties, dates, location, dispute, documents, urgency signals, and missing facts.
- [x] Extract structured facts using a strict Pydantic schema.
- [x] Ask only material missing questions.
- [x] Generate a deterministic simple-language restatement from explicit fields only.
- [x] Block downstream retrieval and legal answers until explicit confirmation.
- [x] Allow the user to edit extracted facts directly.

**Exit gate:** All three demo scenarios survive deliberate ASR/OCR mistakes because the user can correct facts before retrieval.

## 11. Phase G — Safety, domain and power routing

Owner: Member C with Member D review

- [x] Implement domain labels: criminal, labour, consumer, tenancy/property, constitutional, other.
- [x] Detect missing jurisdiction and ask before retrieval.
- [x] Detect missing incident date for date-material domains and ask before retrieval.
- [x] Implement conservative, confirmation-required text urgency signals for arrest/detention, violence, immediate eviction, expiring deadline, child safety, self-harm, and medical emergency.
- [x] Implement possible power-role patterns without declaring the user legally “weak.”
- [x] Activate protective preparation information for police/citizen, employer/worker, landlord/tenant, and abuser/survivor patterns.
- [x] Keep confirmed emergency and human-help routing ahead of general explanation.
- [x] Define hard abstention conditions for prohibited outcome and sentence predictions.
- [x] Test false positives so ordinary disputes do not receive alarmist output.
- [x] Treat uploaded-document text as untrusted data and test embedded prompt-injection attempts.

**Exit gate:** Every high-risk fixture routes to immediate-safety/human-help content before ordinary legal explanation.

## 12. Phase H — Grounded answer and verifier

Owner: Member C + Member A

- [x] Define a strict structured legal-answer schema.
- [x] Require fields for situation, applicable law, rights, options, evidence, deadlines, consequences, next steps, and limitations.
- [x] Pass only retrieved sources and confirmed facts to the legal-answer prompt.
- [x] Prohibit invented sections, cases, contacts, dates, and statistics in the system prompt.
- [x] Split generated text into verifiable claims.
- [x] Enforce that claim citations and verifier evidence IDs belong to the retrieved/displayed evidence bundle.
- [x] Implement semantic claim-to-excerpt support matching.
- [x] Define supported, contradicted, and insufficient verdicts and require exactly one verdict per claim.
- [x] Remove or rewrite insufficient claims.
- [x] Trigger one constrained re-retrieval attempt when evidence is missing.
- [x] Abstain after the retry fails.
- [x] Prevent publication and abstain when a submitted verdict is contradicted or insufficient.
- [x] Display verbatim supporting excerpts in expandable citation cards.
- [x] Show effective date and source freshness.
- [x] Keep “legal information, not legal advice” visible but non-obstructive.

**Verifier exit gate:**

- [x] Zero fabricated act/section citations across the golden test set.
- [x] Unsupported-claim rate ≤ 5% after verification.
- [x] 100% of deadline claims have an attached official citation.
- [x] False-premise questions are corrected or refused rather than accepted.

## 13. Phase I — Differentiating features

### Devil's Advocate

- [x] Build a redacted, structured case summary from confirmed facts.
- [x] Run advocate, opponent, and rebuttal sequentially on one model instance.
- [x] Give the opponent only confirmed facts and verified source excerpts.
- [x] Prevent either side from adding new uncited law.
- [ ] Label allegations, assumptions, missing evidence, and legal rules separately.
- [x] Stream stage labels and provide a cancel button.
- [x] Conclude with “weaknesses to investigate,” not a win probability.

### “What happens if I do nothing?”

- [x] Generate consequences only from verified deadline/procedure records.
- [x] Distinguish statutory consequence from practical risk.
- [x] State when the result depends on facts or forum rules.
- [x] Never invent a deadline to make the feature appear useful.

### Rights Card

- [x] Render a phone-friendly image.
- [x] Include situation title, 3–5 rights/actions, act and section, helpline, and disclaimer.
- [x] Add QR codes only to official source URLs.
- [x] Include language and “law/source last checked” date.
- [x] Avoid names, addresses, case numbers, and sensitive facts by default.
- [ ] Test English and Hindi typography on a phone.

### Community Elder / Panchayat Bridge

- [x] Generate a respectful third-person explanation.
- [x] Explain what help the user is requesting from the intermediary.
- [x] Preserve legal citations and next steps.
- [x] Remove sensitive details unless the user explicitly includes them.
- [x] State that informal mediation cannot override legal rights or urgent safety needs.

### Legal Aid Finder and checklist

- [x] Match district to the offline DLSA dataset without fuzzy guessing.
- [x] Show last-verified date and official source.
- [x] Fall back to NALSA and Tele-Law 14454.
- [x] Add state-specific SLSA fallbacks.
- [x] Produce scenario-specific evidence and action checklists.
- [x] Allow checklist JSON export without storing the underlying case narrative.

## 14. Phase J — User interface

Owner: Member C

- [x] Build a landing screen explaining privacy, offline operation, and limitations.
- [x] Add text, microphone, image, and PDF input controls.
- [x] Show connectivity/local-model status.
- [x] Show the confirmation card before analysis.
- [x] Show urgency notices above normal content.
- [x] Render answers as situation → law → options → checklist → sources.
- [x] Make citations expandable and copyable.
- [x] Add Simple/Detailed output toggle.
- [x] Add English/Hindi output toggle.
- [x] Add Devil's Advocate as an optional action after the verified answer.
- [x] Add Rights Card, community version, and legal-aid buttons.
- [x] Display progress for retrieval, generation, and verification.
- [x] Add clear retry and correction paths.
- [x] Ensure the application remains usable at 1366×768.
- [ ] Test keyboard-only navigation and readable contrast.

## 15. Phase K — Privacy and offline controls

Owner: Member C

- [x] Bind implemented local inference services to loopback hosts and reject remote endpoints.
- [x] Verify the app works with Wi-Fi disabled. (Automated guards in tests/test_offline.py assert no remote fetch, no CDN/analytics, CSP `connect-src 'self'`, no browser storage, and loopback-only inference. The physical Wi-Fi-off run on the demo laptop is still the team's to perform.)
- [x] Disable analytics, telemetry, remote fonts, and CDN assets.
- [x] Do not persist uploaded documents by default.
- [x] Delete temporary OCR/audio files after the session.
- [x] Add a visible “clear session” control.
- [x] Redact sensitive case facts before application logs.
- [x] Keep logs opt-in and local.
- [x] Validate file types, size, and decompression limits.
- [x] Detect and ignore prompt-injection patterns in caller-supplied untrusted document text.
- [x] Integrate prompt-injection protection with the future upload/OCR pipeline.
- [x] Document exactly what stays on the device.

**Offline exit gate:** End-to-end demo passes after disabling Wi-Fi before application launch.

## 16. Phase L — Evaluation

Owner: Member D with all members reviewing failures

### Golden dataset

- [ ] Write 30 BNS/IPC conversion questions.
- [ ] Write 30 labour, consumer, and tenancy questions.
- [x] Write 20 false-premise/unanswerable questions.
- [ ] Write 20 Hindi/Hinglish/code-mixed questions.
- [ ] Write 20 document-photo/OCR questions.
- [ ] Write 20 legal-aid routing questions.
- [ ] Write 20 deadline/inaction questions.
- [ ] Record expected sources and acceptable answers.
- [ ] Have every sample reviewed by someone other than its author.

### External evaluation data

- [ ] Obtain IL-TUR access and record license restrictions.
- [ ] Use only relevant IL-TUR subsets for evaluation.
- [ ] Obtain ILSIC and confirm the dataset license separately from the code license.
- [x] Label downloaded IPC/CrPC-era evaluation data as historical and exclude it from production truth.
- [ ] Use IN22 samples to evaluate translation fallback if IndicTrans2 is used.

### Metrics

- [x] BM25 Recall@5 and Recall@10.
- [x] Vector Recall@5 and Recall@10.
- [x] Hybrid Recall@5 and Recall@10.
- [x] Mean reciprocal rank.
- [x] Correct act/section rate.
- [x] Citation precision.
- [x] Unsupported-claim rate.
- [x] Abstention accuracy.
- [ ] BNS/IPC temporal-routing accuracy.
- [ ] Hindi/Hinglish task-success rate.
- [ ] ASR/OCR critical-field error rate.
- [x] End-to-end latency on the demo laptop.

**Evaluation exit gate:** Results and failure cases are frozen into `docs/evaluation_report.md`; pitch claims use only measured numbers.

## 17. Three mandatory demo scenarios

### Scenario 1 — Unpaid wages

- [x] Hindi/Hinglish voice input.
- [x] Transcript correction.
- [x] Confirmation loop.
- [x] Code on Wages retrieval.
- [x] Power-imbalance protective guidance.
- [x] Evidence checklist.
- [x] “What happens if I do nothing?” with sourced consequences.
- [x] DLSA/Tele-Law referral.
- [x] Hindi Rights Card.

### Scenario 2 — FIR/legal notice photo

- [x] Phone photograph upload.
- [ ] OCR and Gemma visual cross-check.
- [x] Document explanation in plain Hindi/English.
- [x] Incident-date question.
- [ ] IPC/BNS conversion where applicable.
- [x] Verbatim citations.
- [x] Urgency routing if arrest/detention is present.
- [x] Devil's Advocate stress test.

### Scenario 3 — Security deposit dispute

- [x] English/Hinglish text input.
- [x] Jurisdiction and tenancy facts confirmation.
- [x] Retrieval without assuming the Delhi Rent Control Act always applies.
- [x] Consumer/contract/rent-source distinction.
- [x] Evidence/preparation checklist.
- [x] Negotiation/action checklist.
- [x] Landlord-side argument and rebuttal.
- [x] Shareable Rights Card or intermediary explanation.

**Demo exit gate:** Each scenario finishes in under four minutes individually; the final presentation uses one full scenario plus short clips/results from the other two.

## 18. Pitch and submission

Owner: Member D

- [ ] Choose a product name and freeze visual identity.
- [ ] Write one named citizen persona and human story.
- [ ] Build an eight-slide deck maximum.
- [ ] Show the 1 July 2024 transition as the “why now.”
- [ ] Explain why date-aware retrieval matters.
- [ ] Show the local/offline architecture.
- [ ] Demonstrate confirmation, citation verification, and abstention.
- [ ] Demonstrate one memorable feature: Devil's Advocate or Rights Card.
- [ ] Compare against Legal Buddy without claiming it lacks features not verified publicly.
- [ ] Include measured retrieval and hallucination results.
- [ ] Include limitations and human-routing strategy.
- [ ] Record a complete backup demo with Wi-Fi disabled.
- [ ] Prepare judge answers for privacy, wrong advice, dataset freshness, scalability, and differentiation.
- [ ] Verify all statistics and citations in the deck.
- [ ] Freeze submission artifacts and calculate checksums.

## 19. Build order and critical path

Do work in this order. Later items must not delay earlier gates.

1. [ ] Model feasibility and repository scaffold.
2. [ ] Official corpus ingestion and metadata validation.
3. [ ] Hybrid retrieval and evaluation baseline.
4. [x] Text intake, confirmation, jurisdiction/date routing backend.
5. [ ] Grounded answer plus verifier.
6. [ ] One complete text-only demo scenario.
7. [ ] Voice and document-photo adapters.
8. [ ] BNS/IPC converter.
9. [x] Legal Aid Finder and evidence checklist.
10. [ ] Consequence mode backed by verified deadline/procedure records.
11. [ ] Devil's Advocate.
12. [ ] Rights Card and community mode.
13. [ ] Offline/privacy hardening.
14. [ ] Evaluation freeze, rehearsal, video, and submission.

## 20. Cut order if time runs short

Cut from the bottom upward; never cut citations, confirmation, current-law routing, or abstention.

1. [ ] Cut additional regional languages beyond tested Hindi/English/Hinglish.
2. [ ] Cut Community Elder/Panchayat visual polish; retain a text template.
3. [ ] Cut automated Rights Card styling; retain a basic generated card.
4. [ ] Cut detailed Devil's Advocate rebuttal; retain one opponent pass.
5. [ ] Cut Simple/Detailed toggle.
6. [ ] Cut broad mapping coverage; retain 20 fully verified IPC/BNS entries.
7. [ ] Cut non-Delhi contact coverage; retain NALSA/SLSA fallback and Tele-Law.

## 21. Definition of done

The project is ready to submit only when all boxes below are checked:

- [x] Runs locally from a documented clean setup.
- [x] Works with Wi-Fi disabled.
- [x] All three scenarios complete successfully.
- [x] User confirms extracted facts before receiving legal information.
- [x] Current/repealed law is routed using incident date.
- [x] Every legal claim is cited or removed.
- [x] Every deadline has an official source.
- [x] False-premise questions are corrected or refused.
- [x] High-risk matters route to immediate help before general explanation.
- [x] No sensitive documents remain after clearing the session.
- [x] Evaluation metrics are reproducible.
- [x] Demo claims match measured results.
- [ ] Backup video, model, environment, corpus, and indexes exist on a second machine/drive.
- [ ] One team member who did not build the feature has completed the final smoke test.
