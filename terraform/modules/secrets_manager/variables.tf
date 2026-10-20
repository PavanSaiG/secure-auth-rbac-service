# modules/secrets_manager/variables.tf

variable "environment" {
  type        = string
  description = "Target deployment environment (dev, qa, prod)"
}

variable "project_name" {
  type        = string
  default     = "auth-service"
  description = "Project name prefix"
}
