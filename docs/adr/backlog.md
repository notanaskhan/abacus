# ADR backlog

This file is the only source of ADR numbers. Specs and tasks cite P-IDs until a number appears here. An ADR number in a plan chapter is a P-ID alias, not a reservation: take the next free number on `main` when you start drafting (`docs/plan/AMENDMENT-solo.md` item 8), then write it into the "ADR number" column the same day.

- **P-ID.** The proposal ID from [`docs/plan/09-decisions-adrs.md`](../plan/09-decisions-adrs.md) section 9.4.2. P-64 to P-69 were added from the backlog tasks that draft them.
- **Epic.** The epic whose backlog task first drafts the ADR (from `docs/plan/backlog.csv`, best match; check the task when drafting starts). Epic keys such as `P-10` are epics, not ADR IDs. A dash means no task names it.
- **ADR number.** `next free` until drafting starts. Numbers minted so far: P-01 = ADR-133, P-38 = ADR-135, P-04 = ADR-136, P-05 = ADR-137, P-34 = ADR-138, P-36 = ADR-139, P-39 = ADR-140, P-54 = ADR-141, P-55 = ADR-142 (all accepted).
- **DEC row.** The decision it records, in [`docs/product/decision-log.md`](../product/decision-log.md).
- **Status.** `to draft`, `proposed`, `accepted`, or `n/a, solo edition`.

| P-ID | Title | Zone | Epic | ADR number | Needed by | DEC row | Status |
|---|---|---|---|---|---|---|---|
| P-01 | Product naming | amber | F-02 | ADR-133 | Fri 23 Oct | DEC-01 | accepted |
| P-02 | Two-founder governance and decision rights | amber | — | — | Wed 21 Oct | DEC-02 | n/a, solo edition |
| P-03 | Accrued design system in `packages/ui` | amber | F-05 | next free | Fri 23 Oct | DEC-04, DEC-11, DEC-15 | to draft |
| P-04 | Engagement + work items + server-enforced gates | red | F-03 | ADR-136 | Fri 23 Oct | DEC-07, DEC-39 | accepted |
| P-05 | Module map (29 modules) | amber | F-03 | ADR-137 | Fri 23 Oct | DEC-13 | accepted |
| P-06 | Generalised `visible()` | red | F-03 | ADR-145 | Fri 6 Nov | DEC-33 | accepted |
| P-07 | Review grammar | red | Q-02 | next free (ADR-134 already binds fieldwork to it) | Fri 6 Nov | DEC-36 | to draft |
| P-08 | Policy principal (dormant) | red | Q-03 | next free | Fri 11 Dec (design); enable ≥ Q2 2027 | DEC-53 | to draft |
| P-09 | Client identity, scoped grants, link principals, portal MFA | red | F-03 | ADR-146 | Fri 6 Nov | DEC-34, DEC-63, DEC-67 | accepted |
| P-10 | Role catalogue and need-to-know | red | F-03 | ADR-147 | Fri 6 Nov | DEC-20, DEC-21 | accepted |
| P-11 | White-label portal, domains, branded email | amber | F-09 | next free | Fri 13 Nov | DEC-59 | to draft |
| P-12 | §7216 consents, TRI, TIN sealing, gateway condition | red | Q-02 | next free | Fri 13 Nov | DEC-52 | to draft |
| P-13 | Independence and attest-client rules | red | P-07 | next free | Fri 27 Nov | DEC-69 | to draft |
| P-14 | Retention, holds, destruction | red | Q-02 | next free | Fri 27 Nov (data model) | DEC-71 | to draft |
| P-15 | Real time via SSE, plus presence | amber | P-10 | next free | Fri 6 Nov | DEC-23 | to draft |
| P-16 | Client-ledger writes (W1) and GRC request sync (W5) | red | C-01 | next free | Fri 27 Nov | DEC-69 | to draft |
| P-17 | `integrations` module and the write-capability framework | red | F-02 | ADR-150 | Fri 6 Nov | DEC-46 | proposed |
| P-18 | Tax-engine integration; never transmit | red | F-09 | next free | Fri 13 Nov | DEC-49 | to draft |
| P-19 | Deterministic document generation | amber | P-11 | next free | Fri 6 Nov | DEC-44 | to draft |
| P-20 | Office add-ins | amber | — | next free | Q2 2027 | DEC-95 | to draft |
| P-21 | Public API, webhooks, MCP | red | — | next free | Fri 11 Dec | DEC-86 | to draft |
| P-22 | Agent model: capabilities vs firm definitions | red | P-10 | next free | Fri 6 Nov | DEC-41 | to draft |
| P-23 | Workbench sessions | red | P-10 | next free | Fri 13 Nov | DEC-40 | to draft |
| P-24 | Structured agent output | red | F-06 | next free | Fri 6 Nov | DEC-41 | to draft |
| P-25 | Model-drafted text to clients | red | Q-03 | next free | Fri 11 Dec | DEC-79 | to draft |
| P-26 | E-signature | red | F-02 | ADR-149 | Fri 30 Oct (vendor clock) | DEC-25 | proposed |
| P-27 | Payments and billing boundary | amber | F-09 | next free | Fri 11 Dec | DEC-89 | to draft |
| P-28 | Entitlements, agent-minutes, two-layer budgets | amber | F-03 | ADR-148 | Fri 13 Nov | DEC-51, DEC-55 | accepted |
| P-29 | Busy-season change policy | amber | F-02 | ADR-151 | Fri 27 Nov | DEC-68 | proposed |
| P-30 | Peer benchmark network | red | — | next free | Deferred | DEC-99 | to draft |
| P-31 | Client withdrawal of unaccepted uploads | red | P-06 | next free | Fri 13 Nov | DEC-58 | to draft |
| P-32 | OCR and document understanding | amber | P-11 | next free | Fri 6 Nov | DEC-42 | to draft |
| P-33 | Search in Postgres | amber | P-02 | next free | Fri 6 Nov | DEC-42, DEC-43 | to draft |
| P-34 | Status registry and codegen | amber | F-03 | ADR-138 | Fri 23 Oct | DEC-08 | accepted |
| P-35 | Suggestions, proposals, approval grants, Undo; dormant policy actor | red | P-04 | next free | Fri 30 Oct | DEC-24, DEC-28 | to draft |
| P-36 | API conventions | amber | F-03 | ADR-139 | Fri 23 Oct | DEC-12 | accepted |
| P-37 | Clock, scenario loader, synthetic marker | amber | F-02 | ADR-143 | Fri 30 Oct | DEC-27 | accepted |
| P-38 | Pre-launch migration policy | red | F-03 | ADR-135 | Wed 21 Oct | DEC-06 | accepted |
| P-39 | Per-module registries and matrix files | amber | F-03 | ADR-140 | Fri 23 Oct | DEC-13 | accepted |
| P-40 | Client-scoped files and cross-engagement fulfilment | red | F-03 | next free | Fri 6 Nov | DEC-33 | to draft |
| P-41 | Templates v2 | amber | K-04 | next free | Fri 13 Nov | DEC-56 | to draft |
| P-42 | Generalised comments | red | P-05 | next free | Fri 27 Nov | DEC-29 | to draft |
| P-43 | Archive seal, DB immutability, hash chain, Object Lock modes | red | A-07 | next free | Fri 11 Dec | DEC-71 | to draft |
| P-44 | Request status enum migration | red | F-03 | ADR-144 | Fri 30 Oct | DEC-09, DEC-74 | accepted |
| P-45 | Unauthenticated `/healthz` and portal branding routes | red | Q-01 | ADR-152 | Fri 13 Nov (with TASK-014) | DEC-59 | proposed |
| P-46 | Gateway conversations and tool use | red | P-10 | next free | Fri 6 Nov | DEC-41 | to draft |
| P-47 | Runs, steps, sessions, canonical run states, run records | red | P-10 | next free | Fri 6 Nov | — | to draft |
| P-48 | Citation v2 and number provenance | red | P-03 | next free | Fri 13 Nov | — | to draft |
| P-49 | Autonomy policy versions and Auto mode | red | P-10 | next free | Fri 13 Nov | DEC-50 | to draft |
| P-50 | Agent schedules | amber | W-03 | next free | Fri 18 Dec | DEC-90 | to draft |
| P-51 | Triggers and run-as | red | K-04 | next free | Fri 18 Dec | DEC-90 | to draft |
| P-52 | Firm-authored instructions as context | red | K-03 | next free | Fri 18 Dec | DEC-90 | to draft |
| P-53 | Learned-context tiers and the skill publish gate | amber | — | next free | Fri 18 Dec | DEC-90 | to draft |
| P-54 | Authentication and sessions | red | Q-01 | ADR-141 | Fri 30 Oct | DEC-22, DEC-34, DEC-35 | accepted |
| P-55 | AWS production topology and regions | red | Q-01 | ADR-142 | Fri 30 Oct | DEC-03 | accepted |
| P-56 | Release train and previews | amber | — | — | Fri 13 Nov | DEC-54 | n/a, solo edition |
| P-57 | Sampling engine | red | A-03 | next free | Fri 11 Dec | DEC-81 | to draft |
| P-58 | Document-extracted ledger snapshots; GL JE fields | red | A-05 | next free | Fri 11 Dec | DEC-82 | to draft |
| P-59 | Structured document model and editor | amber | X-01 | next free | Fri 11 Dec | DEC-80 | to draft |
| P-60 | Firm mailbox integration (W6) | red | N-01 | next free | Fri 27 Nov | DEC-75 | to draft |
| P-61 | Practice-management writes (W3, W4) | amber | I-03 | next free | When scheduled (P3) | DEC-98 | to draft |
| P-62 | Platform reference data | amber | A-05 | next free | Fri 27 Nov | DEC-76 | to draft |
| P-63 | Multi-entity engagements and consolidation | red | A-03 | next free | Fri 20 Nov | DEC-65, DEC-66 | to draft |
| P-64 | Malware scanning service | red | Q-01 | ADR-153 | Fri 13 Nov (draft open Fri 30 Oct) | — | proposed |
| P-65 | Tenant key provisioning | red | Q-01 | next free | Fri 27 Nov | — | to draft (confirmed 2026-10-20) |
| P-66 | Platform controls and kill switches | red | Q-01 | next free | Fri 27 Nov | — | to draft (confirmed 2026-10-20) |
| P-67 | Observability and on-call vendors | red | Q-01 | ADR-154 | Fri 13 Nov (draft open Fri 30 Oct) | — | proposed |
| P-68 | Tax computation boundary | amber | T-02 | next free | Fri 28 May 2027 (draft S14) | DEC-77 | to draft (confirmed 2026-10-20) |
| P-69 | Workbook formula engine and the ADR-052 exception for tax workbooks | red | T-05 | next free | Fri 18 Feb 2028 (draft S33) | DEC-84 | to draft (confirmed 2026-10-20) |

## ADRs outside the P-programme

These ADRs have no P-ID.

| ADR | Subject | Status |
|---|---|---|
| [ADR-131](ADR-131-workpapers.md) | Fieldwork workpapers: rendered by code, versioned, signed off by people | accepted |
| [ADR-132](ADR-132-procedures.md) | Fieldwork procedures: code builds the population and selects the sample, agents assess, people conclude | accepted |
| [ADR-134](ADR-134-fieldwork-on-review-grammar.md) | Fieldwork sign-off, review notes and workpapers ride the P-04 review grammar (DEC-110) | accepted |
| ADR-116 | Reserved for a dated coverage exception (DEC-10); drafted only if back-fill costs more than 2 working days | reserved |
