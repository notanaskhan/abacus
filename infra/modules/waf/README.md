# waf

A CloudFront-scope WebACL (chapter 06 section 1.13). Resources set `region = "us-east-1"` themselves, so callers pass no aliased provider. The portal distribution uses it today (Q-01-T56, `envs/staging/portal_edge.tf`); the firm distribution takes its own instance with Q-01-T15.

| Priority | Rule | Action |
|---|---|---|
| 0 | `auth-and-code-rate`: `auth_rate_limit` (30) requests per `rate_window_seconds` (300) per IP on `auth_rate_limit_paths` (`/v1/auth/`, `/v1/portal/auth/`) | always block, 429 `{"detail": "rate_limited"}` |
| 1 | `general-rate`: 2,000 per 5 minutes per IP | always block, 429 |
| 10 | `AWSManagedRulesAmazonIpReputationList` | `managed_rules_action` |
| 20 | `AWSManagedRulesCommonRuleSet`, with `SizeRestrictions_BODY` counted | `managed_rules_action` |
| 21 | `body-size-outside-uploads`: the body-size label on any path not matching `upload_path_regex` | `managed_rules_action` |
| 30 | `AWSManagedRulesKnownBadInputsRuleSet` | `managed_rules_action` |
| 40 | `AWSManagedRulesAnonymousIpList` | count only (offshore staff and VPN users are legitimate) |

- `managed_rules_action` is `count` for the first two weeks on a new environment, then `block`.
- Logging (rule 7) redacts `authorization` and `cookie`. It is created only once `log_destination_arn` names the Firehose stream in `log-archive`.
- AWS WAF acts on a rate rule a few seconds after the limit is crossed, so a fast burst can get slightly more than 30 requests through before the block starts.
- POR-17 respondent code verification has no route yet. Add its prefix to `auth_rate_limit_paths` when it lands.
