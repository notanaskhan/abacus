output "cluster_name" {
  description = "Cluster name."
  value       = aws_ecs_cluster.this.name
}

output "cluster_arn" {
  description = "Cluster ARN."
  value       = aws_ecs_cluster.this.arn
}

output "execution_role_arn" {
  description = "Task execution role."
  value       = aws_iam_role.execution.arn
}

output "tasks_trust_json" {
  description = "Trust policy document for task roles."
  value       = data.aws_iam_policy_document.tasks_trust.json
}
