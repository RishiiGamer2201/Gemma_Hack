# Dataset Guide — What to Download, How, and Where to Save It

Owner: **Member B (Data + RAG)** · Supports Phase 2 of [PLAN.md](PLAN.md)

## Folder layout (create this first)

All data lives under `data/` in this repo. Large files stay local — they are git-ignored; only scripts and this guide get committed.

```
Gemma_Hack/
├── data/
│   ├── raw/
│   │   ├── bare_acts/        # PDFs/text of acts from India Code
│   │   ├── legal_aid/        # NALSA schemes, DLSA contacts, Tele-Law info
│   │   └── benchmarks/       # IL-TUR and other eval datasets
│   ├── processed/
│   │   └── chunks/           # one JSON per act: [{act, section_no, title, text}]
│   └── vectordb/             # ChromaDB / FAISS index
└── models/                   # downloaded embedding/ASR models (git-ignored)
```

Create it:

```powershell
mkdir data\raw\bare_acts, data\raw\legal_aid, data\raw\benchmarks, data\processed\chunks, data\vectordb, models
```

---

## 1. Bare Acts — the core RAG corpus

**Source: [India Code portal](https://www.indiacode.nic.in)** — the Government of India's official repository of all central and state acts. Free, no login. Regional-language versions are available for many acts.

**Steps:**
1. Go to https://www.indiacode.nic.in
2. Use the search box ("Search by Act Title") for each act below.
3. On the act's page, download the **PDF of the full act** (and the Hindi version where offered).
4. Save into `data/raw/bare_acts/` with clean names, e.g. `bns_2023_en.pdf`, `bns_2023_hi.pdf`.

**Acts to download (driven by our 3 demo scenarios):**

| Act | Why | Save as |
|---|---|---|
| Bharatiya Nyaya Sanhita, 2023 (BNS) | Criminal law — FIR/notice scenario | `bns_2023_en.pdf` |
| Bharatiya Nagarik Suraksha Sanhita, 2023 (BNSS) | Criminal procedure — arrest/FIR rights | `bnss_2023_en.pdf` |
| Consumer Protection Act, 2019 | Deposit/refund disputes | `cpa_2019_en.pdf` |
| Delhi Rent Control Act, 1958 | Landlord/deposit scenario (Delhi demo audience) | `drc_1958_en.pdf` |
| Payment of Wages Act, 1936 | Unpaid wages scenario | `pow_1936_en.pdf` |
| Legal Services Authorities Act, 1987 | Who qualifies for FREE legal aid (great pitch fact) | `lsa_1987_en.pdf` |

> Backup source if India Code is slow: [Legislative Department](https://legislative.gov.in) publishes the same official texts.

**Convert PDFs to text** (run from repo root):

```powershell
pip install pymupdf
python -c "import fitz,glob,pathlib; [pathlib.Path(f.replace('.pdf','.txt')).write_text('\n'.join(p.get_text() for p in fitz.open(f)), encoding='utf-8') for f in glob.glob('data/raw/bare_acts/*.pdf')]"
```

Then chunk **by section** (regex on `^\d+\.` section headers) into `data/processed/chunks/<act>.json`.

---

## 2. Legal Aid Directory — for the `find_legal_aid` tool

**Source: [NALSA](https://nalsa.gov.in)** (National Legal Services Authority).

**Steps:**
1. Go to https://nalsa.gov.in/legal-aid/ — save the "who is entitled to free legal aid" criteria as `data/raw/legal_aid/nalsa_eligibility.txt` (copy text or print-to-PDF).
2. From the NALSA site's State Legal Services Authorities section, collect **Delhi SLSA + district DLSA contact details** (address, phone, email) into a small hand-made CSV: `data/raw/legal_aid/dlsa_contacts.csv` with columns `district, name, address, phone`.
   - Delhi SLSA: https://dslsa.org (has all 11 Delhi district DLSA contacts)
3. Note the **Tele-Law helpline: 14454** and portal https://www.tele-law.in — hardcode these into the tool's fallback response.
4. NALSA schemes (victim compensation, Lok Adalat, etc.): https://nalsa.gov.in/preventive-strategic-legal-services-schemes/ — save the scheme list as `data/raw/legal_aid/nalsa_schemes.txt`.

> 20–30 rows of accurate Delhi contacts beats a scraped all-India dump for the demo. Keep it small and correct.

---

## 3. IL-TUR Benchmark — for eval numbers in the writeup (optional but impressive)

**Source: [Exploration-Lab/IL-TUR on Hugging Face](https://huggingface.co/datasets/Exploration-Lab/IL-TUR)** — 8 Indian legal understanding/reasoning tasks, English + Hindi + 9 Indic languages.

```powershell
pip install datasets
python -c "from datasets import load_dataset; ds = load_dataset('Exploration-Lab/IL-TUR', 'bail'); ds.save_to_disk('data/raw/benchmarks/il_tur_bail')"
```

Use 20–50 samples to report "we evaluated retrieval/answer quality on IL-TUR" in the writeup — judges love a real eval, even a small one.

---

## 4. Models

### Gemma 4 E4B (the brain) — via Ollama, simplest path

```powershell
# install from https://ollama.com/download first
ollama pull gemma4:e4b
```

Alternative (raw weights, needs HF login + license acceptance on the model page):
- https://huggingface.co/google/gemma-4-E4B-it

```powershell
pip install -U huggingface_hub
huggingface-cli login
huggingface-cli download google/gemma-4-E4B-it --local-dir models/gemma-4-e4b-it
```

### InLegalBERT (retrieval embeddings) — [law-ai/InLegalBERT](https://huggingface.co/law-ai/InLegalBERT)

```powershell
python -c "from transformers import AutoModel, AutoTokenizer; AutoTokenizer.from_pretrained('law-ai/InLegalBERT'); AutoModel.from_pretrained('law-ai/InLegalBERT')"
```

(Downloads to the HF cache automatically; no manual save needed.)

**Simpler fallback embedder** (smaller, faster, good enough):

```powershell
pip install sentence-transformers
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"
```

### IndicConformer ASR (only if Gemma's native audio fails Phase 1 tests)

- GitHub: https://github.com/AI4Bharat/IndicConformerASR
- Models: https://huggingface.co/collections/ai4bharat/indicconformer — download the **Hindi** checkpoint to `models/indicconformer_hi/`

### IndicTrans2 translation (only if Gemma's Hindi generation is weak)

- GitHub: https://github.com/AI4Bharat/IndicTrans2 (distilled 200M variants run on CPU)

---

## 5. Vector DB build (end of Phase 2)

```powershell
pip install chromadb
```

Build script writes to `data/vectordb/` — embed every section chunk with metadata `{act, section_no, title}` so answers can cite **"Section 316, BNS 2023 — Criminal breach of trust"** verbatim.

---

## Checklist

- [ ] Folder layout created
- [ ] 6 bare acts downloaded from India Code → `data/raw/bare_acts/`
- [ ] PDFs converted to text, chunked by section → `data/processed/chunks/`
- [ ] NALSA eligibility + schemes saved → `data/raw/legal_aid/`
- [ ] Delhi DLSA contacts CSV hand-built (`dlsa_contacts.csv`)
- [ ] IL-TUR sample downloaded (optional)
- [ ] `ollama pull gemma4:e4b` done on demo laptop
- [ ] Embedder downloaded (InLegalBERT or MiniLM)
- [ ] Vector DB built in `data/vectordb/`, retrieval spot-checked (≥ 8/10 hit-rate)
