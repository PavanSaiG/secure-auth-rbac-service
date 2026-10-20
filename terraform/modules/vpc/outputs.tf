# modules/vpc/outputs.tf

output "vpc_id" {
  value       = aws_vpc.main.id
  description = "ID of the VPC"
}

output "public_subnet_ids" {
  value       = aws_subnet.public[*].id
  description = "List of public subnet IDs"
}

output "private_subnet_ids" {
  value       = aws_subnet.private[*].id
  description = "List of private subnet IDs for Lambda"
}

output "database_subnet_ids" {
  value       = aws_subnet.database[*].id
  description = "List of isolated database subnet IDs"
}

output "db_subnet_group_name" {
  value       = aws_db_subnet_group.db_subnet_group.name
  description = "RDS DB subnet group name"
}
