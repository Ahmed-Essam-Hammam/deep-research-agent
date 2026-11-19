# EKS Auto Mode: AWS runs the worker nodes, the load balancer controller and the EBS storage
# driver for us - no node groups, no add-ons, no controller to install.
module "eks" {
  source = "terraform-aws-modules/eks/aws"
  version = "~> 21.29"

  name               = var.name
  kubernetes_version = var.kubernetes_version

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets # nodes run in private subnets

  compute_config = {
    enabled    = true
    node_pools = ["general-purpose"]
  }

  # When you create an EKS cluster, AWS provides an API server endpoint.
  # The Kubernetes API server is the component that receives and processes Kubernetes commands.
  # EKS allows you to configure this endpoint as:
  # - Public: Accessible over the internet.
  # - Private: Accessible only from within the cluster's VPC or connected networks.
  # - Both: Accessible through both public and private networking.
  endpoint_public_access = true
  endpoint_private_access = true
  # Controls whether your EKS cluster uses IAM Roles for Service Accounts (IRSA).
  # Normally, when an application runs inside an EKS Pod and needs to access AWS services, such as:
  #  - Amazon S3
  #  - Amazon DynamoDB
  # It needs AWS permissions.
  # IRSA allows you to assign an IAM Role to a specific Kubernetes ServiceAccount.
  # This means your application can access AWS services without storing AWS access keys inside the container.

  # Imagine you have a Pod that needs to upload files to an S3 bucket.
  # The process:
  # 1. You create an IAM Role with permissions to access a specific S3 bucket.
  # 2. You associate that role with a Kubernetes ServiceAccount.
  # 3. Your Pod uses that ServiceAccount.
  # 4. EKS provides a projected identity token.
  # 5. AWS STS validates the token using the cluster's OIDC provider.
  # 6. STS provides temporary AWS credentials.
  # 7. Your application uses those credentials to access S3.
  enable_irsa = false

  # This configuration enables encryption of Kubernetes Secrets stored in your Amazon EKS cluster's data store (etcd).
  encryption_config = {
    resources = ["secrets"]
  }

  # This configuration controls whether the IAM identity that creates the EKS cluster through Terraform (which is the github actions) automatically receives Kubernetes administrator permissions.
  # why false: It's an implementation of the Principle of Least Privilege.
  # Each identity receives only the permissions necessary to perform its job.
  enable_cluster_creator_admin_permissions = false

  # This configuration creates an EKS Access Entry for GitHub Actions, allowing your GitHub Actions IAM role to interact with your EKS cluster,
  # but only with editing permissions inside your application namespace.

  # 1. What is access_entries?
  # In EKS, an Access Entry connects an AWS IAM identity (user or role) to your Kubernetes cluster.

  # It tells EKS:
  # 1. Which IAM identity is allowed to access the cluster.
  # 2. What permissions that identity receives.
  # 3. Whether those permissions apply to the entire cluster or specific namespaces.

  # Terraform's merge() function combines multiple maps into one map.

  access_entries = merge(
    {
      github_deploy = {
        # This specifies WHO gets access.
        principal_arn = aws_iam_role.github_deploy.arn
        policy_associations = {
          # This specifies WHICH permissions the IAM role receives.
          edit = {
            # This references an AWS-managed EKS access policy called AmazonEKSEditPolicy.
            # It grants permissions to create, update, delete, and manage many Kubernetes resources.
            policy_arn   = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSEditPolicy"
            # It determines WHERE the policy applies.
            # There are two main scopes:
	        # cluster	Permissions -> apply across the entire cluster.
            # namespace Permissions -> apply only within specified namespaces.
            access_scope = { type = "namespace", namespaces = [local.namespace] }
          }
        }
      }
    },
        {
      for arn in var.admin_principal_arns : "admin-${md5(arn)}" => {
        principal_arn = arn
        policy_associations = {
          admin = {
            policy_arn   = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy"
            access_scope = { type = "cluster" }
          }
        }
      }
    }
  )
}



