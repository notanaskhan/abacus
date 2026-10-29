# Q-01-T07/T11: release images are scanned by Amazon Inspector (enhanced scanning, on push and
# continuously while the image is recent), which build.yml's `inspector` job reads
# (`inspector2 list-findings` by digest) to decide whether a release is promotable.

resource "aws_inspector2_enabler" "ecr" {
  account_ids    = [data.aws_caller_identity.current.account_id]
  resource_types = ["ECR"]
}

resource "aws_ecr_registry_scanning_configuration" "this" {
  scan_type = "ENHANCED"

  rule {
    scan_frequency = "CONTINUOUS_SCAN"

    repository_filter {
      filter      = "*"
      filter_type = "WILDCARD"
    }
  }

  depends_on = [aws_inspector2_enabler.ecr]
}
