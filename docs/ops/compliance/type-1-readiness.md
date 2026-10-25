# SOC 2 Type I readiness: the gap register (Q-02-T35)

The readiness assessment for the Type I "as of" date, **Mon Mar 1, 2027**. The plan runs the assessment in the compliance tool from Jan 4 to Feb 26, 2027 (chapter 06 §5.7). This file is the repository's half of it: one row per control in [`../soc2-control-map.md`](../soc2-control-map.md), with what `main` shows today (`d2920364`, Sat Oct 24, 2026), the gap, the task that closes it, the owner and a due date on or before **Fri Feb 26, 2027**. Q-02-T35's acceptance: "Every readiness gap has a ticket with an owner and a date before Feb 26."

Rules (from [`README.md`](README.md)): only the tool's evidence moves a control to `operating`. Nothing here names the auditor, the tool's vendor, a price or a person beyond "builder". The **Ticket** column is empty until the builder opens each ticket: sessions open no issues. Filling it in is readiness gate item PT-12.

## Cross-wide gaps (block many controls at once)

| Gap | What | Controls | Closing | Owner | Due | Ticket |
|---|---|---|---|---|---|---|
| R-01 | Compliance tool not chosen or connected (M4-06) | all `tool:` evidence | Q-02-T10 | builder | Fri Jan 8, 2027 | |
| R-02 | Staging and production have no network, database, compute, firm edge or alarms in Terraform; nothing is applied | SEC-06, SEC-18, SEC-19, SEC-24, AVL-01, AVL-05, AVL-06, AVL-09 | Q-01-T14, Q-01-T15, Q-01-T28, Q-01-T25, Q-01-T33 | builder | Fri Jan 22, 2027 | |
| R-03 | No control has evidence dated in the tool, so the M4 evidence (due Fri Dec 11, 2026) has to be collected late, and the auditor told | every M4 row | Q-02-T19 | builder | Fri Jan 29, 2027 | |
| R-04 | Change management with one person (no second approver) | SEC-28, SEC-31 | settle the description with the auditor (`README.md`, "Open items"); compensating controls evidenced | builder, auditor | Fri Feb 5, 2027 | |

## Security

| ID | Map state | Seen on `main` today | Gap | Closing | Due | Ticket |
|---|---|---|---|---|---|---|
| SEC-01 | designed | QI designated (`README.md`); WISP v1 drafted ([`wisp.md`](wisp.md), 2026-10-25) | WISP not yet approved by the QI; counsel review open | Q-02-T40 | Fri Feb 19, 2027 | |
| SEC-02 | designed | — | training, acceptable-use policy | R-01; policies in the tool | Fri Jan 29, 2027 | |
| SEC-03 | designed | `docs/operations/provider-terms.yaml` exists with no entries | status page, generated sub-processor list for customers | Q-01-T41; Q-02-T18 | Fri Feb 19, 2027 | |
| SEC-04 | building | threat model refreshed (Q-03-T018) | risk assessment in the tool | R-01 | Fri Jan 29, 2027 | |
| SEC-05 | building | `docs/architecture/ai-threat-model.md` current to S7 | N's review of the refresh | Q-03-T018 | Fri Feb 5, 2027 | |
| SEC-06 | designed | `docs/ops/slos.md` | alarms as code, dashboards | R-02 | Fri Jan 22, 2027 | |
| SEC-07 | building | `evals/` suites | eval reports dated in the tool | Q-02-T44 | Fri Feb 19, 2027 | |
| SEC-08 | building | stages in `.github/workflows/ci.yml`, `security.yml` | ruleset export showing the required checks (a repository setting) | Q-02-T15 (M4-13) | Fri Jan 8, 2027 | |
| SEC-09 | building | allowlist and CI checks exist | evidence of findings ticketed | R-01 | Fri Jan 29, 2027 | |
| SEC-10 | building | staff BFF refuses tokens without MFA (`backend/tests/integration/test_staff_session.py`) | identity provider integration in the tool; WorkOS adapter (Q-01-T17) | Q-01-T17; R-01 | Fri Jan 22, 2027 | |
| SEC-11 | building | generated matrix tests exist (`backend/tests/security/test_permission_matrix_generated.py`) | none in code; evidence in the tool | R-03 | Fri Jan 29, 2027 | |
| SEC-12 | building | generated isolation test exists (`backend/tests/security/test_tenant_isolation.py`) | none in code; evidence in the tool | R-03 | Fri Jan 29, 2027 | |
| SEC-13 | designed | — | role catalogue evidence; break-glass procedure evidenced | R-01 | Fri Feb 12, 2027 | |
| SEC-14 | designed | `make access-review` exists (`Makefile`) | first quarterly review recorded (M4-07) | R-03 | Fri Jan 29, 2027 | |
| SEC-15 | building | portal MFA floor tested (`backend/tests/integration/test_portal_mfa.py`) | `make mfa-report` and the staff-route MFA test (Q-02-T37) | Q-02-T37 | Fri Feb 19, 2027 | |
| SEC-16 | building | route introspection exists (`backend/tests/security/test_route_introspection.py`) | portal-scope and host-pinning files (P-08-T25) | P-08-T25 | Fri Feb 12, 2027 | |
| SEC-17 | designed | — | cloud provider's report reviewed and recorded | builder (vault) | Fri Jan 29, 2027 | |
| SEC-18 | built | crypto tests exist | database encryption at rest and TLS applied; database client certificate verification (ASVS G-09) | R-02; ticket | Fri Jan 22, 2027 | |
| SEC-19 | building | portal edge written; DNS Firewall a README | network boundary and egress allowlist applied | R-02 | Fri Jan 22, 2027 | |
| SEC-20 | built | secrets scan in `make check-fast` | Secrets Manager wiring | Q-01-T14 | Fri Jan 22, 2027 | |
| SEC-21 | built | scanning tests exist | upload type policy (ED-018 to ED-021; decided 2026-10-24, in flight) | Q-03-T016 | Fri Feb 12, 2027 | |
| SEC-22 | building | CI security stage | vulnerability feed in the tool; DAST baseline (Q-03-T004) | Q-03-T004; R-01 | Fri Feb 12, 2027 | |
| SEC-23 | designed | environment and checklist written (`docs/ops/pentests/2027-02-environment.md`) | pen test booked (M4-12), run, letter received | F-09-T42; Q-02-T42 | test by Fri Mar 5; booking evidenced by Fri Feb 12, 2027 | |
| SEC-24 | designed | audit-chain mismatch is a runbook only | baseline detections and alarms applied | R-02; Q-01-T25 | Fri Feb 19, 2027 | |
| SEC-25 | building | hash chain tested (`backend/tests/integration/test_audit_chain.py`) | nightly verification history (7 nights) | Q-02-T21 | Fri Feb 19, 2027 | |
| SEC-26 | designed | incident register built (`backend/tests/integration/test_security_incidents.py`) | tabletop (M4-08); register live in the tool | R-03 | Fri Jan 29, 2027 | |
| SEC-27 | building | runbook index exists | rehearsal dates | Q-02-T51; Q-01-T40 | Fri Feb 19, 2027 | |
| SEC-28 | building | PRs with required checks | release manifests (Q-01-T11); R-04 | Q-01-T11; R-04 | Fri Feb 5, 2027 | |
| SEC-29 | built | flags directory `docs/architecture/feature-flags/` with expiry checks | evidence in the tool | R-03 | Fri Jan 29, 2027 | |
| SEC-30 | built | `docs/architecture/protected-paths.md` | evidence in the tool | R-03 | Fri Jan 29, 2027 | |
| SEC-31 | building | human-only guard tested (`backend/tests/integration/test_human_only_guard.py`) | PR model records; R-04 | R-04 | Fri Feb 5, 2027 | |
| SEC-32 | built | boundary tests exist | Bedrock register entry with counsel (Q-02-T18) | Q-02-T18 | Fri Feb 26, 2027 | |
| SEC-33 | built | context and eval tests exist | sanitiser backend test (threat-model gap, HC-10) | ticket | Fri Feb 12, 2027 | |
| SEC-34 | designed | — | founder-dependency plan evidenced | R-01 | Fri Feb 19, 2027 | |
| SEC-35 | building | vendor tracker exists | register reviews dated | F-09 | Fri Feb 19, 2027 | |

## Availability

| ID | Map state | Seen on `main` today | Gap | Closing | Due | Ticket |
|---|---|---|---|---|---|---|
| AVL-01 | designed | `docs/ops/slos.md` | burn-rate alarms applied | Q-01-T33; R-02 | Fri Feb 19, 2027 | |
| AVL-02 | built | `backend/tests/integration/test_work_class_queues.py` | evidence in the tool | R-03 | Fri Jan 29, 2027 | |
| AVL-03 | built | budget tests | cost anomaly alert routed; firm and engagement limits tested (ASVS G-24) | Q-01-T25; ticket | Fri Feb 19, 2027 | |
| AVL-04 | designed | — | RB-16 written | builder | Fri Feb 26, 2027 | |
| AVL-05 | building | — | RDS PITR, cross-region copies, evidence replication applied | Q-01-T14; Q-01-T28 | Fri Jan 22, 2027 | |
| AVL-06 | building | — | deploy pipeline with rollback (Q-01-T18) | Q-01-T18 | Fri Feb 5, 2027 | |
| AVL-07 | designed | — | first restore drill (M4-05) | Q-01-T39 | Fri Jan 29, 2027 | |
| AVL-08 | building | chain verification command (`make audit-chain-verify`) | nightly run history | Q-02-T21 | Fri Feb 19, 2027 | |
| AVL-09 | designed | — | canary schedule on production with paging (Q-01-T35) | Q-01-T35 | Fri Jan 22, 2027 | |

## Confidentiality

| ID | Map state | Seen on `main` today | Gap | Closing | Due | Ticket |
|---|---|---|---|---|---|---|
| CON-01 | built | classification tests, TRI/PHI/PII flags (`backend/tests/unit/kernel/test_classification_flags.py`) | evidence in the tool | R-03 | Fri Jan 29, 2027 | |
| CON-02 | built | walls file (`backend/tests/security/test_walls_and_need_to_know.py`) | evidence in the tool | R-03 | Fri Jan 29, 2027 | |
| CON-03 | designed | — | contract terms (vault) | F-09 | Fri Feb 26, 2027 | |
| CON-04 | built | scrubbing tests, TIN masking (`backend/tests/unit/kernel/test_pii_scrubbing.py`) | sampled sink audit (Q-03-T083) is after M7; evidence in the tool now | R-03 | Fri Jan 29, 2027 | |
| CON-05 | designed | — | two-firm cache and example test (threat-model gap CT-03) | ticket | Fri Feb 19, 2027 | |
| CON-06 | building | register exists, no entries | Bedrock entry (Q-02-T18) | Q-02-T18 | Fri Feb 26, 2027 | |
| CON-07 | built | crypto tests | tenant key rotation (ASVS G-19) | ticket | Fri Feb 26, 2027 | |
| CON-08 | building | holds and Object Lock tested (`backend/tests/integration/test_legal_holds.py`, `test_retention_object_lock.py`) | approved destruction (Q-05-T14) is after Type I: state as a known limitation | builder, auditor | Fri Feb 5, 2027 | |
| CON-09 | designed | — | firm export (Q-02-T43) and RB-13 | Q-02-T43 | Fri Feb 26, 2027 (or carve out with the auditor) | |
| CON-10 | built | `backend/tests/integration/test_evidence_storage.py` | Object Lock applied on the real bucket (Q-01-T14) | Q-01-T14 | Fri Jan 22, 2027 | |

## Notes

- Two evidence paths in the control map had moved: the flag registry and the permission matrix became directories. The map now names `docs/architecture/feature-flags/` and `docs/architecture/permission-matrix/` (TASK-1176).
- Several rows marked *planned* in the map now have their tests on `main`: SEC-11, SEC-12, SEC-16 and SEC-25. Their state stays as it is until evidence is in the tool.
