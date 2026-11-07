---
version: notices-responder-shadow-plan v1
updated: 2026-11-07
---
# notices.responder: clearance, shadow and live, per firm (N-04-T25)

The plan for the notices responder (library card #17), from evaluation to a firm's live stage.
N-04 §6 sets the rule; this page is how it runs. J09 P0 (Notices live at M15) does **not** wait on
any of it: the code analysis and the manual-entry path carry a notice end to end with the
responder off.

## 1. Clearance (once, for the platform)

1. **The CPA label review first.** The suite's position labels were set from the scenarios by the
   builder (`label_review: pending`, DEC-2312). A tax CPA reviews them; only then does the suite
   read `label_review: reviewed`. Until that, `analyze` cannot clear, whatever the run says.
2. **Direct, then Bedrock**, in the evaluation account, on synthetic data only:

   ```
   python -m abacus_tools.evals --agent notices.responder --route direct
   python -m abacus_tools.evals --agent notices.responder --route bedrock
   ```

   Each needs the route enabled with a parity report from the last 90 days (`guard_real`), and
   CI's signing key so the report is signed (HMAC-SHA256).
3. **Per mode.** The Bedrock report's `clearance` block says, for `analyze` and for `extract`,
   whether that mode cleared and every reason it didn't: a failed frozen threshold, an errored
   attempt, a median cost more than 10 % over `evals/baselines.yaml`, a pending label review, or a
   route other than Bedrock.
4. **Recorded by a person** in `evals/notices_responder/clearance.yaml`, one record per cleared
   mode, naming the signed report's sha256. The spec's `client_data` turns `cleared` only when
   every mode is recorded (`test_n04t25_clearance.py`). Until then the gateway refuses the
   responder for every real firm (SPEC-036), so no real firm can even reach shadow.

Extract cases need the notice's word layer (`document_lines`) before a real run reads them; a run
with any chosen extract case missing it fails and names the cases.

## 2. Shadow, per firm

A real firm reaches shadow only when all of these hold, recorded in its go-live dossier
(`docs/ops/go-live/<pilot-code>.md`, "Agents"):

| Record | Where |
|---|---|
| Clearance for both modes | `evals/notices_responder/clearance.yaml` |
| The firm's AI opt-in, current version of `ai-optin-briefing.md` acknowledged in writing | the vault; the dossier records date and version |
| The firm's ADM-04 AI policy allows the responder | the firm's AI policy screen |
| Stage `shadow` for the firm (the `notices.responder` flag retired, DEC-2602) | `agent_stages` (platform staff route) |

In shadow every analysis runs the responder and records its answer on the agent run; nothing is
shown (`recommended_position` is stored only from a live stage, 0650's CHECK).

## 3. Live, per firm

`set_agent_stage(..., "live")` refuses unless, as of the named shadow report:

- SPEC-036 Q1 and QD-10, as for every agent (50 runs over 14 days; 25 decided, at most 8 %
  disagreement, no DE-1, DE-4 or DE-5 miss);
- **N-04's rule** (`shadow_score.responder_criterion`): at least **28 days** since the first shadow
  run (`n04_shadow_weeks`), at least **10 compared notices**, each a shadow recommendation against
  the signer's decided position (`n04_compared_notices`), and **no disagreement on amounts**, that
  is no shadow answer code refused for a number without provenance (`n04_amounts`).

Then, outside the code: the first Tuesday 19:00 CT window after the criteria hold, and both
founders' written approval (ADR P-29 rule 3), recorded in the dossier.

## 4. Firms

There are no live pilot firms (DEC-1391). PF-X1 (Brightwater Hale, synthetic; DEC-1530) runs the
responder live through the synthetic pass, which is how the code paths are exercised; it proves
nothing about a real firm's shadow. Each real pilot firm gets a row here at onboarding:

| Firm | Opt-in acknowledged | Flag on | Shadow from | Compared notices | Live approved |
|---|---|---|---|---|---|
| PF-X1 (synthetic) | n/a (synthetic) | yes | n/a | n/a | n/a: synthetic pass |

At M15 (Fri Dec 10, 2027) no real firm is above shadow: four weeks of shadow cannot start before
clearance, which waits on the label review and the Bedrock run.
