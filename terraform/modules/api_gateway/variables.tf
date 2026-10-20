# modules/api_gateway/variables.tf

variable "environment" {
  type        = string
  description = "Target deployment environment (dev, qa, prod)"
}

variable "project_name" {
  type        = string
  default     = "auth-service"
  description = "Project name prefix"
}

variable "lambda_function_arn" {
  type        = string
  description = "ARN of the API Lambda function to invoke"
}

variable "lambda_function_name" {
  type        = string
  description = "Name of the API Lambda function"
}

variable "log_retention_days" {
  type        = number
  default     = 14
  description = "Access log retention in days"
}
