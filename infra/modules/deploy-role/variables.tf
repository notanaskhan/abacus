variable "name" {
  description = "Role name."
  type        = string
}

variable "description" {
  description = "Role description."
  type        = string
}

variable "github_repo" {
  description = "Repository, owner/name."
  type        = string
}

variable "github_environment" {
  description = "The GitHub environment whose OIDC tokens may assume the role."
  type        = string
}

variable "policy_json" {
  description = "The role's permission document."
  type        = string
}
