output "role_name" {
  description = "Role name (compose the ARN outside git)."
  value       = aws_iam_role.this.name
}
