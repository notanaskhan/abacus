variable "enabled" {
  description = "Create the endpoint, the worker policy, alarms, budget and quota requests (P-11-T22)."
  type        = bool
  default     = false
}
variable "environment" {
  description = "staging or production."
  type        = string
}
variable "vpc_id" {
  description = "The environment's VPC."
  type        = string
}
variable "subnet_ids" {
  description = "The app subnets the endpoint's network interfaces sit in."
  type        = list(string)
}
variable "worker_security_group_id" {
  description = "The worker tasks' security group (the only HTTPS source)."
  type        = string
}
variable "worker_role_name" {
  description = "The background worker's task role (worker-background)."
  type        = string
}
variable "alarm_topic_arns" {
  description = "SNS topics the throttle and error alarms notify."
  type        = list(string)
  default     = []
}
variable "throttle_alarm_threshold" {
  description = "Throttled calls in five minutes before the alarm."
  type        = number
  default     = 10
}
variable "error_alarm_threshold" {
  description = "Errored calls in five minutes before the alarm."
  type        = number
  default     = 5
}
variable "monthly_budget_usd" {
  description = "The Textract cost budget per month (forecast alert at 80%)."
  type        = string
  default     = "200"
}
variable "budget_emails" {
  description = "Who the budget alert emails."
  type        = list(string)
  default     = []
}
variable "quota_requests" {
  description = "Service Quotas codes to raise for the x100 load test, code => value (reviewed in a PR)."
  type        = map(number)
  default     = {}
}
