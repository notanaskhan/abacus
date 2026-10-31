# Matcher v3: Bedrock rerun, clearance and shadow stage (N-01-T26)

Status note for TASK-2334 (DEC-1380). The code half is merged with this task; the steps below are the
operator's and the founder's, in order. No step uses real client data until step 4 is done, and
nothing a shadow run produces is shown to anyone (SPEC-036 D2).

| # | Step | Who | Evidence it leaves | State 2026-10-31 |
|---|---|---|---|---|
| 1 | Provider terms entry for the Bedrock route (ADR-114): documents, no training, retention, US region, subprocessors, breach notice, counsel then founder approval | Founder, counsel | An entry in `docs/operations/provider-terms.yaml`, regenerated `kernel/_provider_terms.py` | **Open**: the register has no entries, so no route may carry client data |
| 2 | Bedrock route parity on synthetic data: `make route-parity ROUTE=bedrock` | Operator (AWS credentials of the eval account) | `docs/operations/route-parity/bedrock-<date>.json` | **Open** (only `direct-*` reports exist) |
| 3 | Bedrock rerun of the matching suite, intake section, at the protected thresholds, in the evaluation environment (`ABACUS_ENVIRONMENT=evaluation`): `make evals EVAL_ARGS="--agent evidence.matcher --route bedrock --section intake"`; copy the passing report to the path on the right | Operator | `docs/operations/matching/bedrock-<date>-passed.json`; its per-file cost is checked against `evals/baselines.yaml` ($0.015, gate +10 % = $0.0165) | **Open**: costs model spend; ask before running |
| 4 | Clearance record: set `client_data: cleared` in `backend/src/abacus/modules/agents/specs/evidence.matcher.yaml` and regenerate (`python -m abacus_tools.codegen.agent_specs`); `check_clearance` refuses it without steps 2 and 3's reports | Founder | The spec change and regenerated `_specs.py` in one PR | Waits on 1–3 |
| 5 | Shadow stage for each PW1 firm that opted in (TASK-076): `make agent-stage FIRM=<id> AGENT=evidence.matcher STAGE=shadow NOTE="N-01-T26 shadow"` | Founder | An `agent_stages` row per firm, audited | Waits on 4 |
| 6 | Live stage per firm: `make shadow-report FIRM=<id> AGENT=evidence.matcher`, then `make agent-stage ... STAGE=live REPORT_SHA=<sha256> REPORT_AS_OF=<as_of>` | Founder | The stage row naming the report's digest | Waits on the shadow score: at least 50 runs over 14 days, 25 scored decisions, override at most 8 %, no DE-4 or DE-5 miss |

## What the code half does (this task)

- **Shadow output is never shown.** `agents/intake_candidates.py` offers only a live run's proposals,
  so a shadow run neither reaches INB-02's candidates nor raises `ambiguous_candidates`.
- **The matcher is scored.** `agents/shadow_score.py` scores each attachment's newest shadow run
  against the person's triage decision (`communications.api.triage_outcomes`): filed where it
  proposed, or ignored or held after a none-fit, agrees; anything else is an override. The live guard
  (`stage_admin.check_live`) reads that score, so live waits on the override rate staying within 8 %.
  `live_override` gives Q-04's W7 the same measure over live runs.
- **The cost baseline is protected.** `evals/baselines.yaml` holds the matcher's $0.015 a file; a
  real-model run more than 10 % over it fails `cost_regression`.

If clearance slips, firm intake runs code-only at M10 (N-01 R7): rule and content suggestions only,
and no client sees anything either way.
