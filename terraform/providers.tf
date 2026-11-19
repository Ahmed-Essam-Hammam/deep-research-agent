terraform {
  required_version = ">= 1.10.0" # S3 native state locking (use_lockfile) needs >= 1.10

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.59" # required by the pinned EKS module
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project   = var.name
      ManagedBy = "terraform"
    }
  }
}