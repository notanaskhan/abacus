output "configuration_set" {
  description = "The app's ses_configuration_set."
  value       = aws_sesv2_configuration_set.this.configuration_set_name
}

output "events_queue_url" {
  description = "The app's ses_events_queue_url."
  value       = aws_sqs_queue.events.id
}

output "events_queue_arn" {
  description = "The delivery-events queue."
  value       = aws_sqs_queue.events.arn
}
