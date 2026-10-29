# The environment network (Q-01-T14; chapter 06 section 1.17). One VPC over two zones with public
# (NAT and nothing else), app (ECS tasks) and data (RDS) subnets; the app subnets reach out only
# through NAT, the data subnets not at all. S3 is a gateway endpoint, so object traffic never
# crosses NAT. Interface endpoints and the DNS Firewall allowlist are a later pass (DEC-1003):
# with a NAT the tasks reach AWS APIs over TLS, which is enough for synthetic staging data.

data "aws_availability_zones" "available" {
  state = "available"
}

locals {
  azs = slice(data.aws_availability_zones.available.names, 0, var.az_count)
  # /20 per subnet: public 0-1, app 4-5, data 8-9 (room for the drill subnets at 12-13).
  public = [for i, _ in local.azs : cidrsubnet(var.cidr, 4, i)]
  app    = [for i, _ in local.azs : cidrsubnet(var.cidr, 4, 4 + i)]
  data   = [for i, _ in local.azs : cidrsubnet(var.cidr, 4, 8 + i)]
  drill  = [for i, _ in local.azs : cidrsubnet(var.cidr, 4, 12 + i)]
}

resource "aws_vpc" "this" {
  cidr_block           = var.cidr
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = { Name = "abacus-${var.environment}" }
}

resource "aws_internet_gateway" "this" {
  vpc_id = aws_vpc.this.id
  tags   = { Name = "abacus-${var.environment}" }
}

resource "aws_subnet" "public" {
  count                   = length(local.azs)
  vpc_id                  = aws_vpc.this.id
  cidr_block              = local.public[count.index]
  availability_zone       = local.azs[count.index]
  map_public_ip_on_launch = false
  tags                    = { Name = "abacus-${var.environment}-public-${count.index}", tier = "public" }
}

resource "aws_subnet" "app" {
  count             = length(local.azs)
  vpc_id            = aws_vpc.this.id
  cidr_block        = local.app[count.index]
  availability_zone = local.azs[count.index]
  tags              = { Name = "abacus-${var.environment}-app-${count.index}", tier = "app" }
}

resource "aws_subnet" "data" {
  count             = length(local.azs)
  vpc_id            = aws_vpc.this.id
  cidr_block        = local.data[count.index]
  availability_zone = local.azs[count.index]
  tags              = { Name = "abacus-${var.environment}-data-${count.index}", tier = "data" }
}

resource "aws_eip" "nat" {
  count  = var.nat_gateways
  domain = "vpc"
  tags   = { Name = "abacus-${var.environment}-nat-${count.index}" }
}

resource "aws_nat_gateway" "this" {
  count         = var.nat_gateways
  allocation_id = aws_eip.nat[count.index].id
  subnet_id     = aws_subnet.public[count.index].id
  tags          = { Name = "abacus-${var.environment}-${count.index}" }

  depends_on = [aws_internet_gateway.this]
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.this.id
  tags   = { Name = "abacus-${var.environment}-public" }
}

resource "aws_route" "public_internet" {
  route_table_id         = aws_route_table.public.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.this.id
}

resource "aws_route_table_association" "public" {
  count          = length(local.azs)
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table" "app" {
  count  = length(local.azs)
  vpc_id = aws_vpc.this.id
  tags   = { Name = "abacus-${var.environment}-app-${count.index}" }
}

resource "aws_route" "app_nat" {
  count                  = length(local.azs)
  route_table_id         = aws_route_table.app[count.index].id
  destination_cidr_block = "0.0.0.0/0"
  nat_gateway_id         = aws_nat_gateway.this[min(count.index, var.nat_gateways - 1)].id
}

resource "aws_route_table_association" "app" {
  count          = length(local.azs)
  subnet_id      = aws_subnet.app[count.index].id
  route_table_id = aws_route_table.app[count.index].id
}

# The data subnets have no route out.
resource "aws_route_table" "data" {
  vpc_id = aws_vpc.this.id
  tags   = { Name = "abacus-${var.environment}-data" }
}

resource "aws_route_table_association" "data" {
  count          = length(local.azs)
  subnet_id      = aws_subnet.data[count.index].id
  route_table_id = aws_route_table.data.id
}

resource "aws_vpc_endpoint" "s3" {
  vpc_id            = aws_vpc.this.id
  service_name      = "com.amazonaws.${data.aws_region.current.region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = aws_route_table.app[*].id
  tags              = { Name = "abacus-${var.environment}-s3" }
}

data "aws_region" "current" {}

# Every flow is logged (SPEC-050): rejected and accepted, 14 days in staging.
resource "aws_cloudwatch_log_group" "flow" {
  name              = "/abacus/${var.environment}/vpc-flow"
  retention_in_days = 14
}

data "aws_iam_policy_document" "flow_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["vpc-flow-logs.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "flow" {
  name               = "abacus-${var.environment}-vpc-flow"
  assume_role_policy = data.aws_iam_policy_document.flow_trust.json
}

data "aws_iam_policy_document" "flow" {
  statement {
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents", "logs:DescribeLogStreams"]
    resources = ["${aws_cloudwatch_log_group.flow.arn}:*"]
  }
}

resource "aws_iam_role_policy" "flow" {
  name   = "flow-logs"
  role   = aws_iam_role.flow.name
  policy = data.aws_iam_policy_document.flow.json
}

resource "aws_flow_log" "this" {
  vpc_id          = aws_vpc.this.id
  traffic_type    = "ALL"
  log_destination = aws_cloudwatch_log_group.flow.arn
  iam_role_arn    = aws_iam_role.flow.arn
}

resource "aws_subnet" "drill" {
  count             = length(local.azs)
  vpc_id            = aws_vpc.this.id
  cidr_block        = local.drill[count.index]
  availability_zone = local.azs[count.index]
  tags              = { Name = "abacus-${var.environment}-drill-${count.index}", tier = "drill" }
}

resource "aws_route_table_association" "drill" {
  count          = length(local.azs)
  subnet_id      = aws_subnet.drill[count.index].id
  route_table_id = aws_route_table.data.id
}

resource "aws_security_group" "endpoints" {
  count       = length(var.interface_endpoints) > 0 ? 1 : 0
  name        = "abacus-${var.environment}-endpoints"
  description = "Interface endpoints: HTTPS from the VPC"
  vpc_id      = aws_vpc.this.id
}

resource "aws_vpc_security_group_ingress_rule" "endpoints" {
  count             = length(var.interface_endpoints) > 0 ? 1 : 0
  security_group_id = aws_security_group.endpoints[0].id
  cidr_ipv4         = var.cidr
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
  description       = "HTTPS from the VPC"
}

resource "aws_vpc_endpoint" "interface" {
  for_each            = toset(var.interface_endpoints)
  vpc_id              = aws_vpc.this.id
  service_name        = "com.amazonaws.${data.aws_region.current.region}.${each.value}"
  vpc_endpoint_type   = "Interface"
  private_dns_enabled = true
  subnet_ids          = aws_subnet.app[*].id
  security_group_ids  = [aws_security_group.endpoints[0].id]
  tags                = { Name = "abacus-${var.environment}-${each.value}" }
}
