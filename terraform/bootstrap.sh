#!/usr/bin/env bash
# One-time: create the S3 bucket that stores Terraform state, then write backend.hcl.
# Usage: ./bootstrap.sh <aws-region>      (needs AWS credentials; safe to re-run)
set -euo pipefail

REGION="${1:?usage: ./bootstrap.sh <aws-region>}"
ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
BUCKET="deep-research-tfstate-${ACCOUNT}"

if aws s3api head-bucket --bucket "$BUCKET" 2>/dev/null; then
  echo "Bucket $BUCKET already exists - re-applying settings."
elif [ "$REGION" = "us-east-1" ]; then
  aws s3api create-bucket --bucket "$BUCKET" --region "$REGION" >/dev/null
else
  aws s3api create-bucket --bucket "$BUCKET" --region "$REGION" \
    --create-bucket-configuration "LocationConstraint=$REGION" >/dev/null
fi

aws s3api put-bucket-versioning --bucket "$BUCKET" --versioning-configuration Status=Enabled
aws s3api put-bucket-encryption --bucket "$BUCKET" --server-side-encryption-configuration \
  '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'
aws s3api put-public-access-block --bucket "$BUCKET" --public-access-block-configuration \
  BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true

printf 'bucket = "%s"\nregion = "%s"\n' "$BUCKET" "$REGION" > "$(dirname "$0")/backend.hcl"
echo "Done. State bucket: $BUCKET   (GitHub variable TF_STATE_BUCKET)"
