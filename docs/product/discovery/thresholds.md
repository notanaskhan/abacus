# Discovery and pilot thresholds (F-09-T14)

Written before the first discovery call, so the evidence cannot move the bar (chapter 11 §11.6.1). Numbers are from chapter 11 §11.6.2. The build plan's rule applies: **a threshold may be tightened later, never loosened.**

## Rules

1. This file merges before the first discovery call is held. The date it merged is the first line of the amendment log below.
2. **Tighten only.** A change that makes green harder to reach, or red easier to trigger, is allowed and is logged. Any change that does the opposite is refused, whatever the evidence says. If the evidence shows a threshold was badly chosen, the answer is a new signal added beside it, not an edit.
3. Definitions in this file are part of the threshold. A new definition that counts more things as "willing" or "accepted" is a loosening.
4. At each read, record **green**, **amber** or **red** for each signal, with the counts behind it, the date and the notes it came from. A read without counts is not a read.
5. Notes use firm codes only; no client data; no prices, contract text or names (see [`interview-guide.md`](interview-guide.md) and DEC-05).
6. **Amber** means fix inside the window and read again. **Red** means a kill-or-pivot review against the pivot menu (chapter 11 §11.6.3) by the date in the *Decided at* column. W3 red narrows the product rather than killing it (chapter 11 §11.6.1).

## Counting rules (part of the thresholds)

The plan states the numbers; these rules say what is counted. They were chosen when this file was first written.

- **Qualified conversation:** a held interview, against the guide, with a partner or manager at a firm that fits one of the three profiles in chapter 01 §1.6.4 (audit and employee-benefit-plan; extension-season tax on the firm's tax engine; client accounting services). Each firm counts once per signal, using the answer of its most senior participant. Interviews with seniors and audited-company controllers inform W3 and the decisions in the guide but are not in the W1 or W2 denominator.
- **Willing (W1):** the partner or manager says the firm would run the PBC list for at least one engagement of its own through a white-label client portal in the next 12 months. "Interested" or "would consider" is not willing.
- **Accept (W2):** the partner says the firm would rely on AI-screened evidence that cites its source, provided a named person on the engagement decides, for at least one engagement. A conditional answer counts as accept only when every condition is one the product already meets in the plan (citations verified, a person decides, firm opt-in).
- **Retrievable (W3):** each item on an anonymised, tagged request list gets a retrievability tier (A to E, `docs/specs/SPEC-022-classification-and-evidence-board.md`). Tiers A to C count as retrievable. The share is retrievable items over all items, pooled across lists, with at least 10 lists.

## Signals set now: W1 to W3

First read at **M3, Fri Nov 20, 2026**, on at least 15 held interviews and 10 tagged request lists.

| # | Signal | Measured where | Green: proceed | Amber: fix inside the window | Red: kill or pivot review | First read | Decided at | Owner |
|---|---|---|---|---|---|---|---|---|
| W1 | Firms willing to run at least one engagement's PBC on a white-label portal this year | Discovery notes | 50% or more of qualified conversations | 25% to 49% | Under 25% | M3 (Fri Nov 20, 2026) | M5 (Fri Jan 22, 2027) | builder |
| W2a | Partners willing to accept AI-screened, cited evidence | Discovery notes | 60% or more | 40% to 59% | Under 40% | M3 | M10 (Tue Jul 13, 2027) | builder |
| W2b | Screener agreement with staff decisions in the first firm's shadow stage | Shadow scoring | 90% or more | 80% to 89% | Under 80% | Mon Jul 12, 2027 | M10 | builder |
| W3a | Retrievable share (tiers A to C) on at least 10 tagged request lists | Discovery tagging | 30% or more | 15% to 29% | Under 15% | M3 | M14 (Fri Oct 15, 2027) | builder |
| W3b | Share of invited clients who connect a ledger in the second pilot window | Portal connections | 30% or more | 15% to 29% | Under 15% | Fri Oct 15, 2027 | M14 | builder |

W2b and W3b are measured later but their numbers are fixed now and cannot be loosened when the pilots start. W2 and W3 are decided at the dates shown; the earlier read does not decide them, it records where they stand.

## The three blanks in the build plan

The original build plan left three discovery thresholds blank: minimum retrievable share, share of controllers willing to grant ledger access, and share of partners willing to accept retrieved evidence. They map as follows.

| Build-plan blank | Where it lives here |
|---|---|
| Minimum retrievable share | W3a |
| Partners willing to accept retrieved evidence | W2a |
| Controllers willing to grant ledger access | W3b is the real test (invited clients who connect). The plan sets no separate discovery pass mark for this. In discovery the share of controllers willing to grant read-only access is tallied beside W3a as context, with no green, amber or red of its own. |

`docs/product/build-plan.md` currently has no section 4.1: its phase sections were replaced by the Accrued plan. The pointer line that F-09-T14 asked for has nowhere to go until a section exists; see the open items in the task log.

## Signals set later: W4 to W8

Not set yet. W4 to W8 are recorded in this file **before Mon Jan 11, 2027** (F-09-T62) and then follow the same rules, never loosened. Their subjects are listed so nothing is forgotten; chapter 11 §11.6.2 gives the plan's recommended values.

| # | Signal | Set by |
|---|---|---|
| W4 | Portal activation: invited client contacts who sign in | Mon Jan 11, 2027 |
| W5 | PBC items delivered through the portal | Mon Jan 11, 2027 |
| W6 | Median request to accepted, against the firm's prior-year baseline | Mon Jan 11, 2027 |
| W7 | Screener override rate in the live stage | Mon Jan 11, 2027 |
| W8 | Champion reliance: shadow exit | Mon Jan 11, 2027 |

W9 (paid conversion) and W10 (tax pilot) are outside this task and are set before their windows open.

## Reading log

One line per read. Counts only; no names.

| Date | Signal | Counts (yes / total) | Result | Notes used |
|---|---|---|---|---|
| | | | | |

## Amendment log (tightening only)

| Date | Change | Direction |
|---|---|---|
| 2026-10-20 | First version: W1, W2a, W2b, W3a, W3b and the counting rules | n/a |
