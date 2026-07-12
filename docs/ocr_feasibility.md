# Offline OCR feasibility

Last measured: 2026-07-13 IST

## Decision

Use pinned Tesseract as the local printed-notice and phone-photo fallback. The compact
Gemma 4 Ollama builds installed for this project do not expose vision, so OCR text must
still pass through the document-type/fact extraction and user-confirmation stages. A
Gemma visual cross-check remains unimplemented and is not implied by these results.

The adapter accepts only bounded PNG/JPEG input, reads it into memory once, verifies
the executable and all OCR assets, sends the image to Tesseract over stdin, caps time
and output, and returns typed text/confidence metadata. It writes neither input nor
recognized text.

## Pinned runtime

| Item | Pinned value |
|---|---|
| Runtime | UB-Mannheim Tesseract `5.4.0.20240606` |
| Runtime license | Apache-2.0 |
| Tessdata repository | `tesseract-ocr/tessdata_fast` |
| Tessdata revision | `87416418657359cb625c412a48b6e1d6d41c29bd` |
| Languages | English, Hindi, English+Hindi |
| Image limit | 15 MiB / 20 megapixels |

The per-file size/SHA-256 receipt is committed at `config/ocr_model.json`; language
models remain in ignored `models/ocr/tessdata/` storage.

Sources:

- [Tesseract documentation](https://tesseract-ocr.github.io/)
- [tessdata_fast repository](https://github.com/tesseract-ocr/tessdata_fast)
- [UB-Mannheim Windows builds](https://github.com/UB-Mannheim/tesseract/wiki)

## Reproduction

```powershell
python scripts/generate_ocr_fixtures.py
python scripts/extract_image_text.py --image .runtime/ocr_samples/printed_notice.png --tessdata-dir models/ocr/tessdata --language eng
python scripts/extract_image_text.py --image .runtime/ocr_samples/phone_notice.jpg --tessdata-dir models/ocr/tessdata --language eng
```

The generator creates synthetic benchmark notices only; it does not use citizen data.

## Results

| Probe | Dimensions | Time | Mean confidence | Text result |
|---|---:|---:|---:|---|
| Printed PNG notice | 1600×2200 | 0.27 s | 96.20% | Exact |
| Rotated, blurred, compressed phone-style JPEG | 1900×2500 | 0.31 s | 96.09% | Exact |

Expected and recognized content included the notice title, date, addressee, security
deposit subject, and the evidence-preservation list. Synthetic images are ignored by
Git and can be regenerated deterministically.

## Remaining gate

- Benchmark a real consented phone photograph before claiming camera-condition
  accuracy; the present fixture only approximates rotation, blur, and compression.
- Add page-image rendering so scanned PDFs can use this same OCR engine.
- Add Gemma visual cross-check only if a verified local multimodal runtime exposes it.
- Keep the editable confirmation gate mandatory because OCR confidence is not legal
  correctness.
