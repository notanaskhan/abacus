# Pen-test #1 readiness gate (Q-03-T019, with Q-02-T35)

This is chapter 10 §10.13's "Pen-test readiness" gate for **Fri Feb 12, 2027**. The build pinned that day is the one pen test #1 runs against (Feb 15 – Mar 5). Q-03-T019's acceptance is: "Both founders sign the readiness checklist on Fri Feb 12 with every listed file green on the pinned SHA." Under the solo amendment the builder signs (`docs/plan/AMENDMENT-solo.md`).

This file holds results only. It never holds client data, exploit detail, addresses, vendor names or the external ID (§10.13; the repository is public).

- **Prepared:** Sat Oct 24, 2026, against `main` at `d2920364` (TASK-1179). Every state below is that day's. Re-run every item on the pinned SHA.
- **Companions:**
  - the environment: [`../pentests/2027-02-environment.md`](../pentests/2027-02-environment.md);
  - the ASVS L2 self-assessment: [`../pentests/2027-02-asvs.md`](../pentests/2027-02-asvs.md);
  - the threat model: [`../../architecture/ai-threat-model.md`](../../architecture/ai-threat-model.md);
  - the Type I readiness: [`../compliance/type-1-readiness.md`](../compliance/type-1-readiness.md).

## What "green on the pinned SHA" means (DEC-308)

1. **Green** means the file ran on the pinned SHA in CI and the run had no failure and no skip. A pen-scope security file (PT-02 to PT-05) also has no strict xfail. A strict xfail in any other listed file is allowed only when its escaped defect is listed in the scope letter as a known item.
2. **The ADR-080 core** is the list in ADR-080 and chapter 10 §10.3.4. Where §10.10 names a file that does not exist but the control is tested elsewhere on `main`, this file names the covering tests. The item is `ready` only once the builder accepts that mapping here, at signing, or the named file lands.
3. **A surface that is not built** is out of scope, and the scope letter says so. It is never "green with a note". A stub behind a contract is not built.
4. **No exception path.** An item that is not ready on Fri Feb 12 moves the pin (and the window, with the tester), or comes out of scope by name. The criterion never changes (`../compliance/README.md`, rule 1).

## Checklist

States: `ready` or `not ready`. Owner **human** is the builder by hand. **Session** is a builder session in the repository.

| # | Item (§10.13 / Q-03-T019 / Q-02-T35) | Evidence on `main` | State 2026-10-24 | Closes it | Owner |
|---|---|---|---|---|---|
| PT-01 | Pen-scope back-fill (S6–S7) complete; no S7 back-fill failure open at the Thu Feb 11 train (Q-03-T016) | `docs/quality/backfill.md` shows TASK-030, 032, 035, 040, 041, 044, 045, 054, 055 and 056 back-filled; open from those suites: ED-008 (S6; ED-010 fixed in S10), ED-018 to ED-021 (S7) in `docs/quality/escaped-defects.md` | not ready | Q-03-T009, Q-03-T016; the upload policy (ED-018 to ED-021) | session |
| PT-02 | Walls and need-to-know file green | `backend/tests/security/test_walls_and_need_to_know.py` (Q-03-T012): records, lists, search, counts, notifications, trace export, agent sessions, admin metadata, seeded bypass per surface; no xfail | ready (re-run on the SHA) | — | session |
| PT-03 | Portal-scope isolation file green | `backend/tests/security/test_portal_scope_isolation.py` **does not exist**. Role-union and grant cases live in `backend/tests/integration/test_portal_home.py` and `test_portal_invitations.py` | not ready | P-08-T25 (S8, due by Fri Feb 12) | session |
| PT-04 | Host-pinning file green | `backend/tests/security/test_portal_host_pinning.py` **does not exist** (ADR-168 names it). The cases are in `backend/tests/integration/test_portal_sign_in.py` (a portal token works only on its own host) | not ready | P-08-T25 | session |
| PT-05 | Hostile-upload file green | `backend/tests/security/test_upload_hostile_files.py` (Q-03-T013) has strict xfails: ED-018 (50 MB), ED-019 (types outside DEC-58, polyglots), ED-020 (HEIC), ED-021 (PDF with JavaScript) | not ready | the client upload policy decided 2026-10-24 (in flight in another workstream): each xfail turns into a pass | session |
| PT-06 | DAST baseline with no high alert | No `.github/workflows/dast.yml`; ZAP has no `containers:` entry in `docs/architecture/dependency-allowlist.yaml` | not ready | Q-03-T004 (needs staging: E-01) | session, human |
| PT-07 | Threat model current, N approved | Refreshed for S5–S7 (Q-03-T018; review row in the file); N's approval open | not ready | N's review by Fri Feb 5, 2027 | human |
| PT-08a | ADR-080 core: tenant isolation | `backend/tests/security/test_tenant_isolation.py` (generated over `TABLE_OWNERS`), `test_tenancy_escape.py` | ready (re-run) | — | session |
| PT-08b | ADR-080 core: matrix permission tests | `backend/tests/security/test_permission_matrix_generated.py`, `test_resolution_actions_generated.py` | ready (re-run) | — | session |
| PT-08c | ADR-080 core: route introspection | `backend/tests/security/test_route_introspection.py`, `test_route_introspection_detects.py` | ready (re-run) | — | session |
| PT-08d | ADR-080 core: RLS schema check | `backend/tests/integration/test_schema_check_db.py`; up/down/up in stage 2 | ready (re-run) | — | session |
| PT-08e | ADR-080 core: connector write interception | `test_connector_write_interception.py` **does not exist**; covered by `backend/tests/unit/connections/test_fake_conformance.py` (a non-read request fails) | not ready (mapping to accept) | accept the mapping at signing, or add the file | human |
| PT-08f | ADR-080 core: output controls with seeded violations | `test_output_controls.py` **does not exist**; front end `apps/web/src/agent-text.test.tsx`; the server sanitiser `backend/src/abacus/ai_gateway/sanitise.py` has **no backend test** (threat model HC-10) | not ready | a backend sanitiser test (SPEC-006 AC-1, AC-2), then the mapping | session |
| PT-08g | ADR-080 core: citation verification with seeded violations | `test_citations.py` **does not exist**; covered by `backend/tests/integration/trust_kit/test_citation_verifiers.py`, `backend/tests/unit/agents/test_agent_citations.py` | not ready (mapping to accept) | accept the mapping at signing | human |
| PT-08h | ADR-080 core: classification tags | `test_classification_scrubbing.py` **does not exist**; covered by `backend/tests/unit/kernel/test_classification.py`, `test_classification_flags.py`, `test_pii_scrubbing.py`, `test_telemetry_scrubbing.py` | not ready (mapping to accept) | accept the mapping at signing | human |
| PT-08i | §10.3.4 R1 files: agent never, immutability | `test_agent_never.py` and `test_immutability.py` **do not exist**; covered by `backend/tests/security/test_agent_principal.py`, `backend/tests/integration/test_human_only_guard.py`; evidence and ledger immutability triggers in `backend/tests/integration/test_schema_check_db.py`, `test_ledger_schema.py` | not ready (mapping to accept) | accept the mapping at signing | human |
| PT-09 | `security` stage required on `main` (M4-13) | `.github/workflows/security.yml` runs; making it required is a ruleset setting | not ready (unverified) | ruleset export | human |
| PT-10 | Environment ready (Q-02-T35): items E-01 to E-11 | `../pentests/2027-02-environment.md` | not ready: no staging or production compute; review role written, unapplied | Q-01-T14, T15, T28, T35, T47, T56; the builder's applies | human |
| PT-11 | ASVS L2 gaps marked "by pin" closed on the SHA; the register re-run | `../pentests/2027-02-asvs.md`: G-01, G-02, G-05, G-06, G-09 to G-11, G-14, G-18, G-21 are "by pin" | not ready | each gap's task | session |
| PT-12 | Every readiness and ASVS gap has a ticket with an owner and a date | The Ticket columns in `../compliance/type-1-readiness.md` and `../pentests/2027-02-asvs.md` are empty | not ready | the builder opens them | human |
| PT-13 | Scope letter lists the known items and the not-built surfaces | ASVS "known item" gaps; threat-model scope table (not built and stub rows) | not ready | the builder writes it (vault) | human |
| PT-14 | Tester's personas work on the pinned build | E-04 | not ready | E-04 | human, tester |
| PT-15 | Build SHA pinned, recorded below, told to the tester | — | not ready | Fri Feb 12, 2027 | human |

## Pin-day run sheet

Run on Fri Feb 12, 2027, after the Thu Feb 11 train. These are commands and checks only, and nothing below changes the environment.

1. Pick the SHA. Use the train's merge commit on `main`. Check that no staging deploy is in flight: `gh run list --workflow deploy-staging.yml --status in_progress`.
2. CI is green for that SHA: `gh run list --commit <sha>`. Stages 1 and 2 (`ci.yml`, whose integration shards run `backend/tests/security`) and `security.yml` must all pass.
3. No strict xfail in a pen-scope file: `grep -n "xfail" backend/tests/security/test_walls_and_need_to_know.py backend/tests/security/test_upload_hostile_files.py backend/tests/security/test_portal_scope_isolation.py backend/tests/security/test_portal_host_pinning.py` prints nothing.
4. The pen-scope and core files exist at the SHA: `git ls-tree -r --name-only <sha> backend/tests/security`.
5. The DAST baseline's last run against staging is on or after the SHA's staging deploy, and has no high alert (PT-06).
6. Re-check the ASVS register's "by pin" gaps on the SHA (PT-11). Copy any still open into the scope letter as known items, or move the pin.
7. Fill in the record below. Then tell the tester the SHA and the start of the window through the agreed channel.

## Record

| Field | Value |
|---|---|
| Pinned SHA | |
| CI runs (stage 1, stage 2, security) | |
| DAST run and result | |
| Items not ready, and what was done (pin moved, or out of scope by name) | |
| Scope letter reference | vault `V-____` |
| Signed (builder) | |
| Date | |

## Human to-dos this checklist surfaces

1. Apply the staging and production platform (Q-01-T14, T15, T28), the portal edge with the canary custom domain (Q-01-T56), the staging mail sink (Q-01-T47) and the canary (Q-01-T35).
2. Apply the review role in both accounts for the window, check it, and remove it after the window (`infra/README.md`, "Pen-test review role").
3. Create the personas through the product on both targets, and set the canary flags (environment E-03 to E-05).
4. Co-sign the rules of engagement with F-09. Write the scope letter from the known items and the not-built surfaces.
5. Open the tickets for every readiness and ASVS gap, and write their ids into the two registers.
6. Make the `security` stage a required check, and export the ruleset as evidence.
7. Get N's approval of the threat-model refresh by Fri Feb 5, 2027.
8. Accept or refuse the ADR-080 file mappings (PT-08e, g, h, i) at signing.
9. Pin the SHA on Fri Feb 12, fill in the record and sign.
