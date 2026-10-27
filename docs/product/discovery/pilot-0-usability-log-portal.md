# Pilot 0 usability log: portal sign-in and home (POR-01, POR-02)

| Field | Value |
|---|---|
| Plan rows | P-08-T29 (this log's structure); F-09-T70 (findings filed as issues), F-09-T93 (top-10 list to owning epics) |
| Pilot | PW0 · Pilot 0, Jan 11 – May 28, 2027, synthetic, on staging (chapter 01); J12 sessions in January |
| Tenant and clock | Brightwater Hale on staging, demo clock (`--slice portal`; both portal flags on for the demo firm, TASK-1359) |
| Screens | POR-01 (sign-in, a–g, c′, d, 390) and POR-02 (home, a–h, M) |
| Journeys | J12 steps 1, 2 and 2b (Claire Feld's code; Tess Moreno's second step), J03 4c (Dana Kowalski) |
| Fixes go to | the P-08 reserve (S11 and later sprints' reserve rows); a fix that changes a screen also updates its contract's Deviations |
| Status | **template only.** No session has been run. Every finding below is a placeholder for a person to fill in after a real session; nothing here is a finding. |

## How to record a session
1. One row per observation in the findings table, written by the person who ran the session, the
   same day. Name the screen ID and its state letter (`POR-01 f`, `POR-02 M`), never a real
   person's name: participants are `P1`, `P2`… with their role (partner, staff, client-side
   stand-in), and the session list below keeps the mapping out of this public repository.
2. Severity: **S1** blocks the task (the person could not sign in or find their to-do);
   **S2** slows it or causes an error the person recovered from; **S3** cosmetic or wording.
3. File each S1 and S2 as an issue (F-09-T70) and put its number in the row. Route the fix: a
   reserve row of P-08 for POR-01 and POR-02 fixes, or the owning epic.
4. Never paste a sign-in code, email address, link token or anything from a real firm. The tenant
   is synthetic; screenshots go to the pilot folder outside the repository.

## Sessions
| Session | Date | Firm (pilot code) | Participants (codes and roles) | Journeys walked | Run by | Notes file |
|---|---|---|---|---|---|---|
| _placeholder: S-01_ | _to fill_ | _to fill_ | _to fill_ | _to fill_ | _to fill_ | _to fill_ |

## Findings
| ID | Session | Screen and state | Width (1400, 720, 390) | What the person did or said | Severity | Issue | Routed to | Fixed in | Contract updated |
|---|---|---|---|---|---|---|---|---|---|
| _placeholder: PU-001_ | _S-01_ | _POR-01 a_ | _to fill_ | _to fill after a real session_ | _S1, S2 or S3_ | _#NNN_ | _P-08 reserve or epic_ | _PR or commit_ | _yes / no_ |

## What to watch (from the contracts, not findings)
Prompts for the session runner, taken from POR-01 and POR-02's open gaps and decisions. They are
questions to observe, not results:
- POR-01: whether the six-box code and "2 tries left" (f) read clearly; whether the lock (g, DEC-35)
  is understood; the 14-day reminder link (e); the c′ setup without a drawn QR code (open gap).
- POR-01 d: whether a delegated third party (Sam Ortiz) understands the invitation landing.
- POR-02: the first-visit cards (b), the stage tracker words (client labels only), the
  "Your day-to-day contact" rule (OQ-5), the 390 bottom tab bar (M, DEC-45).
- White label everywhere: the person should never see "Accrued".

## Top-10 for M9 (F-09-T93)
| Rank | Finding IDs | Fix | Owner epic | Status |
|---|---|---|---|---|
| _placeholder_ | _to fill after the sessions_ | _to fill_ | _to fill_ | _to fill_ |
