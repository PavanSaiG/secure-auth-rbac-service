# modules/secrets_manager/outputs.tf

output "secret_arn" {
  value       = aws_secretsmanager_secret.app_secrets.arn
  description = "ARN of Secrets Manager secret containing app credentials"
}

output "secret_name" {
  value       = aws_secretsmanager_secret.app_secrets.name
  description = "Name of Secrets Manager secret"
}

output "db_password" {
  value       = random_password.db_password.result
  sensitive   = true
  description = "Generated database master password"
}
