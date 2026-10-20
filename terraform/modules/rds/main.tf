# modules/rds/main.tf

# 1. RDS Database Security Group
resource "aws_security_group" "rds_sg" {
  name        = "${var.environment}-${var.project_name}-rds-sg"
  description = "Controls database ingress traffic strictly from application Lambda"
  vpc_id      = var.vpc_id

  ingress {
    description     = "PostgreSQL inbound from Lambda compute security group"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [var.lambda_security_group_id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "${var.environment}-${var.project_name}-rds-sg"
    Environment = var.environment
  }
}

# 2. Managed Amazon RDS PostgreSQL Instance
resource "aws_db_instance" "postgres" {
  identifier        = "${var.environment}-${var.project_name}-db"
  engine            = "postgres"
  engine_version    = "16.3"
  instance_class    = var.instance_class
  allocated_storage = var.allocated_storage
  storage_type      = "gp3"

  db_name  = "auth_db"
  username = "auth_admin"
  password = var.db_password
  port     = 5432

  db_subnet_group_name   = var.db_subnet_group_name
  vpc_security_group_ids = [aws_security_group.rds_sg.id]

  # Security & Compliance controls
  storage_encrypted       = true
  multi_az                = var.multi_az
  publicly_accessible     = false
  skip_final_snapshot     = var.environment != "prod"
  deletion_protection     = var.environment == "prod"
  backup_retention_period = var.environment == "prod" ? 30 : 7

  tags = {
    Environment = var.environment
    Project     = var.project_name
  }
}
