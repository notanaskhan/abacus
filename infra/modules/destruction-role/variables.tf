variable "environment" {
  type = string
}

variable "worker_task_role_arn" {
  description = "The worker task role (the batch class runs DestructionExecuteWorkflow)."
  type        = string
}

variable "evidence_bucket_arn" {
  type = string
}

variable "replica_bucket_arn" {
  description = "The us-west-2 replica of the evidence bucket; null until the DR replica exists."
  type        = string
  default     = null
}

variable "oncall_topic_arn" {
  description = "The SNS topic that pages on-call."
  type        = string
}
