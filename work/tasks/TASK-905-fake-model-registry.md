---
id: TASK-905
title: Fake-model scenario response registry keyed by prompt and content hash (F-04-T19)
spec: SPEC-307
acceptance_criteria: [AC-6]
risk_zone: red
status: done
epic: F-04
plan_key: F-04-T19
branch: f04-t19-fake-model-registry
created: 2026-10-23
updated: 2026-10-23
---

## Objective
"Responses load from data keyed by prompt and content hash in synthetic environments only" (F-04.26).

## What changed
- **`FakeModel.record(prompt_ref, content_sha256, text)`:**
  - a recorded response is served before the prompt's responder;
  - it is served only when the request carries that content: the SHA-256 of the rendered input, or a document SHA-256 named in it.
- **Decision:** the provider request has no document field, so the key is matched against the request's content. This avoids threading a new field through the gateway.
- **`brightwater_hale/responses.py`:**
  - loads `responses/*.json` (`{prompt_ref, content_sha256, response}`), refusing a duplicate key, and `install(fake)`;
  - `responses/README.md` sets the rules: hand-written from the scenario documents, never model-generated, with citations verified by code.
- **Synthetic only:** `FakeModel` still refuses to exist outside local, test and evaluation, so recorded responses can't answer anywhere else.
- **Not done:** the E0 slice (F-04-T20) adds the response files.

## Progress log
- 2026-10-23: `tests/unit/ai_gateway/test_fake_model_registry.py` passes.
