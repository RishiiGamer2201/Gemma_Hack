# Full Review — IEEE Papers & Team Ideation Document ("Judge My Win")

Reviewed 11 July 2026. Companion docs: [RELATED_WORK.md](RELATED_WORK.md) (positioning table), [SENIOR_REVIEW.md](SENIOR_REVIEW.md), [PLAN.md](PLAN.md).

---

# PART A — The Three IEEE Papers

## A1. JusticeAI-Legal Chatbot: A Blockchain-secured Multilingual Legal Chatbot for Accessible Justice
*Jha, Ansari, Shaikh, Pawar — A.C. Patil College of Engineering, Navi Mumbai. ICNTE 2026, DOI 10.1109/ICNTE66387.2026.11437425*

### What it does
A web platform where citizens ask legal questions and upload case documents. Stack: React/Vite frontend, FastAPI backend, SQLite storage, **Google Gemini API** as the entire AI layer, and Polygon PoS (Amoy testnet) blockchain that stores **SHA-256 hashes of uploaded documents** as proof-of-existence. Supports Hindi and Marathi alongside English, with role-based access (Citizen / Lawyer / Admin) and a case-precedent search module for lawyers.

### Strengths
1. **Excellent problem framing with citable statistics.** The introduction is the best part of the paper: less than 16 lakh people received legal aid in 2023–24 despite ~80% of the population being eligible under the Legal Services Authorities Act; **one legal aid clinic per 163 villages**; ~90% of Indians can't fluently navigate English legal documents; 65% rural population faces the steepest barriers. These go straight into our pitch's problem slide.
2. **Honest scope.** It repeatedly frames itself as "an informational tool, not a replacement for professional advice" — the correct legal-ethics posture, same as ours.
3. **Working end-to-end system** with screenshots of registration, chat, case search, and chat history — this is a real build, not vaporware.
4. The blockchain design is at least sensible in one respect: only hashes go on-chain, not documents, so it doesn't leak user data to a public ledger.

### Weaknesses
1. **The "AI" is a thin cloud wrapper.** Every legal query — potentially about domestic violence, police complaints, evictions — is sent to the Gemini API. For a paper whose keywords include "transparency," the privacy analysis of this is absent.
2. **No grounding whatsoever.** Answers come from Gemini's parametric memory. There is no retrieval, no statute corpus, no citations mechanism, and no hallucination evaluation — the two "accuracy" examples (legal marriage age; how to file a domestic violence case) are anecdotal screenshots.
3. **The blockchain secures the wrong thing.** It creates tamper-proof records of *uploaded documents*, but the actual risk surface — the *advice the AI gave* — is unaudited. An immutable log of unverified advice would arguably be worse than no log.
4. **No quantitative evaluation at all.** No accuracy metrics, no user study, no multilingual benchmark. "Field results" promised in the abstract never materialize as numbers.
5. Requirements confusion typical of student papers (e.g., listing Intel i3 / 4 GB RAM as "hardware requirements" for a cloud-API system).

### What we take
- The intro statistics (verify their primary sources before the writeup).
- The architecture as our **contrast case**: cloud wrapper + no grounding = exactly the failure modes our design answers (on-device Gemma 4 = privacy; RAG + verifier + citations = advice you can check).
- A lesson: don't bolt on a fashionable technology (their blockchain, which judges may ask us about too) unless it addresses the actual risk.

**Verdict: cite for problem statistics and as the representative cloud-wrapper baseline. Architecture not worth borrowing.**

---

## A2. AI-Driven Multilingual Legal Advisory Framework with Privacy-Preserving E-Docs and Case Precedent Mining ("LexiServe")
*Kalaichelvi T., Manam, Vallapuneni — Vel Tech, Chennai. ICCTWC 2026, DOI 10.1109/ICCTWC68241.2026.11583649*

### What it does
A layered framework: multilingual query intake (8 Indian languages, typed or spoken) → language detection and preprocessing → **legal-domain classification** (civil / criminal / property / labour / constitutional) → **Case Precedent Mining**: queries and judgments embedded as vectors, cosine similarity, Top-K retrieval over a **FAISS index** → domain-specific prompt assembled with retrieved precedents → **Gemini API** generates simplified advice → optional PDF output. Sensitive documents are AES-encrypted with RSA key exchange and role-based access control.

### Strengths
1. **Architecturally the closest published system to ours.** Chunk → embed → FAISS → Top-K → LLM-with-retrieved-context is precisely our RAG backbone. Their explicit argument for semantic retrieval over keyword/BM25 search is one we can reuse.
2. **A real evaluation section with a reusable design.** Query classification: accuracy 93.4%, precision 91.2%, recall 89.8%, F1 90.5% on a labeled query set; confusion-matrix analysis (<7% misclassification); **Top-K retrieval accuracy curves** (rising toward ~85% at K=10); ROC AUC 0.92 vs 0.78 keyword baseline; precision-recall curves vs BM25. **This is our writeup's evaluation template** — all of it replicable at small scale (30–50 labeled queries) in an afternoon.
3. **Multilingual usage table** (English 55%, Hindi 18%, Tamil 12%, Telugu 8%...) supports the demand argument for Indic-language support.
4. Grounding-adjacent prompting: constructing the prompt from retrieved precedents "so the AI model does not operate outside legally significant boundaries" — the same hallucination-control philosophy we use, one verifier-agent short of our design.

### Weaknesses
1. **Still cloud-dependent** — Gemini API for generation, cloud deployment as the stated scaling strategy. The "privacy-preserving" label covers document storage, not query processing.
2. **Internal inconsistencies.** The ROC *figure* is titled "AUC = 1.00" while the text claims 0.92; one conclusion paragraph contains a copy-paste splice mid-sentence ("...various improvemeThe semantic case..."). The dataset (size, source, languages of the labeled queries) is never described — so the good-looking metrics aren't reproducible.
3. Retrieval corpus is **case precedents**, not statutes, and nothing is BNS-aware; a citizen asking about a post-July-2024 criminal matter would get IPC-era precedent framing.
4. Speech input is mentioned at the interface level but no ASR pipeline or evaluation exists.

### What we take
- Validation-by-prior-art for the RAG design (cite it exactly this way).
- **The evaluation recipe**: labeled-query classification accuracy + Top-K retrieval accuracy + a keyword-search baseline comparison. Even a small version of this puts real numbers in our writeup, which most hackathon teams won't have.
- The language-demand table.

**Verdict: the most useful paper of the three. Cite the architecture and replicate the eval design; don't lean on its (unreproducible) metrics.**

---

## A3. Development of Multilingual AI Legal Assistants for Real-Time Legal Aid Delivery, Document Drafting, and Procedural Guidance in Underserved Judicial Systems
*Adain et al. — seven authors across Iraqi universities (colleges of Law, Dentistry, Nursing, Computer Engineering). ICCR 2025, DOI 10.1109/ICCR67387.2025.11292048*

### What it claims
A transformer-based assistant (XLM-R + LegalT5 + mBERT) with ontology-based procedural rule modeling and RAG, trained on "90k+ legal artifacts in 18 languages (2015–2024)," achieving **96.5% accuracy, F1 0.94, 0.96 procedural compliance, <700 ms latency**, deployed in "mobile legal kiosks in five countries" with 4.6/5 user satisfaction, 21% court-backlog reduction, and 78% drafting-latency reduction.

### Why this paper should not be trusted
1. **The figures do not belong to the described system.** Fig 1 is a hybrid LSTM network for *sentiment scoring of short user reviews*. Fig 4 is a *multilingual adversarial hate-speech/fake-data detection* architecture (generator/discriminator over English/German/Hindi hate-speech classes). Neither has anything to do with a legal assistant — they appear recycled from unrelated work.
2. **The confusion matrix (Fig 6) reveals the real scale**: the cells contain 2, 2, 1, 1, 2 — i.e., roughly **eight test samples** behind headline claims of 96.5% accuracy. The ROC figure (Fig 7) shows per-class AUCs of 0.69, 0.19, 0.50, 0.62, 0.44 — *worse than random* for several classes — directly contradicting the text's "AUC 0.92."
3. **Off-topic self-citations padded into the references**: multilevel-inverter harmonic elimination, dung-beetle optimizers, solar-tracking systems, blood-cell CNNs, IoT threat detection — none relevant to legal NLP.
4. Extraordinary deployment claims (five-country kiosk pilots, court backlog reductions) with zero named jurisdictions, partners, or protocols; implausible author composition for such a system build.
5. Metrics are internally inconsistent across tables (96.5% vs 96.1% vs 93.8% "final accuracy" for the same system).

### What we take
- **Nothing technical.** At most a one-line related-work mention. Do not quote its numbers.
- **A pitch asset, used carefully:** this paper is a live demonstration of why unverifiable claims are the disease of the legal-AI space — the same disease as hallucinated citations. If provenance and verification come up, we can note that even the literature needs a "verifier agent."

**Verdict: red-flagged. Exclude from any benchmark comparison; keep only as a cautionary reference.**

---

# PART B — Team Ideation Document ("Judge My Win.pdf")

A 22-page Google-Docs export with per-member sections. Overall: the team independently converged on the repo plan's architecture and then extended it with genuinely differentiating features — the document's best ideas are now the locked scope candidates. Issues are mostly stale model references and a few features that quietly require data we don't have.

## B1. Links section
GitHub repo, ideation Google Doc, Meet link. ✔ Repo link matches. (Note: the Meet and Doc links are publicly readable in this PDF — fine for a team doc, but don't commit the PDF itself to the public repo.)

## B2. Rishii — Idea, papers, 10 features

**The idea statement** is a faithful, well-written restatement of the locked concept: plain-language multilingual assistant, voice + photo intake, rights/options/next-steps output, exact citations, BNS-era "why now," tagline *"Nyaya in your pocket, in your language, on your device."* The "How It Works Technically" section correctly explains RAG-before-generation as the safety spine, and the three tools (`search_law`, `find_legal_aid`, `draft_document`) match PLAN.md. ✔ No corrections needed — this is writeup-ready prose.

**The 10 features**, with verdicts:

| # | Feature | Verdict |
|---|---|---|
| 1 | Cited Legal Answer | **Core.** Already the trust backbone. |
| 2 | Voice input (Hindi/English) | **Core.** Gemma 4 native audio; Phase-1 go/no-go test. |
| 3 | Photo upload (FIR/notice) | **Core.** Gemma 4 native image; demo scenario 2. |
| 4 | Legal Aid Finder | **Core.** `find_legal_aid` tool + DLSA CSV. |
| 5 | Complaint/Application drafting | **Core.** `draft_document` tool. |
| 6 | Risk & Urgency Detector | **Build** — as prompt-level triage merged with Sarthak's #8 (safety-first mode for DV/arrest cases → route to human + helplines). |
| 7 | Simple vs Detailed mode | **Cheap add** — a toggle that changes the system prompt. Do it if time allows. |
| 8 | Rights Checklist | **Fold into** the action-plan output format rather than a separate feature. |
| 9 | BNS vs IPC Converter | **Build as demo beat** — one mapping table (top ~50 sections) + the "before or after July 2024?" question. This is the "why now" made tangible. |
| 10 | Case Timeline Builder | **Roadmap.** Real value, but drafting quality depends on it less than it seems in a 4-min demo. |

His "best MVP combo" (cited answers + voice + photo + legal-aid finder + drafting) is exactly right.

## B3. Sarthak — 10 features, "Trash" list, external research

**Best of his 10:**
- **#1 Confirmation loop** ("So you're saying your employer hasn't paid you for 2 months — correct?"). **Build — near-free** (one system-prompt instruction), catches code-mixed misunderstandings before advice, and *looks* great in a demo.
- **#9 Translate-my-document reverse mode** — correct insight that explaining *received* documents beats drafting outgoing ones as a pain point; this is already our photo-intake scenario, so **merge, don't duplicate**.
- **#4 "What happens if I do nothing"** — the safe version of outcome simulation: consequences grounded in statutory deadlines (e.g., cheque-bounce reply windows), which we can cite. **Build as prompt behavior**, not a separate module.
- **#10 QR-backed citations** — clever trust artifact (QR on the rights card linking to the bare act on India Code). **Cheap add** via any QR lib; pairs with Mansi's rights card.
- **#2 Power-imbalance detector / #5 multi-party perspective** — good instincts; fold both into the Strategist agent's prompt (present the other side's likely argument; protective tone for weaker parties) rather than building "detectors."
- **#6 local precedent stats / #7 panchayat bridge / #8 emotion-aware mode** — #6 **rejected** (requires outcome data we don't have; inventing statistics is the sin we campaign against), #7 roadmap (lovely for the impact slide), #8 **merged** into the urgency triage.

**The "Trash" list is mislabeled** — it's the 10-point restatement of the base MVP (multilingual intake, RAG grounding, action plans, drafting, DLSA locator, eligibility matching, urgency flagging, privacy-first design). It duplicates PLAN.md rather than adding to it, which is presumably why it got binned, but every item in it is what we're building.

**His external research notes are high-value:**
- **Legal Buddy** (a Gemma 4 Challenge submission): local-first Indian legal assistant via Ollama, section-by-section document review, multimodal notice parsing. **Direct competitor evidence — we are not alone in this niche.** Our answer: citizen-facing voice-first UX, BNS-mapping, verifier agent, legal-aid routing. Find and study its writeup before the 15th.
- **Tunix "Legal" reasoning track**: SFT → GRPO with composite rewards to make small models show structured legal reasoning. **Roadmap slide material** (with Nishant's note) — credible future-work, not a 1-day activity.
- **VitalGuide**: offline RAG + multilingual emergency assistant — same shape as us in a different domain; useful one-line analogy for the pitch.

## B4. Nishant — three keywords
"Local deploy-offline, GRPO, Multilingual." The right compass headings; two are core (offline, multilingual), GRPO goes to roadmap as above.

## B5. Mansi — 9 features + Devil's Advocate appendix

**The strongest single section in the document.** Verdicts:

| # | Feature | Verdict |
|---|---|---|
| 1 | Case Outcome Simulator with stats ("70% settle...") | **Reject the statistics**, keep the *interactive decision-tree* framing fed by statutory/procedural facts only. |
| 2 | **Devil's Advocate mode** | **Build — the demo wow.** The appendix's design is right: one model, three sequential calls with different system prompts. |
| 3 | Evidence checklist + case-strength meter | Checklist: **build** (part of action-plan output). Numeric "40% ready" score: **skip** — unfounded precision in a legal context. |
| 4 | **Multi-agent pipeline with visible Verifier** | **Build — the technical wow.** Intake → Classifier → Researcher (RAG) → Strategist → Drafter → Verifier, with the agent trace visible in a debug panel. Cheapest credible answer to "how do you stop hallucinations?" |
| 5 | Jurisdiction + time awareness | **Build the time half** (pre/post-July-2024 question + BNS/IPC mapping). State-specific acts beyond Delhi: roadmap. |
| 6 | Negotiation/settlement composer | **Cheap add** — escalation kit (polite message → firm letter → legal notice) is just three drafting templates; "most disputes settle" is a great pitch line. |
| 7 | Deadline & limitation tracker | **Build small**: hardcode limitation periods for our 3 demo scenarios and compute dates from the user's story. Full calendar/reminders: roadmap. |
| 8 | **Rights Card generator** | **Build — the shareable wow.** Pocket "know your rights" image card with sections + helplines (+ Sarthak's QR). |
| 9 | Explainability panel | **Merge with #4** — the visible verifier trace *is* the explainability panel. |

Her recommended combo (#4 technical wow + #2 demo wow + #7 practical wow) matches my independent assessment.

**The Devil's Advocate appendix** (clearly an AI-chat excerpt): the orchestration logic (sequential role prompts, summary-not-history to the adversary, streamed stage labels like "⚖️ Opposing counsel is reviewing your case...") is correct and worth implementing verbatim. **But every model reference is one generation stale:** `gemma3:4b`, "Gemma 2 9B / Gemma 3 12B," and its VRAM table predate Gemma 4. Corrected numbers: **Gemma 4 E4B ≈ 3 GB at Q4** (with native audio+image, which Gemma 3 4B lacked), so the "fits comfortably in 8 GB" conclusion still holds — even better than the appendix assumed. Nobody should type `ollama pull gemma3:4b` on the 15th; it's `gemma4:e4b`.

## B6. Bottom line on the team doc

- **Consensus achieved**: all four members are aligned on the base pipeline; the doc independently reproduces PLAN.md's architecture. No conceptual conflicts to resolve.
- **Locked additions from this doc**: Verifier-agent pipeline with visible trace (Mansi #4/#9), Devil's Advocate mode (Mansi #2), Rights Card + QR citations (Mansi #8 + Sarthak #10), confirmation loop (Sarthak #1), BNS/IPC time-awareness (Mansi #5 + Rishii #9), urgency/safety triage (Rishii #6 + Sarthak #8).
- **Rejected on principle**: anything requiring invented statistics (outcome percentages, case-strength scores, district settlement rates) — fabricated numbers in a legal tool would contradict the project's entire thesis.
- **Corrections to circulate**: Gemma 3 → Gemma 4 E4B everywhere; GRPO is roadmap, not build; the "Trash" list is actually the MVP foundation.
- **Action item**: find the Legal Buddy submission and read it — closest competitor in the same competition family.

---

# PART C — Project Evolution: Baseline vs. New Add-ons

One-glance summary of what the project looked like after the original plan ([PLAN.md](PLAN.md) / [RESEARCH.md](RESEARCH.md)), and everything added or changed by the senior's material, the team ideation doc, and the four papers.

| Dimension | Baseline (original plan) | New add-ons (after all reviews) | Source |
|---|---|---|---|
| **Core features** | Cited answers · voice input (Hi/En) · photo intake (FIR/notice) · `search_law` · `find_legal_aid` · `draft_document` · safety disclaimer + human routing | — unchanged, confirmed as MVP by all reviews — | Team doc "Trash" list independently re-derived it |
| **New demo features** | – | **Devil's Advocate mode** (one model, 3 sequential role prompts) · **Rights Card generator** (shareable image + **QR-backed citations** to India Code) · **confirmation loop** before advice · **BNS↔IPC converter** + "before or after July 2024?" question · urgency/safety triage (DV/arrest → helplines + human first) · "what happens if I do nothing" (statute-grounded consequences) · negotiation escalation kit (message → letter → legal notice) · Simple/Detailed toggle | Mansi #2/#8, Sarthak #1/#10/#4/#8, Rishii #6/#9, Mansi #6/#7 |
| **Pipeline** | Single-prompt RAG: query → retrieve sections → Gemma answers with citations | **Multi-agent pipeline with visible trace**: Intake → Classifier → Researcher (RAG) → Strategist → Drafter → **Verifier** (checks every claim against retrieved law, doubles as the explainability panel) — all roles = same loaded model, different system prompts | Mansi #4/#9; grounding philosophy validated by LexiServe |
| **Retrieval design** | Chunk bare acts by section → embed → ChromaDB/FAISS → top-K | + **priority tier per chunk** (1 = Constitution, 2 = BNS/BNSS/BSA/CPC/Contract Act, 3 = other acts) ranking citations the way lawyers reason; architecture confirmed by LexiServe's FAISS + cosine top-K design | Senior's law-hierarchy insight; LexiServe |
| **Models** | Gemma 4 E4B via Ollama (~3 GB Q4, native audio+image, function calling); InLegalBERT or MiniLM embedder; IndicConformer/IndicTrans2 fallbacks | — unchanged — plus explicit **correction**: all `gemma3:4b` / Gemma 2 9B references in the team doc are stale → `gemma4:e4b`; the 8 GB VRAM feasibility conclusion still holds. **GRPO/SFT (Tunix recipe) → roadmap slide**, not build | Mansi's appendix (corrected); Nishant; Sarthak's Tunix note |
| **Dataset** | 6 bare acts from India Code (BNS, BNSS, CPA, Delhi Rent, Wages, LSA) · NALSA/DLSA contacts CSV · Tele-Law 14454 · IL-TUR (optional eval) | + **Constitution of India** (top priority tier) · + **Hindi bare acts** from legislative.gov.in (grounded Hindi citations, no translation step) · + akshatgupta7 Kaggle QA — **Constitution subset only, eval-only** (IPC/CrPC pairs reference repealed law) · + **limitation-period table** for the 3 demo scenarios · + BNS↔IPC mapping table (~50 sections). **Rejected**: amohankumar dataset (Australian), SC-judgments corpus (roadmap), any invented outcome statistics | Senior's links; SENIOR_REVIEW.md; Mansi #7 |
| **Evaluation** | Retrieval spot-check (≥8/10 hit-rate) | + **LexiServe-style eval for the writeup**: 30–50 labeled queries → domain-classification accuracy + Top-K retrieval accuracy vs keyword baseline — real numbers most teams won't have | LexiServe (A2) |
| **Pitch assets** | Problem stats, BNS "why now," privacy story, Gemma 3n winners pattern | + JusticeAI intro stats (1 clinic / 163 villages; 16 lakh aided vs 80% eligible) · + **positioning table** vs JusticeAI / LexiServe / ICCR / Mina ([RELATED_WORK.md](RELATED_WORK.md)) · + png2 hallucination exhibit ("Section 247A of the Constitution") · + ICCR paper as cautionary tale of unverifiable claims · + VitalGuide analogy (offline+RAG+multilingual, different domain) · + "most disputes settle informally" framing | Papers A1–A3; senior's png2; Sarthak's notes |
| **Explicitly rejected** | – | Lawyer-facing courtroom diarization (off-track) · Whisper+pyannote (Gemma 4 native audio covers it) · Qwen fine-tune (hackathon requires Gemma) · outcome statistics / case-strength percentages (fabrication risk) · blockchain layer (audits the wrong thing — see JusticeAI) | SENIOR_REVIEW.md; A1; team-doc review |

**Abstract of the evolution:** the baseline was a grounded, on-device, multilingual RAG assistant; the reviews didn't change that spine — they *hardened* it (verifier agent, priority-tiered retrieval, eval numbers) and gave it three memorable moments (devil's advocate, rights card, BNS converter) plus a defensible list of things we deliberately did **not** build.
