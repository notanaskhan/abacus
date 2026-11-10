---
id: RB-65
title: "SSE edge path: CloudFront, the internal ALB and the WAF carry server-sent event streams"
owner: builder
alarms: []
last_rehearsed: never
rehearse_by: 2027-12-17
---
# RB-65 · SSE edge path

| Field | Value |
|---|---|
| Owner | builder |
| Severity range | SEV3 (streams drop and clients fall back to 1 s polling) to SEV2 (no live run updates) |
| Source | P-10-T15; SPEC-647 AC-T1, AC-T5; P-10 §7 |

## What the edge must do
- **CloudFront (firm distribution):** the `/v1/*events` behavior is never cached or compressed and
  forwards every viewer header but Host (managed `AllViewerExceptHostHeader`), so `Last-Event-ID`
  and `Authorization` reach the API. The VPC origin waits 60 s for bytes; streams send `:hb` every
  15 s.
- **Internal ALB:** idle timeout 120 s.
- **WAF:** rule 1 (general rate, 2,000 per 5 min per IP) does not count `stream_path_regex`; the API
  caps streams at 6 per person.

## Apply (staging, then production on the Dec train)
1. `terraform plan` in `infra/envs/staging`; expect three changes: the ALB `idle_timeout`, the
   distribution's new ordered behavior and origin timeouts, and the WAF rule 1 scope-down.
2. Apply with the staging apply role; nothing else should change.
3. Verify through the VPC origin (below). Production: the same plan once `infra/envs/production`
   carries the API stack; until then the modules carry the setting and production inherits it.

## Verify
1. Sign in to staging, open a run with the dock, and confirm in the browser's network panel one
   `text/event-stream` request that stays open past 60 s with `:hb` lines every 15 s.
2. Drop the network for 10 s; the dock reconnects with `Last-Event-ID` and receives the missed
   events in order (AC-T1). The API log shows the header on the reconnect.
3. In WAF sampled requests for rule 1, no `/v1/*events` path appears.

## Roll back
Revert the three settings in Terraform and apply. Streams fall back to the client's 1 s polling
(SPEC-647 §3.8), so nothing is lost but latency.
