# The audit-log export-signing key (G-02-T17, DEC-621). Needs nothing else in this root, so it plans
# on its own; the worker role arrives with Q-01-T15. Apply is the builder's, then the public key is
# published in docs/operations/export-signing-keys.md (infra/README.md "Export-signing key").

module "export_signing" {
  source = "../../modules/kms-export-signing"

  environment           = "staging"
  worker_task_role_name = var.worker_task_role_name
}
