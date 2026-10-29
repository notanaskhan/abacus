output "vpc_id" {
  description = "The environment VPC."
  value       = aws_vpc.this.id
}

output "vpc_cidr" {
  description = "The VPC CIDR."
  value       = aws_vpc.this.cidr_block
}

output "public_subnet_ids" {
  description = "Public subnets (NAT only)."
  value       = aws_subnet.public[*].id
}

output "app_subnet_ids" {
  description = "App subnets (ECS tasks, the internal ALB)."
  value       = aws_subnet.app[*].id
}

output "data_subnet_ids" {
  description = "Data subnets (RDS), no route out."
  value       = aws_subnet.data[*].id
}

output "app_subnet_cidrs" {
  description = "App subnet CIDRs (the API trusts proxy headers from the ALB here)."
  value       = aws_subnet.app[*].cidr_block
}

output "drill_subnet_ids" {
  description = "Drill subnets (restore drills), no route out."
  value       = aws_subnet.drill[*].id
}
