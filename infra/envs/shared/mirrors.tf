# Q-01-T07/T14 (review fix, DEC-1008): the two third-party images staging runs (ClamAV and the
# Temporal dev server, both on the image allowlist) are mirrored here by digest, so the staging
# VPC pulls only from ECR and the DNS Firewall needs no Docker Hub egress. The builder copies each
# pinned index with `docker buildx imagetools create` (infra/README.md "Staging stand-up"), which
# keeps the upstream digest; tags are immutable.

locals {
  mirrors = toset(["thirdparty/clamav/clamav", "thirdparty/temporalio/temporal"])
}

resource "aws_ecr_repository" "mirror" {
  for_each             = local.mirrors
  name                 = each.value
  image_tag_mutability = "IMMUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "KMS"
    kms_key         = aws_kms_key.artifacts.arn
  }
}

resource "aws_ecr_repository_policy" "mirror" {
  for_each   = length(local.readers) > 0 ? local.mirrors : toset([])
  repository = aws_ecr_repository.mirror[each.value].name
  policy     = data.aws_iam_policy_document.ecr_readers[0].json
}
