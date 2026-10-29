# Q-01-T14: the staging data plane. Minimal sizing (DEC-1003): a single-AZ db.t4g.micro, the
# platform key without its us-west-2 replica. Task roles join the key and bucket policies once
# Q-01-T15 creates them (compute.tf passes their ARNs).

module "kms_platform" {
  source = "../../modules/kms-platform"

  environment   = "staging"
  app_role_arns = local.app_role_arns
}

module "db" {
  source = "../../modules/rds-postgres"

  environment               = "staging"
  vpc_id                    = module.network.vpc_id
  data_subnet_ids           = module.network.data_subnet_ids
  client_security_group_ids = [aws_security_group.tasks.id]
  instance_class            = "db.t4g.micro"
  allocated_storage         = 20
  multi_az                  = false
  kms_key_arn               = module.kms_platform.key_arn
}

module "evidence" {
  source = "../../modules/s3-evidence"

  environment      = "staging"
  kms_key_arn      = module.kms_platform.key_arn
  writer_role_arns = local.app_role_arns
}

module "records" {
  source = "../../modules/s3-records"

  environment      = "staging"
  kms_key_arn      = module.kms_platform.key_arn
  writer_role_arns = local.app_role_arns
}

module "web" {
  source = "../../modules/s3-web"

  environment      = "staging"
  kms_key_arn      = module.kms_platform.key_arn
  writer_role_arns = local.deploy_role_arns
  distribution_arn = local.firm_distribution_arn
}
