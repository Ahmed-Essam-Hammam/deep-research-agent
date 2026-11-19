variable "aws_region" {
  description = "AWS region to deploy into."
  type        = string
  default     = "eu-central-1"
}

variable "name" {
  description = "Name used for the cluster, VPC, ECR repository and IAM roles."
  type        = string
  default     = "deep-research"
}

variable "github_repo" {
  description = "GitHub repository allowed to deploy, as owner/name."
  type        = string
  default     = "Ahmed-Essam-Hammam/deep-research-agent"
}

variable "kubernetes_version" {
  description = "EKS Kubernetes version (check AWS for versions still in standard support)."
  type        = string
  default     = "1.36"
}

variable "admin_principal_arns" {
  description = "IAM user/role ARNs that get cluster-admin (kubectl) access. For IAM Identity Center use the role ARN WITHOUT the aws-reserved/sso.amazonaws.com/ path."
  type        = list(string)

  validation {
    condition     = length(var.admin_principal_arns) > 0 && alltrue([for a in var.admin_principal_arns : can(regex("^arn:aws[a-z-]*:iam::[0-9]{12}:(user|role)/.+", a))])
    error_message = "Set admin_principal_arns in prod.auto.tfvars to at least one IAM user or role ARN (yours)."
  }
}

variable "create_github_oidc_provider" {
  description = "Create the GitHub OIDC provider. Set false if your AWS account already has one."
  type        = bool
  default     = true
}

