# Nyaya Navigator — frontend

Local-only React interface for the offline Indian legal-navigation prototype.

Vite + React + TypeScript, plain CSS. No Tailwind CDN, no external fonts, no CDN
scripts, no analytics, no telemetry, no remote images. It is built to run with
Wi-Fi disabled.

## Run it

From this directory (`frontend/`):

```powershell
npm install
npm run dev
```

Then open <http://127.0.0.1:5173/>.

If `npm install` prints an `allow-scripts` warning about `esbuild` (npm 11+),
approve it once — Vite's bundler needs its platform binary:

```powershell
npm approve-scripts esbuild
```

### Backend

The UI expects the local FastAPI server on `http://127.0.0.1:8000`. The Vite dev
server proxies `/api` to it (see `vite.config.ts`), so the browser only ever
talks to its own origin.

Start the backend first. Without it, the UI still loads and shows a red
"Local server: unreachable" badge with a retry button — it never shows a blank
screen.

### Other scripts

```powershell
npm run build      # type-check (tsc -b) and produce dist/
npm run preview    # serve the production build on 127.0.0.1:5173
```

## The flow

This is a legal-safety flow, not a chat app.

1. **Landing** — privacy, offline operation, and limitations. Live status from
   `GET /api/health` (backend, local model, corpus chunk count, corpus SHA-256).
2. **Intake** — textarea for English / Hindi / Hinglish, plus optional PNG/JPEG
   upload. The image goes to `POST /api/ocr`; the recognised text is dropped into
   the textarea **for the user to correct**, with the confidence score shown.
3. **Confirmation gate** — the load-bearing screen. `POST /api/intake` returns a
   restatement and extracted facts; every field is editable (incident date,
   jurisdiction, location, domain dropdown, parties, material facts, documents).
   Detected urgency signals appear as **unticked** checkboxes: they are proposals,
   never auto-applied. Nothing proceeds until the user ticks the acknowledgement
   and clicks "Yes, this is correct".
4. **Routing** — `POST /api/route` with the confirmed facts and confirmed
   urgencies:
   - `immediate_human_help` → an urgent safety panel renders **above everything
     else** with emergency numbers and auto-searched legal-aid contacts. No
     ordinary legal content is shown.
   - `hard_abstain` → the refusal and its recorded reason.
   - `needs_information` → only the `missing_questions`, each with its "why this
     matters" reason. Answers are merged back into the facts and routing re-runs.
   - `standard` → proceed to evidence.
5. **Evidence** — `POST /api/evidence`. `warnings[]` render at the **top**, in a
   permanently-expanded block (never a toast, never collapsed) — they carry
   things like "commencement date not proven". Each citation is an expandable
   card: act, section, heading, verbatim excerpt, effective from/to, status,
   page, retrieved-at, SHA-256, a copy-citation button, and the official URL
   opening in a new tab.
6. **Side panel** — tabs for the Legal Aid Finder (`POST /api/legal-aid`), the
   Evidence Checklist (`GET /api/checklists`, `GET /api/checklists/{id}`, with
   JSON export that contains the checklist only, never the case narrative), and
   a plain-language summary of what stays on the device.

A "legal information, not legal advice" bar is pinned under the header on every
screen and cannot be dismissed. "Clear session" in the header wipes the
description, facts, routing result, and evidence from memory.

## Privacy and offline properties

- Every request is same-origin `/api/*`; there are no absolute remote URLs in the
  source.
- `index.html` sets a CSP with `default-src 'self'` and `connect-src 'self'`, so
  a remote request would be blocked by the browser even if one were introduced.
- `fetch` uses `credentials: "omit"`, `cache: "no-store"`, and
  `referrerPolicy: "no-referrer"`.
- Fonts are the system stack only (`system-ui`, with `Nirmala UI` /
  `Noto Sans Devanagari` for Devanagari). Nothing is fetched.
- No state is written to `localStorage`, `sessionStorage`, or cookies. Reloading
  or closing the tab discards everything.
- Uploads are validated client-side (PNG/JPEG, ≤ 10 MB) before being sent to the
  local OCR endpoint; the backend remains the authority.
- The only `console` output is a render-crash message from the error boundary.

## Accessibility

- Skip link, landmark regions, and focus moved to the main region on each step
  change.
- Tabs implement the roving-tabindex pattern with arrow-key navigation.
- Expandable citations are real buttons with `aria-expanded` / `aria-controls`.
- Errors use `role="alert"`; progress uses `role="status"` with `aria-live`.
- `prefers-reduced-motion` disables the progress animation.
- Two-column layout at ≥ 1100 px (fits 1366×768) and a single column below.

## Verified contract

The types in `src/api/types.ts` were checked against the running backend's
`/openapi.json`, not just the written spec. Five differences were found and
handled — they are worth knowing about:

1. **`/api/route` and `/api/evidence` take `ConfirmedFacts`, not the `IntakeFacts`
   that `/api/intake` returns.** `ConfirmedFacts` has **no `documents` key** and
   both request models set `additionalProperties: false`, so echoing the intake
   facts back verbatim is a 422 (`Extra inputs are not permitted`,
   `field: body.facts.documents`). `ConfirmedFacts` also adds `input_language`,
   `confirmed`, and `confirmed_at`. `toConfirmedFacts()` in `src/api/types.ts`
   does the conversion and stamps `confirmed: true` with the moment the user
   clicked "Yes, this is correct".
2. **`domain` is a closed enum**: `criminal | labour | consumer |
   tenancy_property | constitutional | other`. Anything else is a 422 on
   `body.facts.domain`. The dropdown offers exactly these, and `clampDomain()`
   guards the value on every path.
3. **`missing_questions[].fact_key` for the domain question is `legal_domain`**,
   not `domain`, and its answer must still be an enum value. That question is
   therefore rendered as a `<select>`, and `incident_date` as a date input — a
   free-text answer would loop forever or 422.
4. **`role_signals` and `document_warnings` are objects, not strings**
   (`RoleSignal`, `DocumentSafetyWarning`). Rendering them directly would throw.
5. **`mean_confidence_percent` (OCR) and `section` / `heading` / `effective_from`
   (evidence) are nullable.** All are guarded.

`confirmed_urgencies` must be `UrgencyCategory` values (`arrest_or_detention`,
`violence`, `immediate_eviction`, `expiring_deadline`, `child_safety`,
`self_harm`, `medical_emergency`); the UI only ever sends categories the backend
itself reported in `urgency_signals`.

All four routing priorities were exercised against the live backend:
`standard`, `needs_information`, `immediate_human_help` (via a confirmed
`violence` urgency), and `hard_abstain`.

## Notes for the backend author

- The client tolerates a bare list *or* a `{templates: [...]}` / `{checklists:
  [...]}` envelope from `GET /api/checklists`.
- Error bodies are read as `{code, message, field?}`; FastAPI's `{detail: "..."}`
  is also understood. A 5xx with no JSON body is reported as "backend
  unreachable", because that is what the dev proxy returns when the API process
  is down.
- `POST /api/evidence` is called with `approved_profiles: []` and `limit: 8`.
- `POST /api/ocr` is sent as multipart with the field name `file`.
