---
id: TASK-6128
title: "P-11-T33 per-firm OCR page caps, December x100 profile, TPS and 80% alarms"
spec: SPEC-000  # row (P-11-T33)
acceptance_criteria: [AC-1]
risk_zone: red
status: done
epic: P-11
plan_key: P-11-T33
branch: s30-p11-t33
worktree: /Users/ayushkbhatia/Accrued/abacus-s30
created: 2026-11-08
updated: 2026-11-08
---

## Objective
Production enablement before the Jan 1 window: December x100 OCR load profile (pages per minute, Textract TPS), per-tenant daily page cap and cost alarm, kill-switch drill, P-11 flag renewals in the Dec 14-18 bundle, per-firm flip checklist.

## Plan
- Migration 0714 `ocr_daily_caps`: insert-only (trust_kit_immutable), forced RLS; `set_by_kind` defaults from `app.actor_kind` and must be `system` (no firm session sets its own cap); a cap above 5,000 needs a second, different operator (R9 both founders); bounds 1..100,000; reason 10..500.
- `ocr_gate`: `daily_page_cap` (latest row else default), `pages_today`, `over_daily_cap` uses the firm's cap, `crossed_warning` and `warn_if_near_cap` (logs `ocr.daily_cap_warning`, ids and counts only, on the crossing read), `set_daily_page_cap` (uow + audit `ocr.daily_cap_set`). OCR step calls the warning after a completed read.
- `abacus_tools.ocr_daily_cap` ops command (refuses up front what the CHECKs refuse; `--show`).
- `abacus_tools.loadtest.ocr_capacity` plan and `scenarios/ocr_december.yaml` read-side profile.
- Terraform: Textract `request-rate` alarm (80% of DetectDocumentText quota), log metric filter + `ocr-daily-cap-80` alarm on worker log groups; ecs-service outputs `log_group_name`.
- RB-68: soak, profile inputs, caps, alarms, drill, flag renewals, per-firm flip checklist.
- Rollback: drop 0714 (gate falls back to the default cap); alarms are additive.

## Progress log
- 2026-11-08: built. Unit (37 incl. the adapted P-11-T25 cap test, same assertions) and infra test_textract pass locally. Migration integration test written, not run (end pass).

## Decisions made during this task
DEC-2715
