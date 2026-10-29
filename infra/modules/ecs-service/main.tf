# One ECS task definition and, for a long-lived process, its Fargate service (Q-01-T15). Images by
# digest only. Logs go to /abacus/<env>/<name> (14 days on staging). The backend image runs
# non-root on a read-only root filesystem with an ephemeral /tmp volume (Q-01-T06).

data "aws_region" "current" {}

resource "aws_cloudwatch_log_group" "this" {
  name              = "/abacus/${var.environment}/${var.name}"
  retention_in_days = 14
}

locals {
  container = merge(
    {
      name                   = var.name
      image                  = var.image
      essential              = true
      command                = length(var.command) > 0 ? var.command : null
      readonlyRootFilesystem = var.read_only_root
      environment            = [for k, v in var.environment_vars : { name = k, value = v }]
      secrets                = [for k, v in var.secrets : { name = k, valueFrom = v }]
      mountPoints            = var.read_only_root ? [{ sourceVolume = "tmp", containerPath = "/tmp", readOnly = false }] : []
      portMappings           = var.port == null ? [] : [{ containerPort = var.port, protocol = "tcp", name = var.name }]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.this.name
          awslogs-region        = data.aws_region.current.region
          awslogs-stream-prefix = var.name
        }
      }
    },
    var.user == null ? {} : { user = var.user },
  )
}

resource "aws_ecs_task_definition" "this" {
  family                   = "abacus-${var.environment}-${var.name}"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.cpu
  memory                   = var.memory
  execution_role_arn       = var.execution_role_arn
  task_role_arn            = var.task_role_arn

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }

  dynamic "volume" {
    for_each = var.read_only_root ? [1] : []
    content {
      name = "tmp"
    }
  }

  container_definitions = jsonencode([local.container])
}

resource "aws_service_discovery_service" "this" {
  count = var.service && var.discovery_namespace_id != null ? 1 : 0
  name  = var.name

  dns_config {
    namespace_id = var.discovery_namespace_id

    dns_records {
      type = "A"
      ttl  = 10
    }
  }
}

resource "aws_ecs_service" "this" {
  count           = var.service ? 1 : 0
  name            = var.name
  cluster         = var.cluster_arn
  task_definition = aws_ecs_task_definition.this.arn
  desired_count   = var.desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.subnet_ids
    security_groups  = var.security_group_ids
    assign_public_ip = false
  }

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  dynamic "load_balancer" {
    for_each = var.target_group_arn == null ? [] : [1]
    content {
      target_group_arn = var.target_group_arn
      container_name   = var.name
      container_port   = var.port
    }
  }

  dynamic "service_registries" {
    for_each = aws_service_discovery_service.this
    content {
      registry_arn = service_registries.value.arn
    }
  }

  health_check_grace_period_seconds = var.target_group_arn == null ? null : var.health_check_grace_seconds

  # Deploys (deploy-staging.yml) register new task definitions; Terraform keeps the shape.
  lifecycle {
    ignore_changes = [task_definition, desired_count]
  }
}
