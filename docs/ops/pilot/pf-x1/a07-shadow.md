# A-07 shadow and the T-04 1040 workspace shadow plan (Q-04-T136; synthetic, PF-X1)

Row: "A-07 dark code shadowed on one engagement per audit firm ahead of M16, and the T-04 1040
workspace shadow plan from Mar 21 per tax firm." Acceptance: "Each audit firm has one shadowed
engagement with a recorded comparison against its own tool."

PF-X1 is the only audit firm (DEC-4100: no live pilot firms, DEC-1391). Its run is reported as
**synthetic (PF-X1)**. A real firm's run uses the same command against its own tool's file.

## How the shadow works (DEC-3305)
- The firm stays on `assurance_release_mode = external`. It releases and archives in its own tool
  and records both in Accrued (A-01 record mode).
- A-07's code runs dark. `assurance.api.a07_shadow_facts` reads, as the system, what the gates
  (G5 to G7), the also-required list, the release (in-app or recorded), the AU-C 230 date and
  the archive say for the engagement. It writes nothing, flips no flag and moves no phase.
- `make a07-shadow FIRM=… WORK_ITEM=… FIRM_TOOL=…` compares those facts with the firm tool's own
  dates and writes one row per check. The checks are the release date, the documentation
  completion date, the archive lock date, and whether G5 to G7 were all met when the firm released.
- A person reads every difference. Code computes; a difference is never resolved by code.

## PF-X1 run (synthetic)
- Engagement: Northwind Robotics 401(k) Plan PY2025 (`--slice archive`, A-07-T41).
- Firm-tool file: `docs/ops/pilot/pf-x1/a07-shadow-firm-tool.yaml`.
- Result: filled in at the S35 round-2 end pass from the loaded tenant (see below).

## T-04 1040 workspace shadow plan, from Tue Mar 21, 2028, per tax firm
For each tax firm (PF-X1: Brightwater Hale; the Feld household's 2025 Form 1040):
1. **Enrol** the return's work item in shadow (`make pilot-enrol … --mode shadow`). The firm keeps
   preparing in its own software (CCH Axcess for Brightwater Hale).
2. **Flags:** the TAX-04 workspace and the return drafter (T-04-T25) on for the firm, in draft
   mode only. No sync back to the engine, nothing filed (T-04 §2.3).
3. **Compare** each week, Mar 21 to Apr 15: Accrued's drafted K-1 and workbook figures against
   the engine's return. A difference is a finding for the tax lead, never a change to the
   engine's return.
4. **Exit:** shadow ends at the filing deadline. The decision to go live for the next season is
   the founders' (the flip rule, Q-04 §4.1).
5. **Owner:** the tax champion. **Record:** `docs/ops/go-live/<pilot-code>.md`, part T.

Not synthetic-able here: the CCH comparison needs the engine's return. PF-X1's Feld return has the
engine's PDFs as files (T-02-T23), so the plan runs on them in the season.

## Result
_(end pass)_
