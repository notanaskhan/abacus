# Infrastructure

AWS for Accrued (code namespace `abacus`). Region **us-east-2**, DR **us-west-2** (DEC-03, ADR-142). Everything after the landing zone is Terraform (Q-01-T03); the console is used only for the one-time steps below, and every console step is logged here with date and operator (SPEC-050 AC-5). Never write a money amount in this repo: budgets refer to "the DEC-03 envelope", and the amount stays in the vault.

## 0. Layout and the rules for sessions

| Path | Holds | State |
|---|---|---|
| `landing-zone/` | SCP and AI opt-out policy documents pasted in section 1 | in use |
| `bootstrap/` | state bucket, GitHub OIDC, plan and apply roles (section "Terraform bootstrap") | applied by hand once |
| `envs/shared/` | PR previews (Q-01-T49); ECR and artifact buckets come with Q-01-T07 | built |
| `envs/staging/` | the portal edge (Q-01-T56, off until its tfvars are set); network, data and compute come with Q-01-T14 and T15 | partly built |
| `envs/production/`, `envs/production-dr/` | backend and provider only (Q-01-T28, T29) | skeleton |
| `modules/` | local modules; `modules/README.md` lists which are built | see there |
| `tests/` | offline assertions: no credentials, no plan (`infra.yml`, job `assertions`) | in use |

Rules (TASK-014 guardrails, SPEC-050 AC-6):

- **A session never applies.** It runs `terraform fmt`, `terraform validate` (after `init -backend=false`), the offline tests and `make check-generated`. `infra.yml` adds `tflint`, `trivy config` and the read-only plan on the pull request. The builder applies by hand, from a laptop SSO session, after the PR merges.
- **Nothing identifying is committed.** No account ID, domain, ARN with an account, secret or money amount. Values go in untracked `terraform.tfvars` files; each root has a `terraform.tfvars.example` with `.test` placeholders and `000000000000` for an account.
- **Every egress host has a sub-processor row.** A host in a `domains`, `*_domains` or `*_hosts` list in any `.tf` file without a row in `docs/operations/sub-processors.yaml` fails `make check-generated` (P-67, ADR-154).
- **How to add an egress host, a bucket or a service:** `.claude/skills/infra-terraform/SKILL.md`.
- Before touching staging, check that no deploy is in flight: `gh run list --workflow deploy-staging.yml --status in_progress` (the workflow arrives with Q-01-T18).

## 1. Landing zone (Q-01-T01, TASK-142) — one-time console steps

Do these signed in as the management account's root user only where a step says so; everything else through Identity Center. Policy documents to paste are in `infra/landing-zone/`.

1. **Management account.** Create (or pick) the account that will be the organisation's management account. Root user: hardware key or passkey MFA, no access keys. Enable IAM Identity Center's prerequisite: AWS Organizations, all features.
2. **Control Tower** in **us-east-2** (home region). Governed regions: us-east-2 and us-west-2. Leave Control Tower's own Region deny control **off**: `scp-region-guard.json` replaces it, because us-east-1 must stay open for the global edge and Bedrock US Geo inference only (SPEC-050 AC-1). Shared accounts Control Tower creates: `log-archive`, `audit`.
3. **Organizational units and accounts** (Account Factory): OU `Workloads` with `staging` and `production`; OU `Shared` with `shared`; OU `Sandbox` with `sandbox` (never holds data, D-OPS-03). Use plus-addressed emails on one mailbox you control.
4. **IAM Identity Center** (us-east-2): identity source = Identity Center directory; MFA = every sign-in, passkey or security key only, no SMS; one user for you.
   - Permission sets: `ReadOnly` (AWS `ReadOnlyAccess`, 8 h session) as the default on every account; `PlatformAdmin` (admin, 1 h session) on `shared`, `staging`, `sandbox`; `BreakGlassAdmin`, `abacus-retention-override`, `abacus-key-custodian` (1 h session) assigned only when needed.
   - Alert on elevated assignments: an EventBridge rule in the management account on CloudTrail `sso:CreateAccountAssignment` for those three permission sets → SNS topic → your email. Test it once.
5. **Service control policies** (Organizations → Policies → SCPs). AWS allows at most five SCPs on a target and Control Tower already uses some, so ours are combined. Attach at the **root**: `scp-region-guard.json` (us-east-2 and us-west-2 only; us-east-1 only for the global edge and Bedrock US Geo) and `scp-baseline-guards.json` (no IAM users or long-lived keys; protected CloudTrail, Config, GuardDuty, Security Hub, Access Analyzer, Macie). Leaving the organisation is already denied by AWS's managed account security policy on the root, and `aws-managed/` keeps a copy of AWS's region-restriction policy as it was enabled (`region-restriction.original.json` before our edit). SCPs never apply to the management account itself, so keep it empty of workloads.
6. **AI services opt-out** (Organizations → Policies → AI services opt-out policies): enable the policy type, create from `ai-services-opt-out.json`, attach at the root (ADR-114, SPEC-050 AC-4).
7. **Budgets** after DEC-03 is recorded: one budget per account at the DEC-03 envelope with 50/80/100 % alerts to your email. The amounts live in the vault, not here.
8. **Portal DNS** when F-09-T09 delivers the neutral portal domain: hosted zone in `shared`, delegate from the registrar. The portal edge then follows section "Portal edge".

### Open gap: 4-hour expiry on elevated assignments (SPEC-050 AC-3)

Identity Center caps how long a *session* lasts (1 h above) but cannot expire an *assignment*. Until Q-01 adds an automation (a scheduled function that removes `BreakGlassAdmin`, `abacus-retention-override` and `abacus-key-custodian` assignments older than 4 hours, or AWS's TEAM solution), remove the assignment by hand when done; the EventBridge alert in step 4 is the reminder. Recorded in TASK-142.

## 2. Your machine: SSO profiles

Add to `~/.aws/config` (fill in the start URL and account IDs from Identity Center; no keys are ever stored):

```ini
[sso-session accrued]
sso_start_url = https://<your-identity-center-id>.awsapps.com/start
sso_region = us-east-2
sso_registration_scopes = sso:account:access

[profile shared]
sso_session = accrued
sso_account_id = <shared account id>
sso_role_name = ReadOnly
region = us-east-2

[profile staging]
sso_session = accrued
sso_account_id = <staging account id>
sso_role_name = ReadOnly
region = us-east-2

[profile production]
sso_session = accrued
sso_account_id = <production account id>
sso_role_name = ReadOnly
region = us-east-2

[profile sandbox]
sso_session = accrued
sso_account_id = <sandbox account id>
sso_role_name = PlatformAdmin
region = us-east-2
```

Then `aws sso login --sso-session accrued`.

## 3. Checks (done when, SU-19)

```bash
aws sts get-caller-identity --profile shared                       # works over SSO
aws ec2 describe-vpcs --region eu-west-1 --profile sandbox         # AccessDenied ... explicit deny in a service control policy
aws ec2 describe-vpcs --region us-east-2 --profile sandbox         # works
aws iam create-user --user-name scp-test --profile sandbox         # AccessDenied (no IAM users)
aws organizations describe-effective-policy --policy-type AISERVICES_OPT_OUT_POLICY --profile shared
```

Record each result in the log below.

## Terraform bootstrap (SU-20)

One-time, run by hand on your laptop after the `shared` account and its SSO profile exist (section 2). Never from a session or CI. `infra/bootstrap` creates the state bucket (versioned, own KMS key, public access blocked, TLS-only, native S3 locking), the GitHub OIDC provider, a read-only plan role per environment (trusted for `repo:notanaskhan/abacus` `pull_request` and `main`) and an apply role per environment (trusted only for `refs/heads/main`). Nothing here contains an account ID: you supply them in an untracked file.

1. Create the variables file (git-ignored; `*.tfvars` is in `infra/.gitignore`):

   ```bash
   cp infra/bootstrap/terraform.tfvars.example infra/bootstrap/terraform.tfvars
   # edit it: set shared_account_id; add staging_account_id / production_account_id once those accounts exist
   ```

2. Sign in and initialise:

   ```bash
   export AWS_PROFILE=shared
   aws sso login --sso-session accrued
   terraform -chdir=infra/bootstrap init
   ```

   Staging and production roles use the `staging` and `production` SSO profiles (variables `staging_profile`, `production_profile`); run `aws sso login` for those too before the pass that includes them. Production needs a time-boxed elevated assignment.

3. Review, then apply:

   ```bash
   terraform -chdir=infra/bootstrap plan -var-file=terraform.tfvars -out=bootstrap.tfplan
   terraform -chdir=infra/bootstrap apply bootstrap.tfplan
   ```

4. Move the bootstrap state into the bucket it created (state then lives in S3 with locking; the local `terraform.tfstate` can be deleted after the migration succeeds):

   ```bash
   cp infra/bootstrap/backend.tf.example infra/bootstrap/backend.tf
   terraform -chdir=infra/bootstrap init -migrate-state
   ```

   Commit `backend.tf` (it holds no account ID). Re-apply later, with the extra account IDs, the same way.

5. Read the role names: `terraform -chdir=infra/bootstrap output`. A role ARN is `arn:aws:iam::<account id>:role/<role name>`; build it in your shell, do not paste it into the repo.

6. In GitHub, repository Settings, Secrets and variables, Actions, tab **Variables** (variables, not secrets; they are not in git), add the plan role ARN per environment: `AWS_PLAN_ROLE_SHARED`, `AWS_PLAN_ROLE_STAGING`, `AWS_PLAN_ROLE_PRODUCTION`, `AWS_PLAN_ROLE_PRODUCTION_DR` (the production account's `abacus-tf-plan-production-dr`). While a variable is unset, `infra.yml` skips that environment's plan with a notice. The apply role ARNs are not used by any workflow yet.

7. Log it in the console log below (date, operator, "terraform bootstrap applied").

Notes: the plan roles carry AWS `ReadOnlyAccess`, which can read objects in their own account, including state in `shared`; they are assumable only by workflows of this repository on pull requests and `main`. The apply roles carry `AdministratorAccess` bounded by the organisation SCPs until each environment narrows it. Environment backends use `use_lockfile = true` and the bucket's default KMS encryption.

## PR previews (Q-01-T49, D-OPS-13)

Opt-in only: `.github/workflows/preview.yml` builds nothing unless the PR carries the `preview` label. With it, each push runs `vite build --mode fixtures` (no backend, no database) into `s3://abacus-shared-previews/pr-<n>/` and comments `https://<preview host>/__preview/pr/<n>`; removing the label or closing the PR deletes the prefix, and the bucket expires everything after 14 days. The host answers 403 to any browser without the gate cookie. Module: `infra/modules/previews`. There is no Vercel or other hosted preview in this repo, so nothing else builds per push.

One-time, by hand, after `infra/envs/shared` is applied with the `shared` apply role or a `PlatformAdmin` session:

1. `terraform -chdir=infra/envs/shared output` gives `preview_host`, `preview_ci_role_name` and `preview_gate_store_name`.
2. Generate a gate key (at least 32 characters; e.g. `openssl rand -hex 32`) and keep it in the vault. Put it into the store; it never goes into git, Terraform or a PR:

   ```bash
   arn=$(aws cloudfront describe-key-value-store --name abacus-shared-previews-gate --query KeyValueStore.ARN --output text --profile shared)
   etag=$(aws cloudfront-keyvaluestore describe-key-value-store --kvs-arn "$arn" --query ETag --output text --profile shared)
   aws cloudfront-keyvaluestore put-key --kvs-arn "$arn" --if-match "$etag" --key gate-key --value "<gate key>" --profile shared
   ```

   Until the key is in the store, the host refuses every request. Rotate by putting a new value; old cookies stop working at once.
3. Repository Settings, Secrets and variables, Actions, tab **Variables**: `AWS_PREVIEW_ROLE` = `arn:aws:iam::<shared account id>:role/abacus-ci-previews` and `PREVIEW_HOST` = the `preview_host` output. While either is unset, `preview.yml` skips with a notice.
4. Create the `preview` label (Issues, Labels, New label).
5. Bookmark the founder-only link `https://<preview host>/__preview/login?k=<gate key>` and open it once per browser (the cookie lasts 14 days). Never paste it anywhere.
6. Check: label a PR; its comment link opens the fixture build; the same link in a private window answers 403; closing the PR leaves `aws s3 ls s3://abacus-shared-previews/pr-<n>/ --profile shared` empty. Log it below.

## Portal edge (Q-01-T56, OPS-14 part)

`infra/envs/staging/portal_edge.tf` with `modules/cloudfront-portal` and `modules/waf`: one CloudFront multi-tenant distribution for the client portal. The tenant `default` serves `*.<portal domain>` (every firm's default host) on a wildcard ACM certificate; the tenant `canary` serves one custom domain with its own CloudFront-managed certificate for pen test 1. Both serve the same portal entry and the same `/v1` origin, the internal API load balancer through a VPC origin. The WebACL blocks the 31st request in 5 minutes from one IP to `/v1/auth/` and `/v1/portal/auth/` (ADR-163; chapter 06 sections 1.12 and 1.13).

It plans to nothing until `portal_base_domain`, `api_vpc_origin_id` and `api_origin_domain_name` are set in the untracked `infra/envs/staging/terraform.tfvars`. It needs:
- the neutral portal domain registered (F-09-T09) with its hosted zone in `shared` (section 1, step 8);
- the staging load balancer and its CloudFront VPC origin (Q-01-T15).

One-time, by hand, with the staging apply role or a `PlatformAdmin` session:

1. `cp infra/envs/staging/terraform.tfvars.example infra/envs/staging/terraform.tfvars` and fill in the portal domain and the two API values. Leave `portal_canary_custom_domain` commented out. The domain must not contain the product name: the variable, and the API's settings, refuse it.
2. `terraform -chdir=infra/envs/staging init`, then `plan -out=portal.tfplan`. Expect the WebACL, the bundle bucket and its key, the wildcard certificate, the distribution, the `default` tenant, the entry function, the headers policy, the runtime-config parameter and the deploy policy. Nothing else should change.
3. Create the certificate first, so its validation record can exist before the distribution waits on it:
   ```bash
   terraform -chdir=infra/envs/staging apply -target='module.portal_edge[0].aws_acm_certificate.portal'
   terraform -chdir=infra/envs/staging output portal_certificate_validation_records
   ```
   Create that CNAME in the portal domain's hosted zone (`shared`), then run the full `apply`. It waits until the certificate is issued.
4. Point `*.<portal domain>` (CNAME) at the default connection group's routing endpoint (`aws cloudfront list-connection-groups --profile staging`).
5. Canary custom domain. Pick a domain you control that stands in for a firm's own domain. It must not be under the portal domain. CNAME `portal.<that domain>` to the same routing endpoint, set `portal_canary_custom_domain` in the tfvars, then plan and apply. CloudFront answers the managed certificate's HTTP validation itself. The tenant is ready when `aws cloudfront get-distribution-tenant --identifier <canary_tenant_id>` shows it deployed.
6. Attach `portal_deploy_policy_arn` to the staging deploy role (Q-01-T18), and switch `portal_managed_rules_action` to `block` two weeks after step 2 (chapter 06 section 1.13).

**Deploy path for the portal entry** (P-08-T07's `pnpm -C apps/web build:portal`, which writes `apps/web/dist/portal/`). `deploy-staging.yml` (Q-01-T18) runs these steps from the release's `s3://abacus-shared-artifacts/web/<sha>/portal/` once it exists; until then the builder runs them for the canary bring-up. The order matters: assets first, so the new entry never names a missing file.

1. `assets/` to `s3://abacus-staging-web-portal/assets/` with `Cache-Control: public, max-age=31536000, immutable`. Never `--delete`: the previous bundle's assets stay for rollback.
2. `portal.html` with `Cache-Control: no-cache`. Never `.vite/` (the manifest is for the bundle budget only).
3. `runtime-config.json` with `Cache-Control: no-cache`. Render it per release (platform-ops contract section 3.2): `portal_base_domain` from the SSM parameter `portal_runtime_config_parameter`, and `release` set to the git SHA.

No invalidation is needed, because entry files are never cached at the edge. Rollback puts back the previous `portal.html` and `runtime-config.json` (noncurrent versions are kept for 30 days).

**Checks** (log the results below):
- `curl -sI https://<slug>.<portal domain>/sign-in` and `curl -sI https://portal.<canary domain>/sign-in` both answer 200 with `portal.html`, `strict-transport-security` and `referrer-policy: no-referrer`. Each presents its own certificate (`openssl s_client -servername <host> -connect <host>:443`).
- `curl -s https://portal.<canary domain>/v1/portal/branding` answers from the API (same origin), and `/healthz` answers 403.
- From one address, send 31 `POST /v1/portal/auth/start` requests within 5 minutes. The 31st (give or take WAF's few seconds of lag) answers 429 `{"detail": "rate_limited"}`, and the `auth-and-code-rate` metric shows the blocks.

## Pen-test review role (Q-02-T35, DEC-306)

`infra/envs/staging/pentest_review.tf` and `infra/envs/production/pentest_review.tf`, with `modules/pentest-review-role`, create one role per account for the tester's read-only AWS configuration review (chapter 06 section 5.6). The tester's own role assumes it with the agreed external ID and MFA, and only inside the test window. It attaches `SecurityAudit` and `ViewOnlyAccess` and denies every data read: object bodies, decrypt, secrets, parameters, log events, items, sessions and role chaining. The window is enforced by the trust policy itself, so the role refuses every assume after `pentest_review_ends_at` even if nobody removes it.

Written in TASK-1176 and **not yet initialised, validated, planned or applied**. It plans to nothing until `pentest_review_principal_arn` is set in the untracked `terraform.tfvars`.

By hand, once the rules of engagement are signed (vault), in each of `staging` and `production`:

1. Put the tester's role ARN, the external ID (at least 32 characters, from the vault) and the window (RFC 3339, UTC) in the untracked `terraform.tfvars`. `terraform.tfvars.example` shows the shape.
2. Run `terraform -chdir=infra/envs/<env> init`, then `validate`, then `plan -out=review.tfplan`. Expect four things and nothing else: the role, its two attachments and the inline deny.
3. Apply it. Give the tester the role name and the account ID through the vault, never in git or a ticket.
4. Check it from your own session, as the tester would: an assume without the external ID is refused. As the role, `s3:GetObject` on an evidence object and `secretsmanager:GetSecretValue` are both refused.
5. After the window, set `pentest_review_principal_arn = null` and apply. That removes the role. Record both applies in the console log below.

## Exports bucket (A-01-T18/T19 follow-up, DEC-454)

`infra/envs/staging/exports.tf` and `infra/envs/production/exports.tf`, with `modules/s3-exports`, create `abacus-<env>-exports`: private, TLS-only, SSE-KMS under its own rotating key, versioned, no Object Lock (a policy deny refuses it), a put naming another key refused, current objects expiring after 6 days and their noncurrent copy 1 day later (gone within 7), incomplete multipart uploads after 1 day. The key policy lets the account administer the key but not use it: only the task roles named in `worker_task_role_name` and `api_task_role_name` may, through S3, for this bucket. Two managed policies come with it: `abacus-<env>-exports-worker` (list the `exports/` prefix; put, get and delete `exports/*`; the key through S3) and `abacus-<env>-exports-api` (get `exports/*`; decrypt through S3). The app reads the name from `ABACUS_EXPORTS_BUCKET`; unset, an export build fails closed.

Written in TASK-1361 and **not yet initialised, validated, planned or applied**. It needs nothing else in the root, so the next plan of each environment shows it.

By hand, in `staging` first, then `production`, with no deploy in flight:

1. Run `terraform -chdir=infra/envs/<env> init`, then `validate`, then `plan -out=exports.tfplan`. Expect the bucket and its six companions (ownership, public access block, versioning, encryption, lifecycle, policy), the key and its alias, and the two policies; with `worker_task_role_name` and `api_task_role_name` set, their two attachments too. Nothing else.
2. Apply it and record the apply in the console log below.
3. Put the API and worker task role names in the untracked `terraform.tfvars` and apply again: until then nobody can use the bucket's key, so exports fail closed. Until Q-01-T15 renders the task definitions from Terraform, set `ABACUS_EXPORTS_BUCKET=abacus-<env>-exports` and `ABACUS_EXPORTS_BUCKET_OWNER=<the account number, from the vault>` in the API's and the worker's environment the way the other `ABACUS_*` settings are set today.
4. Check it: an engagement export on the synthetic tenant reaches `ready` and downloads; as the API role, `s3:PutObject` into the bucket is refused; `aws s3api get-bucket-lifecycle-configuration` shows the 6-day rule and the 1-day noncurrent rule.

## Export-signing key (G-02-T17, DEC-621)

`infra/envs/<env>/export_signing.tf` with `modules/kms-export-signing` creates the environment's asymmetric key (`ECC_NIST_P256`, `SIGN_VERIFY`) behind `alias/abacus/<env>/export-signing`, and `abacus-<env>-export-signing-worker` (`kms:Sign` with `ECDSA_SHA_256` on that key only). The account administers the key and cannot sign; only the worker role named in `worker_task_role_name` may, over a digest.

Written in TASK-1480 and **not yet initialised, validated, planned or applied**. By hand, `staging` first, then `production`, with no deploy in flight:

1. `terraform -chdir=infra/envs/<env> init`, `validate`, `plan -out=signing.tfplan`. Expect the key, its alias and the policy (and its attachment once the worker role name is set). Nothing else.
2. Apply it and record it in the console log below.
3. Publish the public key: `aws kms get-public-key --key-id alias/abacus/<env>/export-signing`, converted to PEM, into `docs/operations/export-signing-keys.md` with the date. Never commit anything but the public key.
4. Set `ABACUS_AUDIT_EXPORT_SIGNING_KEY_ALIAS=alias/abacus/<env>/export-signing` in the worker's environment. Until then every audit export fails `signing_unavailable` (fail closed).
5. Check it: an audit export on the synthetic tenant reaches `ready`; `openssl dgst -sha256 -verify` with the published key accepts its `manifest.sig`.

## 4. Console log

Every one-time console step, newest last. Operator is the person at the keyboard.

| Date | Operator | Account | Step | Result |
|---|---|---|---|---|
| | | | | |
