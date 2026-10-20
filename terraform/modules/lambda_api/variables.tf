# modules/lambda_api/variables.tf

variable "environment" {
  type        = string
  description = "Target deployment environment (dev, qa, prod)"
}

variable "project_name" {
  type        = string
  default     = "auth-service"
  description = "Project name prefix"
}

variable "vpc_id" {
  type        = string
  description = "ID of VPC"
}

variable "private_subnet_ids" {
  type        = list(string)
  description = "Private subnets for VPC Lambda execution"
}

variable "secret_arn" {
  type        = string
  description = "ARN of Secrets Manager secret containing JWT and DB credentials"
}

variable "database_url" {
  type        = string
  sensitive   = true
  description = "Database connection string"
}

variable "log_retention_days" {
  type        = number
  default     = 14
  description = "CloudWatch log retention in days"
}
