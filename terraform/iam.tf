# This Terraform code configures GitHub Actions to authenticate with AWS using OpenID Connect (OIDC),
# instead of storing AWS Access Keys and Secret Access Keys in GitHub Secrets.

resource "aws_iam_openid_connect_provider" "github" {
  # If var.create_github_oidc_provider = true, create one provider.
  # If false, create zero providers. 
  count = var.create_github_oidc_provider ? 1 : 0

  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]
}

# The idea is:
# - If the OIDC provider doesn't exist, create it.
# - If it already exists, retrieve it instead of trying to create a duplicate.

#An AWS account might already have a GitHub OIDC provider because another project or repository created it. You don't want Terraform to fail because you're attempting to create a duplicate.
data "aws_iam_openid_connect_provider" "github" {
  count = var.create_github_oidc_provider ? 0 : 1
  url   = "https://token.actions.githubusercontent.com"
}


# Scenario A: Creating a new provider -> var.create_github_oidc_provider = true
# Terraform evaluates: aws_iam_openid_connect_provider.github[0].arn

# Scenario B: Using an existing provider -> var.create_github_oidc_provider = false
# Terraform evaluates: data.aws_iam_openid_connect_provider.github[0].arn
locals {
  oidc_provider_arn = var.create_github_oidc_provider ? aws_iam_openid_connect_provider.github[0].arn : data.aws_iam_openid_connect_provider.github[0].arn
}

# This code defines an IAM Role Trust Policy that determines exactly which GitHub Actions workflows are allowed to assume an AWS IAM Role.
# The important distinction is:
# - Trust policy: Who is allowed to assume the role?
# - Permissions policy: What can someone do after assuming the role?

# Trust policy: only this repository, and only the listed subjects, can assume a role.
data "aws_iam_policy_document" "trust_main_branch" {

  # This specifies the action that the policy allows.
  # sts:AssumeRoleWithWebIdentity is an AWS STS action.
  # Remember our previous flow:
  # GitHub Actions obtains an OIDC token and sends it to AWS STS.
  # STS validates that token and, if the trust policy allows it, returns temporary AWS credentials.

  # This action is what allows that process to happen.
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    # A principal identifies the entity that is allowed to perform the action.
    principals {
      type        = "Federated"               # means we're dealing with an external identity provider.
      identifiers = [local.oidc_provider_arn] # contains the ARN of our GitHub OIDC provider.
    }

    # AWS trusts tokens issued by the GitHub OIDC provider to request role assumption.
    # But does that mean every GitHub repository can assume this role?
    # No! That's where the conditions come in.

    # OIDC tokens contain claims (information about the token).
    # One of those claims is aud, which stands for Audience.
    # It identifies the intended recipient of the token.
    # Here we're saying:
    # The token's audience must be exactly: sts.amazonaws.com
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }
    # This is the condition that restricts access to your repository and branch.
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:${var.github_repo}:ref:refs/heads/main"]
    }
  }
}


#This is very similar to the previous trust policy, but there's one important difference: this policy allows two different GitHub Actions contexts to assume the same AWS IAM Role.
# Those contexts are:
# 1. A workflow running directly on the main branch.
# 2. A workflow running inside a GitHub Environment named terraform-production.
data "aws_iam_policy_document" "trust_terraform" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [local.oidc_provider_arn]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }
    # The plan job runs on main; the apply job runs in the approval-protected environment.
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values = [
        "repo:${var.github_repo}:ref:refs/heads/main",
        "repo:${var.github_repo}:environment:terraform-production",
      ]
    }
  }
}


################################################################################
# Role 1: application deploy (deploy.yml) - least privilege
################################################################################
# After creating the policies, we now need to use (assume) them

resource "aws_iam_role" "github_deploy" {
  name               = "${var.name}-github-deploy"
  assume_role_policy = data.aws_iam_policy_document.trust_main_branch.json
}

# This code defines the permissions policy for your GitHub deployment IAM Role (github_deploy).
# Unlike the trust policy we discussed earlier, this policy determines what GitHub Actions can actually do inside AWS after assuming the role.

# In this case, the permissions are limited to three things:
# 1. Authenticate with Amazon ECR, through ecr:GetAuthorizationToken
# 2. Push and pull Docker images from a specific ECR repository.
# 3. Retrieve information about a specific EKS cluster.

data "aws_iam_policy_document" "github_deploy" {
  statement {
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"] # Because ecr:GetAuthorizationToken does not support resource-level permissions, That means AWS requires this permission to apply to all resources (*), you can't specifiy a single resource (repository) to apply the this permission to. 
  }
  statement {
    actions = [
      "ecr:BatchCheckLayerAvailability", "ecr:BatchGetImage", "ecr:CompleteLayerUpload",
      "ecr:DescribeImages", "ecr:GetDownloadUrlForLayer", "ecr:InitiateLayerUpload",
      "ecr:PutImage", "ecr:UploadLayerPart",
    ]
    resources = [aws_ecr_repository.app.arn]
  }
}

resource "aws_iam_role_policy" "github_deploy" {
  role   = aws_iam_role.github_deploy.id
  policy = data.aws_iam_policy_document.github_deploy.json
}


################################################################################
# Role 2: infrastructure (terraform.yml)
################################################################################
# Unlike github_deploy, which has limited permissions to deploy application images to EKS, 
# this role has AdministratorAccess because Terraform needs to create, modify, and delete AWS infrastructure.
resource "aws_iam_role" "github_terraform" {
  name               = "${var.name}-github-terraform"
  assume_role_policy = data.aws_iam_policy_document.trust_terraform.json
}

resource "aws_iam_role_policy_attachment" "github_terraform" {
  role       = aws_iam_role.github_terraform.name
  policy_arn = "arn:aws:iam::aws:policy/AdministratorAccess"
}









