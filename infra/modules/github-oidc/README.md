# github-oidc

GitHub Actions OIDC provider plus, per environment, a read-only plan role (trusted for `pull_request` and `main`) and an apply role (trusted for `main` only), for one AWS account. Used by `infra/bootstrap`. Outputs role names only; compose the ARN from the account ID outside git.
