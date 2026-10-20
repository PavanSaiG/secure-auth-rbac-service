# modules/vpc/variables.tf

variable "environment" {
  type        = string
  description = "Target deployment environment (dev, qa, prod)"
}

variable "project_name" {
  type        = string
  default     = "auth-service"
  description = "Project name prefix"
}

variable "vpc_cidr" {
  type        = string
  default     = "10.10.0.0/16"
  description = "CIDR block for VPC"
}

variable "availability_zones" {
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b"]
  description = "List of availability zones for multi-AZ topology"
}
