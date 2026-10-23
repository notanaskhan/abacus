# previews

PR preview host (Q-01-T49, D-OPS-13; chapter 06 section 2.7). Used by `envs/shared`.

- `abacus-shared-previews`: private, TLS-only, versioned, SSE-KMS with its own key; everything expires after 14 days, noncurrent versions a day after deletion.
- CloudFront with origin access control. A viewer-request CloudFront Function (`gate.js`) answers 403 unless the request carries the gate cookie, whose value must equal `gate-key` in the associated KeyValueStore. The key is put into the store by hand, never by Terraform, so it is in neither git nor state.
- `abacus-ci-previews`: assumable through GitHub OIDC by this repository's `pull_request` workflows only; it may list, put and delete under `pr-*` and nothing else.

Links (the host is the `host` output):

| Link | Effect |
|---|---|
| `/__preview/login?k=<gate key>` | Founder-only. Sets the gate cookie for 14 days. Never paste it into a PR, issue or commit |
| `/__preview/pr/<n>` | With the gate cookie: selects PR `<n>` and redirects to `/`. This is the link preview.yml comments |
| anything else | With both cookies: served from `pr-<n>/`; a path without an extension serves the SPA's `index.html` |

The bundle is the ordinary fixture build at the root path, so a browser shows one PR at a time.
