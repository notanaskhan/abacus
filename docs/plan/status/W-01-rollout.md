# W-01 rollout plan (W-01-T21; W-01 §10 item 2; DEC-5423)

| When | What | Who | Evidence |
|---|---|---|---|
| Thu Aug 24, 2028 train | Renew `integrations.connect_v1` and `integrations.health_monitor` (registry renewal; ADR-089 ≤ 90 days; no expiry inside Sep 1 – Oct 20) | notanaskhan | `make flag-calendar` shows no window column for either flag |
| before Tue Aug 29 | Production catalogue import (`abacus_tools.integration_catalog import`, `connect_v2.yaml`) logged with both founders' approval | notanaskhan, ayushkbhatia | the import's operator log line and the approvals in the slot ticket |
| Tue Aug 29, 2028, 7 pm CT | Canary flip: `connect_v1`, then `health_monitor` (RB-01 W-01 section, written rollback) | both founders | `j14 3` and `j14 3d` green against the canary |
| Thu Aug 31, 2028 | Last pre-window promotion of W-01 code (dark for real firms) | notanaskhan | release train log |
| from Tue Oct 24, 2028 | Real-firm flips, one Tuesday per firm (or the full P-29 checklist for an earlier ask) | both founders | per-firm slot tickets |

**Not done here (human steps):** the production import, the canary flip and the tickets are filed in
their slots. The W-01-T20 delta pen test is deferred (DEC-1389).
