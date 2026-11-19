# Retrieves the Availability Zones (AZs) available in your AWS region and selects the first two.
data "aws_availability_zones" "available" {
  state = "available"
}

# 1. Defines local Terraform variables that can be reused throughout your configuration.
# slice(list, start_index, end_index)
locals {
  azs       = slice(data.aws_availability_zones.available.names, 0, 2)
  namespace = "deep-research" # Kubernetes namespace of the app (k8s/namespace.yaml)
}

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 6.7"

  name = var.name
  cidr = "10.0.0.0/16"
  azs  = local.azs

  private_subnets = ["10.0.0.0/20", "10.0.16.0/20"]    # nodes and pods
  public_subnets  = ["10.0.200.0/24", "10.0.201.0/24"] # load balancers and NAT 

  # Cost: one shared NAT Gateway instead of one per AZ (the biggest fixed network cost).
  # For higher availability set single_nat_gateway = false and one_nat_gateway_per_az = true.
  enable_nat_gateway = true
  single_nat_gateway = true

  # Subnet tags that EKS Auto Mode uses to place load balancers.
  public_subnet_tags  = { "kubernetes.io/role/elb" = "1" }
  private_subnet_tags = { "kubernetes.io/role/internal-elb" = "1" }
}


# This Terraform resource creates an S3 Gateway VPC Endpoint, allowing resources inside your private subnets to access Amazon S3 without going through a NAT Gateway.
# 1. First, what problem are we solving?
# Imagine your EKS worker nodes are running inside private subnets.
# Your application needs a Docker image stored in Amazon ECR.
# When Kubernetes starts a new Pod, the worker node needs to pull that image.
# The image is stored in ECR, but there's an important detail:
# ECR stores image metadata and manifests, while the actual image layers are downloaded from Amazon S3.
# So pulling an image involves accessing both ECR and S3.
resource "aws_vpc_endpoint" "s3" {
  vpc_id            = module.vpc.vpc_id
  # Specifies the AWS service you're connecting to.
  service_name      = "com.amazonaws.${var.aws_region}.s3"
  # Gateway	-> Used for S3 and DynamoDB.
  # Interface -> Uses Elastic Network Interfaces (ENIs) and private IP addresses.
  vpc_endpoint_type = "Gateway"
  route_table_ids   = module.vpc.private_route_table_ids
}

