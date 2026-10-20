# Infrastructure

AWS for Accrued (code namespace `abacus`). Region **us-east-2**, DR **us-west-2** (DEC-03, ADR-142). Everything after the landing zone is Terraform (Q-01-T03); the console is used only for the one-time steps below, and every console step is logged here with date and operator (SPEC-050 AC-5). Never write a money amount in this repo: budgets refer to "the DEC-03 envelope", and the amount stays in the vault.

## 1. Landing zone (Q-01-T01, TASK-142) — one-time console steps

Do these signed in as the management account's root user only where a step says so; everything else through Identity Center. Policy documents to paste are in `infra/landing-zone/`.

1. **Management account.** Create (or pick) the account that will be the organisation's management account. Root user: hardware key or passkey MFA, no access keys. Enable IAM Identity Center's prerequisite: AWS Organizations, all features.
2. **Control Tower** in **us-east-2** (home region). Governed regions: us-east-2 and us-west-2. Leave Control Tower's own Region deny control **off**: `scp-region-guard.json` replaces it, because us-east-1 must stay open for the global edge and Bedrock US Geo inference only (SPEC-050 AC-1). Shared accounts Control Tower creates: `log-archive`, `audit`.
3. **Organizational units and accounts** (Account Factory): OU `Workloads` with `staging` and `production`; OU `Shared` with `shared`; OU `Sandbox` with `sandbox` (never holds data, D-OPS-03). Use plus-addressed emails on one mailbox you control.
4. **IAM Identity Center** (us-east-2): identity source = Identity Center directory; MFA = every sign-in, passkey or security key only, no SMS; one user for you.
   - Permission sets: `ReadOnly` (AWS `ReadOnlyAccess`, 8 h session) as the default on every account; `PlatformAdmin` (admin, 1 h session) on `shared`, `staging`, `sandbox`; `BreakGlassAdmin`, `abacus-retention-override`, `abacus-key-custodian` (1 h session) assigned only when needed.
   - Alert on elevated assignments: an EventBridge rule in the management account on CloudTrail `sso:CreateAccountAssignment` for those three permission sets → SNS topic → your email. Test it once.
5. **Service control policies** (Organizations → Policies → SCPs). Create and attach at the **root**: `scp-region-guard.json`, `scp-deny-iam-users.json`, `scp-protect-security-services.json`, `scp-deny-leave-org.json`. SCPs never apply to the management account itself, so keep it empty of workloads.
6. **AI services opt-out** (Organizations → Policies → AI services opt-out policies): enable the policy type, create from `ai-services-opt-out.json`, attach at the root (ADR-114, SPEC-050 AC-4).
7. **Budgets** after DEC-03 is recorded: one budget per account at the DEC-03 envelope with 50/80/100 % alerts to your email. The amounts live in the vault, not here.
8. **Portal DNS** when F-09-T09 delivers the neutral portal domain: hosted zone in `shared`, delegate from the registrar.

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

## 4. Console log

Every one-time console step, newest last. Operator is the person at the keyboard.

| Date | Operator | Account | Step | Result |
|---|---|---|---|---|
| | | | | |
