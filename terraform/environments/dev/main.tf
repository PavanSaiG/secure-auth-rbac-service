# environments/dev/main.tf

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.50"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.4"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Environment = var.environment
      Project     = var.project_name
      ManagedBy   = "Terraform"
    }
  }
}

# 1. Multi-AZ VPC Module
module "vpc" {
  source       = "../../modules/vpc"
  environment  = var.environment
  project_name = var.project_name
}

# 2. Secrets Manager Module
module "secrets_manager" {
  source       = "../../modules/secrets_manager"
  environment  = var.environment
  project_name = var.project_name
}

# 3. RDS Managed PostgreSQL Module
module "rds" {
  source                   = "../../modules/rds"
  environment              = var.environment
  project_name             = var.project_name
  vpc_id                   = module.vpc.vpc_id
  db_subnet_group_name     = module.vpc.db_subnet_group_name
  lambda_security_group_id = module.lambda_api.lambda_security_group_id
  db_password              = module.secrets_manager.db_password
  instance_class           = "db.t4g.micro"
  allocated_storage        = 20
  multi_az                 = false
}

# 4. API Lambda inside VPC
module "lambda_api" {
  source             = "../../modules/lambda_api"
  environment        = var.environment
  project_name       = var.project_name
  vpc_id             = module.vpc.vpc_id
  private_subnet_ids = module.vpc.private_subnet_ids
  secret_arn         = module.secrets_manager.secret_arn
  database_url       = "postgresql+asyncpg://auth_admin:${module.secrets_manager.db_password}@${module.rds.endpoint}/${module.rds.db_name}"
  log_retention_days = var.log_retention_days
}

# 5. HTTP API Gateway
module "api_gateway" {
  source               = "../../modules/api_gateway"
  environment          = var.environment
  project_name         = var.project_name
  lambda_function_arn  = module.lambda_api.lambda_arn
  lambda_function_name = module.lambda_api.lambda_name
  log_retention_days   = var.log_retention_days
}
