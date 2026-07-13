# AdhiKaar teammate integration

A teammate built a parallel Track-1 assistant, **AdhiKaar** (Flask + vanilla JS +
ChromaDB). Rather than merge two conflicting architectures, we keep this project's
verified pipeline and import the teammate's *content* through it as review-pending
candidates. This first integration brings in the IPC/BNS mappings.

## Why not merge the code

The two builds hold opposite philosophies. AdhiKaar trusts the model: its
confirmation loop is a prompt instruction, its power-imbalance detector injects
prompt text, and its 95 IPC/BNS mappings are served directly from a JSON file with
no source citation or verification. This project does the opposite — a hard
confirmation gate, an independent claim verifier, per-source provenance and hashes,
and a mapping catalogue that stays empty until a human approves each entry against an
official source. Serving unverified mappings is the exact failure (`png2.jpg`,
"Section 247A of the Constitution") the verifier exists to prevent, so the teammate's
mappings cannot be adopted as-is.

## What was imported, and how

`scripts/import_adhikaar_mappings.py` reads the teammate's `ipc_bns_mapping.json`
(95 entries) and writes `data/processed/mappings/adhikaar_candidates.jsonl`. Every
candidate is `pending_human_review`, records its provenance
(`adhikaar_teammate_contribution`) and the source file's SHA-256, and is **not**
served — `CURATED_MAPPINGS` in `src/api/state.py` stays empty and the converter keeps
returning `not_found` until a human approves entries into `config/ipc_bns_mappings.json`.

The value added by importing through our pipeline is the **cross-check**. Each
teammate mapping is compared against our own NCRB Sankalan snapshot
(`data/processed/mappings/ipc_bns_candidates.jsonl`) by IPC section, and tagged:

| Cross-check verdict | Count | Meaning for the reviewer |
|---|---:|---|
| `agrees_with_ncrb` | 69 | The teammate's BNS section matches the official Sankalan row. Corroborated; quicker to approve. |
| `conflicts_with_ncrb` | 15 | The teammate's BNS section differs from the Sankalan row. **Review these first.** |
| `ipc_not_in_ncrb_snapshot` | 4 | No Sankalan row for that IPC section to compare against. |
| `no_ipc_ancestor` | 7 | A "New Provision" with no IPC predecessor to corroborate. |

Reproduce with:

```powershell
python scripts/import_adhikaar_mappings.py --source <path>\AdhiKaar\data\ipc_bns_mapping.json
```

The teammate source file's SHA-256 at import: `5eba9ec232aab63d…`. Raw candidate
output stays under Git-ignored `data/`; this document and the importer are the
committed, reproducible record.

## Reviewer worklist

1. Resolve the 15 `conflicts_with_ncrb` rows against the official BNS text — a
   conflict is a discrepancy between two unofficial sources, not proof either is
   right. Examples flagged: IPC 489A (teammate BNS 344 vs Sankalan 178), IPC 144,
   IPC 351.
2. Approve `agrees_with_ncrb` rows only after confirming the section text against an
   official source; corroboration lowers risk but is not approval.
3. Treat the 7 `no_ipc_ancestor` "New Provisions" as BNS-only entries.
4. Move approved entries into `config/ipc_bns_mappings.json`, filling `change_notes`,
   `reviewed_by`, and `reviewed_at`. Only then does the converter serve them.

## Legal-aid directory (second pass)

`scripts/import_adhikaar_legal_aid.py` imports the teammate's 98 district contacts
as `pending_human_review` candidates and cross-checks his 20 SLSA numbers against
our 34 verified state contacts (built from a NALSA snapshot with provenance).

The cross-check earned its keep here. Of the 15 states where we hold a published
number to compare, **14 of the teammate's SLSA numbers conflict** with ours and only
1 agrees (5 states we list as "not published", so there is nothing to compare). The
disagreements are real, not formatting — e.g. Maharashtra: teammate `022-22617612`
vs our verified `022-22691395 / 22691358`; Karnataka: teammate `080-22112700` vs our
`080-22111875 / 22111714`. Plausibly formatted but different numbers is the signature
of fabricated contact data, and a wrong helpline shown to a person in crisis is the
worst failure this project can make.

Conclusion: **do not use the teammate's legal-aid contacts.** Our verified 34-state
SLSA directory is better, and it already covers non-Delhi routing. The 98 district
candidates are retained for review only and must each be confirmed against the
official DLSA site before any is shown; given the SLSA conflict rate they should be
treated with high suspicion.

## Mapping reviewer worksheet

`docs/MAPPING_REVIEW_WORKSHEET.md` lists the 15 mapping conflicts side by side with
our NCRB snapshot's BNS section and a decision checkbox, so the human review can
start immediately on the rows that matter.

## Not imported

The teammate's rights-knowledge and 11-language prompt set were left for a later
pass. They carry no provenance and need the same candidate-plus-review treatment.
