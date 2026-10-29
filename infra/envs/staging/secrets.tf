# Q-01-T14: Secrets Manager entries, created empty. Values never pass through Terraform or git:
# `infra/envs/staging/fill-secrets.sh` (run by the builder) generates the role passwords, the
# payload keyring and the peppers on the laptop and writes them straight to each secret; the
# WorkOS values are pasted by the builder from the WorkOS dashboard (infra/README.md "Staging").

locals {
  secret_names = {
    db_owner         = "abacus/staging/db/owner"
    db_app           = "abacus/staging/db/app"
    db_relay         = "abacus/staging/db/relay"
    db_identity      = "abacus/staging/db/identity"
    db_ops           = "abacus/staging/db/ops"
    temporal_keyring = "abacus/staging/temporal/payload-keyring"
    peppers          = "abacus/staging/peppers"
    workos           = "abacus/staging/workos"
  }
}

resource "aws_secretsmanager_secret" "this" {
  for_each                = local.secret_names
  name                    = each.value
  kms_key_id              = module.kms_platform.key_arn
  recovery_window_in_days = 7
}
