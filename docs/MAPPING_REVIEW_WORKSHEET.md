# Reviewer worksheet — AdhiKaar mapping conflicts

The teammate import cross-checked 95 IPC/BNS mappings against our NCRB Sankalan
snapshot. These 15 **conflict** with the snapshot and need resolving first. A
conflict is a disagreement between two unofficial sources; confirm the correct BNS
section against the gazetted BNS before approving. Neither column is authoritative.

| IPC | Offence | Teammate says BNS | Our NCRB snapshot says BNS | Reviewer decision |
|---|---|---|---|---|
| 144 | Joining Unlawful Assembly Armed with Deadly Weapon | 187 | 189(4) | ☐ |
| 166A | Public Servant Not Recording FIR | 218 | 199 | ☐ |
| 171E | Bribery | 171 | 173 | ☐ |
| 171B | Bribery at Elections | 168 | 170 | ☐ |
| 191 | Giving False Evidence | 229 | 227 | ☐ |
| 228 | Intentional Insult to Court | 266 | 267 | ☐ |
| 268 | Public Nuisance | 284 | 270 | ☐ |
| 295 | Injuring Place of Worship | 297 | 298 | ☐ |
| 320 | Grievous Hurt | 114(1) | 116 | ☐ |
| 351 | Assault | 131 | 130 | ☐ |
| 365 | Kidnapping for Wrongful Confinement | 139 | 140(3) | ☐ |
| 366 | Kidnapping Woman to Compel Marriage | 140 | 87 | ☐ |
| 448 | House Trespass | 331 | 329(4) | ☐ |
| 468 | Forgery for Purpose of Cheating | 339 | 336(3) | ☐ |
| 489A | Counterfeiting Currency Notes | 344 | 178 | ☐ |

## Also for review

- **69** teammate mappings `agree_with_ncrb` — corroborated, confirm text then approve.
- **7** `no_ipc_ancestor` (new BNS provisions) — approve as BNS-only entries.
- **4** `ipc_not_in_ncrb_snapshot` — no snapshot row to compare; verify directly.

Approved rows go into `config/ipc_bns_mappings.json` with `change_notes`,
`reviewed_by`, `reviewed_at`. Only then does the converter serve them.
