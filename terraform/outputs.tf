output "cluster_name" {
  description = "GitHub variable EKS_CLUSTER_NAME"
  value       = module.eks.cluster_name
}

output "ecr_repository_name" {
  description = "GitHub variable ECR_REPOSITORY"
  value       = aws_ecr_repository.app.name
}

output "ecr_repository_url" {
  value = aws_ecr_repository.app.repository_url
}

output "github_deploy_role_arn" {
  description = "GitHub secret AWS_DEPLOY_ROLE_ARN"
  value       = aws_iam_role.github_deploy.arn
}

output "github_terraform_role_arn" {
  description = "GitHub secret AWS_TERRAFORM_ROLE_ARN"
  value       = aws_iam_role.github_terraform.arn
}