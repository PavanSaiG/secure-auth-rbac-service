# modules/rds/outputs.tf

output "endpoint" {
  value       = aws_db_instance.postgres.endpoint
  description = "PostgreSQL connection endpoint (host:port)"
}

output "address" {
  value       = aws_db_instance.postgres.address
  description = "Database hostname"
}

output "port" {
  value       = aws_db_instance.postgres.port
  description = "Database port"
}

output "db_name" {
  value       = aws_db_instance.postgres.db_name
  description = "Database name"
}

output "rds_security_group_id" {
  value       = aws_security_group.rds_sg.id
  description = "Security group ID of the RDS database"
}
