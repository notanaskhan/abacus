> **Solo edition (2026-10-20).** One builder, repo public, no approvals, reviews, rulesets, release-train windows or worktree cadence. `AMENDMENT-solo.md` and chapter 08 win over any other chapter on process. Ten governance-only F-01 tasks are removed from `backlog.csv`; its `lead` column is gone and a `status` column is added.

# Accrued · Engineering & build plan

Plan of record for building Accrued from the Claude Design handoff, the blueprint prompts and the abacus repo. Written 17 Oct 2026; Sprint 0 starts Mon 19 Oct 2026.

## Chapters

- [01 · Strategy, roadmap & epics](01-strategy-roadmap.md)
- [02 · Current state & reconciliation](02-current-state.md)
- [03 · Backend & data architecture](03-backend-architecture.md)
- [04 · Frontend & design system](04-frontend-architecture.md)
- [05 · Accrued Agent architecture](05-agent-architecture.md)
- [06 · Platform, security & integrations](06-platform-ops-security.md)
- [07 · Sprint plan](07-sprint-plan.md)
- [08 · Collaboration & Claude Code](08-collaboration.md)
- [09 · Decisions, ADRs & glossary](09-decisions-adrs.md)
- [10 · Quality & evaluation](10-quality-strategy.md)
- [11 · Risk register](11-risk-register.md)

## Epic specifications

- [F-01 · Two-founder governance, CI enforcement & repo safety](epics/F-01.md) — notanaskhan, S0–S1
- [F-02 · Decision Day, ADR programme & glossary](epics/F-02.md) — shared, S0–S2
- [F-03 · Domain model migrations & contract register](epics/F-03.md) — notanaskhan, S0–S4
- [F-04 · Seed universe, demo clock, fakes & journey harness](epics/F-04.md) — ayushkbhatia, S1–S9
- [F-05 · Design system core & MVP templates (DS tiers 0-2)](epics/F-05.md) — ayushkbhatia, S0–S10
- [F-06 · Design system tier 3: workbook, document, signing & tax surfaces](epics/F-06.md) — ayushkbhatia, S14–S24
- [F-07 · Design system tier 4: agent chat, calendar, graph & form surfaces](epics/F-07.md) — ayushkbhatia, S38–S43
- [F-08 · Design system tier 5: Sheet, Board, editor, analytics & add-in surfaces](epics/F-08.md) — ayushkbhatia, S50–S55
- [F-09 · Vendor, design-partner & commercial programme (non-code)](epics/F-09.md) — ayushkbhatia, S0–S30
- [P-01 · Firm shell, sign-in & notifications](epics/P-01.md) — ayushkbhatia, S2–S7
- [P-02 · Search & command palette](epics/P-02.md) — notanaskhan, S39–S41
- [P-03 · Trust kit v1: citations v2 & source viewer](epics/P-03.md) — notanaskhan, S5–S12
- [P-04 · Review grammar & sign-off engine](epics/P-04.md) — notanaskhan, S3–S26
- [P-05 · Collaboration: comments v2, to-dos & activity log](epics/P-05.md) — ayushkbhatia, S33–S37
- [P-06 · Requests & binders engine](epics/P-06.md) — notanaskhan, S3–S10
- [P-07 · Clients, engagements & gates G1-G3](epics/P-07.md) — notanaskhan, S4–S15
- [P-08 · Portal shell & client identity](epics/P-08.md) — notanaskhan, S4–S11
- [P-09 · Agent transparency v1: run dock & trace](epics/P-09.md) — notanaskhan, S31–S34
- [P-10 · Agent runtime v2 & real-time (SSE)](epics/P-10.md) — notanaskhan, S29–S38
- [P-11 · Document services: renderer, OCR & regions](epics/P-11.md) — notanaskhan, S17–S34
- [K-01 · Knowledge library & methodology v1](epics/K-01.md) — ayushkbhatia, S10–S26
- [K-02 · Firm standards, rules tables & content import](epics/K-02.md) — ayushkbhatia, S16–S19
- [K-03 · Templates v2 & Sheets engine](epics/K-03.md) — notanaskhan, S52–S60
- [K-04 · Board, triggers, review package & set up with AI](epics/K-04.md) — notanaskhan, S59–S65
- [K-05 · Learning layer & content: skills, learned context, packs, notes](epics/K-05.md) — ayushkbhatia, S67–S72
- [A-01 · Audit evidence spine & binder export](epics/A-01.md) — notanaskhan, S7–S13
- [A-02 · Trial balance & ledger connections](epics/A-02.md) — notanaskhan, S8–S17
- [A-03 · Sampling & TB mapping](epics/A-03.md) — ayushkbhatia, S20–S23
- [A-04 · Audit planning & risk (G4)](epics/A-04.md) — ayushkbhatia, S22–S28
- [A-05 · EBP plan audits](epics/A-05.md) — ayushkbhatia, S23–S31
- [A-06 · Findings, adjustments, review notes & FS draft](epics/A-06.md) — notanaskhan, S24–S30
- [A-07 · EQR, completion, letters, report, release & archive (G6-G9)](epics/A-07.md) — notanaskhan, S27–S36
- [A-08 · Audit fieldwork depth](epics/A-08.md) — ayushkbhatia, S45–S50
- [A-09 · Group audit (SAS 149)](epics/A-09.md) — notanaskhan, S45–S50
- [A-10 · Statements studio](epics/A-10.md) — ayushkbhatia, S58–S64
- [A-11 · Agentic audit: procedure session & pre-review](epics/A-11.md) — notanaskhan, S65–S68
- [X-01 · Attest core (SOC 1/2, AUP, readiness) & frameworks](epics/X-01.md) — ayushkbhatia, S62–S69
- [X-02 · Attest depth: ISO readiness & GRC sync](epics/X-02.md) — notanaskhan, S68–S72
- [X-03 · Co-sourced internal audit](epics/X-03.md) — ayushkbhatia, S68–S73
- [T-01 · Tax compliance rails: §7216 gate, CCH file bridge, e-file record](epics/T-01.md) — notanaskhan, S16–S21
- [T-02 · Tax extension-season pilot kit](epics/T-02.md) — ayushkbhatia, S16–S21
- [T-03 · TY2027 season readiness: organizer editor, extensions & rules tables](epics/T-03.md) — ayushkbhatia, S26–S29
- [T-04 · Return workspace & individual returns](epics/T-04.md) — ayushkbhatia, S32–S39
- [T-05 · Entity return workspace & K-1 engines (P0)](epics/T-05.md) — ayushkbhatia, S35–S44
- [T-06 · Entity return depth, relationships & hand-offs (P1)](epics/T-06.md) — ayushkbhatia, S49–S55
- [T-07 · Trusts & estates (1041 / 706 / 709)](epics/T-07.md) — ayushkbhatia, S44–S47
- [T-08 · Tax season & practice tools (TY2028)](epics/T-08.md) — ayushkbhatia, S50–S55
- [T-09 · Advisory projects & research](epics/T-09.md) — ayushkbhatia, S66–S70
- [C-01 · Close engine (read-only QBO)](epics/C-01.md) — ayushkbhatia, S44–S51
- [C-02 · Ledger posting, deliverables & hand-offs](epics/C-02.md) — notanaskhan, S49–S55
- [N-01 · Firm inbox, triage & files](epics/N-01.md) — notanaskhan, S13–S18
- [N-02 · Signatures & engagement letters](epics/N-02.md) — notanaskhan, S13–S21
- [N-03 · Firm mailbox, compose & client messages](epics/N-03.md) — ayushkbhatia, S56–S62
- [N-04 · Notices](epics/N-04.md) — ayushkbhatia, S25–S29
- [R-01 · Portal PBC core & white-label](epics/R-01.md) — ayushkbhatia, S7–S18
- [R-02 · Portal approvals, deliverables & governance room](epics/R-02.md) — ayushkbhatia, S29–S35
- [R-03 · Portal mobile capture, payments link-outs & prospect intake](epics/R-03.md) — ayushkbhatia, S59–S63
- [W-01 · Integration catalogue & Connect](epics/W-01.md) — notanaskhan, S45–S48
- [W-02 · Workbench sessions](epics/W-02.md) — notanaskhan, S40–S45
- [W-03 · Agent library, my agents, schedules & saved prompts](epics/W-03.md) — notanaskhan, S63–S69
- [W-04 · Office add-ins](epics/W-04.md) — ayushkbhatia, S69–S73
- [G-01 · Firm settings, users, roles, offices & walls](epics/G-01.md) — notanaskhan, S6–S13
- [G-02 · AI policy, security center & audit log](epics/G-02.md) — notanaskhan, S9–S14
- [G-03 · Developer platform & data model](epics/G-03.md) — notanaskhan, S69–S73
- [G-04 · Platform console, plan & usage, support panel](epics/G-04.md) — notanaskhan, S47–S51
- [I-01 · Home & approvals queue](epics/I-01.md) — ayushkbhatia, S10–S35
- [I-02 · Today brief](epics/I-02.md) — notanaskhan, S40–S43
- [I-03 · Insights](epics/I-03.md) — ayushkbhatia, S61–S67
- [I-04 · Practice economics & capacity](epics/I-04.md) — ayushkbhatia, S70–S73
- [Q-01 · Infrastructure, environments & platform services](epics/Q-01.md) — notanaskhan, S0–S5
- [Q-02 · Real-data readiness & compliance programme](epics/Q-02.md) — notanaskhan, S0–S13
- [Q-03 · Hardening & test back-fill (reserve-funded)](epics/Q-03.md) — shared, S6–S73
- [Q-04 · Pilot operations, release train & freeze contract](epics/Q-04.md) — shared, S12–S74
- [Q-05 · Quality management & records governance](epics/Q-05.md) — ayushkbhatia, S50–S54

## Appendices

- [A · Screen traceability matrix](appendix-a-traceability.md) (also `traceability.csv`)
- [B · Task backlog](backlog.csv) — every task, sorted by sprint, ready to import into GitHub Projects
- `epic_catalogue.json` — machine-readable phases and epics
