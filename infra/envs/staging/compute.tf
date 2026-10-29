# Q-01-T15: staging compute and edge, minimal sizing (DEC-1003). One API task behind an internal
# ALB, one worker for every class but keyops, one keyops worker (the only role allowed to make
# tenant keys), the ClamAV scanner and a single in-VPC Temporal dev server (DEC-1004), each found
# by name through Cloud Map; one-off migrate, bootstrap and ops task definitions; the firm edge on
# CloudFront. Everything here plans to nothing until `image_digest` is set in terraform.tfvars.

data "aws_caller_identity" "current" {}

locals {
  enabled = var.image_digest != null
  account = data.aws_caller_identity.current.account_id
  region  = "us-east-2"
  role    = "arn:aws:iam::${local.account}:role"
  app_role_arns = local.enabled ? [
    "${local.role}/abacus-staging-api", "${local.role}/abacus-staging-worker", "${local.role}/abacus-staging-keyops",
    "${local.role}/abacus-staging-ops",
  ] : []
  deploy_role_arns      = local.enabled ? ["${local.role}/abacus-staging-deploy"] : []
  firm_distribution_arn = local.enabled ? module.firm_edge[0].distribution_arn : null
  dns                   = "abacus-staging.internal"
  secret                = { for k, v in aws_secretsmanager_secret.this : k => v.arn }

  # Settings every backend process reads (kernel/config.py). Nothing secret: those are `secrets`.
  common_env = local.enabled ? merge(module.exports.task_environment, {
    ABACUS_ENVIRONMENT              = "staging"
    ABACUS_S3_REGION                = local.region
    ABACUS_EVIDENCE_BUCKET          = module.evidence.bucket
    ABACUS_RECORDS_BUCKET           = module.records.bucket
    ABACUS_KMS_REGION               = local.region
    ABACUS_KMS_PLATFORM_KEY_ALIAS   = module.kms_platform.alias_name
    ABACUS_TEMPORAL_TARGET          = "temporal.${local.dns}:7233"
    ABACUS_TEMPORAL_IN_VPC          = "true"
    ABACUS_TEMPORAL_PAYLOAD_CURRENT = "staging-v1"
    ABACUS_SCANNER_ENDPOINT         = "scanner.${local.dns}:3310"
    ABACUS_SES_REGION               = local.region
    ABACUS_SES_CONFIGURATION_SET    = module.ses.configuration_set
    ABACUS_SES_EVENTS_QUEUE_URL     = module.ses.events_queue_url
    ABACUS_SES_FROM_ADDRESS         = coalesce(var.ses_verified_address, "no-reply@example.invalid")
    ABACUS_IDENTITY_ISSUER          = coalesce(var.workos_issuer, "https://unset.invalid")
    ABACUS_IDENTITY_AUDIENCE        = coalesce(var.workos_client_id, "unset")
    ABACUS_IDENTITY_JWKS            = coalesce(var.workos_jwks, "{\"keys\": []}")
    ABACUS_WORKOS_CLIENT_ID         = coalesce(var.workos_client_id, "unset")
    ABACUS_TRUSTED_HOSTS            = "[\"${module.firm_edge[0].domain_name}\"]"
    ABACUS_PROXY_TRUSTED_HOSTS      = jsonencode(module.network.app_subnet_cidrs)
    ABACUS_RELEASE                  = split("@", var.image_digest)[1]
    ABACUS_DATABASE_CA_FILE         = "/app/src/abacus/kernel/certs/rds-global-bundle.pem"
  }) : {}
  common_secrets = {
    ABACUS_DATABASE_URL                  = "${local.secret.db_app}:url::"
    ABACUS_RELAY_DATABASE_URL            = "${local.secret.db_relay}:url::"
    ABACUS_IDENTITY_DATABASE_URL         = "${local.secret.db_identity}:url::"
    ABACUS_MIGRATIONS_DATABASE_URL       = "${local.secret.db_owner}:url::"
    ABACUS_OPS_DATABASE_URL              = "${local.secret.db_ops}:url::"
    ABACUS_TEMPORAL_PAYLOAD_KEYS         = local.secret.temporal_keyring
    ABACUS_EMAIL_SUPPRESSION_PEPPER      = "${local.secret.peppers}:email_suppression::"
    ABACUS_TIN_FINGERPRINT_PEPPER        = "${local.secret.peppers}:tin_fingerprint::"
    ABACUS_RUN_RECORD_FINGERPRINT_PEPPER = "${local.secret.peppers}:run_record_fingerprint::"
    ABACUS_WORKOS_API_KEY                = "${local.secret.workos}:api_key::"
  }
}

module "cluster" {
  source = "../../modules/ecs-cluster"

  environment = "staging"
  secret_arns = concat([for s in aws_secretsmanager_secret.this : s.arn], [module.db.master_secret_arn])
  kms_key_arn = module.kms_platform.key_arn
}

resource "aws_service_discovery_private_dns_namespace" "internal" {
  name = local.dns
  vpc  = module.network.vpc_id
}

# --- task roles ---------------------------------------------------------------------------------

resource "aws_iam_role" "task" {
  for_each           = toset(["api", "worker", "keyops", "ops"])
  name               = "abacus-staging-${each.key}"
  assume_role_policy = module.cluster.tasks_trust_json
}

data "aws_iam_policy_document" "app" {
  statement {
    sid = "Objects"
    actions = [
      "s3:GetObject", "s3:GetObjectVersion", "s3:PutObject", "s3:ListBucket",
      "s3:GetObjectRetention", "s3:PutObjectRetention",
    ]
    resources = flatten([for b in [module.evidence.arn, module.records.arn] : [b, "${b}/*"]])
  }

  statement {
    sid       = "PlatformKey"
    actions   = ["kms:Encrypt", "kms:Decrypt", "kms:GenerateDataKey", "kms:DescribeKey"]
    resources = [module.kms_platform.key_arn]
  }

  # Tenant keys are used by alias (alias/abacus/tenant/<id>); their policies are the keyops role's.
  statement {
    sid       = "TenantKeysUse"
    actions   = ["kms:Encrypt", "kms:Decrypt", "kms:GenerateDataKey", "kms:DescribeKey"]
    resources = ["arn:aws:kms:*:${local.account}:key/*"]

    condition {
      test     = "StringEquals"
      variable = "aws:ResourceTag/abacus:env"
      values   = ["staging"]
    }
  }

  statement {
    sid       = "Email"
    actions   = ["ses:SendEmail", "ses:SendRawEmail"]
    resources = ["*"]

    condition {
      test     = "StringEquals"
      variable = "ses:FromAddress"
      values   = [coalesce(var.ses_verified_address, "no-reply@example.invalid")]
    }
  }

  statement {
    sid       = "EmailEvents"
    actions   = ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes"]
    resources = [module.ses.events_queue_arn]
  }
}

resource "aws_iam_role_policy" "app" {
  for_each = toset(["api", "worker", "keyops"])
  name     = "app"
  role     = aws_iam_role.task[each.key].name
  policy   = data.aws_iam_policy_document.app.json
}

# Q-01-T27: only keyops makes, tags, aliases and replicates tenant keys.
data "aws_iam_policy_document" "keyops" {
  statement {
    sid       = "CreateTenantKeys"
    actions   = ["kms:CreateKey", "kms:TagResource"]
    resources = ["*"]

    condition {
      test     = "StringEquals"
      variable = "aws:RequestTag/abacus:env"
      values   = ["staging"]
    }
  }

  statement {
    sid       = "ManageTenantKeys"
    actions   = ["kms:ReplicateKey", "kms:CreateAlias", "kms:DescribeKey", "kms:TagResource"]
    resources = ["arn:aws:kms:*:${local.account}:key/*", "arn:aws:kms:*:${local.account}:alias/abacus/tenant/*"]
  }

  statement {
    sid       = "ListAliases"
    actions   = ["kms:ListAliases"]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "keyops" {
  name   = "tenant-keys"
  role   = aws_iam_role.task["keyops"].name
  policy = data.aws_iam_policy_document.keyops.json
}

# --- internal load balancer ---------------------------------------------------------------------

resource "aws_security_group" "alb" {
  name        = "abacus-staging-alb"
  description = "Internal API load balancer: CloudFront VPC origin only"
  vpc_id      = module.network.vpc_id
}

data "aws_ec2_managed_prefix_list" "cloudfront" {
  name = "com.amazonaws.global.cloudfront.origin-facing"
}

resource "aws_vpc_security_group_ingress_rule" "alb_from_cloudfront" {
  security_group_id = aws_security_group.alb.id
  prefix_list_id    = data.aws_ec2_managed_prefix_list.cloudfront.id
  ip_protocol       = "tcp"
  from_port         = 80
  to_port           = 80
  description       = "CloudFront origin-facing ranges (VPC origin)"
}

resource "aws_vpc_security_group_egress_rule" "alb_to_tasks" {
  security_group_id            = aws_security_group.alb.id
  referenced_security_group_id = aws_security_group.tasks.id
  ip_protocol                  = "tcp"
  from_port                    = 8000
  to_port                      = 8000
  description                  = "To the API tasks"
}

resource "aws_vpc_security_group_ingress_rule" "tasks_from_alb" {
  security_group_id            = aws_security_group.tasks.id
  referenced_security_group_id = aws_security_group.alb.id
  ip_protocol                  = "tcp"
  from_port                    = 8000
  to_port                      = 8000
  description                  = "API from the internal ALB"
}

resource "aws_lb" "api" {
  name                       = "abacus-staging-api"
  internal                   = true
  load_balancer_type         = "application"
  subnets                    = module.network.app_subnet_ids
  security_groups            = [aws_security_group.alb.id]
  drop_invalid_header_fields = true
}

resource "aws_lb_target_group" "api" {
  name        = "abacus-staging-api"
  port        = 8000
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = module.network.vpc_id

  health_check {
    path                = "/readyz"
    matcher             = "200"
    interval            = 15
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }
}

resource "aws_lb_listener" "api" {
  load_balancer_arn = aws_lb.api.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
}

# --- services and one-off tasks -----------------------------------------------------------------

locals {
  backend_services = {
    api    = { cpu = 512, memory = 1024, command = ["api"], role = "api", port = 8000 }
    worker = { cpu = 512, memory = 1024, command = ["worker", "--classes", "interactive,time_sensitive,background,batch"], role = "worker", port = null }
    keyops = { cpu = 256, memory = 512, command = ["worker", "--classes", "keyops"], role = "keyops", port = null }
  }
  oneoffs = {
    migrate   = { command = ["migrate"], role = "worker" }
    bootstrap = { command = ["bootstrap"], role = "ops" }
    ops       = { command = ["ops", "tenants"], role = "ops" }
  }
}

module "backend" {
  source   = "../../modules/ecs-service"
  for_each = local.enabled ? local.backend_services : {}

  environment            = "staging"
  name                   = each.key
  cluster_arn            = module.cluster.cluster_arn
  execution_role_arn     = module.cluster.execution_role_arn
  task_role_arn          = aws_iam_role.task[each.value.role].arn
  image                  = var.image_digest
  command                = each.value.command
  cpu                    = each.value.cpu
  memory                 = each.value.memory
  environment_vars       = local.common_env
  secrets                = local.common_secrets
  port                   = each.value.port
  subnet_ids             = module.network.app_subnet_ids
  security_group_ids     = [aws_security_group.tasks.id]
  target_group_arn       = each.key == "api" ? aws_lb_target_group.api.arn : null
  discovery_namespace_id = aws_service_discovery_private_dns_namespace.internal.id
}

module "oneoff" {
  source   = "../../modules/ecs-service"
  for_each = local.enabled ? local.oneoffs : {}

  environment        = "staging"
  name               = each.key
  cluster_arn        = module.cluster.cluster_arn
  execution_role_arn = module.cluster.execution_role_arn
  task_role_arn      = aws_iam_role.task[each.value.role].arn
  image              = var.image_digest
  command            = each.value.command
  cpu                = 512
  memory             = 1024
  environment_vars   = merge(local.common_env, each.key == "bootstrap" ? { ABACUS_DB_HOST = module.db.address } : {})
  secrets = merge(local.common_secrets, each.key == "bootstrap" ? {
    ABACUS_DB_MASTER_USER              = "${module.db.master_secret_arn}:username::"
    ABACUS_DB_MASTER_PASSWORD          = "${module.db.master_secret_arn}:password::"
    ABACUS_BOOTSTRAP_OWNER_PASSWORD    = "${local.secret.db_owner}:password::"
    ABACUS_BOOTSTRAP_APP_PASSWORD      = "${local.secret.db_app}:password::"
    ABACUS_BOOTSTRAP_RELAY_PASSWORD    = "${local.secret.db_relay}:password::"
    ABACUS_BOOTSTRAP_IDENTITY_PASSWORD = "${local.secret.db_identity}:password::"
    ABACUS_BOOTSTRAP_OPS_PASSWORD      = "${local.secret.db_ops}:password::"
  } : {})
  service = false
}

# ClamAV (clamd on 3310): its own image, by digest; it refreshes signatures through NAT.
module "scanner" {
  source = "../../modules/ecs-service"
  count  = local.enabled ? 1 : 0

  environment            = "staging"
  name                   = "scanner"
  cluster_arn            = module.cluster.cluster_arn
  execution_role_arn     = module.cluster.execution_role_arn
  image                  = "clamav/clamav:1.4@sha256:982e28f90061d0e66eb03276419f589a47c9fa601e985e472fc2f6c64b497ca0"
  cpu                    = 1024
  memory                 = 3072
  port                   = 3310
  read_only_root         = false
  subnet_ids             = module.network.app_subnet_ids
  security_group_ids     = [aws_security_group.tasks.id]
  discovery_namespace_id = aws_service_discovery_private_dns_namespace.internal.id
}

# DEC-1004: a single Temporal dev server inside the VPC instead of Temporal Cloud, staging only.
# In-memory: histories go with the task; the deploy re-ensures the platform Schedules.
module "temporal" {
  source = "../../modules/ecs-service"
  count  = local.enabled ? 1 : 0

  environment            = "staging"
  name                   = "temporal"
  cluster_arn            = module.cluster.cluster_arn
  execution_role_arn     = module.cluster.execution_role_arn
  image                  = "temporalio/temporal:1.9.1@sha256:ad4c82c97bd12b417d1ea942610dbcd511afb250c4d5ed26c694009533df447e"
  command                = ["server", "start-dev", "--ip", "0.0.0.0", "--headless"]
  cpu                    = 512
  memory                 = 1024
  port                   = 7233
  read_only_root         = false
  subnet_ids             = module.network.app_subnet_ids
  security_group_ids     = [aws_security_group.tasks.id]
  discovery_namespace_id = aws_service_discovery_private_dns_namespace.internal.id
}

# --- edge and email -----------------------------------------------------------------------------

module "firm_edge" {
  source = "../../modules/cloudfront-firm"
  count  = local.enabled ? 1 : 0

  environment                = "staging"
  web_bucket_regional_domain = module.web.regional_domain_name
  alb_arn                    = aws_lb.api.arn
  alb_dns_name               = aws_lb.api.dns_name
}

module "ses" {
  source = "../../modules/ses"

  environment      = "staging"
  verified_address = var.ses_verified_address
  kms_key_arn      = module.kms_platform.key_arn
}
