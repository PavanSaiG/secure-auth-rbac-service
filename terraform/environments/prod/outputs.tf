# environments/prod/outputs.tf

output "api_endpoint" {
  value       = module.api_gateway.api_endpoint
  description = "Public API Gateway invocation endpoint"
}

output "rds_endpoint" {
  value       = module.rds.endpoint
  description = "RDS PostgreSQL database endpoint"
}

output "secrets_manager_secret_arn" {
  value       = module.secrets_manager.secret_arn
  description = "ARN of Secrets Manager secret storing production credentials"
}
