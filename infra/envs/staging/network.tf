# Q-01-T14: the staging network (chapter 06 section 1.17), minimal sizing (DEC-1003): two zones,
# one NAT gateway.
module "network" {
  source = "../../modules/network"

  environment  = "staging"
  cidr         = "10.20.0.0/16"
  az_count     = 2
  nat_gateways = 1
}

# The ECS tasks' security group (Q-01-T15 attaches it): outbound only, inbound from the ALB.
resource "aws_security_group" "tasks" {
  name        = "abacus-staging-tasks"
  description = "ECS tasks: API, workers, scanner, Temporal"
  vpc_id      = module.network.vpc_id
}

resource "aws_vpc_security_group_egress_rule" "tasks_out" {
  security_group_id = aws_security_group.tasks.id
  ip_protocol       = "-1"
  cidr_ipv4         = "0.0.0.0/0"
  description       = "Out through NAT (AWS APIs, WorkOS) and to Postgres"
}

# Tasks reach each other (Temporal 7233, the scanner 3310) inside the group.
resource "aws_vpc_security_group_ingress_rule" "tasks_peer" {
  security_group_id            = aws_security_group.tasks.id
  referenced_security_group_id = aws_security_group.tasks.id
  ip_protocol                  = "tcp"
  from_port                    = 3310
  to_port                      = 8000
  description                  = "Task to task: scanner 3310, Temporal 7233, API 8000"
}
