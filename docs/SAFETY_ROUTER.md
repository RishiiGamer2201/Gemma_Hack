# Confirmed-facts safety router

The safety router runs after explicit fact confirmation and before legal retrieval.
It is deterministic, offline, and does not produce substantive legal conclusions.

| Priority | Effect on workflow |
|---|---|
| `immediate_human_help` | Stops ordinary retrieval and routes safety/human help first. |
| `hard_abstain` | Ends requests for outcome probabilities, guarantees, or sentence predictions. |
| `needs_information` | Keeps the workflow at `confirmed` and asks only material questions. |
| `standard` | Opens the existing retrieval-ready gate. |

Confirmed urgency always takes priority over abstention or missing-fact questions.
Every decision contains a SHA-256 fingerprint of the exact confirmed facts used to
create it. The workflow rejects a decision created for a different case.

## Local CLI

PowerShell users can supply explicit fields without shell-sensitive inline JSON:

```powershell
python scripts/route_safety.py `
  --summary "My landlord has my security deposit" `
  --incident-date 2026-06-01 `
  --jurisdiction Delhi `
  --domain tenancy_property `
  --party Tenant `
  --party Landlord `
  --confirmed-at 2026-07-13T02:30:00+05:30
```

`--facts-json` remains available to programmatic callers. Neither mode writes the
facts or document text to disk.

## Safety boundaries

- Urgency categories must have been confirmed by the caller; raw intake matches do
  not automatically activate them.
- Role matches are labelled `possible_role_pattern`, never “weak party,” and never
  include a confidence percentage.
- Protective prompts cover preservation and seeking human help, not uncited rights.
- Missing jurisdiction, dispute type, or a legally material incident date blocks
  retrieval.
- Uploaded text is untrusted data. Instruction-like patterns produce deduplicated
  warnings and are never allowed to alter the route.
- Route states are mutually exclusive and use strict booleans and bounded inputs.
