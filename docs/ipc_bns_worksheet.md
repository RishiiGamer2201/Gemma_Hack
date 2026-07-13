# IPC to BNS mapping worksheet

50 candidate pairs drawn from the verified NCRB Sankalan snapshot (508 pairs available of 534 rows).

**This is a legal judgement, not a lookup.** When the IPC became the BNS, provisions were split, merged, reworded, and dropped. A matching number is not a matching offence. Nothing here is approved by running this script: every record ships as `pending_human_review`, and the app serves only mappings a reviewer has marked `reviewed`.

For each row, decide the relationship and record it:

- `exact` — one IPC provision, one BNS provision, same offence
- `partial` — overlaps but the scope changed
- `split` — one IPC provision became several BNS provisions
- `merged` — several IPC provisions became one
- `omitted` — dropped from the BNS
- `no_direct_equivalent`

Then edit `config/ipc_bns_mappings.json`, fill `change_notes` and `reviewed_by`, and set `review_status` to `reviewed`.

---

## 1. IPC 397 → BNS 311

- **Sankalan hint:** `corresponding_provision`
- **Sankalan BNS text:** 311. Robbery, or dacoity, with attempt to cause death or grievous hurt.
- **Sankalan IPC text:** 397. Robbery, or dacoity, with attempt to cause death or grievous hurt.
- **Source:** https://cytrain.ncrb.gov.in/staticpage/web_pages/SectionTableBNS.html (retrieved 2026-07-12T15:44:28.747188+00:00)

BNS text we actually hold for that section:

```text
311. Robbery, or dacoity, with attempt to cause death or grievous hurt.—If, at the time of
committing robbery or dacoity, the offender uses any deadly weapon, or causes grievous hurt to any
person, or attempts to cause death or grievous hurt to any person, the imprisonment with which such
offender shall be punished shall not be less than seven years.
```

Reviewer: relationship = ____________  [ ] approved  [ ] rejected

Notes on what changed: 

---

## 2. IPC 455 → BNS 331(5)

- **Sankalan hint:** `corresponding_provision`
- **Sankalan BNS text:** 331 (5)
- **Sankalan IPC text:** 455. Lurking house-trespass or house-breaking after preparation for hurt, assault or wrongful restraint.
- **Source:** https://cytrain.ncrb.gov.in/staticpage/web_pages/SectionTableBNS.html (retrieved 2026-07-12T15:44:28.747188+00:00)

BNS text we actually hold for that section:

```text
331. Punishment for house-trespass or house-breaking.—(1) Whoever commits lurking house-
trespass or house-breaking, shall be punished with imprisonment of either description for a term which
may extend to two years, and shall also be liable to fine.
(2) Whoever commits lurking house-trespass or house-breaking after sunset and before sunrise, shall
be punished with imprisonment of either description for a term which may extend to three years, and
shall also be liable to fine.
(3) Whoever commits lurking house-trespass or house-breaking, in order to the committing of any
offence punishable with imprisonment, shall be punished with imprisonment of either description for a
term which may extend…
```

Reviewer: relationship = ____________  [ ] approved  [ ] rejected

Notes on what changed: 

---

## 3. IPC 458 → BNS 331(6)

- **Sankalan hint:** `corresponding_provision`
- **Sankalan BNS text:** 331 (6)
- **Sankalan IPC text:** 458. Lurking house-trespass or house-breaking by night after preparation for hurt, assault, or wrongful restraint.
- **Source:** https://cytrain.ncrb.gov.in/staticpage/web_pages/SectionTableBNS.html (retrieved 2026-07-12T15:44:28.747188+00:00)

BNS text we actually hold for that section:

```text
331. Punishment for house-trespass or house-breaking.—(1) Whoever commits lurking house-
trespass or house-breaking, shall be punished with imprisonment of either description for a term which
may extend to two years, and shall also be liable to fine.
(2) Whoever commits lurking house-trespass or house-breaking after sunset and before sunrise, shall
be punished with imprisonment of either description for a term which may extend to three years, and
shall also be liable to fine.
(3) Whoever commits lurking house-trespass or house-breaking, in order to the committing of any
offence punishable with imprisonment, shall be punished with imprisonment of either description for a
term which may extend…
```

Reviewer: relationship = ____________  [ ] approved  [ ] rejected

Notes on what changed: 

---

## 4. IPC 452 → BNS 333

- **Sankalan hint:** `corresponding_provision`
- **Sankalan BNS text:** 333. House-trespass after preparation for hurt, assault or wrongful restraint.
- **Sankalan IPC text:** 452. House-trespass after preparation for hurt, assault or wrongful restraint.
- **Source:** https://cytrain.ncrb.gov.in/staticpage/web_pages/SectionTableBNS.html (retrieved 2026-07-12T15:44:28.747188+00:00)

BNS text we actually hold for that section:

```text
333. House-trespass after preparation for hurt, assault or wrongful restraint.—Whoever
commits house-trespass, having made preparation for causing hurt to any person or for assaulting any
person, or for wrongfully restraining any person, or for putting any person in fear of hurt, or of assault, or
of wrongful restraint, shall be punished with imprisonment of either description for a term which may
extend to seven years, and shall also be liable to fine.
```

Reviewer: relationship = ____________  [ ] approved  [ ] rejected

Notes on what changed: 

---

## 5. IPC 356 → BNS 134

- **Sankalan hint:** `corresponding_provision`
- **Sankalan BNS text:** 134. Assault or criminal force in attempt to commit theft of property carried by a person.
- **Sankalan IPC text:** 356. Assault or criminal force in attempt to commit theft of property carried by a person.
- **Source:** https://cytrain.ncrb.gov.in/staticpage/web_pages/SectionTableBNS.html (retrieved 2026-07-12T15:44:28.747188+00:00)

BNS text we actually hold for that section:

```text
134. Assault or criminal force in attempt to commit theft of property carried by a person.—
Whoever assaults or uses criminal force to any person, in attempting to commit theft on any property
which that person is then wearing or carrying, shall be punished with imprisonment of either description
for a term which may extend to two years, or with fine, or with both.
```

Reviewer: relationship = ____________  [ ] approved  [ ] rejected

Notes on what changed: 

---

## 6. IPC 387 → BNS 308(4)

- **Sankalan hint:** `corresponding_provision`
- **Sankalan BNS text:** 308 (4)
- **Sankalan IPC text:** 387. Putting person in fear of death or of grievous hurt, in order to commit extortion.
- **Source:** https://cytrain.ncrb.gov.in/staticpage/web_pages/SectionTableBNS.html (retrieved 2026-07-12T15:44:28.747188+00:00)

BNS text we actually hold for that section:

```text
308. Extortion.—(1) Whoever intentionally puts any person in fear of any injury to that person, or to
any other, and thereby dishonestly induces the person so put in fear to deliver to any person any property,
or valuable security or anything signed or sealed which may be converted into a valuable security,
commits extortion.
Illustrations.
(a) A threatens to publish a defamatory libel concerning Z unless Z gives him money. He thus
induces Z to give him money. A has committed extortion.
(b) A threatens Z that he will keep Z’s child in wrongful confinement, unless Z will sign and deliver
to A a promissory note binding Z to pay certain monies to A. Z signs and delivers the note. A has
committe…
```

Reviewer: relationship = ____________  [ ] approved  [ ] rejected

Notes on what changed: 

---

## 7. IPC 386 → BNS 308(5)

- **Sankalan hint:** `corresponding_provision`
- **Sankalan BNS text:** 308 (5)
- **Sankalan IPC text:** 386. Extortion by putting a person in fear of death or grievous hurt.
- **Source:** https://cytrain.ncrb.gov.in/staticpage/web_pages/SectionTableBNS.html (retrieved 2026-07-12T15:44:28.747188+00:00)

BNS text we actually hold for that section:

```text
308. Extortion.—(1) Whoever intentionally puts any person in fear of any injury to that person, or to
any other, and thereby dishonestly induces the person so put in fear to deliver to any person any property,
or valuable security or anything signed or sealed which may be converted into a valuable security,
commits extortion.
Illustrations.
(a) A threatens to publish a defamatory libel concerning Z unless Z gives him money. He thus
induces Z to give him money. A has committed extortion.
(b) A threatens Z that he will keep Z’s child in wrongful confinement, unless Z will sign and deliver
to A a promissory note binding Z to pay certain monies to A. Z signs and delivers the note. A has
committe…
```

Reviewer: relationship = ____________  [ ] approved  [ ] rejected

Notes on what changed: 

---

## 8. IPC 459 → BNS 331(7)

- **Sankalan hint:** `corresponding_provision`
- **Sankalan BNS text:** 331 (7)
- **Sankalan IPC text:** 459. Grievous hurt caused whilst committing lurking house-trespass or house-breaking.
- **Source:** https://cytrain.ncrb.gov.in/staticpage/web_pages/SectionTableBNS.html (retrieved 2026-07-12T15:44:28.747188+00:00)

BNS text we actually hold for that section:

```text
331. Punishment for house-trespass or house-breaking.—(1) Whoever commits lurking house-
trespass or house-breaking, shall be punished with imprisonment of either description for a term which
may extend to two years, and shall also be liable to fine.
(2) Whoever commits lurking house-trespass or house-breaking after sunset and before sunrise, shall
be punished with imprisonment of either description for a term which may extend to three years, and
shall also be liable to fine.
(3) Whoever commits lurking house-trespass or house-breaking, in order to the committing of any
offence punishable with imprisonment, shall be punished with imprisonment of either description for a
term which may extend…
```

Reviewer: relationship = ____________  [ ] approved  [ ] rejected

Notes on what changed: 

---

## 9. IPC 460 → BNS 331(8)

- **Sankalan hint:** `corresponding_provision`
- **Sankalan BNS text:** 331 (8)
- **Sankalan IPC text:** 460. All persons jointly concerned in lurking house-trespass or house-breaking by night punishable where death or grievous hurt caused by one of them.
- **Source:** https://cytrain.ncrb.gov.in/staticpage/web_pages/SectionTableBNS.html (retrieved 2026-07-12T15:44:28.747188+00:00)

BNS text we actually hold for that section:

```text
331. Punishment for house-trespass or house-breaking.—(1) Whoever commits lurking house-
trespass or house-breaking, shall be punished with imprisonment of either description for a term which
may extend to two years, and shall also be liable to fine.
(2) Whoever commits lurking house-trespass or house-breaking after sunset and before sunrise, shall
be punished with imprisonment of either description for a term which may extend to three years, and
shall also be liable to fine.
(3) Whoever commits lurking house-trespass or house-breaking, in order to the committing of any
offence punishable with imprisonment, shall be punished with imprisonment of either description for a
term which may extend…
```

Reviewer: relationship = ____________  [ ] approved  [ ] rejected

Notes on what changed: 

---

## 10. IPC 320 → BNS 116

- **Sankalan hint:** `corresponding_provision`
- **Sankalan BNS text:** 116. Grievous hurt.
- **Sankalan IPC text:** 320. Grievous hurt.
- **Source:** https://cytrain.ncrb.gov.in/staticpage/web_pages/SectionTableBNS.html (retrieved 2026-07-12T15:44:28.747188+00:00)

BNS text we actually hold for that section:

```text
116. Grievous hurt.—The following kinds of hurt only are designated as “grievous”, namely:—
(a) Emasculation;
(b) Permanent privation of the sight of either eye;
(c) Permanent privation of the hearing of either ear;
(d) Privation of any member or joint;
(e) Destruction or permanent impairing of the powers of any member or joint;
(f) Permanent disfiguration of the head or face;
(g) Fracture or dislocation of a bone or tooth;
(h) Any hurt which endangers life or which causes the sufferer to be during the space of fifteen
days in severe bodily pain, or unable to follow his ordinary pursuits.
```

Reviewer: relationship = ____________  [ ] approved  [ ] rejected

Notes on what changed: 

---

## 11. IPC 322 → BNS 117

- **Sankalan hint:** `corresponding_provision`
- **Sankalan BNS text:** 117. Voluntarily causing grievous hurt. 117(1)
- **Sankalan IPC text:** 322. Voluntarily causing grievous hurt.
- **Source:** https://cytrain.ncrb.gov.in/staticpage/web_pages/SectionTableBNS.html (retrieved 2026-07-12T15:44:28.747188+00:00)

BNS text we actually hold for that section:

```text
117. Voluntarily causing grievous hurt.—(1) Whoever voluntarily causes hurt, if the hurt which he
intends to cause or knows himself to be likely to cause is grievous hurt, and if the hurt which he causes is
grievous hurt, is said “voluntarily to cause grievous hurt”.
Explanation.—A person is not said voluntarily to cause grievous hurt except when he both causes
grievous hurt and intends or knows himself to be likely to cause grievous hurt. But he is said voluntarily
to cause grievous hurt, if intending or knowing himself to be likely to cause grievous hurt of one kind, he
actually causes grievous hurt of another kind.
Illustration.
A, intending of knowing himself to be likely permanently to …
```

Reviewer: relationship = ____________  [ ] approved  [ ] rejected

Notes on what changed: 

---

## 12. IPC 325 → BNS 117(2)

- **Sankalan hint:** `corresponding_provision`
- **Sankalan BNS text:** 117(2)
- **Sankalan IPC text:** 325. Punishment for voluntarily causing grievous hurt.
- **Source:** https://cytrain.ncrb.gov.in/staticpage/web_pages/SectionTableBNS.html (retrieved 2026-07-12T15:44:28.747188+00:00)

BNS text we actually hold for that section:

```text
117. Voluntarily causing grievous hurt.—(1) Whoever voluntarily causes hurt, if the hurt which he
intends to cause or knows himself to be likely to cause is grievous hurt, and if the hurt which he causes is
grievous hurt, is said “voluntarily to cause grievous hurt”.
Explanation.—A person is not said voluntarily to cause grievous hurt except when he both causes
grievous hurt and intends or knows himself to be likely to cause grievous hurt. But he is said voluntarily
to cause grievous hurt, if intending or knowing himself to be likely to cause grievous hurt of one kind, he
actually causes grievous hurt of another kind.
Illustration.
A, intending of knowing himself to be likely permanently to …
```

Reviewer: relationship = ____________  [ ] approved  [ ] rejected

Notes on what changed: 

---

## 13. IPC 324 → BNS 118

- **Sankalan hint:** `corresponding_provision`
- **Sankalan BNS text:** 118. Voluntarily causing hurt or grievous hurt by dangerous weapons or means. 118(1)
- **Sankalan IPC text:** 324. Voluntarily causing hurt by dangerous weapons or means.
- **Source:** https://cytrain.ncrb.gov.in/staticpage/web_pages/SectionTableBNS.html (retrieved 2026-07-12T15:44:28.747188+00:00)

BNS text we actually hold for that section:

```text
118. Voluntarily causing hurt or grievous hurt by dangerous weapons or means.—(1) Whoever,
except in the case provided for by sub-section (1) of section 122, voluntarily causes hurt by means of any
instrument for shooting, stabbing or cutting, or any instrument which, used as a weapon of offence, is
52

likely to cause death, or by means of fire or any heated substance, or by means of any poison or any
corrosive substance, or by means of any explosive substance, or by means of any substance which it is
deleterious to the human body to inhale, to swallow, or to receive into the blood, or by means of any
animal, shall be punished with imprisonment of either description for a term which may ext…
```

Reviewer: relationship = ____________  [ ] approved  [ ] rejected

Notes on what changed: 

---

## 14. IPC 326 → BNS 118(2)

- **Sankalan hint:** `corresponding_provision`
- **Sankalan BNS text:** 118(2)
- **Sankalan IPC text:** 326. Voluntarily causing grievous hurt by dangerous weapons or means.
- **Source:** https://cytrain.ncrb.gov.in/staticpage/web_pages/SectionTableBNS.html (retrieved 2026-07-12T15:44:28.747188+00:00)

BNS text we actually hold for that section:

```text
118. Voluntarily causing hurt or grievous hurt by dangerous weapons or means.—(1) Whoever,
except in the case provided for by sub-section (1) of section 122, voluntarily causes hurt by means of any
instrument for shooting, stabbing or cutting, or any instrument which, used as a weapon of offence, is
52

likely to cause death, or by means of fire or any heated substance, or by means of any poison or any
corrosive substance, or by means of any explosive substance, or by means of any substance which it is
deleterious to the human body to inhale, to swallow, or to receive into the blood, or by means of any
animal, shall be punished with imprisonment of either description for a term which may ext…
```

Reviewer: relationship = ____________  [ ] approved  [ ] rejected

Notes on what changed: 

---

## 15. IPC 327 → BNS 119

- **Sankalan hint:** `corresponding_provision`
- **Sankalan BNS text:** 119. Voluntarily causing hurt or grievous hurt to extort property, or to constrain to an illegal act. 119(1)
- **Sankalan IPC text:** 327. Voluntarily causing hurt to extort property, or to constrain to an illegal to an act.
- **Source:** https://cytrain.ncrb.gov.in/staticpage/web_pages/SectionTableBNS.html (retrieved 2026-07-12T15:44:28.747188+00:00)

BNS text we actually hold for that section:

```text
119. Voluntarily causing hurt or grievous hurt to extort property, or to constrain to an illegal
act.—(1) Whoever voluntarily causes hurt for the purpose of extorting from the sufferer, or from any
person interested in the sufferer, any property or valuable security, or of constraining the sufferer or any
person interested in such sufferer to do anything which is illegal or which may facilitate the commission
of an offence, shall be punished with imprisonment of either description for a term which may extend to
ten years, and shall also be liable to fine.
(2) Whoever voluntarily causes grievous hurt for any purpose referred to in sub-section (1), shall be
punished with imprisonment for life,…
```

Reviewer: relationship = ____________  [ ] approved  [ ] rejected

Notes on what changed: 

---

## 16. IPC 329 → BNS 119(2)

- **Sankalan hint:** `corresponding_provision`
- **Sankalan BNS text:** 119(2)
- **Sankalan IPC text:** 329. Voluntarily causing grievous hurt to extort property, or to constrain to an illegal act.
- **Source:** https://cytrain.ncrb.gov.in/staticpage/web_pages/SectionTableBNS.html (retrieved 2026-07-12T15:44:28.747188+00:00)

BNS text we actually hold for that section:

```text
119. Voluntarily causing hurt or grievous hurt to extort property, or to constrain to an illegal
act.—(1) Whoever voluntarily causes hurt for the purpose of extorting from the sufferer, or from any
person interested in the sufferer, any property or valuable security, or of constraining the sufferer or any
person interested in such sufferer to do anything which is illegal or which may facilitate the commission
of an offence, shall be punished with imprisonment of either description for a term which may extend to
ten years, and shall also be liable to fine.
(2) Whoever voluntarily causes grievous hurt for any purpose referred to in sub-section (1), shall be
punished with imprisonment for life,…
```

Reviewer: relationship = ____________  [ ] approved  [ ] rejected

Notes on what changed: 

---

## 17. IPC 330 → BNS 120

- **Sankalan hint:** `corresponding_provision`
- **Sankalan BNS text:** 120. Voluntarily causing hurt or grievous hurt to extort confession, or to compel restoration of property. 120(1)
- **Sankalan IPC text:** 330. Voluntarily causing hurt to extort confession, or to compel restoration of property.
- **Source:** https://cytrain.ncrb.gov.in/staticpage/web_pages/SectionTableBNS.html (retrieved 2026-07-12T15:44:28.747188+00:00)

BNS text we actually hold for that section:

```text
120. Voluntarily causing hurt or grievous hurt to extort confession, or to compel restoration of
property.—(1) Whoever voluntarily causes hurt for the purpose of extorting from the sufferer or from
any person interested in the sufferer, any confession or any information which may lead to the detection
of an offence or misconduct, or for the purpose of constraining the sufferer or any person interested in the
sufferer to restore or to cause the restoration of any property or valuable security or to satisfy any claim
or demand, or to give information which may lead to the restoration of any property or valuable security,
shall be punished with imprisonment of either description for a term whic…
```

Reviewer: relationship = ____________  [ ] approved  [ ] rejected

Notes on what changed: 

---

## 18. IPC 331 → BNS 120(2)

- **Sankalan hint:** `corresponding_provision`
- **Sankalan BNS text:** 120(2)
- **Sankalan IPC text:** 331. Voluntarily causing grievous hurt to extort confession, or to compel restoration of property.
- **Source:** https://cytrain.ncrb.gov.in/staticpage/web_pages/SectionTableBNS.html (retrieved 2026-07-12T15:44:28.747188+00:00)

BNS text we actually hold for that section:

```text
120. Voluntarily causing hurt or grievous hurt to extort confession, or to compel restoration of
property.—(1) Whoever voluntarily causes hurt for the purpose of extorting from the sufferer or from
any person interested in the sufferer, any confession or any information which may lead to the detection
of an offence or misconduct, or for the purpose of constraining the sufferer or any person interested in the
sufferer to restore or to cause the restoration of any property or valuable security or to satisfy any claim
or demand, or to give information which may lead to the restoration of any property or valuable security,
shall be punished with imprisonment of either description for a term whic…
```

Reviewer: relationship = ____________  [ ] approved  [ ] rejected

Notes on what changed: 

---

## 19. IPC 332 → BNS 121

- **Sankalan hint:** `corresponding_provision`
- **Sankalan BNS text:** 121. Voluntarily causing hurt or grievous hurt to deter public servant from his duty. 121(1)
- **Sankalan IPC text:** 332. Voluntarily causing hurt to deter public servant from his duty.
- **Source:** https://cytrain.ncrb.gov.in/staticpage/web_pages/SectionTableBNS.html (retrieved 2026-07-12T15:44:28.747188+00:00)

BNS text we actually hold for that section:

```text
121. Voluntarily causing hurt or grievous hurt to deter public servant from his duty.—(1)
Whoever voluntarily causes hurt to any person being a public servant in the discharge of his duty as such
public servant, or with intent to prevent or deter that person or any other public servant from discharging
his duty as such public servant or in consequence of anything done or attempted to be done by that person
in the lawful discharge of his duty as such public servant, shall be punished with imprisonment of either
description for a term which may extend to five years, or with fine, or with both.
(2) Whoever voluntarily causes grievous hurt to any person being a public servant in the discharge of…
```

Reviewer: relationship = ____________  [ ] approved  [ ] rejected

Notes on what changed: 

---

## 20. IPC 333 → BNS 121(2)

- **Sankalan hint:** `corresponding_provision`
- **Sankalan BNS text:** 121(2)
- **Sankalan IPC text:** 333. Voluntarily causing grievous hurt to deter public servant from his duty.
- **Source:** https://cytrain.ncrb.gov.in/staticpage/web_pages/SectionTableBNS.html (retrieved 2026-07-12T15:44:28.747188+00:00)

BNS text we actually hold for that section:

```text
121. Voluntarily causing hurt or grievous hurt to deter public servant from his duty.—(1)
Whoever voluntarily causes hurt to any person being a public servant in the discharge of his duty as such
public servant, or with intent to prevent or deter that person or any other public servant from discharging
his duty as such public servant or in consequence of anything done or attempted to be done by that person
in the lawful discharge of his duty as such public servant, shall be punished with imprisonment of either
description for a term which may extend to five years, or with fine, or with both.
(2) Whoever voluntarily causes grievous hurt to any person being a public servant in the discharge of…
```

Reviewer: relationship = ____________  [ ] approved  [ ] rejected

Notes on what changed: 

---

## 21. IPC 334 → BNS 122

- **Sankalan hint:** `corresponding_provision`
- **Sankalan BNS text:** 122. Voluntarily causing hurt or grievous hurt on provocation. 122(1)
- **Sankalan IPC text:** 334. Voluntarily causing hurt on provocation.
- **Source:** https://cytrain.ncrb.gov.in/staticpage/web_pages/SectionTableBNS.html (retrieved 2026-07-12T15:44:28.747188+00:00)

BNS text we actually hold for that section:

```text
122. Voluntarily causing hurt or grievous hurt on provocation.—(1) Whoever voluntarily causes
hurt on grave and sudden provocation, if he neither intends nor knows himself to be likely to cause hurt
to any person other than the person who gave the provocation, shall be punished with imprisonment of
either description for a term which may extend to one month, or with fine which may extend to five
thousand rupees, or with both.
(2) Whoever voluntarily causes grievous hurt on grave and sudden provocation, if he neither intends
nor knows himself to be likely to cause grievous hurt to any person other than the person who gave the
provocation, shall be punished with imprisonment of either descript…
```

Reviewer: relationship = ____________  [ ] approved  [ ] rejected

Notes on what changed: 

---

## 22. IPC 335 → BNS 122(2)

- **Sankalan hint:** `corresponding_provision`
- **Sankalan BNS text:** 122(2)
- **Sankalan IPC text:** 335. Voluntarily causing grievous hurt on provocation.
- **Source:** https://cytrain.ncrb.gov.in/staticpage/web_pages/SectionTableBNS.html (retrieved 2026-07-12T15:44:28.747188+00:00)

BNS text we actually hold for that section:

```text
122. Voluntarily causing hurt or grievous hurt on provocation.—(1) Whoever voluntarily causes
hurt on grave and sudden provocation, if he neither intends nor knows himself to be likely to cause hurt
to any person other than the person who gave the provocation, shall be punished with imprisonment of
either description for a term which may extend to one month, or with fine which may extend to five
thousand rupees, or with both.
(2) Whoever voluntarily causes grievous hurt on grave and sudden provocation, if he neither intends
nor knows himself to be likely to cause grievous hurt to any person other than the person who gave the
provocation, shall be punished with imprisonment of either descript…
```

Reviewer: relationship = ____________  [ ] approved  [ ] rejected

Notes on what changed: 

---

## 23. IPC 326A → BNS 124

- **Sankalan hint:** `corresponding_provision`
- **Sankalan BNS text:** 124. Voluntarily causing grievous hurt by use of acid, etc. 124(1)
- **Sankalan IPC text:** 326A. Voluntarily causing grievous hurt by use of acid, etc.
- **Source:** https://cytrain.ncrb.gov.in/staticpage/web_pages/SectionTableBNS.html (retrieved 2026-07-12T15:44:28.747188+00:00)

BNS text we actually hold for that section:

```text
124. Voluntarily causing grievous hurt by use of acid, etc.—(1) Whoever causes permanent or
partial damage or deformity to, or burns or maims or disfigures or disables, any part or parts of the body
of a person or causes grievous hurt by throwing acid on or by administering acid to that person, or by
using any other means with the intention of causing or with the knowledge that he is likely to cause such
injury or hurt or causes a person to be in a permanent vegetative state shall be punished with
imprisonment of either description for a term which shall not be less than ten years but which may extend
to imprisonment for life, and with fine:
Provided that such fine shall be just and reasonab…
```

Reviewer: relationship = ____________  [ ] approved  [ ] rejected

Notes on what changed: 

---

## 24. IPC 338 → BNS 125(b)

- **Sankalan hint:** `corresponding_provision`
- **Sankalan BNS text:** 125(b)
- **Sankalan IPC text:** 338. Causing grievous hurt by act endangering life or personal safety of others.
- **Source:** https://cytrain.ncrb.gov.in/staticpage/web_pages/SectionTableBNS.html (retrieved 2026-07-12T15:44:28.747188+00:00)

BNS text we actually hold for that section:

```text
125. Act endangering life or personal safety of others.—Whoever does any act so rashly or
negligently as to endanger human life or the personal safety of others, shall be punished with
imprisonment of either description for a term which may extend to three months or with fine which may
extend to two thousand five hundred rupees, or with both, but—
(a) where hurt is caused, shall be punished with imprisonment of either description for a term
which may extend to six months, or with fine which may extend to five thousand rupees, or with
both;
(b) where grievous hurt is caused, shall be punished with imprisonment of either description for a
term which may extend to three years, or with fine whic…
```

Reviewer: relationship = ____________  [ ] approved  [ ] rejected

Notes on what changed: 

---

## 25. IPC 352 → BNS 131

- **Sankalan hint:** `corresponding_provision`
- **Sankalan BNS text:** 131. Punishment for assault or criminal force otherwise than on grave provocation.
- **Sankalan IPC text:** 352. Punishment for assault or criminal force otherwise than on grave provocation.
- **Source:** https://cytrain.ncrb.gov.in/staticpage/web_pages/SectionTableBNS.html (retrieved 2026-07-12T15:44:28.747188+00:00)

BNS text we actually hold for that section:

```text
131. Punishment for assault or criminal force otherwise than on grave provocation.—Whoever
assaults or uses criminal force to any person otherwise than on grave and sudden provocation given by
that person, shall be punished with imprisonment of either description for a term which may extend to
three months, or with fine which may extend to one thousand rupees, or with both.
Explanation 1.—Grave and sudden provocation will not mitigate the punishment for an offence under
this section,—
(a) if the provocation is sought or voluntarily provoked by the offender as an excuse for the
offence; or
(b) if the provocation is given by anything done in obedience to the law, or by a public servant, in
the…
```

Reviewer: relationship = ____________  [ ] approved  [ ] rejected

Notes on what changed: 

---

## 26. IPC 353 → BNS 132

- **Sankalan hint:** `corresponding_provision`
- **Sankalan BNS text:** 132. Assault or criminal force to deter public servant from discharge of his duty
- **Sankalan IPC text:** 353. Assault or criminal force to deter public servant from discharge of his duty
- **Source:** https://cytrain.ncrb.gov.in/staticpage/web_pages/SectionTableBNS.html (retrieved 2026-07-12T15:44:28.747188+00:00)

BNS text we actually hold for that section:

```text
132. Assault or criminal force to deter public servant from discharge of his duty.—Whoever
assaults or uses criminal force to any person being a public servant in the execution of his duty as such
public servant, or with intent to prevent or deter that person from discharging his duty as such public
servant, or in consequence of anything done or attempted to be done by such person in the lawful
discharge of his duty as such public servant, shall be punished with imprisonment of either description for
a term which may extend to two years, or with fine, or with both.
```

Reviewer: relationship = ____________  [ ] approved  [ ] rejected

Notes on what changed: 

---

## 27. IPC 355 → BNS 133

- **Sankalan hint:** `corresponding_provision`
- **Sankalan BNS text:** 133. Assault or criminal force with intent to dishonour person, otherwise than on grave provocation.
- **Sankalan IPC text:** 355. Assault or criminal force with intent to dishonour person, otherwise than on grave provocation.
- **Source:** https://cytrain.ncrb.gov.in/staticpage/web_pages/SectionTableBNS.html (retrieved 2026-07-12T15:44:28.747188+00:00)

BNS text we actually hold for that section:

```text
133. Assault or criminal force with intent to dishonour person, otherwise than on grave
provocation.—Whoever assaults or uses criminal force to any person, intending thereby to dishonour
that person, otherwise than on grave and sudden provocation given by that person, shall be punished with
imprisonment of either description for a term which may extend to two years, or with fine, or with both.
57
```

Reviewer: relationship = ____________  [ ] approved  [ ] rejected

Notes on what changed: 

---

## 28. IPC 357 → BNS 135

- **Sankalan hint:** `corresponding_provision`
- **Sankalan BNS text:** 135. Assault or criminal force in attempt to wrongfully to confine a person.
- **Sankalan IPC text:** 357. Assault or criminal force in attempt wrongfully to confine a person.
- **Source:** https://cytrain.ncrb.gov.in/staticpage/web_pages/SectionTableBNS.html (retrieved 2026-07-12T15:44:28.747188+00:00)

BNS text we actually hold for that section:

```text
135. Assault or criminal force in attempt to wrongfully confine a person.—Whoever assaults or
uses criminal force to any person, in attempting wrongfully to confine that person, shall be punished with
imprisonment of either description for a term which may extend to one year, or with fine which may
extend to five thousand rupees, or with both.
```

Reviewer: relationship = ____________  [ ] approved  [ ] rejected

Notes on what changed: 

---

## 29. IPC 358 → BNS 136

- **Sankalan hint:** `corresponding_provision`
- **Sankalan BNS text:** 136. Assault or criminal force on grave provocation.
- **Sankalan IPC text:** 358. Assault or criminal force on grave provocation.
- **Source:** https://cytrain.ncrb.gov.in/staticpage/web_pages/SectionTableBNS.html (retrieved 2026-07-12T15:44:28.747188+00:00)

BNS text we actually hold for that section:

```text
136. Assault or criminal force on grave provocation.—Whoever assaults or uses criminal force to
any person on grave and sudden provocation given by that person, shall be punished with simple
imprisonment for a term which may extend to one month, or with fine which may extend to one thousand
rupees, or with both.
Explanation.—This section is subject to the same Explanation as section 131.
Of kidnapping, abduction, slavery and forced labour
```

Reviewer: relationship = ____________  [ ] approved  [ ] rejected

Notes on what changed: 

---

## 30. IPC 367 → BNS 140(4)

- **Sankalan hint:** `corresponding_provision`
- **Sankalan BNS text:** 140(4)
- **Sankalan IPC text:** 367. Kidnapping or abducting in order to subject person to grievous hurt, slavery, etc.
- **Source:** https://cytrain.ncrb.gov.in/staticpage/web_pages/SectionTableBNS.html (retrieved 2026-07-12T15:44:28.747188+00:00)

BNS text we actually hold for that section:

```text
140. Kidnapping or abducting in order to murder or for ransom, etc.—(1) Whoever kidnaps or
abducts any person in order that such person may be murdered or may be so disposed of as to be put in
danger of being murdered, shall be punished with imprisonment for life or rigorous imprisonment for a
term which may extend to ten years, and shall also be liable to fine.
Illustrations.
(a) A kidnaps Z from India, intending or knowing it to be likely that Z may be sacrificed to an idol. A
has committed the offence defined in this section.
(b) A forcibly carries or entices B away from his home in order that B may be murdered. A has
committed the offence defined in this section.
(2) Whoever kidnaps or a…
```

Reviewer: relationship = ____________  [ ] approved  [ ] rejected

Notes on what changed: 

---

## 31. IPC 87 → BNS 25

- **Sankalan hint:** `corresponding_provision`
- **Sankalan BNS text:** 25. Act not intended and not known to be likely to cause death or grievous hurt, done by consent.
- **Sankalan IPC text:** 87. Act not intended and not known to be likely to cause death or grievous hurt, done by consent.
- **Source:** https://cytrain.ncrb.gov.in/staticpage/web_pages/SectionTableBNS.html (retrieved 2026-07-12T15:44:28.747188+00:00)

BNS text we actually hold for that section:

```text
25. Act not intended and not known to be likely to cause death or grievous hurt, done by
consent.—Nothing which is not intended to cause death, or grievous hurt, and which is not known by the
doer to be likely to cause death or grievous hurt, is an offence by reason of any harm which it may cause,
or be intended by the doer to cause, to any person, above eighteen years of age, who has given consent,
whether express or implied, to suffer that harm; or by reason of any harm which it may be known by the
doer to be likely to cause to any such person who has consented to take the risk of that harm.
Illustration.
A and Z agree to fence with each other for amusement. This agreement implies the cons…
```

Reviewer: relationship = ____________  [ ] approved  [ ] rejected

Notes on what changed: 

---

## 32. IPC 382 → BNS 307

- **Sankalan hint:** `corresponding_provision`
- **Sankalan BNS text:** 307. Theft after preparation made for causing death, hurt or restraint in order to committing of theft.
- **Sankalan IPC text:** 382. Theft after preparation made for causing death, hurt or restraint in order to the committing of the theft.
- **Source:** https://cytrain.ncrb.gov.in/staticpage/web_pages/SectionTableBNS.html (retrieved 2026-07-12T15:44:28.747188+00:00)

BNS text we actually hold for that section:

```text
307. Theft after preparation made for causing death, hurt or restraint in order to committing
of theft.—Whoever commits theft, having made preparation for causing death, or hurt, or restraint, or
fear of death, or of hurt, or of restraint, to any person, in order to the committing of such theft, or in order
to the effecting of his escape after the committing of such theft, or in order to the retaining of property
taken by such theft, shall be punished with rigorous imprisonment for a term which may extend to ten
years, and shall also be liable to fine.
Illustrations.
(a) A commits theft on property in Z’s possession; and while committing this theft, he has a loaded
pistol under his garment, …
```

Reviewer: relationship = ____________  [ ] approved  [ ] rejected

Notes on what changed: 

---

## 33. IPC 394 → BNS 309(6)

- **Sankalan hint:** `corresponding_provision`
- **Sankalan BNS text:** 309(6)
- **Sankalan IPC text:** 394. Voluntarily causing hurt in committing robbery.
- **Source:** https://cytrain.ncrb.gov.in/staticpage/web_pages/SectionTableBNS.html (retrieved 2026-07-12T15:44:28.747188+00:00)

BNS text we actually hold for that section:

```text
309. Robbery.—(1) In all robbery there is either theft or extortion.
(2) Theft is robbery if, in order to the committing of the theft, or in committing the theft, or in
carrying away or attempting to carry away property obtained by the theft, the offender, for that end
voluntarily causes or attempts to cause to any person death or hurt or wrongful restraint, or fear of instant
death or of instant hurt, or of instant wrongful restraint.
(3) Extortion is robbery if the offender, at the time of committing the extortion, is in the presence of
the person put in fear, and commits the extortion by putting that person in fear of instant death, of instant
hurt, or of instant wrongful restraint to tha…
```

Reviewer: relationship = ____________  [ ] approved  [ ] rejected

Notes on what changed: 

---

## 34. IPC 398 → BNS 312

- **Sankalan hint:** `corresponding_provision`
- **Sankalan BNS text:** 312. Attempt to commit robbery or dacoity when armed with deadly weapon.
- **Sankalan IPC text:** 398. Attempt to commit robbery or dacoity when armed with deadly weapon.
- **Source:** https://cytrain.ncrb.gov.in/staticpage/web_pages/SectionTableBNS.html (retrieved 2026-07-12T15:44:28.747188+00:00)

BNS text we actually hold for that section:

```text
312. Attempt to commit robbery or dacoity when armed with deadly weapon.—If, at the time of
attempting to commit robbery or dacoity, the offender is armed with any deadly weapon, the
imprisonment with which such offender shall be punished shall not be less than seven years.
```

Reviewer: relationship = ____________  [ ] approved  [ ] rejected

Notes on what changed: 

---

## 35. IPC 440 → BNS 324(6)

- **Sankalan hint:** `corresponding_provision`
- **Sankalan BNS text:** 324 (6)
- **Sankalan IPC text:** 440. Mischief committed after preparation made for causing death or hurt.
- **Source:** https://cytrain.ncrb.gov.in/staticpage/web_pages/SectionTableBNS.html (retrieved 2026-07-12T15:44:28.747188+00:00)

BNS text we actually hold for that section:

```text
324. Mischief.—(1) Whoever with intent to cause, or knowing that he is likely to cause, wrongful
loss or damage to the public or to any person, causes the destruction of any property, or any such change
in any property or in the situation thereof as destroys or diminishes its value or utility, or affects it
injuriously, commits mischief.
Explanation 1.—It is not essential to the offence of mischief that the offender should intend to cause
loss or damage to the owner of the property injured or destroyed. It is sufficient if he intends to cause, or
knows that he is likely to cause, wrongful loss or damage to any person by injuring any property, whether
it belongs to that person or not.
Explana…
```

Reviewer: relationship = ____________  [ ] approved  [ ] rejected

Notes on what changed: 

---

## 36. IPC 468 → BNS 336(3)

- **Sankalan hint:** `corresponding_provision`
- **Sankalan BNS text:** 336 (3)
- **Sankalan IPC text:** 468. Forgery for purpose of cheating.
- **Source:** https://cytrain.ncrb.gov.in/staticpage/web_pages/SectionTableBNS.html (retrieved 2026-07-12T15:44:28.747188+00:00)

BNS text we actually hold for that section:

```text
336. Forgery.—(1) Whoever makes any false document or false electronic record or part of a
document or electronic record, with intent to cause damage or injury, to the public or to any person, or to
support any claim or title, or to cause any person to part with property, or to enter into any express or
implied contract, or with intent to commit fraud or that fraud may be committed, commits forgery.
(2) Whoever commits forgery shall be punished with imprisonment of either description for a term
which may extend to two years, or with fine, or with both.
(3) Whoever commits forgery, intending that the document or electronic record forged shall be used
for the purpose of cheating, shall be puni…
```

Reviewer: relationship = ____________  [ ] approved  [ ] rejected

Notes on what changed: 

---

## 37. IPC 472, 467 → BNS 341

- **Sankalan hint:** `possible_merge`
- **Sankalan BNS text:** 341. Making or possessing counterfeit seal, etc., with intent to commit forgery punishable under section 338. 341 (1)
- **Sankalan IPC text:** 472. Making or possessing counterfeit seal, etc., with intent to commit forgery punishable under section 467.
- **Source:** https://cytrain.ncrb.gov.in/staticpage/web_pages/SectionTableBNS.html (retrieved 2026-07-12T15:44:28.747188+00:00)

BNS text we actually hold for that section:

```text
341. Making or possessing counterfeit seal, etc., with intent to commit forgery punishable under
section 338.—(1) Whoever makes or counterfeits any seal, plate or other instrument for making an
impression, intending that the same shall be used for the purpose of committing any forgery which would
be punishable under section 338 of this Sanhita, or, with such intent, has in his possession any such seal,
plate or other instrument, knowing the same to be counterfeit, shall be punished with imprisonment for
life, or with imprisonment of either description for a term which may extend to seven years, and shall
also be liable to fine.
(2) Whoever makes or counterfeits any seal, plate or other instr…
```

Reviewer: relationship = ____________  [ ] approved  [ ] rejected

Notes on what changed: 

---

## 38. IPC 473 → BNS 341(2)

- **Sankalan hint:** `corresponding_provision`
- **Sankalan BNS text:** 341 (2)
- **Sankalan IPC text:** 473. Making or possessing counterfeit seal, etc., with intent to commit forgery punishable otherwise.
- **Source:** https://cytrain.ncrb.gov.in/staticpage/web_pages/SectionTableBNS.html (retrieved 2026-07-12T15:44:28.747188+00:00)

BNS text we actually hold for that section:

```text
341. Making or possessing counterfeit seal, etc., with intent to commit forgery punishable under
section 338.—(1) Whoever makes or counterfeits any seal, plate or other instrument for making an
impression, intending that the same shall be used for the purpose of committing any forgery which would
be punishable under section 338 of this Sanhita, or, with such intent, has in his possession any such seal,
plate or other instrument, knowing the same to be counterfeit, shall be punished with imprisonment for
life, or with imprisonment of either description for a term which may extend to seven years, and shall
also be liable to fine.
(2) Whoever makes or counterfeits any seal, plate or other instr…
```

Reviewer: relationship = ____________  [ ] approved  [ ] rejected

Notes on what changed: 

---

## 39. IPC 354 → BNS 74

- **Sankalan hint:** `corresponding_provision`
- **Sankalan BNS text:** 74. Assault or use of criminal force to woman with intent to outrage her modesty.
- **Sankalan IPC text:** 354. Assault or criminal force to woman with intent to outrage her modesty.
- **Source:** https://cytrain.ncrb.gov.in/staticpage/web_pages/SectionTableBNS.html (retrieved 2026-07-12T15:44:28.747188+00:00)

BNS text we actually hold for that section:

```text
74. Assault or use of criminal force to woman with intent to outrage her modesty.—Whoever
assaults or uses criminal force to any woman, intending to outrage or knowing it to be likely that he will
thereby outrage her modesty, shall be punished with imprisonment of either description for a term which
shall not be less than one year but which may extend to five years, and shall also be liable to fine.
```

Reviewer: relationship = ____________  [ ] approved  [ ] rejected

Notes on what changed: 

---

## 40. IPC 354B → BNS 76

- **Sankalan hint:** `corresponding_provision`
- **Sankalan BNS text:** 76. Assault or use of criminal force to woman with intent to disrobe.
- **Sankalan IPC text:** 354B. Assault or use of criminal force to woman with intent to disrobe.
- **Source:** https://cytrain.ncrb.gov.in/staticpage/web_pages/SectionTableBNS.html (retrieved 2026-07-12T15:44:28.747188+00:00)

BNS text we actually hold for that section:

```text
76. Assault or use of criminal force to woman with intent to disrobe.—Whoever assaults or uses
criminal force to any woman or abets such act with the intention of disrobing or compelling her to be
naked, shall be punished with imprisonment of either description for a term which shall not be less than
three years but which may extend to seven years, and shall also be liable to fine.
```

Reviewer: relationship = ____________  [ ] approved  [ ] rejected

Notes on what changed: 

---

## 41. IPC 319 → BNS 114

- **Sankalan hint:** `corresponding_provision`
- **Sankalan BNS text:** 114. Hurt.
- **Sankalan IPC text:** 319. Hurt
- **Source:** https://cytrain.ncrb.gov.in/staticpage/web_pages/SectionTableBNS.html (retrieved 2026-07-12T15:44:28.747188+00:00)

BNS text we actually hold for that section:

```text
114. Hurt.—Whoever causes bodily pain, disease or infirmity to any person is said to cause hurt.
```

Reviewer: relationship = ____________  [ ] approved  [ ] rejected

Notes on what changed: 

---

## 42. IPC 321 → BNS 115

- **Sankalan hint:** `corresponding_provision`
- **Sankalan BNS text:** 115. Voluntarily causing hurt. 115(1)
- **Sankalan IPC text:** 321. Voluntarily causing hurt.
- **Source:** https://cytrain.ncrb.gov.in/staticpage/web_pages/SectionTableBNS.html (retrieved 2026-07-12T15:44:28.747188+00:00)

BNS text we actually hold for that section:

```text
115. Voluntarily causing hurt.—(1) Whoever does any act with the intention of thereby causing
hurt to any person, or with the knowledge that he is likely thereby to cause hurt to any person, and does
thereby cause hurt to any person, is said “voluntarily to cause hurt”.
(2) Whoever, except in the case provided for by sub-section (1) of section 122 voluntarily causes
hurt, shall be punished with imprisonment of either description for a term which may extend to one year,
or with fine which may extend to ten thousand rupees, or with both.
```

Reviewer: relationship = ____________  [ ] approved  [ ] rejected

Notes on what changed: 

---

## 43. IPC 323 → BNS 115(2)

- **Sankalan hint:** `corresponding_provision`
- **Sankalan BNS text:** 115(2)
- **Sankalan IPC text:** 323. Punishment for voluntarily causing hurt.
- **Source:** https://cytrain.ncrb.gov.in/staticpage/web_pages/SectionTableBNS.html (retrieved 2026-07-12T15:44:28.747188+00:00)

BNS text we actually hold for that section:

```text
115. Voluntarily causing hurt.—(1) Whoever does any act with the intention of thereby causing
hurt to any person, or with the knowledge that he is likely thereby to cause hurt to any person, and does
thereby cause hurt to any person, is said “voluntarily to cause hurt”.
(2) Whoever, except in the case provided for by sub-section (1) of section 122 voluntarily causes
hurt, shall be punished with imprisonment of either description for a term which may extend to one year,
or with fine which may extend to ten thousand rupees, or with both.
```

Reviewer: relationship = ____________  [ ] approved  [ ] rejected

Notes on what changed: 

---

## 44. IPC 328 → BNS 123

- **Sankalan hint:** `corresponding_provision`
- **Sankalan BNS text:** 123. Causing hurt by means of poison, etc., with intent to commit an offence.
- **Sankalan IPC text:** 328. Causing hurt by means of poison, etc., with intent to commit and offence.
- **Source:** https://cytrain.ncrb.gov.in/staticpage/web_pages/SectionTableBNS.html (retrieved 2026-07-12T15:44:28.747188+00:00)

BNS text we actually hold for that section:

```text
123. Causing hurt by means of poison, etc., with intent to commit an offence.—Whoever
administers to or causes to be taken by any person any poison or any stupefying, intoxicating or
unwholesome drug, or other thing with intent to cause hurt to such person, or with intent to commit or to
facilitate the commission of an offence or knowing it to be likely that he will thereby cause hurt, shall be
punished with imprisonment of either description for a term which may extend to ten years, and shall also
be liable to fine.
```

Reviewer: relationship = ____________  [ ] approved  [ ] rejected

Notes on what changed: 

---

## 45. IPC 337 → BNS 125(a)

- **Sankalan hint:** `corresponding_provision`
- **Sankalan BNS text:** 125(a)
- **Sankalan IPC text:** 337. Causing hurt by act endangering life or personal safety of others.
- **Source:** https://cytrain.ncrb.gov.in/staticpage/web_pages/SectionTableBNS.html (retrieved 2026-07-12T15:44:28.747188+00:00)

BNS text we actually hold for that section:

```text
125. Act endangering life or personal safety of others.—Whoever does any act so rashly or
negligently as to endanger human life or the personal safety of others, shall be punished with
imprisonment of either description for a term which may extend to three months or with fine which may
extend to two thousand five hundred rupees, or with both, but—
(a) where hurt is caused, shall be punished with imprisonment of either description for a term
which may extend to six months, or with fine which may extend to five thousand rupees, or with
both;
(b) where grievous hurt is caused, shall be punished with imprisonment of either description for a
term which may extend to three years, or with fine whic…
```

Reviewer: relationship = ____________  [ ] approved  [ ] rejected

Notes on what changed: 

---

## 46. IPC 339 → BNS 126

- **Sankalan hint:** `corresponding_provision`
- **Sankalan BNS text:** 126. Wrongful restraint. 126(1)
- **Sankalan IPC text:** 339. Wrongful restraint.
- **Source:** https://cytrain.ncrb.gov.in/staticpage/web_pages/SectionTableBNS.html (retrieved 2026-07-12T15:44:28.747188+00:00)

BNS text we actually hold for that section:

```text
126. Wrongful restraint.—(1) Whoever voluntarily obstructs any person so as to prevent that person
from proceeding in any direction in which that person has a right to proceed, is said wrongfully to restrain
that person.
Exception.—The obstruction of a private way over land or water which a person in good faith
believes himself to have a lawful right to obstruct, is not an offence within the meaning of this section.
Illustration.
A obstructs a path along which Z has a right to pass, A not believing in good faith that he has a right
to stop the path. Z is thereby prevented from passing. A wrongfully restrains Z.
(2) Whoever wrongfully restrains any person shall be punished with simple impriso…
```

Reviewer: relationship = ____________  [ ] approved  [ ] rejected

Notes on what changed: 

---

## 47. IPC 341 → BNS 126(2)

- **Sankalan hint:** `corresponding_provision`
- **Sankalan BNS text:** 126(2)
- **Sankalan IPC text:** 341. Punishment for wrongful restraint.
- **Source:** https://cytrain.ncrb.gov.in/staticpage/web_pages/SectionTableBNS.html (retrieved 2026-07-12T15:44:28.747188+00:00)

BNS text we actually hold for that section:

```text
126. Wrongful restraint.—(1) Whoever voluntarily obstructs any person so as to prevent that person
from proceeding in any direction in which that person has a right to proceed, is said wrongfully to restrain
that person.
Exception.—The obstruction of a private way over land or water which a person in good faith
believes himself to have a lawful right to obstruct, is not an offence within the meaning of this section.
Illustration.
A obstructs a path along which Z has a right to pass, A not believing in good faith that he has a right
to stop the path. Z is thereby prevented from passing. A wrongfully restrains Z.
(2) Whoever wrongfully restrains any person shall be punished with simple impriso…
```

Reviewer: relationship = ____________  [ ] approved  [ ] rejected

Notes on what changed: 

---

## 48. IPC 340 → BNS 127

- **Sankalan hint:** `corresponding_provision`
- **Sankalan BNS text:** 127. Wrongful confinement. 127(1)
- **Sankalan IPC text:** 340. Wrongful confinement.
- **Source:** https://cytrain.ncrb.gov.in/staticpage/web_pages/SectionTableBNS.html (retrieved 2026-07-12T15:44:28.747188+00:00)

BNS text we actually hold for that section:

```text
127. Wrongful confinement.—(1) Whoever wrongfully restrains any person in such a manner as to
prevent that person from proceedings beyond certain circumscribing limits, is said “wrongfully to
confine” that person.
Illustrations.
(a) A causes Z to go within a walled space, and locks Z in. Z is thus prevented from proceeding in
any direction beyond the circumscribing line of wall. A wrongfully confines Z.
(b) A places men with firearms at the outlets of a building, and tells Z that they will fire at Z if Z
attempts to leave the building. A wrongfully confines Z.
(2) Whoever wrongfully confines any person shall be punished with imprisonment of either
description for a term which may extend to o…
```

Reviewer: relationship = ____________  [ ] approved  [ ] rejected

Notes on what changed: 

---

## 49. IPC 342 → BNS 127(2)

- **Sankalan hint:** `corresponding_provision`
- **Sankalan BNS text:** 127(2)
- **Sankalan IPC text:** 342. Punishment for wrongful confinement.
- **Source:** https://cytrain.ncrb.gov.in/staticpage/web_pages/SectionTableBNS.html (retrieved 2026-07-12T15:44:28.747188+00:00)

BNS text we actually hold for that section:

```text
127. Wrongful confinement.—(1) Whoever wrongfully restrains any person in such a manner as to
prevent that person from proceedings beyond certain circumscribing limits, is said “wrongfully to
confine” that person.
Illustrations.
(a) A causes Z to go within a walled space, and locks Z in. Z is thus prevented from proceeding in
any direction beyond the circumscribing line of wall. A wrongfully confines Z.
(b) A places men with firearms at the outlets of a building, and tells Z that they will fire at Z if Z
attempts to leave the building. A wrongfully confines Z.
(2) Whoever wrongfully confines any person shall be punished with imprisonment of either
description for a term which may extend to o…
```

Reviewer: relationship = ____________  [ ] approved  [ ] rejected

Notes on what changed: 

---

## 50. IPC 343 → BNS 127(3)

- **Sankalan hint:** `corresponding_provision`
- **Sankalan BNS text:** 127(3)
- **Sankalan IPC text:** 343. Wrongful confinement for three or more days.
- **Source:** https://cytrain.ncrb.gov.in/staticpage/web_pages/SectionTableBNS.html (retrieved 2026-07-12T15:44:28.747188+00:00)

BNS text we actually hold for that section:

```text
127. Wrongful confinement.—(1) Whoever wrongfully restrains any person in such a manner as to
prevent that person from proceedings beyond certain circumscribing limits, is said “wrongfully to
confine” that person.
Illustrations.
(a) A causes Z to go within a walled space, and locks Z in. Z is thus prevented from proceeding in
any direction beyond the circumscribing line of wall. A wrongfully confines Z.
(b) A places men with firearms at the outlets of a building, and tells Z that they will fire at Z if Z
attempts to leave the building. A wrongfully confines Z.
(2) Whoever wrongfully confines any person shall be punished with imprisonment of either
description for a term which may extend to o…
```

Reviewer: relationship = ____________  [ ] approved  [ ] rejected

Notes on what changed: 

---
