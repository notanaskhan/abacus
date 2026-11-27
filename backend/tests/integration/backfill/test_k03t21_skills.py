# ac-test-author: ayushkbhatia
"""K-03-T21 (TASK-9015; K-03 F10; KNW-06 c; DEC-6021) on the migrated Postgres. Row acceptance:
"Importing BH-SK-430 v1 and v2 needs skill.import with fresh MFA, unsafe markdown is refused, and
a pin to a draft skill version shows the KNW-06c warning without blocking publish."

Margaret (the quality partner) imports BH-SK-430 v1 (published) and v2 (draft) with fresh MFA;
without it, or as a manager, the import is refused; a body with raw HTML is refused whole and
writes nothing; an identical re-import adds nothing. FS v6 pins v2: the pin reads as the KNW-06c
warning, a warning (never an error), and only the published v1 body is what a run would use."""

from __future__ import annotations

import uuid
from typing import cast

import httpx
import pytest

from abacus.kernel.db import TenantContext
from abacus.modules.methodology.api import skills

from .support import Net, Seeder

pytestmark = pytest.mark.asyncio

V1 = "# Inventory obsolescence\n\nRead the aged inventory report and the [policy](#policy).\n"
V2 = V1 + "\n- Compare the reserve with prior-year write-offs.\n"


def _pack(*versions: tuple[int, str, str]) -> dict[str, object]:
    return {
        "pack": {
            "skills": [
                {
                    "key": "BH-SK-430",
                    "name": "Inventory obsolescence review",
                    "group": "Inventory",
                    "versions": [
                        {"version": n, "status": status, "body_md": body,
                         "linked_step_keys": ["BH-FS-345"]}
                        for n, status, body in versions
                    ],
                }
            ]
        }
    }  # fmt: skip


def _code(response: httpx.Response) -> str:
    return str(response.json().get("code") or response.json().get("detail"))


async def test_k03t21_acceptance_import_needs_fresh_mfa_refuses_unsafe_and_warns_on_draft_pins(
    net: Net, seed: Seeder
) -> None:
    tenant = await seed.firm()
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'templates_v2.enabled', 'true', 'test-seed', 'K-03-T21')",
        tenant,
    )
    owner = await seed.person(tenant, "quality_partner")
    manager = await seed.person(tenant)
    both = _pack((1, "published", V1), (2, "draft", V2))

    stale = await net.call(
        "POST", "/v1/skills/import", owner, body=both, mfa=False, headers=net.keyed()
    )
    assert stale.status_code in (401, 403), stale.text
    refused = await net.call("POST", "/v1/skills/import", manager, body=both, headers=net.keyed())
    assert refused.status_code in (403, 404), refused.text

    unsafe = _pack((1, "published", V1 + "\n<script>alert(1)</script>\n"))
    bad = await net.call("POST", "/v1/skills/import", owner, body=unsafe, headers=net.keyed())
    assert bad.status_code == 422 and _code(bad) == "skill_markdown_unsafe", bad.text
    assert bad.json()["facts"]["reason"] == "html"
    assert await seed.value("SELECT count(*) FROM agent_skills WHERE tenant_id = $1", tenant) == 0

    made = await net.call("POST", "/v1/skills/import", owner, body=both, headers=net.keyed())
    assert made.status_code == 201, made.text
    assert [(i["key"], i["version"], i["status"]) for i in made.json()["items"]] == [
        ("BH-SK-430", 1, "published"),
        ("BH-SK-430", 2, "draft"),
    ]
    again = await net.call("POST", "/v1/skills/import", owner, body=both, headers=net.keyed())
    assert again.status_code == 201 and again.json()["items"] == []
    changed = await net.call(
        "POST", "/v1/skills/import", owner, body=_pack((2, "draft", V2 + "more")),
        headers=net.keyed(),
    )  # fmt: skip
    assert changed.status_code == 409 and _code(changed) == "skill_version_exists", changed.text
    events = await seed.value(
        "SELECT count(*) FROM audit_events WHERE tenant_id = $1 "
        "AND action = 'skill_version.imported'",
        tenant,
    )
    assert events == 2
    listed = await net.call("GET", "/v1/skills", owner)
    assert listed.status_code == 200 and len(listed.json()["items"]) == 2

    v1, v2 = (uuid.UUID(i["version_id"]) for i in made.json()["items"])
    methodology = uuid.uuid4()
    await seed.run(
        "INSERT INTO methodology_templates (id, tenant_id, name, created_by, engagement_types, "
        "family) VALUES ($1, $2, 'BH Audit Methodology · FS', $3, '{fs_audit}', 'fs')",
        methodology,
        tenant,
        owner.user_id,
    )
    template = await seed.value(
        "INSERT INTO engagement_templates (tenant_id, methodology_template_id, name, family) "
        "VALUES ($1, $2, 'FS audit', 'fs') RETURNING id",
        tenant,
        methodology,
    )
    draft = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO template_versions (tenant_id, template_id, seq, label, created_by) "
            "VALUES ($1, $2, 6, 'FS v6', $3) RETURNING id",
            tenant,
            template,
            owner.user_id,
        ),
    )
    await seed.run(
        "INSERT INTO template_skill_pins (tenant_id, template_version_id, skill_key, "
        "skill_version_id) VALUES ($1, $2, 'BH-SK-430', $3)",
        tenant,
        draft,
        v2,
    )
    warnings = await net.call("GET", f"/v1/template-versions/{draft}/skill-pin-warnings", owner)
    assert warnings.status_code == 200, warnings.text
    assert warnings.json()["items"] == [
        {
            "skill_key": "BH-SK-430",
            "version": 2,
            "severity": "warning",
            "text": "Skill BH-SK-430 v2 is a draft",
        },
    ]  # fmt: skip  (a warning: publish is never blocked by it)

    system = TenantContext(tenant, "system", "test:k03t21")
    assert await skills.published_body(system, v1) == V1
    assert await skills.published_body(system, v2) is None


@pytest.mark.parametrize(
    ("body", "reason"),
    [
        ("Hello <b>there</b>", "html"),
        ("![chart](https://x.test/a.png)", "image"),
        ("[click](javascript:alert(1))", "script_url"),
        ("[site](http://plain.test)", "link_target"),
        ("[ref]: https://x.test\n", "reference_definition"),
        ("Tab‮right", "control"),
        ("", "length"),
    ],
)
def test_k03t21_the_sanitised_schema_refuses(body: str, reason: str) -> None:
    assert skills.unsafe_reason(body) == reason


def test_k03t21_the_schema_keeps_plain_markdown() -> None:
    body = "## Steps\n\n1. Read *the* report.\n2. See [the guide](https://bh.test/g).\n\n> Note\n"
    assert skills.unsafe_reason(body) is None
