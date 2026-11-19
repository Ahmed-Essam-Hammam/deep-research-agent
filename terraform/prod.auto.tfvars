# Non-secret settings, loaded automatically locally AND by the GitHub workflow.
# Terraform automatically loads this file when running commands such as terraform plan or terraform apply.
# aws_region must equal the GitHub variable AWS_REGION.
aws_region = "eu-central-1"

# REQUIRED: your IAM user/role ARN (run: aws sts get-caller-identity).
admin_principal_arns = ["arn:aws:iam::057481081900:user/deep-research-admin"]
