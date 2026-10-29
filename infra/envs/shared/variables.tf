variable "github_repo" {
  description = "Repository whose workflows may assume this account's CI roles, as owner/name."
  type        = string
  default     = "notanaskhan/abacus"
}

variable "reader_account_ids" {
  description = "Environment accounts that pull release images and read release records (staging now; production later). From the untracked terraform.tfvars."
  type        = list(string)
  default     = []

  validation {
    condition     = alltrue([for id in var.reader_account_ids : can(regex("^[0-9]{12}$", id))])
    error_message = "reader_account_ids must be 12-digit AWS account IDs."
  }
}
