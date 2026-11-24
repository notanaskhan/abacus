---
id: TASK-8906
title: "C-02-T34: Vendor-screen capability close.agent mode vendor_screen"
spec: SPEC-000
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: red
status: in-review
branch: s53-c02t34
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-22
updated: 2026-11-22
plan_key: C-02-T34
---

## Objective
Read tools over masked vendor facts and W-9 regions, propose tool returning entity type, attorney flag and exemption with region citations as suggestions, ai_gateway route with TIN masking, register_suggestion_target applier in closes, spec enabled for synthetic firms only behind closes.vendor_screen; fake-model and Bedrock runs against T51's frozen suite with signed reports. Acceptance: on the synthetic Copperleaf vendors the agent proposes Hartwell & Lowe as an attorney with a verified W-9 citation, never adopts a value and never sees a TIN digit, and its Bedrock run meets every T51 threshold with the run committed.

## Done
- closes/agent.py: mode vendor_screen (prompt close.agent.vendor_screen@v1), CloseAgentInput.pages, VendorScreenOut/W9QuoteOut, settle_screen (offered entity type, W-9 exemption codes, offered pages, no 4-digit run → tin_in_output), fake answer (Hartwell & Lowe LLP, partnership, attorney)
- closes/vendor_screen.py: tools close.read_vendor_facts (masked, no TIN digit), close.read_vendor_document (evidence.masked_pages + scrub_digits), close.propose_vendor_classification (document_text citations verified first, then one suggestion on vendor_classification); screen_vendor run (synthetic only behind closes.vendor_screen, W-9 on file and scanned, inline capability run, escalates on refusal or unverified quote, shadow writes nothing); applier apply_vendor_classification (adopting person, vendor_1099.update, entity_type_source agent_suggestion_adopted)
- Route POST /v1/vendors/{id}/screen (matrix action vendor_1099.screen, agent deny); spec close.agent.yaml tools and untrusted inputs; _specs_v2, _matrix, security tests, route introspection, actions.gen.ts regenerated; 4 registry prompts; eval_suites EXTRA_MODES (vendor_screen on evals/close_vendor_screen)
- abacus_tools/evals/close_vendor_screen_run.py: every case through settle on the fake model (rates all at threshold, signed report), real direct/bedrock harness behind guard_real; __main__ runs the recorded grading then the capability run
- tests/unit/closes/test_c02t34_vendor_screen.py (13 pass)

## Progress log
- `2026-11-22` — Built in the S53 sequential stack (DEC-5908). Human remainder (DEC-5901): the Bedrock run in the evaluation account (python -m abacus_tools.evals --agent close_vendor_screen --route bedrock) and its committed signed report; real-firm enablement after it and a shadow.

## Plan (red)
1. Mode, settle and fake answer in `closes/agent.py`; tools, run and applier in `closes/vendor_screen.py`; registered from `agent_tools.py` (codegen imports it) and `api.py`.
2. Protected edits: matrix action `vendor_1099.screen`, spec `close.agent.yaml`, prompts; regenerate `_specs_v2`, `_matrix`, security tests, `_eval_suites`.
3. Eval: capability run over T51's frozen suite (fake now; Bedrock by a person).
4. Rollback: the route answers 404 with `closes.vendor_screen` off; no table changes.
