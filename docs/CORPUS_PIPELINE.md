# Official Corpus Pipeline

The production corpus must contain only reviewed, versioned sources with provenance.
Community datasets may be used for evaluation, but never as the final authority for a
citizen-facing legal claim.

## Pipeline stages

1. Review `config/official_sources.json` against the official government landing page.
2. Download into the ignored `data/raw/official_law/` directory.
3. Record the final URL, byte size, SHA-256, retrieval time, and source metadata.
4. Extract text while preserving page boundaries.
5. Split acts by statutory section/subsection rather than arbitrary token windows.
6. Audit samples against the original PDF.
7. Write deterministic JSONL into `data/processed/sections/`.
8. Build lexical/vector indexes only from audited chunks.

## Safety rules

- Downloads must use HTTPS and an explicitly allowed government host.
- Redirects are rejected because an allowed URL must not redirect to an unreviewed host.
- Existing files are not overwritten unless the operator explicitly requests it.
- A PDF must pass content-type, size, and `%PDF-` magic checks before acceptance.
- Receipts and SHA-256 hashes are stored beside the local source.
- Missing effective dates or source URLs make a chunk ineligible for date-filtered
  production retrieval.
- OCR-derived text must be labeled and manually audited more heavily than digital text.
- Tables of contents are not legal section bodies and must not become duplicate chunks.
- No downloader or parser may silently guess missing statute metadata.

## Commands

```powershell
# List and validate the reviewed manifest without network access.
python scripts/download_official_sources.py --manifest config/official_sources.json --list

# Download required sources after review.
python scripts/download_official_sources.py --manifest config/official_sources.json --output-dir data/raw/official_law

# Build deterministic, review-pending chunks without network access.
python scripts/build_corpus.py --manifest config/official_sources.json --raw-dir data/raw/official_law --output-dir data/processed/sections
```

The builder verifies every local PDF against its reviewed manifest entry and download
receipt before extraction. It writes one JSONL file per source plus a deterministic
`build_report.json`; any required-source failure produces a nonzero exit code.

The raw and processed data directories are intentionally ignored by Git. Commit the
manifest, parsers, tests, and evaluation reports—not downloaded government files or
model weights.

## Human review gate

Before a source is marked production-ready, a reviewer must confirm:

- [ ] Correct official government domain and landing page
- [ ] Correct act/rule title and edition
- [ ] Correct language
- [ ] Correct effective date or explicit “unknown” status
- [ ] Complete section extraction
- [ ] Provisos, explanations, illustrations, schedules, and amendments remain attached
- [ ] Page references agree with the PDF
- [ ] SHA-256 receipt matches the audited local file
- [ ] No table-of-contents duplicates are indexed as operative law
