---
name: infra-terraform
description: How a session changes infra/ — plan only, never apply — and the recipes for adding an egress host, a bucket or a service, including the sub-processor register rule. Use for any change under infra/ or to docs/operations/sub-processors.yaml.
---

# Terraform pattern (plan only)

Binding: ADR-142 (AWS topology and regions), ADR-087 (environments), ADR-154 (P-67, the sub-processor register), ADR-163 (the portal domain is a setting), SPEC-050. Read `infra/README.md` section 0 first. Copy `infra/modules/previews` (a bucket, a key, CloudFront) and `infra/modules/cloudfront-portal` (a multi-tenant edge with optional tenants) rather than writing from memory.

## 0. What a session may run

| Allowed | Never |
|---|---|
| `terraform fmt -recursive infra` | `terraform apply`, `destroy`, `import`, `state` (the shell hook refuses the last three) |
| `terraform -chdir=infra/<root> init -backend=false -input=false` then `validate` | `terraform plan` from the session: plans run in `infra.yml` on the pull request, with the read-only plan role |
| `cd backend && uv run pytest --import-mode=importlib -q ../infra/tests` | any AWS credential or profile; `aws` CLI calls of any kind |
| `make check-generated` (the sub-processor register drift check) and `make check-fast` | writing an account ID, domain, ARN with an account, secret or amount into git |

The pull request's `infra / plan` comment is the plan. The builder reads it, merges, and applies by hand (`infra/README.md`). Write the apply steps and the checks the builder runs into `infra/README.md` in the same PR. A session that needs something applied says so in its task file under "Not done (needs the builder)" and stops there.

Before any change: `git fetch origin` and branch off `origin/main`. Say "holding for the batch" in the PR: infra changes ship with the sprint's batch, like everything else.

## 1. Add an egress host

An egress host is any name the `app` subnets may resolve: the DNS Firewall allowlist (SPEC-050 AC-22). Every one needs a row in the sub-processor register, in the same PR. `make check-generated` scans every `infra/**/*.tf` for the strings in a `domains = [...]` list or any `*_domains` / `*_hosts` list, and fails on a host that no row covers.

1. **Register row first.** Edit `docs/operations/sub-processors.yaml` (protected by rule: change it deliberately, with the Terraform that needs it):
   - the party already has a row: add the host to its `egress_hosts`;
   - a new party: add a row with every field (`id`, `party`, `service`, `kind`, `role`, `data_seen`, `client_data`, `region`, `dpa`, `needed_by`, `egress_hosts`, `references`). Use `dpa: to-confirm` until F-09 confirms it. Write no terms and no prices.
   A row covers a host when one of its `egress_hosts` equals it, or is `*.<suffix>` and the host ends in `.<suffix>`. Prefer the exact host over a wildcard.
2. **The Terraform list.** Add the host as a plain string literal to the allowlist list (`domains = [...]` in `modules/dns-firewall`, built by Q-01-T14; until then, the list the environment's task names). Never build a host from an interpolation: the check reads literals only, so an interpolated host escapes the register. A list whose name ends `_domains` or `_hosts` is always scanned, so never put a non-egress name (an alias, a certificate SAN) in one.
3. **Regenerate the Markdown:** `cd backend && uv run python -m abacus_tools.codegen.sub_processors`. Never hand-edit `docs/operations/sub-processors.md`.
4. **Check:** `make check-generated` passes, then `fmt`, `validate` and the infra tests (section 0).
5. **Client data?** If the party can see client data (`client_data: true`), it is a sub-processor, and it also needs the provider-terms register (ADR-114) and the ADM-04 disclosure (generated, C-03). Stop and add it to the task's questions if those are not in scope.

To prove the check holds, a session can add a host without its row and watch `make check-generated` fail, naming the host and the file. Then add the row.

## 2. Add a bucket

Every bucket in `infra/` is held to `infra/tests/test_repository_files.py`. Copy `aws_s3_bucket.previews` and its neighbours:

- `aws_s3_bucket_public_access_block` with all four settings `true`;
- `aws_s3_bucket_versioning` `Enabled`;
- `aws_s3_bucket_server_side_encryption_configuration` with `aws:kms` and a named key (`kms_master_key_id`), `bucket_key_enabled = true`;
- `aws_s3_bucket_ownership_controls` `BucketOwnerEnforced`;
- a bucket policy whose document denies `s3:*` when `aws:SecureTransport` is `"false"`;
- a lifecycle rule for noncurrent versions and incomplete uploads;
- Object Lock only for `evidence` and `records` (D-OPS-06); never for anything else.

Name buckets `abacus-<env>-<purpose>`. CloudFront reads through origin access control with an `aws:SourceArn` condition on the distribution, never through a public policy. A bucket that holds client content is a data-plane change: it is red, so write the plan in the task file first.

## 3. Add a service

A service is a new ECS service, a new AWS service used by the app, or a new edge resource.

- **Region.** Resources go in us-east-2 (DR us-west-2). Only the global edge (CloudFront, WAF, ACM for CloudFront) and Bedrock US Geo routing use us-east-1. Use the resource's own `region = "us-east-1"` (provider v6), as `modules/waf` and the portal certificate do, or a provider alias named `edge`. The tests refuse any other region.
- **Module.** Put the resources in `infra/modules/<name>/` with `versions.tf` (`required_version = "~> 1.10"`, `hashicorp/aws ~> 6.0`), `variables.tf` (typed, described), `main.tf`, `outputs.tf` and a `README.md`. Only local module sources; no registry, git or URL modules (check_dependencies).
- **Wiring.** The environment root calls the module with variables. Gate it with `count` on the settings it needs, so a root without its tfvars plans to nothing (see `envs/staging/portal_edge.tf`). Values that identify anything go in the untracked `terraform.tfvars`; add a placeholder line to `terraform.tfvars.example` (`.test` domains, `000000000000` accounts).
- **IAM.** No IAM users or access keys (the tests refuse them). Roles are assumed through GitHub OIDC or ECS task roles. Scope actions to named ARNs. Give a deploy permission as a managed policy that the deploy role attaches, as `aws_iam_policy.deploy` in the portal module does.
- **Network egress.** If the service calls out of the VPC, it adds an egress host (section 1).
- **Alarms.** A CloudWatch alarm carries a runbook URL in its description (ADR-098), pointing at `docs/runbooks/<slug>.md`.
- **Settings.** A new `ABACUS_*` setting goes in `kernel/config.py` with a classification, and in the task definition rendered by Terraform. A setting that names a host is never a code constant (ADR-163).
- **New providers or tools** need a row in `docs/architecture/dependency-allowlist.yaml` (`terraform:` section) first.

## 4. Tests for a change

Add offline assertions to `infra/tests/` for what the change promises (copy `test_portal_edge.py`: parse the `.tf` text, run a CloudFront Function under `node`). They run in `infra.yml`'s `assertions` job with no credentials. Never weaken an existing assertion to fit a change.
