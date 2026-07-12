# Offline text intake

The text-intake component prepares English, Hindi, or Hinglish input for the existing
confirmation-gated workflow. It is deterministic, makes no network or model calls,
and does not write the narrative to disk.

```powershell
python scripts/process_text_intake.py `
  --text "Mera rent deposit nahi mila" `
  --domain tenancy_property `
  --party "Tenant" `
  --document "Rent agreement" `
  --missing-fact "Incident date"
```

The JSON result contains:

- the minimally normalized text;
- a script-based language assessment;
- explicitly supplied structured fields;
- conservative urgency phrase signals that require user confirmation;
- a plain restatement; and
- `requires_confirmation: true` and `confirmed: false`.

## Safety boundary

This component does not infer parties, dates, jurisdiction, domain, or legal rules
from the narrative. Structured values are supplied explicitly until the local Gemma
extractor is implemented. Converting the result to `ConfirmedFacts` always produces
an unconfirmed object, so `LegalWorkflow` continues to block retrieval.

Line endings and surrounding whitespace are normalized. Internal whitespace and the
contents of names, quotations, dates, money values, and section references are left
unchanged. Romanized Hindi detection uses a small marker vocabulary and requires at
least two markers to reduce false positives; it is a routing hint, not a claim about
the user's preferred language.

Dangerous bidirectional display controls, lone Unicode surrogates, and unsupported
control characters are rejected before the confirmation display. Urgency matching
uses whole phrases, ignores quoted, directly negated, and explicitly historical
matches, and still labels every match as requiring user confirmation.
