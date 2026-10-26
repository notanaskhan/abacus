output "exports_bucket_name" {
  description = "The engagement export bucket (ABACUS_EXPORTS_BUCKET)."
  value       = module.exports.bucket_name
}

output "exports_task_environment" {
  description = "Merge into the API and worker task definitions' environment (Q-01-T15)."
  value       = module.exports.task_environment
}
