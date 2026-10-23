variable "bucket_name" {
  description = "Name of the previews bucket; also names the key alias, the function and the store."
  type        = string
  default     = "abacus-shared-previews"
}

variable "github_repo" {
  description = "Repository whose pull_request workflows may assume the CI role, as owner/name."
  type        = string
}

variable "ci_role_name" {
  description = "Name of the role preview.yml assumes through GitHub OIDC."
  type        = string
  default     = "abacus-ci-previews"
}

variable "expiry_days" {
  description = "Days after which every preview object expires (D-OPS-13: 14)."
  type        = number
  default     = 14
}
