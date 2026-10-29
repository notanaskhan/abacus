output "bucket_arn" {
  description = "The log bucket (a WebACL's log destination)."
  value       = aws_s3_bucket.this.arn
}
