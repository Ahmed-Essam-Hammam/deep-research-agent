resource "aws_ecr_repository" "app" {
  name                 = "${var.name}-agent"
  image_tag_mutability = "IMMUTABLE" # a Git SHA tag can never be overwritten.

  # This configuration enables automatic vulnerability scanning of Docker images whenever you push them to Amazon ECR (Elastic Container Registry).
  image_scanning_configuration {
    scan_on_push = true
  }
}


# This Terraform resource creates an ECR Lifecycle Policy that automatically deletes old Docker images from your Amazon ECR repository, keeping only the 30 most recent images.

resource "aws_ecr_lifecycle_policy" "app" {
  repository = aws_ecr_repository.app.name

  policy = jsonencode({
    rules = [{
      # Defines the priority of this rule relative to other lifecycle rules.
      # - Lower numbers mean higher priority.
      # - Rule priorities must be unique within the lifecycle policy.
      rulePriority = 1
      description  = "Keep the 30 most recent images"

      #	tagStatus = "any"	Consider all images, whether tagged or untagged.
      # countType = "imageCountMoreThan"	Apply the rule when the image count exceeds a threshold.
      # countNumber = 30	Keep the 30 most recent images.
      selection = { tagStatus = "any", countType = "imageCountMoreThan", countNumber = 30 }

      # expire means delete the selected images from the repository.
      action = { type = "expire" }
    }]
  })
}
