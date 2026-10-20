# modules/rds/variables.tf

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

variable "db_subnet_group_name" {
  type        = string
  description = "Name of DB subnet group"
}

variable "lambda_security_group_id" {
  type        = string
  description = "Security group ID of the Lambda function for ingress access"
}

variable "db_password" {
  type        = string
  sensitive   = true
  description = "Master password for PostgreSQL database"
}

variable "instance_class" {
  type        = string
  default     = "db.t4g.micro"
  description = "RDS instance compute class"
}

variable "allocated_storage" {
  type        = number
  default     = 20
  description = "Allocated storage in GiB"
}

variable "multi_az" {
  type        = bool
  default     = false
  description = "Deploy multi-AZ high availability standby instance"
}
