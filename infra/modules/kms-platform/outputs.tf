output "key_arn" {
  description = "The platform key."
  value       = aws_kms_key.platform.arn
}

output "alias_name" {
  description = "The app's kms_platform_key_alias."
  value       = aws_kms_alias.platform.name
}
