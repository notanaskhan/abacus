# Names and the CloudFront domain only; no ARN carries an account ID into an output.

output "bucket_name" {
  description = "Previews bucket; preview.yml writes pr-<n>/ here."
  value       = aws_s3_bucket.previews.id
}

output "host" {
  description = "Preview host (the distribution's CloudFront domain). Set vars.PREVIEW_HOST to it."
  value       = aws_cloudfront_distribution.previews.domain_name
}

output "ci_role_name" {
  description = "Role preview.yml assumes. Set vars.AWS_PREVIEW_ROLE to its full ARN."
  value       = aws_iam_role.ci.name
}

output "gate_store_name" {
  description = "KeyValueStore that holds gate-key; put the key by hand (infra/README.md)."
  value       = aws_cloudfront_key_value_store.gate.name
}
