# Q-05-T14 (ADR-179 / OQ-1; DEC-5823): the records-destruction role, off until enabled with the
# on-call topic (the apply and the staging proof are a person's: RB-100).
module "destruction_role" {
  source = "../../modules/destruction-role"
  count  = var.destruction_role_enabled ? 1 : 0

  environment          = "staging"
  worker_task_role_arn = aws_iam_role.task["worker"].arn
  evidence_bucket_arn  = module.evidence.arn
  replica_bucket_arn   = var.evidence_replica_bucket_arn
  oncall_topic_arn     = var.oncall_topic_arn
}
