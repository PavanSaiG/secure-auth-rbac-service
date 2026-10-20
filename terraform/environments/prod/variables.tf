# environments/prod/variables.tf

variable "aws_region" {
  type        = string
  default     = "us-east-1"
  description = "AWS deployment region"
}

variable "environment" {
  type        = string
  default     = "prod"
  description = "Target deployment environment"
}

variable "project_name" {
  type        = string
  default     = "auth-service"
  description = "Project name"
}

variable "log_retention_days" {
  type        = number
  default     = 90
  description = "CloudWatch log retention in days for production"
}
