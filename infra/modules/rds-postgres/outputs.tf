output "endpoint" {
  description = "host:port of the instance."
  value       = aws_db_instance.this.endpoint
}

output "address" {
  description = "Hostname of the instance."
  value       = aws_db_instance.this.address
}

output "security_group_id" {
  description = "The database security group."
  value       = aws_security_group.db.id
}

output "master_secret_arn" {
  description = "Secrets Manager secret RDS manages for the master user (the bootstrap task reads it)."
  value       = aws_db_instance.this.master_user_secret[0].secret_arn
}
