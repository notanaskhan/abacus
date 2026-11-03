output "endpoint_id" {
  description = "The Textract interface endpoint (the worker's only route to Textract)."
  value       = var.enabled ? aws_vpc_endpoint.textract[0].id : null
}
