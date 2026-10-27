# Names only; no ARN carries an account ID into an output.

output "alias" {
  description = "The signing key's alias (settings().audit_export_signing_key_alias)."
  value       = aws_kms_alias.export_signing.name
}

output "task_environment" {
  description = "Environment for the worker task definition (Q-01-T15): the setting kernel/config.py reads."
  value = {
    ABACUS_AUDIT_EXPORT_SIGNING_KEY_ALIAS = aws_kms_alias.export_signing.name
  }
}

output "worker_policy_name" {
  description = "Attach to the worker task role when Q-01-T15 creates it (or set worker_task_role_name)."
  value       = aws_iam_policy.worker.name
}
