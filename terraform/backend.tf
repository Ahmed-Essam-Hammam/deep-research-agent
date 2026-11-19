# This configuration tells Terraform to store its state file in an Amazon S3 bucket instead of storing it locally on your machine.
# It also enables encryption and state locking to protect your infrastructure state and prevent conflicting Terraform operations.
terraform {
  backend "s3" {
    key          = "deep-research/terraform.tfstate"
    encrypt      = true
    use_lockfile = true
  }
}