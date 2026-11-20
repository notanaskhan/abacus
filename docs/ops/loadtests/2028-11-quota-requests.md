# Provider quota requests for the November 2028 x100 test (Q-03-T358)

**Human tickets.** Each request is raised by the account owner in the provider's console; nothing
here is sent by the build. Ticket numbers and confirmed limits are recorded when they come back,
never account ids (compliance rule 4). The test is Q-03-T376 (Nov 13–24, 2028) on the perf stack
with `scenarios/november_2028.yaml` (Q-03-T359).

Acceptance: "Every quota is confirmed before Mon Nov 13." **Open** until each row reads confirmed.

| Provider | What the x100 run needs | Basis in the profile | Ticket | Confirmed limit | Status |
|---|---|---|---|---|---|
| Amazon Bedrock (the approved model route) | concurrent invocations and tokens per minute for the agent mix on the synthetic tenants | `november_2028.yaml` runs no model call itself; the background agents of the x100 firm profile do (`make seed-staging PROFILE=x100`) | — | — | to raise |
| Amazon Textract | pages per second for evidence OCR during month-end intake | the x100 profile's PBC bursts (Q-03-T161) | — | — | to raise |
| Amazon SES | sending rate and daily quota on the perf stack's sink | the closing-date "ask the client" mails and notices | — | — | to raise |
| Intuit (QuickBooks Online sandbox) | API calls per minute per realm for reads and the W1 writes | `w1_post` (dry run, post, one replay) and the posting log, 22 closes posting in one hour (C-02-T43) | — | — | to raise |

Raise each at least one month before the window (ADR-075): by Fri Oct 13, 2028 in the plan's
calendar. A request that is refused or partly granted is recorded with the limit granted, and the
profile's `users` and `think_ms` are scaled to it before the run, never the targets.
