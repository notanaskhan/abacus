output "bucket" {
  description = "Bucket name."
  value       = aws_s3_bucket.this.id
}

output "arn" {
  description = "Bucket ARN."
  value       = aws_s3_bucket.this.arn
}

output "key_arn" {
  description = "The bucket's KMS key."
  value       = aws_kms_key.this.arn
}

output "regional_domain_name" {
  description = "Regional domain name (CloudFront origin)."
  value       = aws_s3_bucket.this.bucket_regional_domain_name
}
