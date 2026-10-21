"""Q-01-T12 / SPEC-050 AC-17: settings validation outside local and test, written from the spec.

Spec: "Given `ABACUS_ENVIRONMENT` in `staging` or `production`, then settings validation refuses
to start without KMS, keyring, scanner, SES and WorkOS settings; in `production` it also refuses an
`anthropic_api_key` (ADR-113: Bedrock only for client data) and a `fake` route." Regions: ADR-142
(us-east-2 primary, us-west-2 DR, KMS and SES in US regions). The WorkOS settings are not built
yet (Q-01-T17) and are not tested here.

Only the setting names from epic Q-01 section 4.10 are used.
"""

from __future__ import annotations

import pytest

from abacus.kernel.config import settings

from .support import fails, override, use_environment, use_staging

ENVIRONMENTS = ["staging", "production"]


@pytest.mark.parametrize("name", ENVIRONMENTS)
def test_ac17_a_complete_environment_starts(monkeypatch: pytest.MonkeyPatch, name: str) -> None:
    use_staging(monkeypatch, ABACUS_ENVIRONMENT=name)
    assert settings().environment == name


REQUIRED = {
    "kms": ("ABACUS_KMS_PLATFORM_KEY_ALIAS",),
    "keyring": ("ABACUS_TEMPORAL_PAYLOAD_KEYS", "ABACUS_TEMPORAL_PAYLOAD_CURRENT"),
    "scanner": ("ABACUS_SCANNER_ENDPOINT",),
    "ses_configuration_set": ("ABACUS_SES_CONFIGURATION_SET",),
    "ses_sender": ("ABACUS_SES_FROM_ADDRESS",),
}


@pytest.mark.parametrize("name", ENVIRONMENTS)
@pytest.mark.parametrize("group", sorted(REQUIRED))
def test_ac17_the_process_refuses_to_start_without_each_adapter_setting(
    monkeypatch: pytest.MonkeyPatch, name: str, group: str
) -> None:
    use_staging(monkeypatch, without=REQUIRED[group], ABACUS_ENVIRONMENT=name)
    fails(settings)


@pytest.mark.parametrize("name", ["local", "test"])
def test_ac17_local_and_test_start_without_the_adapter_settings(
    monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    use_environment(monkeypatch, {"ABACUS_ENVIRONMENT": name})
    assert settings().environment == name


def test_ac17_production_refuses_an_anthropic_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    use_staging(
        monkeypatch,
        ABACUS_ENVIRONMENT="production",
        ABACUS_ANTHROPIC_API_KEY="fake-provider-key-not-real",
    )
    fails(settings)


def test_ac17_staging_may_hold_an_anthropic_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """The provider's endpoint is on the staging egress allowlist for synthetic data (epic F2)."""
    use_staging(monkeypatch, ABACUS_ANTHROPIC_API_KEY="fake-provider-key-not-real")
    assert settings().environment == "staging"


@pytest.mark.xfail(
    strict=True,
    reason="Q-01 bug: SPEC-050 AC-17 says production refuses a `fake` model route, but production "
    "starts on the default route list (TASK-343 deferred it to the first production model "
    "route, Q-02) (TASK-346 #346)",
)
def test_ac17_production_refuses_a_fake_model_route(monkeypatch: pytest.MonkeyPatch) -> None:
    use_staging(monkeypatch, ABACUS_ENVIRONMENT="production", ABACUS_MODEL_ROUTES='["fake"]')
    fails(settings)


@pytest.mark.parametrize("variable", ["ABACUS_SES_REGION", "ABACUS_KMS_REGION"])
@pytest.mark.parametrize("region", ["eu-west-1", "ap-southeast-2", "ca-central-1"])
def test_ac17_kms_and_ses_regions_must_be_us_regions(
    monkeypatch: pytest.MonkeyPatch, variable: str, region: str
) -> None:
    """ADR-142: tenants are pinned to a US region; SES and KMS live in us-east-2 / us-west-2."""
    use_staging(monkeypatch)
    override(monkeypatch, variable, region)
    fails(settings)


@pytest.mark.parametrize("variable", ["ABACUS_SES_REGION", "ABACUS_KMS_REGION"])
def test_ac17_the_primary_region_is_accepted(
    monkeypatch: pytest.MonkeyPatch, variable: str
) -> None:
    use_staging(monkeypatch)
    override(monkeypatch, variable, "us-east-2")
    assert settings().environment == "staging"


def test_ac17_the_tenant_key_alias_prefix_is_the_documented_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    use_staging(monkeypatch)
    assert settings().kms_alias_prefix == "alias/abacus/tenant/"
