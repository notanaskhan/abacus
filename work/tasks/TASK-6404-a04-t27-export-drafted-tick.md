---
id: TASK-6404
title: A-04-T27 remainder - AUD-04 downloads the workpaper; an agent's drafted value carries an outlined tick
spec: SPEC-000  # row
acceptance_criteria: [AC-1, AC-2, AC-3]
risk_zone: green
status: in-review
epic: A-04
plan_key: A-04-T27
branch: s26p-a04-t27-export
worktree: /Users/ayushkbhatia/Accrued/abacus-s26
created: 2026-11-08
updated: 2026-11-08
---

# TASK-6404 · A-04-T27: AUD-04 downloads the paper; drafted values carry an outlined tick

TASK-3234 drew Open in Excel and Download as icons with no export, and the C-02 kit had no outlined tick for a drafted value.

AC-1: Download and Open in Excel fetch the paper's XLSX from the existing export route (audited `workpaper.exported`) and save it under the server's file name; a failure says so in words.

AC-2: The kit's tick has a `drafted` state, an outlined dashed ring named "Drafted by the agent, not yet adopted", never a green pill.

AC-3: AUD-04 shows ✓ on an adopted value and the outlined ring on a value the agent drafted that no person has adopted.

## Decisions (DEC-2954)
- Open in Excel downloads the same XLSX: the browser hands it to Excel. No separate route.
- The ring is dashed ink-3 at 11px, beside where the bare check sits, so a drafted and an adopted cell line up.

## Known limits
- The gallery specimen for the drafted tick is not added: a new specimen needs a visual baseline recorded on the CI image. The kit test covers its render.
- Two citation quotes stay withheld: the handoff names the sources (Keystone SOC 1 p. 14, BH-EBP-140 step 3) without their text.

## Progress log
- 2026-11-08: built on main a801fff01; tests written, run at the S26 partials end pass.
