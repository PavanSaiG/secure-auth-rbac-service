# modules/api_gateway/outputs.tf

output "api_endpoint" {
  value       = aws_apigatewayv2_stage.default_stage.invoke_url
  description = "Public API Gateway invocation URL"
}

output "api_id" {
  value       = aws_apigatewayv2_api.http_api.id
  description = "ID of API Gateway"
}
