# Consumer Protection rules corpus review

Reviewed and acquired: 13 July 2026.

Authority: the Department of Consumer Affairs' current
[Consumer Protection Acts and Rules page](https://consumeraffairs.gov.in/pages/consumer-protection-acts).
The Direct Selling amendment is retained from an official Goa Civil Supplies
government mirror because the current central page lists the instrument but omits its
attachment from the rendered link inventory.

## Selected citizen-facing instruments

| Source | Publication / commencement | Gazette reference | SHA-256 |
|---|---|---|---|
| CDRC Rules 2020 + General Rules 2020 | 15 Jul 2020 / 20 Jul 2020 | G.S.R. 448(E), 449(E) | `65b360f6a62bb219ad35742adc48ee669ecda1dd3e28de7cd05f309f9f6f39da` |
| Mediation Rules 2020 | 15 Jul 2020 / 20 Jul 2020 | G.S.R. 450(E) | `03e1a2b838afd37f1df5cec8cb10bed9256cb3bb8e9509fd7328c15ce089ae48` |
| E-Commerce Rules 2020 | 23 Jul 2020 / 23 Jul 2020 | G.S.R. 462(E) | `3012b37f6f6dba2d29523abf10f43fbb3a503768e578ef0fa02e4b9e4593bd0c` |
| E-Commerce corrigendum 2020 | 5 Aug 2020 / not independently inferred | G.S.R. 488(E) | `47f56d66c0df51a58694acb8b2833714bd65a85bd781161535708dfa59fb2086` |
| E-Commerce amendment 2021 | 17 May 2021 | G.S.R. 328(E) | `a7db1f7a8c900e0bc9c7fcb1f2921130ff85e6fac517fb5222efcf76cf559654` |
| Direct Selling Rules 2021 | 28 Dec 2021 | G.S.R. 889(E) | `1fe6c562987e4a94a59739fd16187f3f90e55d926d0b010fd69b4ce8bb181098` |
| Consumer Commission Jurisdiction Rules 2021 | 30 Dec 2021 | G.S.R. 912(E) | `dd22dbfa7ac8bc0ef968765d6cd521ad7a29742afb071b9a919c164f83b765b7` |
| CDRC amendment 2022 | 21 Dec 2022 | G.S.R. 892(E) | `a4a2ff2f7dfa0bc856a1337401003c5d40bbe3ebe510b4a48bc3afdce7ae68d0` |
| Direct Selling amendment 2023 | 21 Jun 2023 | G.S.R. 454(E) | `7b13520daf5ddada8a88a10437713ec2d238a5fc3b9de5cfc8696a3cce50c934` |
| CDRC amendment 2023 | 17 Aug 2023 | G.S.R. 606(E) | `7984ef2f8f324a46a812705df17586f8f178826108d39c1ce0a9e3a145071f1c` |
| Consumer Commission Procedure Regulations 2020 | 24 Jul 2020 | A-105/CCPR/NCDRC/2020 | `07eb8fd33f2b165e9d768476f30641dda84590546206c9c1a426ca00a6467a89` |
| Mediation Regulations 2020 | 24 Jul 2020 | A-105/MR/NCDRC/2020 | `0a61b4e738b4c9181d53ba8f8febaef278c798050998377c7f28a32ccb30465e` |

## Current-text and retrieval treatment

- Amendment and corrigendum records explicitly reference their principal source in
  `modifies_source_ids` and the exact bundled instrument in `target_instrument_title`;
  they are not mislabeled as consolidated principal rules.
- G.S.R. 606(E) substitutes the CDRC Rule 7 fee table again after G.S.R. 892(E).
  A current answer must therefore retrieve the 2020 principal plus the applicable
  amendment chain and must not quote the 2022 table as the latest table.
- The E-Commerce corrigendum corrects the Gazette text but states no independent
  commencement clause. Its `effective_from` remains `null` instead of inferring a date.
- The selected PDFs are Hindi-English Gazette artifacts. The deterministic
  `gazette_rules_en` strategy emits the English operative rules, labels the source as
  `hi-en`, separates bundled instruments, and keeps tables/provisos with the parent rule.
- Every emitted chunk remains `pending_human_review`. Download, hashing, metadata
  review, and parser tests do not replace the required human source audit.

## Reproducible evidence

The ignored raw directory contains each PDF and its URL/timestamp/byte-count/SHA-256
receipt. The ignored processed directory contains one JSONL file per source and a build
report. The committed manifest, downloader, parser, and tests allow those outputs to be
reproduced without treating the downloaded binaries as source code.
