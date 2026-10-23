# PR previews (Q-01-T49, D-OPS-13): abacus-shared-previews, its cookie-gated CloudFront host and
# the pull_request-only role preview.yml assumes. The OIDC provider comes from infra/bootstrap.
module "previews" {
  source = "../../modules/previews"

  github_repo = var.github_repo
}
