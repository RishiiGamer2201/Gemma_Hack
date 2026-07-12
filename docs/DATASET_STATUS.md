# Dataset acquisition status

Last acquisition run: 2026-07-12. Raw data and model files remain ignored by Git;
manifests, downloaders, receipts, and processing code are versioned.

## Production grounding sources

- 18 official PDFs downloaded with URL, timestamp, byte count, and SHA-256 receipts.
- Current 2026 English Constitution: downloaded and processed.
- Current 2026 Hindi-English diglot Constitution: downloaded and processed.
- BNS, BNSS, BSA, Consumer Protection Act, Delhi Rent Control Act, Code on
  Wages, 2026 Central Rules, implementation material, and wage/labour FAQs:
  downloaded and processed.
- Legal Services Authorities Act and core NALSA/DSLSA rules and regulations:
  downloaded. Three scanned PDFs are intentionally blocked from retrieval until an
  OCR adapter can label page-level OCR provenance.
- NCRB Sankalan IPC/BNS table, NALSA schemes and national directory, Delhi DLSA
  directory, and PIB Tele-Law page: content-marker-validated HTML snapshots with
  receipts.
- NCRB snapshot produced 534 `pending_human_review` mapping candidates. These are
  not converter claims until the curated mapping review is complete.
- DSLSA snapshot produced 12 verified district contact records plus the sourced
  Tele-Law 14454 fallback. Postal addresses remain explicitly flagged for review.
- Legislative Department glossary and regional-language portal: automated raw-page
  requests return HTTP 403/empty application shells. No false “downloaded” receipt is
  retained; these remain pending a supported export route.

## Evaluation-only sources

- Indian legal QA repository: complete six-file snapshot at revision
  `653a6e3fcf03b7d587e44d7a5ed09358c5bc660c`, with per-file hashes. Only the
  Constitution subset is approved by default; IPC/CrPC files are historical.
- ILSI: repository and included datasets downloaded. Treat labels as evaluation-only.
- ILSIC: code repository downloaded. The linked Drive inventory is accessible, but
  the repository's MIT license covers code and does not establish the dataset license;
  the Drive dataset remains blocked pending license confirmation.
- MILDSum: repository and published samples downloaded. The full dataset requires
  maintainer contact and has not been fabricated or substituted.
- IndicTrans2: repository and artifact instructions downloaded. IN22 and model/data
  artifacts require Hugging Face access in the current environment.
- IL-TUR: pinned at revision `d16219ad0423cc181ec8460d930fd10a907664b6`, but
  the 1.6 GB repository returns HTTP 401 until the user accepts the gated dataset and
  authenticates Hugging Face.
- Aalap and IN22 Hugging Face repositories currently require authentication.
- IndicVoices: the 745 GB corpus was deliberately not downloaded. Only bounded
  language validation subsets should be acquired after Hugging Face authentication.

Evaluation datasets must never enter the production legal index.
