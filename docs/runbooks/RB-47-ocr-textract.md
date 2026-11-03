---
id: RB-47
title: OCR on Textract — throttling and error alarms, the kill switch, provider terms
owner: builder
alarms: [abacus-<env>-textract-throttled, abacus-<env>-textract-usererrorcount, abacus-<env>-textract-servererrorcount]
last_rehearsed: never
rehearse_by: 2027-11-12
---
# RB-47 · OCR on Textract: throttling and error alarms, the kill switch, provider terms

| Field | Value |
|---|---|
| Owner | builder |
| Severity range | Throttling or errors that stop OCR for a firm: SEV3 (uploads still land; the viewer shows the page image). A page image or OCR text reaching AWS for a firm whose terms do not cover it: SEV1, go to RB-08 |
| Linked from | The Textract alarms (`infra/modules/textract`), the OCR gate's refusals (P-11-T23) |
| SLO affected | none |
| Kill switches that apply | The platform's `model_route_block` on route `textract` (every firm) and the firm's OCR flag |
| Rehearse by | Fri Nov 12, 2027, on staging with the synthetic test firm PF-X1 (Brightwater Hale; DEC-1530) |
| Last rehearsed | never |
| Last reviewed against an incident | never |

## A. Throttled (`textract-throttled`)
1. The port retries throttling with backoff and then refuses the page (`ocr_throttled`); nothing
   is lost: the evidence version stays and the viewer shows its image.
2. Read the alarm's period: one burst after a bulk upload clears on its own. A sustained alarm
   means the account's Textract quota is too low for the volume: request a quota increase in the
   AWS console (a human step) and note it in the incident register.

## B. User or server errors (`textract-usererrorcount`, `textract-servererrorcount`)
1. User errors are documents Textract refuses (format, size, page count): they surface as the
   page's refusal reason and need no action unless the count climbs for one firm.
2. Server errors are AWS's: check the AWS Health dashboard. If they persist, block the route
   (§C) until AWS recovers.

## C. Stop OCR
1. Every firm: set `model_route_block` on route `textract` (platform console). The OCR gate
   refuses with `kill_switch` first; uploads continue without layers.
2. One firm: turn the firm's OCR flag off; the gate refuses with `flag_off`.
3. Restore in reverse; pages uploaded while blocked are re-read by asking for OCR again.

## D. Provider terms
The gate refuses `terms_not_covering` unless the firm's provider-terms entry records the AWS
AI-services opt-out. If a page reached AWS without it, treat it as SEV1 under RB-08: block the
route, record what was sent (image hashes only), and follow the disclosure steps there.
