# EBP modes: the clearance path (A-05-T63; DEC-2818)

**Status on 2026-11-08: not cleared.** The five EBP modes of `workpapers.section_drafter`
(`ebp_provisions`, `ebp_attribute`, `ebp_reconcile`, `ebp_trust`, `ebp_form5500`) and
`related_parties` stay **synthetic-only**. The spec's `client_data` is `none`; a real firm gets 409
`drafting_not_enabled` (`agents/section_draft.py`); `evals/workpapers_section_drafter/clearance.yaml`
records no mode.

## What clears a mode
1. **Provider terms cover the route.** `docs/operations/provider-terms.yaml` has no approved
   Bedrock entry (`entries: []`), so no route may carry client data yet (ADR-114). Counsel's
   review, then the founder's approval, comes first (RB-40).
2. **A full-suite real run on Bedrock passes.** It runs
   `python -m abacus_tools.evals --agent workpapers.section_drafter --route bedrock` on a
   throwaway stack's synthetic firm, with every frozen threshold of each mode passing, no
   errored attempt, and median cost within 10 % of `evals/baselines.yaml`. This costs money, so
   it runs once the provider terms are approved, never speculatively.
3. **The report is signed and published.** CI signs the report with HMAC-SHA256
   (`ABACUS_EVAL_SIGNING_KEY`) and publishes it under this folder as
   `<date>-section-drafter-bedrock-passed.json`. A person then records each passing mode in
   `clearance.yaml` (path, sha256, signature, date, recorder).
4. **The spec turns `cleared`** only when every mode is recorded
   (`test_a05t63_ebp_clearance.py` fails otherwise).

## Shadow plan for PW4 (Apr 18, 2028)
- Until cleared, the EBP screens work agent-off on real firms: keyed or imported values with a
  required citation note (DV-EBP-07-1). A firm's first EBP season can run without the agent.
- Once cleared, each firm starts at the shadow stage for the drafter (ADR P-49, RB-39). The modes
  draft beside the team's own work on PF-X1's EBP slices and the firm's first engagement, and are
  scored, not shown. Promotion past shadow follows RB-39's criterion.
- Target: provider terms approved and the signed run published before the M15 bundle (Tue Dec 7,
  2027), so PW4 starts in shadow. If either slips, PW4 runs agent-off and this file records the
  slip.
