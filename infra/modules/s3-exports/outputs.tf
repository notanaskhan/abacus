# Names only; no ARN carries an account ID into an output.

output "bucket_name" {
  description = "The exports bucket (settings().exports_bucket)."
  value       = aws_s3_bucket.exports.id
}

output "task_environment" {
  description = "Environment for the API and worker task definitions (Q-01-T15): the setting kernel/config.py reads."
  value = {
    ABACUS_EXPORTS_BUCKET = aws_s3_bucket.exports.id
  }
}

output "worker_policy_name" {
  description = "Attach to the worker task role when Q-01-T15 creates it (or set worker_task_role_name)."
  value       = aws_iam_policy.worker.name
}

output "api_policy_name" {
  description = "Attach to the API task role when Q-01-T15 creates it (or set api_task_role_name)."
  value       = aws_iam_policy.api.name
}

output "key_alias" {
  description = "Alias of the bucket's SSE-KMS key."
  value       = aws_kms_alias.exports.name
}
