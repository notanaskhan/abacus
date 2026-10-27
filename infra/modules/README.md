# modules

Local Terraform modules only (git, URL or bucket sources are refused by check_dependencies).

| Module | Used by | State |
|---|---|---|
| `github-oidc` | `bootstrap` | built |
| `previews` | `envs/shared` | built (Q-01-T49) |
| `cloudfront-portal` | `envs/staging` (`portal_edge.tf`) | built (Q-01-T56) |
| `s3-exports` | `envs/staging`, `envs/production` (`exports.tf`) | written, not applied (DEC-454) |
| `kms-export-signing` | `envs/staging`, `envs/production` (`export_signing.tf`) | written, not applied (G-02-T17, DEC-621) |
| `waf` | `envs/staging` (`portal_edge.tf`) | built (Q-01-T56, portal WebACL) |
| everything else | — | skeleton README only |

How to add a module, a bucket, a service or an egress host: `.claude/skills/infra-terraform/SKILL.md`.
