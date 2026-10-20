# modules/secrets_manager/main.tf

# 1. Random 32-byte string for JWT HMAC-SHA256 signing secret
resource "random_password" "jwt_secret" {
  length  = 48
  special = false
}

# 2. Random DB Master Password
resource "random_password" "db_password" {
  length           = 24
  special          = true
  override_special = "!#$%&*()-_=+[]{}<>:?"
}

# 3. AWS Secrets Manager Secret
resource "aws_secretsmanager_secret" "app_secrets" {
  name                    = "${var.environment}/${var.project_name}/credentials"
  description             = "Production application credentials: DB connection and JWT secret"
  recovery_window_in_days = var.environment == "prod" ? 30 : 0

  tags = {
    Environment = var.environment
    Project     = var.project_name
  }
}

resource "aws_secretsmanager_secret_version" "app_secrets_version" {
  secret_id = aws_secretsmanager_secret.app_secrets.id

  secret_string = jsonencode({
    JWT_SECRET_KEY = random_password.jwt_secret.result
    DB_USER        = "auth_admin"
    DB_PASSWORD    = random_password.db_password.result
    DB_NAME        = "auth_db"
  })
}
