# Q-04-T202: the Aug 2028 flag-hygiene bundle, recorded at the S48 build (2026-11-17)

Row: every flag on at a tax or EBP firm (T-05, T-07, C-01, W-01, A-08, A-09) renewed past
Oct 20, 2028; `make flag-calendar` shows no expiry inside Sep 1 to Oct 20, 2028.

| Clause | State | Where |
|---|---|---|
| `make flag-calendar` | passes today | 129 flags; none expires inside a release window (`deploy/windows.yaml`: the autumn window applies only to firms live on tax or EBP work, and PF-X1 is synthetic, so no window binds a flag yet, DEC-68); none expires within 21 days |
| The six epics' flags (`closes.*`, `integrations.connect_v1`, `integrations.health_monitor`, `audits.analytics`, `audits.confirmations`, `audits.fieldwork_*`, `audits.ssars_workspace`, `assurance.group_audit`, `tax.*`, `platform.console`) | expire Feb 12 to May 13, 2027 | each before its first window; renewed in turn by its owner |
| Renewals past Oct 20, 2028 | cannot be written yet | a renewal runs at most 90 days from its own day (ADR-089) and 180 from the registry's rule (DEC-137); the Aug 24, 2028 train is the last renewal before the window, run then |

Flag calendar at main + the S48 stack (`python -m abacus_tools.codegen.feature_flags --calendar`):
3 flags expire 2027-02-11, 4 on 02-12, 1 on 02-13, 52 on 04-21, 1 on 04-26, 7 on 04-27, 4 on 04-28,
6 on 04-29, 3 on 04-30, 5 on 05-01, 25 on 05-07, 18 on 05-13.

**Partial (ops, dated):** the Aug 24, 2028 renewals and that day's calendar run. Nothing in code is
left for this row.
