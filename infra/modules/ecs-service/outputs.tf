output "task_definition_arn" {
  description = "The task definition."
  value       = aws_ecs_task_definition.this.arn
}

output "family" {
  description = "Task definition family."
  value       = aws_ecs_task_definition.this.family
}

output "service_name" {
  description = "The service, or null for a one-off task."
  value       = var.service ? aws_ecs_service.this[0].name : null
}

output "log_group_name" {
  description = "The task's CloudWatch log group (P-11-T33: the OCR cap alarm's metric filter reads it)."
  value       = aws_cloudwatch_log_group.this.name
}
