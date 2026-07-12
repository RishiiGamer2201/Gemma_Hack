# Offline legal-aid finder

The finder reads only the generated local directory. It performs no network requests,
does not persist a user's location query, and never guesses a district using fuzzy
matching.

```powershell
python scripts/build_legal_aid_directory.py
python scripts/find_legal_aid.py --district "Rouse Avenue" --state Delhi
python scripts/find_legal_aid.py --district Mumbai --state Maharashtra
```

Results include one of four explicit statuses:

- `matched`: an exact reviewed Delhi district or alias matched;
- `unmatched_delhi`: Delhi was explicit but no reviewed district matched;
- `outside_delhi`: another state was explicit, so only national fallbacks are shown;
- `unknown_location`: no state was supplied and no reviewed Delhi alias matched.

Every result includes source hashes and the oldest/newest verification dates. The
directory must contain the reviewed NALSA 15100 and Tele-Law 14454 national fallbacks;
the loader refuses to operate if either record is missing or rewritten.

## Evidence checklists

The three demo templates are general preparation guidance, not legal conclusions.
They contain no statutory deadlines and mark items likely to contain sensitive data.

```powershell
python scripts/get_evidence_checklist.py --template unpaid_wages
python scripts/get_evidence_checklist.py --template fir_or_legal_notice
python scripts/get_evidence_checklist.py --template security_deposit
```

The commands emit JSON and do not accept or store the user's case narrative.
