# Review of Senior's Recommendations — What to Use, Adapt, or Skip

Source: [senior_recommendations.txt](senior_recommendations.txt) (WhatsApp notes + diagram `png1.jpg` + sample output `png2.jpg` + `pdf.pdf`). His project dates to **Aug 2025** — before Gemma 4 existed and while IPC/CrPC-era resources were still standard. That context explains most of what needs updating.

## ✅ USE — directly valuable to us

| Item | Verdict |
|---|---|
| **Law hierarchy insight** (Constitution → main bare acts → other bare acts) | **Adopt as retrieval design.** Tag every RAG chunk with a `priority` level (1 = Constitution, 2 = core codes, 3 = other acts) and rank citations accordingly. This is how lawyers actually reason, and it makes answers defensible. |
| [Constitution of India](https://legislative.gov.in/constitution-of-india/) + [legislative.gov.in important legislations](https://legislative.gov.in/important-legislations/) (**Hindi versions available**) | **Add to corpus.** Hindi bare-act text = grounded Hindi citations without translation. Added to DATASET.md sources. |
| [NALSA important bare acts](https://nalsa.gov.in/important-bare-acts/) | Already in our plan; his link confirms it. |
| [InLegalBERT](https://huggingface.co/law-ai/InLegalBERT) + [InCaseLawBERT](https://huggingface.co/law-ai/InCaseLawBERT) + [Law-AI GitHub](https://github.com/Law-AI) + [InLegalBERT paper](https://arxiv.org/pdf/2209.06049) | Already our chosen retriever; the paper is a writeup citation. |
| [IndicTrans2](https://huggingface.co/ai4bharat/indictrans2-indic-en-1B) | Already our fallback translation layer. Agreed it's not generative — it's a bridge, exactly how we planned. |
| [Ayn paper (arXiv 2403.13681)](https://arxiv.org/abs/2403.13681) — 88M Indian legal model beating far larger LLMs on judgment prediction | **Writeup ammunition**: supports "small + domain-focused works for Indian law." Note it's for prediction/summarization, not citizen QA. |

## ⚠️ ADAPT — usable with corrections

| Item | Issue & fix |
|---|---|
| [Kaggle: LLM Fine-Tuning Dataset of Indian Legal Texts](https://www.kaggle.com/datasets/akshatgupta7/llm-fine-tuning-dataset-of-indian-legal-texts) (QA pairs on IPC, CrPC, Constitution; CC BY-SA; also [mirrored on HF](https://huggingface.co/datasets/Techmaestro369/indian-legal-texts-finetuning)) | **IPC and CrPC are repealed** (BNS/BNSS since 1 July 2024). Fine-tuning on it would teach the model dead section numbers — the exact failure our pitch attacks. **Use only**: (a) Constitution QA pairs, still valid; (b) as an eval set for question *style*; (c) as few-shot examples with section numbers stripped. |
| [Kaggle: Indian Supreme Court judgments](https://www.kaggle.com/datasets/vangap/indian-supreme-court-judgments) | Real and useful, but case-law RAG is too heavy for a 1-day build. **Roadmap item**, not hackathon scope. |
| "Fine-tune karna hi hai" (Qwen 2.5-1.5B) | Two problems: (1) **this hackathon requires Gemma 4** — Qwen is disqualifying; (2) his own evidence argues against tiny fine-tunes: see below. If we fine-tune anything, it's a Gemma 4 LoRA via Unsloth as polish, *on top of* RAG — never instead of it. |
| Mock trials / OCR doc reading | Mock hearing practice = good **roadmap slide**. Document reading = already covered by Gemma 4 native image input (explain an FIR/notice); skip "anomaly detection" — undemoable in a day. |

## ❌ SKIP — with reasons we can defend to judges

1. **The lawyer-facing courtroom assistant** (diarization + real-time citation + suggested questions). It's a decent product idea, but it's a different product: Track 1 explicitly asks for a **regular-citizen** assistant. It's also undemoable (no courtroom), and recording Indian court proceedings has legal restrictions. Keep as a "future: lawyer mode" roadmap line.
2. **Whisper large-v3 + pyannote.** His stack needed Whisper because his SLM was text-only. **Gemma 4 E4B has native audio input** — Whisper is a redundant 1.5B-param moving part. Pyannote diarization only matters for multi-speaker courtroom audio (see #1). If Phase-1 audio tests fail, our fallback is IndicConformer (30M params, 22 languages) — lighter and Indic-tuned vs Whisper.
3. **[Kaggle: Legal Text Classification Dataset](https://www.kaggle.com/datasets/amohankumar/legal-text-classification-dataset).** Verified: it's **Australian case law** (Case ID/Outcome/Title/Text format). Not Indian, not QA. Don't touch it.
4. **[SmolLM2-FT-legal-india](https://huggingface.co/saicharan1010/SmolLM2-FT-legal-india) as a path to follow.** The numbers: 135M params, BLEU 0.126 vs base 0.121 — a rounding-error improvement. And `png2.jpg` (his own screenshot!) shows it citing **"Section 247A and 247B of the Indian Constitution" — which do not exist** (the Constitution has Articles, not Sections). **Keep the screenshot**: it's a perfect pitch exhibit for "why fine-tuned tiny models hallucinate and why we ground every answer in retrieved bare-act text."
5. **Dropbox folder** — inaccessible to us; ask the senior what's in it before the 15th if possible.

## The big correction across all his notes

His "5 main acts: IPC, CRPC, CPC, Evidence Act, Contract Act" is one year out of date:

| His list | Today (since 1 July 2024) |
|---|---|
| IPC | **Bharatiya Nyaya Sanhita (BNS) 2023** |
| CrPC | **Bharatiya Nagarik Suraksha Sanhita (BNSS) 2023** |
| Evidence Act | **Bharatiya Sakshya Adhiniyam (BSA) 2023** |
| CPC | unchanged |
| Contract Act | unchanged |

This isn't a nitpick — it's our **differentiator**: most available legal AI datasets and fine-tunes (including everything he shared) are IPC-era. A RAG corpus built on current BNS-era bare acts is the freshest thing in the room, and png2 is the proof of what happens otherwise.

## Net effect on our plan

- No architecture change — the senior's material validates the RAG + citations + on-device direction.
- DATASET.md gains: legislative.gov.in (Hindi bare acts), Constitution of India, akshatgupta7 Constitution-QA subset (eval only).
- Pitch gains: png2 hallucination exhibit + Ayn/InLegalBERT papers as citations + "our corpus is BNS-current, prior art isn't" slide.
