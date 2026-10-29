output "rule_group_id" {
  description = "The egress rule group."
  value       = aws_route53_resolver_firewall_rule_group.this.id
}
