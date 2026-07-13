# Delhi Rent Control Act applicability gate

Reviewed: 13 July 2026.

Authority: the [official India Code PDF](https://www.indiacode.nic.in/bitstream/123456789/19223/1/a1958-59.pdf),
recorded as `delhi_rent_control_act_1958_en` in `config/official_sources.json`.

The Act is not safe to retrieve as applicable merely because a user says “Delhi
tenant.” The deterministic gate in `src/applicability/delhi_rent.py` requires
confirmation of the material facts expressly identified by sections 1(2) and 3:

- whether the premises are within the statutory or separately notified territorial area;
- whether the premises belong to Government;
- whether a Government-owned premises is lawfully let by a private person under the
  section 3(a) proviso;
- whether the tenancy or similar relationship was created by Government grant;
- whether monthly rent exceeds ₹3,500; and
- whether qualifying premises were completed on or after 1 December 1988 and the
  incident falls within ten years after completion.

Temporal routing follows the source text and amendment footnotes. Incidents before
9 February 1959 cannot use the Act. For incidents from commencement through
30 November 1988, the evaluator does not retroactively apply clauses 3(c) and 3(d),
which commenced on 1 December 1988. From that date onward, the rent threshold and
ten-year construction exclusion are evaluated.

An unknown fact produces `needs_facts`. A confirmed statutory exclusion produces
`not_applicable`. Only `applicable` returns the profile ID that permits profiled DRC
chunks through `SearchFilters`. This is fail-closed: ordinary retrieval excludes the
DRC source unless the applicability profile was explicitly approved.

The evaluator does not infer notified territorial coverage from an address, decide
ownership disputes, or interpret later judgments. Those questions require verified
notification material or human legal review. The source PDF and every processed chunk
remain subject to the corpus human-review gate.
