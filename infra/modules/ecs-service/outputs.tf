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
