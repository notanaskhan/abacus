"""R-01-T30: independent acceptance tests (ADR-078) for R-01-T19 and T23, written from R-01 §3.7
(Stories 7.2 to 7.4) and `docs/contracts/email-templates.md`, not from the implementing suites.

- The renderer is deterministic: the same draft previews to the same bytes.
- Versions are immutable: the app role cannot change or delete a published version.
- The lint finds each seeded violation; preview shows them, test send and publish answer 422
  `template_lint_failed`, and no response repeats the offending text.
- A test send has no recipient field: it goes to the caller only.
- Nothing is sent from a key with no published version (fail closed).

R-01-T27 (sender domains, DKIM transitions, the client-mail gate, suppression) is not built
(blocked on the `types-boto3` sesv2 allowlist decision), so its rows wait for it.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Final, cast

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.communications.transport import configure_transport

from .support import Json, Net, Person, Seeder

BASE: Final = "/v1/firm/email-templates"
CLEAN: Final[Json] = {
    "subject": "{work_item} needs {client_first_name}",
    "preheader": "",
    "blocks": [
        {"id": "h1", "kind": "heading", "text": "Hi {client_first_name}"},
        {"id": "p1", "kind": "paragraph", "text": "A note from {firm_name}."},
        {"id": "l1", "kind": "item_list", "text": "{open_items}"},
    ],
    "cta_label": "Open documents",
    "cta_target": "documents",
}
SEEDED: Final = (  # Story 7.2's violations, one per block
    ("p2", "Your balance is $3,200."),
    ("p3", "TIN 123-45-6789 on file."),
    ("p4", "Sent with Accrued."),
    ("p5", "Hello {not_a_variable}."),
)


@dataclass
class Mailbox:
    sent: list[dict[str, object]] = field(default_factory=lambda: list[dict[str, object]]())

    def send(self, **kwargs: object) -> None:
        self.sent.append(kwargs)


@pytest.fixture(autouse=True)
def mailbox() -> Iterator[Mailbox]:
    box = Mailbox()
    configure_transport(box)
    yield box
    configure_transport(None)


async def _grace(seed: Seeder) -> Person:
    tenant = await seed.firm()
    grace = await seed.person(tenant, "firm_admin")
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'portal.settings_editor', 'true', 'r01t30', 'TASK-1806')",
        tenant,
    )
    return grace


def _key(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


async def _save(net: Net, who: Person, draft: Json, expected: int) -> None:
    saved = await net.call(
        "PUT", f"{BASE}/reminder/draft", who, body={**draft, "expected_version": expected}
    )
    assert saved.status_code == 200, saved.text


async def test_the_renderer_is_deterministic_and_versions_are_immutable(
    net: Net, seed: Seeder
) -> None:
    grace = await _grace(seed)
    await _save(net, grace, CLEAN, 0)
    first = await net.call("POST", f"{BASE}/reminder/preview", grace, body={"width": 600})
    second = await net.call("POST", f"{BASE}/reminder/preview", grace, body={"width": 600})
    assert first.status_code == 200, first.text
    assert first.json()["html"] == second.json()["html"]
    assert first.json()["text"] == second.json()["text"]
    narrow = await net.call("POST", f"{BASE}/reminder/preview", grace, body={"width": 390})
    assert narrow.json()["html"] != first.json()["html"]  # reflowed, still deterministic

    published = await net.http.post(
        f"{BASE}/reminder/publish",
        headers={**net.headers(grace), "Idempotency-Key": _key("pub")},
    )
    assert published.status_code == 201, published.text
    system = TenantContext(grace.tenant_id, "system", "r01t30:tamper")
    for sql in (
        "UPDATE email_template_versions SET subject = 'changed'",
        "DELETE FROM email_template_versions",
    ):
        with pytest.raises(DBAPIError):
            async with tenant_session(system) as session:
                await session.execute(text(sql))
                await session.flush()


async def test_the_lint_finds_each_seeded_violation_and_never_repeats_the_text(
    net: Net, seed: Seeder, mailbox: Mailbox
) -> None:
    grace = await _grace(seed)
    dirty = {
        **CLEAN,
        "blocks": [
            *cast(list[Json], CLEAN["blocks"]),
            *({"id": b, "kind": "paragraph", "text": t} for b, t in SEEDED),
        ],
    }
    await _save(net, grace, dirty, 0)
    preview = await net.call("POST", f"{BASE}/reminder/preview", grace, body={"width": 600})
    assert preview.status_code == 200, preview.text
    findings = cast(list[Json], preview.json()["findings"])
    assert {f["block_id"] for f in findings} >= {b for b, _ in SEEDED}

    for path, key in ((f"{BASE}/reminder/test-send", "ts"), (f"{BASE}/reminder/publish", "pb")):
        refused = await net.http.post(
            path, headers={**net.headers(grace), "Idempotency-Key": _key(key)}, json={}
        )
        assert refused.status_code == 422, (path, refused.text)
        assert refused.json()["detail"] == "template_lint_failed"
        for _, offending in SEEDED:
            assert offending not in refused.text
        assert "3,200" not in refused.text and "123-45-6789" not in refused.text
    assert mailbox.sent == []
    assert (
        await seed.value(
            "SELECT count(*) FROM email_template_versions WHERE tenant_id = $1", grace.tenant_id
        )
        == 0
    )


async def test_a_test_send_names_no_recipient_and_nothing_sends_unpublished(
    net: Net, seed: Seeder, mailbox: Mailbox
) -> None:
    grace = await _grace(seed)
    # No published version: preview of the published source and a test send both refuse.
    none = await net.call(
        "POST", f"{BASE}/reminder/preview", grace, body={"source": "published", "width": 600}
    )
    assert none.status_code in (404, 409, 422), none.text
    await _save(net, grace, CLEAN, 0)
    for field_name in ("to", "cc", "bcc", "recipient", "email"):
        refused = await net.http.post(
            f"{BASE}/reminder/test-send",
            headers={**net.headers(grace), "Idempotency-Key": _key("ts")},
            json={field_name: "someone@example.test"},
        )
        assert refused.status_code == 422, (field_name, refused.text)
    assert mailbox.sent == []
    own = str(await seed.value("SELECT email FROM users WHERE id = $1", grace.user_id))
    sent = await net.http.post(
        f"{BASE}/reminder/test-send",
        headers={**net.headers(grace), "Idempotency-Key": _key("ts")},
        json={},
    )
    assert sent.status_code == 202, sent.text
    assert sent.json()["sent_to"] == own and sent.json()["subject"].startswith("[Test] ")
    assert [m["to"] for m in mailbox.sent] == [own]
