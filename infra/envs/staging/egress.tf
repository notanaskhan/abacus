# Q-01-T14 (SPEC-050 AC-22): the staging VPC resolves only registered hosts (the module's staging
# list) and its own Cloud Map zone; every other lookup answers NXDOMAIN.
module "dns_firewall" {
  source = "../../modules/dns-firewall"

  environment        = "staging"
  profile            = "staging"
  vpc_id             = module.network.vpc_id
  private_zone_names = [aws_service_discovery_private_dns_namespace.internal.name]
}
