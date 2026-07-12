# Dataset acquisition status

Last acquisition run: 2026-07-12. Raw data and model files remain ignored by Git;
manifests, downloaders, receipts, and processing code are versioned.

## Production grounding sources

- [x] Download 18 official PDFs with URL, timestamp, byte count, and SHA-256 receipts.
- [x] Download and process the current 2026 English Constitution.
- [x] Download and process the current 2026 Hindi-English diglot Constitution.
- [x] Download and process BNS, BNSS, BSA, Consumer Protection Act, Delhi Rent Control Act, Code on
  Wages, 2026 Central Rules, implementation material, and wage/labour FAQs.
- [x] Download the Legal Services Authorities Act and core NALSA/DSLSA rules and regulations.
- [ ] Process all legal-aid PDFs for retrieval.
  - [x] Process digitally readable legal-aid PDFs.
  - [ ] Add page-level OCR provenance and process the three scanned PDFs.
- [x] Snapshot the NCRB Sankalan IPC/BNS table with content validation and receipts.
- [x] Snapshot NALSA schemes and the national directory with content validation and receipts.
- [x] Snapshot the Delhi DLSA directory with content validation and receipts.
- [x] Snapshot the PIB Tele-Law page with content validation and receipts.
- [ ] Complete the production IPC/BNS mapping catalogue.
  - [x] Generate 534 `pending_human_review` candidates from the NCRB snapshot.
  - [ ] Curate and independently approve mappings before using them as converter claims.
- [ ] Complete the offline Delhi legal-aid directory.
  - [x] Generate 12 verified district contact records.
  - [x] Add the sourced Tele-Law 14454 fallback.
  - [ ] Verify and add postal addresses.
- [ ] Obtain the Legislative Department legal glossary through a supported export route.
  - [x] Detect and reject the HTTP 403/empty application-shell response.
- [ ] Obtain regional-language legal publications through a supported export route.
  - [x] Detect and reject the HTTP 403/empty application-shell response.

## Evaluation-only sources

- [x] Download the complete six-file Indian legal QA repository snapshot at revision
  `653a6e3fcf03b7d587e44d7a5ed09358c5bc660c`, with per-file hashes. Only the
  Constitution subset is approved by default; IPC/CrPC files are historical.
- [x] Download the ILSI repository and included datasets for evaluation-only use.
- [ ] Complete ILSIC acquisition.
  - [x] Download the ILSIC code repository.
  - [x] Verify that the linked Drive inventory is accessible.
  - [ ] Confirm the dataset's license separately from the repository's MIT code license.
  - [ ] Download the Drive dataset after license confirmation.
- [ ] Complete MILDSum acquisition.
  - [x] Download the repository and published samples.
  - [ ] Obtain the full dataset from its maintainers.
- [ ] Complete IndicTrans2 evaluation setup.
  - [x] Download the repository and artifact instructions.
  - [ ] Authenticate Hugging Face and download bounded IN22 evaluation data.
  - [ ] Download the selected distilled model separately from dataset acquisition.
- [ ] Download IL-TUR revision `d16219ad0423cc181ec8460d930fd10a907664b6`.
  - [x] Pin the intended 1.6 GB revision.
  - [x] Confirm that the repository currently returns HTTP 401 without authentication.
  - [ ] Accept the gated dataset terms and authenticate Hugging Face.
  - [ ] Download and receipt-verify the complete dataset.
- [ ] Download Aalap for evaluation-only use after Hugging Face authentication.
- [ ] Download bounded IndicVoices validation subsets for selected languages after authentication.
  - [x] Exclude the complete 745 GB corpus from the hackathon download scope.

Evaluation datasets must never enter the production legal index.
