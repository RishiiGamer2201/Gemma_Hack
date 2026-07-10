# Related Work — The Four Papers, What They Give Us, and How We Differ

Papers collected by the team (see ideation doc). Verdicts below feed the writeup's related-work section and the "how are you different?" judge question.

## 1. JusticeAI (ICNTE 2026, A.C. Patil College, Navi Mumbai) — IEEE 11437425

**What it is:** Web chatbot (React + FastAPI + SQLite) answering legal queries via the **cloud Google Gemini API**, with Hindi/Marathi support. Uploaded documents are SHA-256-hashed onto Polygon testnet for tamper-proof records.

**What we take:**
- **Pitch statistics from its introduction** (with their sourcing): only ~16 lakh people received legal aid in 2023–24 vs ~80% of the population eligible; **one legal aid clinic per 163 villages**; ~90% of Indians can't fluently navigate English legal documents. Strong numbers for our problem slide.
- A clean example of the **dominant architecture we differentiate against**: cloud LLM wrapper.

**How we differ (say this in the pitch):** their "AI layer" sends every sensitive legal query to a cloud API — the exact privacy failure our on-device Gemma 4 design eliminates. No RAG grounding either: answers come from the model's memory. The blockchain layer audits *documents* but nothing verifies the *advice*. Our verifier-agent + verbatim citations attack the part they left unsolved.

## 2. LexiServe (ICCTWC 2026, Vel Tech Chennai) — IEEE 11583649

**What it is:** Multilingual legal advisory framework: query classification → **FAISS vector index + top-K semantic retrieval of precedents (cosine similarity)** → Gemini API for generation, plus AES/RSA-encrypted document storage. Reports 93.4% query-classification accuracy, AUC 0.92, 8 Indian languages.

**What we take:**
- **Strongest architectural validation of our exact RAG design** — chunk → embed → FAISS/Chroma → top-K → LLM with retrieved context. Cite it as evidence the pipeline shape is sound.
- **Their evaluation template is our writeup eval**: (a) legal-domain classification accuracy on a labeled query set, (b) Top-K retrieval accuracy. Both are replicable in an afternoon with 30–50 queries — instant credibility numbers.
- Their language-usage table (English 55%, Hindi 18%, Tamil 12%...) supports the multilingual-demand argument.

**How we differ:** still cloud-based (Gemini API + cloud deployment section), statute corpus not BNS-specific, text-only. Note: internal inconsistency (ROC figure shows AUC = 1.00 while text claims 0.92) — cite the architecture, don't lean on their metrics.

## 3. "Multilingual AI Legal Assistants for Underserved Judicial Systems" (ICCR 2025, Iraq) — IEEE 11292048

**What it is:** Claims an XLM-R + LegalT5 + ontology + RAG system with 96.5% accuracy, 18 languages, <700 ms latency, deployed in "mobile legal kiosks in five countries."

**⚠️ Treat with serious caution — do not cite as a benchmark.** Red flags on close reading:
- Figures are recycled from unrelated papers: Fig 1 is an LSTM sentiment classifier for *user reviews*, Fig 4 is a *hate-speech/fake-data detection* architecture — neither belongs to this system.
- The reference list contains off-topic self-citations (solar tracking optimization, multilevel inverters, blood-cell CNNs).
- The headline claims (18 languages, 96.5% accuracy, flawless multi-country pilots, sub-700 ms transformer drafting) are extraordinary with no reproducible detail.

**What we take:** at most a one-line related-work mention that "recent work claims multilingual legal-aid deployment in underserved systems." Nothing else. If a judge knows this paper, being the team that spotted its problems is a credibility win — it mirrors our whole thesis about verification.

## 4. Mina (arXiv 2511.08605) — Bangladesh

Multilingual LLM legal assistant for Bangladesh, LangGraph multi-agent architecture. Closest in spirit to us: South Asian jurisdiction, citizen-facing, agentic. Differs: cloud LLM, no on-device story, Bangladeshi law, text-first.

## The positioning table (for writeup + pitch slide)

| | JusticeAI | LexiServe | ICCR '25 | Mina | **Ours** |
|---|---|---|---|---|---|
| Model runs | Cloud (Gemini) | Cloud (Gemini) | Cloud | Cloud | **On-device (Gemma 4 E4B)** |
| Grounding | None | RAG (precedents) | Claimed RAG | RAG | **RAG on official bare acts + verifier agent** |
| Citations shown | No | Partial | No | Partial | **Verbatim sections, every answer** |
| BNS-era (post-2024) law | No | No | N/A | N/A | **Yes — core differentiator** |
| Voice input | No | Partial | Claimed | No | **Native (Gemma 4 audio)** |
| Document photo intake | No | PDF only | No | No | **Native (Gemma 4 image)** |
| Privacy | Cloud + hash audit | Encryption at rest | Unclear | Cloud | **Nothing leaves the device** |
| Human routing (legal aid) | No | No | No | No | **DLSA/Tele-Law referral tool** |

One sentence for the writeup: *"Prior systems (JusticeAI, LexiServe, Mina) demonstrate demand for multilingual legal chatbots but uniformly rely on cloud LLMs, pre-2024 statutes, and text-only interfaces — we contribute the first citizen-facing assistant that is simultaneously on-device, multimodal, BNS-current, and citation-grounded."*
