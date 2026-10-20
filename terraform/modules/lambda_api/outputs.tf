# modules/lambda_api/outputs.tf

output "lambda_arn" {
  value       = aws_lambda_function.api.arn
  description = "ARN of the API Lambda function"
}

output "lambda_name" {
  value       = aws_lambda_function.api.function_name
  description = "Name of the API Lambda function"
}

output "lambda_security_group_id" {
  value       = aws_security_group.lambda_sg.id
  description = "Security Group ID of the Lambda function"
}
