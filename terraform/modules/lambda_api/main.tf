# modules/lambda_api/main.tf

# 1. Lambda Security Group
resource "aws_security_group" "lambda_sg" {
  name        = "${var.environment}-${var.project_name}-lambda-sg"
  description = "Security group for Auth API Lambda executing inside VPC"
  vpc_id      = var.vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "${var.environment}-${var.project_name}-lambda-sg"
    Environment = var.environment
  }
}

# 2. IAM Role & Policies
data "aws_iam_policy_document" "lambda_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]
    effect  = "Allow"
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "lambda_role" {
  name               = "${var.environment}-${var.project_name}-lambda-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json

  tags = {
    Environment = var.environment
    Project     = var.project_name
  }
}

# Attach standard VPC execution role (creates elastic network interfaces)
resource "aws_iam_role_policy_attachment" "lambda_vpc_execution" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

# Least-privilege policy granting access ONLY to the application's secret
data "aws_iam_policy_document" "secrets_access" {
  statement {
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [var.secret_arn]
    effect    = "Allow"
  }
}

resource "aws_iam_policy" "secrets_policy" {
  name        = "${var.environment}-${var.project_name}-secrets-policy"
  description = "Allows Lambda to fetch auth secrets from Secrets Manager"
  policy      = data.aws_iam_policy_document.secrets_access.json
}

resource "aws_iam_role_policy_attachment" "attach_secrets" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = aws_iam_policy.secrets_policy.arn
}

# 3. CloudWatch Log Group
resource "aws_cloudwatch_log_group" "lambda_logs" {
  name              = "/aws/lambda/${var.environment}-${var.project_name}-api"
  retention_in_days = var.log_retention_days

  tags = {
    Environment = var.environment
    Project     = var.project_name
  }
}

# 4. Dummy package for Terraform initialization and validation
data "archive_file" "lambda_dummy_zip" {
  type        = "zip"
  output_path = "${path.module}/dummy_lambda.zip"

  source {
    content  = "def handler(event, context): return {'statusCode': 200, 'body': 'OK'}"
    filename = "dummy.py"
  }
}

# 5. Auth API Lambda Function
resource "aws_lambda_function" "api" {
  function_name = "${var.environment}-${var.project_name}-api"
  role          = aws_iam_role.lambda_role.arn
  handler       = "app.main.handler"
  runtime       = "python3.12"
  timeout       = 30
  memory_size   = 512

  filename         = data.archive_file.lambda_dummy_zip.output_path
  source_code_hash = data.archive_file.lambda_dummy_zip.output_base64sha256

  vpc_config {
    subnet_ids         = var.private_subnet_ids
    security_group_ids = [aws_security_group.lambda_sg.id]
  }

  environment {
    variables = {
      ENVIRONMENT                = var.environment
      DATABASE_URL               = var.database_url
      SECRETS_MANAGER_SECRET_ARN = var.secret_arn
      LOG_LEVEL                  = var.environment == "prod" ? "INFO" : "DEBUG"
    }
  }

  depends_on = [
    aws_cloudwatch_log_group.lambda_logs,
    aws_iam_role_policy_attachment.lambda_vpc_execution,
  ]

  tags = {
    Environment = var.environment
    Project     = var.project_name
  }
}
