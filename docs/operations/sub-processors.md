<!-- GENERATED from docs/operations/sub-processors.yaml. Do not edit. -->
<!-- Regenerate: python -m abacus_tools.codegen.sub_processors -->

# Sub-processors

Every party that runs part of Accrued or that our network reaches (P-67, ADR-154).
Client data stays in Accrued's AWS account, in the US. DPA status only, no terms.

## Sub-processors

| Party | Service | Role | Data seen | Client data | Region | DPA | Needed by |
|---|---|---|---|---|---|---|---|
| Amazon Web Services | AWS (incl. Bedrock, SES, KMS, S3, RDS; Textract later, P-32) | hosting, storage, model inference, email | all client data, encrypted; Bedrock processes prompts in the US with no training | yes | us-east-2, us-west-2 (+ us-east-1 for the global edge and Bedrock US Geo routing) | to-confirm | R0 |
| Temporal Technologies | Temporal Cloud | workflow orchestration | workflow metadata; payloads are encrypted with our codec before they leave | no | AWS us-east-2 (to verify) | to-confirm | R0 |
| WorkOS | WorkOS (AuthKit, SSO) | authentication | staff and client identities (name, email) and SSO metadata | yes | US (to verify) | to-confirm | R0 |
| Functional Software | Sentry (US) | error tracking | scrubbed events only (route, tenant UUID, error type) | no | US | to-confirm | R0 |
| Better Stack | Better Stack (uptime, status page, on-call) | uptime checks, status page, paging | none (synthetic checks and alert metadata) | no | to verify | to-confirm | R1 |
| DocuSeal | DocuSeal (cloud API, signing form, KBA) | e-signature and signer identity verification | documents sent for signature, signer identity answers (KBA) and signer evidence (IP, user agent) | yes | US (to verify) | to-confirm | R3 |

## Customer-authorised integrations (not sub-processors)

| Party | Service | Role | Data seen | Client data | Region | DPA | Needed by |
|---|---|---|---|---|---|---|---|
| Microsoft | Microsoft Graph | customer-authorised integration | what the customer authorises, from the customer's own tenant | yes | the customer's tenant | not-required | per integration |
| Intuit | QuickBooks Online | customer-authorised integration | what the customer authorises, from the customer's own company file | yes | vendor | not-required | per integration |
| Oracle | NetSuite | customer-authorised integration | what the customer authorises, from the customer's own account | yes | vendor | not-required | per integration |
| Xero | Xero | customer-authorised integration | what the customer authorises, from the customer's own organisation | yes | vendor | not-required | per integration |
| Sage | Sage | customer-authorised integration | what the customer authorises, from the customer's own account | yes | vendor | not-required | per integration |
| Wolters Kluwer | Wolters Kluwer tax and accounting products | customer-authorised integration | what the customer authorises, from the customer's own account | yes | vendor | not-required | per integration |

## Accrued's own operations (no client data)

| Party | Service | Role | Data seen | Client data | Region | DPA | Needed by |
|---|---|---|---|---|---|---|---|
| Anthropic | Anthropic API (direct) | evaluation runs only (staging) | none (synthetic data only) | no | US | not-required | R0 |
| GitHub | GitHub (source, CI) | Accrued's own source control and CI | none | no | US | not-required | R0 |
| Drata | Drata | Accrued's own compliance programme | none | no | US | not-required | R0 |

## Egress only (no data sent)

| Party | Service | Role | Data seen | Client data | Region | DPA | Needed by |
|---|---|---|---|---|---|---|---|
| ClamAV project (Cisco Talos) | ClamAV signature database | malware signature downloads for the scanner | none (downloads only) | no | global mirror | not-required | R0 |
