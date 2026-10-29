output "distribution_id" {
  description = "Set vars.FIRM_DISTRIBUTION_ID in the staging GitHub environment."
  value       = aws_cloudfront_distribution.firm.id
}

output "distribution_arn" {
  description = "The distribution (the web bucket's OAC condition)."
  value       = aws_cloudfront_distribution.firm.arn
}

output "domain_name" {
  description = "The firm app's host until the firm domain exists."
  value       = aws_cloudfront_distribution.firm.domain_name
}

output "api_vpc_origin_id" {
  description = "The API's CloudFront VPC origin (the portal edge reuses it)."
  value       = aws_cloudfront_vpc_origin.api.id
}
