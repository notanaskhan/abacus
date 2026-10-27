# Release windows (P-29 implementation note)

Owner: both founders · Source: ADR P-29 (DEC-68), Q-04 §4.9, chapter 01 §1.3.3 · Task: Q-04-T001 · Status: **draft for both founders' approval in the S12 window** (the plan's approval line; DEC-654)

This note says when production may change once real firms rely on it. `deploy/windows.yaml` (Q-04-T002) is the machine-checked copy; where they disagree, fix the file to match this note, then both founders approve the change.

## 1. When windows apply

- **From the first real data.** Windows start for a firm on the day its first non-synthetic data lands (P-29: the freeze starts at the first real go-live, not before). Before any firm is live, the release train is a stability milestone, never a freeze.
- **Season window: Jan 1 – Apr 20,** every live firm.
- **Autumn window: Sep 1 – Oct 20,** firms live on tax or EBP work.
- **Platform rules apply when any live firm is in a window.** One promotion touches every tenant, so promotion, migrations and deadline weeks follow the strictest live firm. **Flip rules apply per firm** (Q-04 OQ-2).

## 2. Inside a window

- **Promotion only in the Tuesday 19:00 CT slot.** That week's release carries `window_mode`. There is no promotion on any other day.
- **Deadline weeks: no promotion, no flip.** A deadline week is the Monday–Friday week containing the shifted deadline (IRC §7503 weekend and holiday shift; DC Emancipation Day moves Apr 15 when observed on the next business day).
- **Mini-freezes.** From the shifted extension deadline minus 7 days through the deadline, 8 calendar days inclusive. In a mini-freeze, no flip changes a live path; a promotion still needs the Tuesday slot.
- **Registry-only renewals.** A flag's expiry may be renewed inside a window as a registry-only change (no code, no migration, no flip). This is so a flag never expires mid-window; it is not a way to ship.
- **Every in-window change names its rollback** in the release or flip record, and its ops request (Q-04-T010).

## 3. Outside windows

- **Production promotes weekly on Thursday** at 10:00 CT (chapter 01 §1.3.3; the time is chapter 08's inference).
- **Flips** for firms outside their window may use any Tuesday or Thursday release day, with the same approval and rollback fields.
- **Merges batch on the Tue/Thu 17:00 CT windows** (F-01). Staging deploys once per batch. Never deploy per fix: a deploy costs build time and leaves every page's cache cold.

## 4. The hotfix lane

Only for three reasons, at any time, inside or outside a window:

1. Production is broken.
2. A security fix.
3. A founder explicitly asks for it now.

A hotfix still carries its rollback and a recurrence test (Q-03's escaped-defect rule). Inside a deadline week, a hotfix needs both founders' approval in the incident record.

## 5. Names in git

Pilot firms appear in git only as codes: `PF-` followed by a letter and digits (`PF-A1`), or a cohort code. Never a firm's name, domain or tenant UUID without its `code`. `make check-fast` refuses anything else in `deploy/windows.yaml` (Q-04 AC-1.3).

## 6. The calendar, 2027–2029

Reproduced from Q-04 §4.9. Verify each year against C21's due-date reference set before the R4 review.

| Window | Applies to | Dates | Mini-freezes | Deadline weeks (no promotion, no flip) | In-window Tuesday 19:00 CT slots |
|---|---|---|---|---|---|
| Autumn 2027 | Firms live on tax or EBP work | Wed Sep 1 – Wed Oct 20, 2027 | Sep 8–15, Sep 23–30, Oct 8–15 | Sep 13–17 (Wed Sep 15), Sep 27 – Oct 1 (Thu Sep 30), Oct 11–15 (Fri Oct 15) | Sep 7, Sep 21, Oct 5, Oct 19 |
| Season 2028 | Every live firm | Sat Jan 1 – Thu Apr 20, 2028 | — | Mar 13–17 (Wed Mar 15), Apr 17–21 (Tue Apr 18) | Every Tuesday except Mar 14 and Apr 18 (Jan 4 … Apr 11) |
| Autumn 2028 | Tax or EBP firms | Fri Sep 1 – Fri Oct 20, 2028 | Sep 8–15, Sep 25 – Oct 2, Oct 9–16 | Sep 11–15 (Fri Sep 15), Oct 2–6 (Mon Oct 2), Oct 16–20 (Mon Oct 16) | Sep 5, Sep 19 only |
| Season 2029 | Every live firm | Mon Jan 1 – Fri Apr 20, 2029 | — | Mar 12–16 (Thu Mar 15), Apr 16–20 (Tue Apr 17) | Every Tuesday except Mar 13 and Apr 17 |
| Autumn 2029 (after GA) | Tax or EBP firms | Sat Sep 1 – Sat Oct 20, 2029 | Sep 10–17, Sep 24 – Oct 1, Oct 8–15 | Sep 17–21 (Mon Sep 17), Oct 1–5 (Mon Oct 1), Oct 15–19 (Mon Oct 15) | Sep 4 only |

## 7. Approval

| Founder | Approved on |
|---|---|
| notanaskhan | |
| ayushkbhatia | |
