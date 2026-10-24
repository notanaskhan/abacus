---
id: TASK-1170
title: Classification flags (tri, phi, pii_kind) and the gateway's pii_in_context refusal (Q-02-T32)
spec: SPEC-036
acceptance_criteria: [AC-2]  # SPEC-036's refusal before any network call; the Q-02 epic ACs proved here: AC-19 to AC-22 (ADR-167 §1, §2)
risk_zone: red
status: done
epic: Q-02
plan_key: Q-02-T32
branch: s7-classification-flags
created: 2026-10-24
updated: 2026-10-24
---

## Objective
"A model call whose context holds an unmasked SSN is refused before any network call, and no tagged value appears in logs or Sentry in the scrubbing test." Built on ADR-167 (accepted 2026-10-24) §1 and §2. §3 (the consent gate, C19) is T-01's and is not built here; no consent text is written.

## Plan (red zone)
- **Kernel, `kernel/classification.py`:** `classified(level, *, tri=False, phi=False, pii_kind=None)`; any flag on a level other than `restricted` raises at class definition (import). The flags are written beside the level in the field's JSON schema extra (`cls`, plus `x-tri`, `x-phi`, `x-pii-kind`; DEC-295). `PiiKind` (`tin`, `bank_account`, `date_of_birth`, `ip_pin`), `Flags`, `flags_of`, `flag_errors`, `tri_paths`, `phi_paths`, `pii_paths` (type-level walk, nested models and containers included, cycle-safe, cached) and the one `mask(value, kind)`.
- **Kernel, `kernel/tin_patterns.py` (new):** the SSN, ITIN and EIN validity rules as code, `find_tins(text)` (unmasked nine-digit forms that pass a rule, NFKC-normalised, alphanumeric boundaries, decimal amounts excluded) and `scrub_tins(text)` (each match replaced by `mask(.., "tin")`). In the kernel so the log, Sentry and metric scrubbers share the gateway's rules (the kernel cannot import the gateway, ADR-101; DEC-295).
- **Scrubbing:** `kernel/logging.py` masks TIN patterns in every string field (models with Restricted fields are still refused, as today); `kernel/error_tracking.py` masks them in every string the allowlisted event keeps; `kernel/metrics.py`'s `meter()` hands out counters and histograms that mask them in attribute values.
- **Gateway:** `ai_gateway/pii.py` (new) scans the system prompt and every context layer, naming the part (`instructions`, `firm`, `engagement`, `examples`, `task`, `untrusted`); `boundary.py` gains reason `pii_in_context` (appended to `REASONS`, so earlier indices keep their meaning) and one `_refuse` used by both refusals; `_call` scans before anything else (no budget read, no admission, no usage record, no provider). Audited `ai.boundary_refused` with `Ref(reason, part)` indices only; never retried or rerouted; on every route, `fake` included.
- **Tags:** `organisations/contract.py` `MaskedTinOut.last4` and `TinRevealOut.value` carry `pii_kind="tin"`; `mask_tin` uses `mask()` for the SSN/ITIN form.
- **Classification-tag check:** the all-models test also checks every field's flags (`flag_errors`); banned pattern `CLS-001` refuses the flag keys as string literals outside `kernel/classification.py`, so flags are set only through `classified()` and read only through the helpers.
- **Regenerate:** `make regenerate` (the OpenAPI document carries the new `x-pii-kind`).
- **Tests:** `tests/unit/kernel/test_classification_flags.py` (AC-19, AC-20), `tests/unit/kernel/test_tin_patterns.py` (validity rules, property tests), `tests/unit/kernel/test_pii_scrubbing.py` (AC-21: one log line, one Sentry event, one metric attribute), `tests/unit/ai_gateway/test_pii_in_context.py` (AC-22, property test over every context part), banned-pattern rule test.
- **No migration**, no new route, action or flag.
- **Rollback:** revert the commit; nothing persistent changes (the new audit reason index 6 stays readable as an integer).

## Progress log
- 2026-10-24: built as planned. Flags, path helpers and `mask` in `kernel/classification.py`; validity rules and the text scan in `kernel/tin_patterns.py`; the backstop in log lines, kept Sentry events and metric attributes (`ScrubbingMeter`); the gateway's `pii_in_context` refusal (`ai_gateway/pii.py`, `boundary._refuse`), first in `_call`; P-07-T10's `MaskedTinOut.last4` and `TinRevealOut.value` tagged `pii_kind="tin"`; CLS-001 and the all-models flag check; `make regenerate` (the OpenAPI document gains two `x-pii-kind`; the generated client is unchanged). Tests: unit, contracts and security 26484 passed, 4 xfailed; `tests/integration/agent_tests` 844 passed; `test_tin_reveal`, `test_telemetry_tunnel`, `test_q01_telemetry_tunnel_acceptance`, `test_q02_attribution_access_acceptance` 145 passed; web `src/status` and `src/fixtures/contracts` 160 passed; `make check-fast` green. **Open (DEC-295):** `ai_gateway.embed` is not scanned (retrieval embeds evidence chunks); decided with P-03's masked material. Q-02-T52 writes the independent AC suite.
- 2026-10-24: security review fixes. (1) The gateway scans the task JSON's values decoded and the task JSON and untrusted blocks as separate segments, so an escape beside a TIN no longer hides it. (2) Boundaries are any non-digit: commas, dots, letters and escapes no longer hide a TIN; a longer digit run still is not one. My first tests asserted that `123456789.25`, `x123456789` and a nanosecond timestamp pass; those expectations were the defect and now assert refusal. (3) Separators: dots, slashes, spaces, mixed and spaced dashes, `ddd ddd ddd`; zero-width characters stripped and every script's decimal digits read as ASCII; UUIDs and long hex runs skipped. (4) `service.TERMINAL` holds `DataBoundaryRefused`: screening retried a refusal; a test runs each of the five agent activities. (5) Self-referential models unroll to `MAX_DEPTH`; the logger's event string is scrubbed too. DEC-295 updated with the known limits. Tests: unit, contracts and security 26501 passed, 4 xfailed; `tests/integration/agent_tests` plus the TIN and telemetry files 989 passed; ruff, pyright, banned_patterns, validate_docs, error_codes, secrets_scan and `make check-fast` green.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-295 | ADR-167 leaves the schema key, the initial members, where the validity rules live and the part names open | No (ADR-167, ADR-031) |
