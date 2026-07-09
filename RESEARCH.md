# Deep Research: Track 1 — Multilingual AI Legal Assistant with Gemma 4

**Team:** Judge My Win · **Event:** Build with Gemma – AIMS DTU, 15 July 2026 (Kaggle-hosted)

---

## 1. The Problem (your pitch's foundation)

- **Justice gap is massive and documented.** Among Indians who experienced a legal problem, **more than half could not meet their need for legal representation**. ~75% of prisoners are undertrials, largely for lack of money and awareness. High litigation cost and procedural complexity are the top barriers.
- **Language is a structural barrier.** English dominates higher courts and legal drafting, alienating non-English-speaking litigants. India has 22 scheduled languages; legal information effectively exists in one or two.
- **Awareness efforts don't scale.** Government has run 13.8+ lakh legal awareness programmes reaching ~15 crore people, and 16.6 lakh people got free legal aid in FY 2025-26 — yet a study across 18 states found the vast majority of surveyed women didn't even know free legal services existed.
- **The "why now" hook: India's criminal laws were just replaced.** On 1 July 2024, IPC/CrPC/Evidence Act became **BNS/BNSS/BSA**. IPC's 511 sections became BNS's 358; 175 sections changed, 8 added, 22 repealed. Even lawyers and law students are relearning the codes — ordinary citizens are navigating two parallel legal systems (old cases under IPC, new under BNS). **No consumer tool cleanly explains "what does the law say about my situation *today*."** This is a fresh, concrete, and demo-able hook for the pitch.

## 2. Prior Art & Competitors (and their gaps)

| Solution | What it is | Gap we can exploit |
|---|---|---|
| **Jugalbandi** (Microsoft + AI4Bharat + OpenNyAI) | WhatsApp bot for govt schemes; voice in 10 Indian languages | Cloud-only (Azure OpenAI), scheme discovery not legal reasoning, pipeline of 4 separate cloud services |
| **Jagrit** (Agami + iProbono) | WhatsApp/Telegram bot for domestic-violence law queries | Single legal domain, cloud-based |
| **Tele-Law / Nyaya Bandhu** (Dept. of Justice) | Connects citizens to volunteer lawyers via video/app; 9,261 registered advocates | Human-bottlenecked, appointment-based, not instant; only ~14.9k women registered on Nyaya Bandhu |
| **NyayGuru, LawFYI** | Web legal chatbots for Indian law | English-centric, cloud, no citation grounding, aimed at semi-professional users |
| **Aalap (OpenNyAI), Indian-LawyerGPT, Law Gemma** | Fine-tuned open models (Mistral 7B, Llama, Gemma 2B) on Indian legal text | Built for lawyers/paralegals, not citizens; text-only; mostly pre-date the BNS transition |

**Key insight:** nobody combines (a) citizen-plain-language, (b) voice-first multilingual, (c) fully on-device/private, (d) grounded in the *new* BNS-era law with citations. That intersection is open.

## 3. Why Gemma 4 Is Uniquely Suited (the technical story)

From the [Gemma 4 model card](https://ai.google.dev/gemma/docs/core/model_card_4):

- **Sizes:** E2B (2.3B eff.), E4B (4.5B eff.), 12B, 26B-A4B MoE (3.8B active), 31B dense.
- **Native audio input on E2B / E4B / 12B** — a citizen can *speak* their problem directly to the model; no separate ASR stage needed (though AI4Bharat ASR is a fallback for low-resource languages).
- **Image input on all sizes** — photograph an FIR, legal notice, rent agreement, or challan and have it explained. Multimodal legal intake is a killer demo.
- **140+ languages** trained with balanced Indic representation; instruction-tuned on top 40 languages.
- **Native function calling (JSON schema)** — the assistant can call tools: search a statute database, find the nearest DLSA/legal-aid clinic, draft an RTI/complaint template.
- **Configurable thinking modes** — reasoning traces for "forensic-grade" explanations of which section applies and why.
- **On-device:** E4B at Q4 quantization ≈ 3 GB — runs on a normal laptop via Ollama/llama.cpp (2–5 tok/s CPU, fast on any modest GPU). 128K context on E2B/E4B; 256K on 12B+.
- **Privacy narrative:** legal problems (domestic violence, workplace harassment, police complaints) are exactly the queries people don't want sent to a cloud. On-device = confidential by construction.

## 4. Building Blocks (all open source)

**Language / speech (if needed beyond Gemma's native audio):**
- [AI4Bharat IndicConformer](https://github.com/AI4Bharat/IndicConformerASR) — ASR for all 22 scheduled languages, only 30M params, runs on-device.
- [AI4Bharat IndicTrans2](https://github.com/AI4Bharat/IndicTrans2) — open NMT for all 22 scheduled languages; distilled 200M variants exist.
- AI4Bharat IndicTTS for spoken responses.

**Legal corpora / retrieval:**
- **India Code portal** — official bare acts, including regional-language versions (BNS, BNSS, BSA, consumer protection, rent laws, labour codes).
- [IL-TUR benchmark](https://huggingface.co/datasets/Exploration-Lab/IL-TUR) — 8 Indian legal NLU/reasoning tasks, English + Hindi + 9 Indic languages (useful for eval numbers in the writeup).
- [InLegalBERT](https://huggingface.co/law-ai/InLegalBERT) — embeddings pre-trained on 1950–2019 Indian court text (1.8M+ downloads) — good retriever for RAG.
- NALSA schemes + FAQ pages, Nyaya Bandhu/Tele-Law directories — content for the "next steps" tool (who to contact, what's free).
- Indian Kanoon–derived datasets (ILDC, IndianBailJudgments-1200) for case-law grounding.

## 5. The Non-Negotiable Risk: Hallucination

- Stanford HAI found even purpose-built legal AI tools hallucinate on **1 in 6 queries or more**; general LLMs hallucinated on 58–88% of direct case-law questions. 1,400+ court incidents globally involve fabricated AI citations.
- For a citizen-facing tool, a wrong answer about rights is worse than no answer.
- **Mitigation = the differentiator, not a checkbox:** RAG over official bare acts with **verbatim section citations rendered in the UI**, an explicit "this is legal information, not legal advice" framing, refusal + route-to-human (Tele-Law/DLSA referral via function call) when confidence is low. Judges will probe this; making "grounded and honest" a headline feature turns the biggest weakness into pitch material.

## 6. What Wins Gemma Hackathons (evidence from the Gemma 3n Impact Challenge)

Winning projects (Gemma Vision, Vite Vere Offline, 3VA, Dream Assistant, LENTERA) shared a pattern Google explicitly highlighted:
1. **On-device / offline deployment** — not cloud API wrappers.
2. **Privacy as a feature** for sensitive users.
3. **A real, named user / underserved population** — the 1st-place winner built for his blind brother.
4. **Human story told well** — video + writeup quality was decisive. Our hackathon page says the same: *"the ability to communicate your vision through a compelling writeup and pitch is what will set the winners apart."*

## 7. Recommended Positioning (synthesis)

**"Nyaya in your pocket, in your language, on your device."**

A citizen speaks (or photographs a document) in their own language → Gemma 4 E4B (on-device) understands the situation → retrieves the exact BNS/relevant-act sections via RAG → explains rights, options, and next steps in the citizen's language, with verbatim citations → function-calls a "next steps" toolkit (nearest free legal aid via NALSA/DLSA data, draft complaint/RTI template, Tele-Law referral).

Differentiators to hammer in the pitch:
1. **Voice-first + document-photo intake** (Gemma 4 native audio/image — no one else does this on-device).
2. **BNS-era current** — competitors' fine-tunes are trained on pre-2024 IPC law.
3. **Private by construction** — sensitive legal matters never leave the device.
4. **Grounded & honest** — every claim cites a section; low confidence routes to a human (Tele-Law).
5. **Works offline** — the people with least legal access often have worst connectivity.

## Sources

- [Gemma 4 model card — Google AI](https://ai.google.dev/gemma/docs/core/model_card_4) · [Gemma 4 — DeepMind](https://deepmind.google/models/gemma/gemma-4/) · [google/gemma-4-E4B-it](https://huggingface.co/google/gemma-4-E4B-it)
- [Unsloth: Run Gemma 4 locally](https://unsloth.ai/docs/models/gemma-4) · [Gemma 4 with Ollama/llama.cpp](https://dev.to/dmaxdev/how-to-run-gemma-4-locally-with-ollama-llamacpp-and-vllm-3n44)
- [Microsoft Source: Jugalbandi](https://news.microsoft.com/source/asia/features/with-help-from-next-generation-ai-indian-villagers-gain-easier-access-to-government-services/) · [ABA Journal: GenAI vs language barriers in Indian justice](https://www.abajournal.com/web/article/could-generative-ai-help-break-down-language-barriers-plaguing-the-indian-justice-system) · [iProbono: Jagrit chatbot](https://i-probono.in/ipb_casestudy/ai-for-legal-empowerment-collaborative-effort-behind-jagrit-chatbot/)
- [Harvard CLP: Access to Justice in India report](https://clp.law.harvard.edu/wp-content/uploads/2023/05/UPDATED-India-National-Report-ILAG-Conference-2023.pdf) · [NLSIU: Knocking on closed doors](https://www.nls.ac.in/wp-content/uploads/2022/01/Knocking-on-closed-doors_Aithala_Suresh_2021.pdf) · [LiveLaw: legal aid for marginalized groups](https://www.livelaw.in/articles/access-to-justice-legal-aid-system-for-marginalized-groups-in-india-259963)
- [Nyaya Bandhu programme](https://currentaffairs.khanglobalstudies.com/nyaya-bandhu-legal-aid-programme/) · [FPJ: Nyaya Bandhu registrations](https://www.freepressjournal.in/india/over-14800-women-registered-for-legal-help-via-nyaya-bandhu-app-till-june-30-centre-tells-rajya-sabha) · [NALSA](https://nalsa.gov.in/legal-aid/)
- [BNS vs IPC: what changed](https://thekanoonadvisors.com/15-key-bns-vs-ipc-differences-a-comprehensive-2026-guide/) · [New criminal laws two years on](https://www.legacyias.com/new-criminal-laws-bns-bnss-bsa/)
- [Stanford HAI: legal models hallucinate 1 in 6 queries](https://hai.stanford.edu/news/ai-trial-legal-models-hallucinate-1-out-6-or-more-benchmarking-queries)
- [Google blog: Gemma 3n Impact Challenge winners](https://blog.google/innovation-and-ai/technology/developers-tools/developers-changing-lives-with-gemma-3n/) · [Kaggle: Gemma 4 Good Hackathon](https://www.kaggle.com/competitions/gemma-4-good-hackathon)
- [AI4Bharat IndicConformer](https://github.com/AI4Bharat/IndicConformerASR) · [IndicTrans2](https://github.com/AI4Bharat/IndicTrans2) · [InLegalBERT](https://huggingface.co/law-ai/InLegalBERT) · [IL-TUR](https://huggingface.co/datasets/Exploration-Lab/IL-TUR)
- [OpenNyAI Aalap](https://medium.com/@vanshajkerni/aalap-a-finetuned-mistral-7b-legally-trained-model-for-indian-legal-system-458b0dfde638) · [Indian-LawyerGPT](https://github.com/NisaarAgharia/Indian-LawyerGPT)
