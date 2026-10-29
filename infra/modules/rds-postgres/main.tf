# RDS PostgreSQL 17 (Q-01-T14; ADR-014): private, TLS-only (rds.force_ssl), encrypted with the
# platform key, the master password managed by RDS in Secrets Manager (never in state). Statement
# logging stays off (parameter logging off: client values never reach the logs). pgvector,
# pg_trgm and btree_gin are created by the bootstrap task, not here (migrations/bootstrap.sql).

resource "aws_db_subnet_group" "this" {
  name       = "abacus-${var.environment}"
  subnet_ids = var.data_subnet_ids
}

resource "aws_security_group" "db" {
  name        = "abacus-${var.environment}-db"
  description = "Postgres, from the app tasks only"
  vpc_id      = var.vpc_id
}

resource "aws_vpc_security_group_ingress_rule" "db" {
  for_each                     = toset(var.client_security_group_ids)
  security_group_id            = aws_security_group.db.id
  referenced_security_group_id = each.value
  ip_protocol                  = "tcp"
  from_port                    = 5432
  to_port                      = 5432
  description                  = "Postgres from the app tasks"
}

resource "aws_db_parameter_group" "this" {
  name   = "abacus-${var.environment}-pg17"
  family = "postgres17"

  parameter {
    name  = "rds.force_ssl"
    value = "1"
  }

  parameter {
    name  = "log_statement"
    value = "none"
  }

  parameter {
    name  = "log_min_duration_statement"
    value = "-1"
  }
}

resource "aws_db_instance" "this" {
  identifier     = "abacus-${var.environment}"
  engine         = "postgres"
  engine_version = "17"
  instance_class = var.instance_class

  db_name                       = "abacus"
  username                      = "abacus_admin"
  manage_master_user_password   = true
  master_user_secret_kms_key_id = var.kms_key_arn

  allocated_storage     = var.allocated_storage
  max_allocated_storage = var.allocated_storage * 5
  storage_type          = "gp3"
  storage_encrypted     = true
  kms_key_id            = var.kms_key_arn

  db_subnet_group_name   = aws_db_subnet_group.this.name
  vpc_security_group_ids = [aws_security_group.db.id]
  parameter_group_name   = aws_db_parameter_group.this.name
  publicly_accessible    = false
  multi_az               = var.multi_az

  backup_retention_period         = 7
  copy_tags_to_snapshot           = true
  auto_minor_version_upgrade      = true
  deletion_protection             = var.deletion_protection
  skip_final_snapshot             = false
  final_snapshot_identifier       = "abacus-${var.environment}-final"
  performance_insights_enabled    = false
  enabled_cloudwatch_logs_exports = ["postgresql"]
}
