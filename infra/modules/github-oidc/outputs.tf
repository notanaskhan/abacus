output "plan_role_names" {
  description = "Plan role name by environment."
  value       = { for k, r in aws_iam_role.plan : k => r.name }
}

output "apply_role_names" {
  description = "Apply role name by environment."
  value       = { for k, r in aws_iam_role.apply : k => r.name }
}
