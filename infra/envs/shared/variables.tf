variable "github_repo" {
  description = "Repository whose workflows may assume this account's CI roles, as owner/name."
  type        = string
  default     = "notanaskhan/abacus"
}
