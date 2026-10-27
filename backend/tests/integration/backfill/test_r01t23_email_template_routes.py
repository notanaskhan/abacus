"""R-01-T23 through the API (TASK-1420; C16 v1.1): preview, test send and import over HTTP.

The test send names no recipient: a body with any address field is refused (422) before anything
runs, the email goes to the caller's own account address with "[Test]", and a retry with the same
`Idempotency-Key` sends nothing again. Preview and a dry-run import write nothing; a stale second
factor is refused (403). Probe strings only."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field

import pytest

from abacus.modules.communications.transport import configure_transport

from .support import Net, Person, Seeder

BASE = "/v1/firm/email-templates"
DRAFT = {
    "subject": "{work_item} needs {client_first_name}",
    "preheader": "",
    "blocks": [
        {"id": "h1", "kind": "heading", "text": "Hi {client_first_name}"},
        {"id": "p1", "kind": "paragraph", "text": "Probe from {firm_name}."},
        {"id": "l1", "kind": "item_list", "text": "{open_items}"},
    ],
    "cta_label": "Open documents",
    "cta_target": "documents",
}


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


async def _admin(seed: Seeder) -> Person:
    tenant = await seed.firm()
    admin = await seed.person(tenant, "firm_admin")
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'portal.settings_editor', 'true', 'r01t23', 'TASK-1420')",
        tenant,
    )
    return admin


async def _published(net: Net, admin: Person) -> None:
    saved = await net.call(
        "PUT", f"{BASE}/reminder/draft", admin, body={**DRAFT, "expected_version": 0}
    )
    assert saved.status_code == 200, saved.text
    published = await net.http.post(
        f"{BASE}/reminder/publish",
        headers={**net.headers(admin), "Idempotency-Key": f"pub-{uuid.uuid4()}"},
    )
    assert published.status_code == 201, published.text


async def test_a_test_send_goes_to_the_caller_only_and_once(
    net: Net, seed: Seeder, mailbox: Mailbox
) -> None:
    admin = await _admin(seed)
    await _published(net, admin)
    own = str(await seed.value("SELECT email FROM users WHERE id = $1", admin.user_id))
    headers = {**net.headers(admin), "Idempotency-Key": "test-send-1"}
    for other in ({"to": "someone@example.test"}, {"bcc": "someone@example.test"}):
        refused = await net.http.post(f"{BASE}/reminder/test-send", json=other, headers=headers)
        assert refused.status_code == 422
    assert mailbox.sent == []
    first = await net.http.post(f"{BASE}/reminder/test-send", json={}, headers=headers)
    assert first.status_code == 202, first.text
    again = await net.http.post(f"{BASE}/reminder/test-send", json={}, headers=headers)
    assert again.status_code == 202
    assert first.json()["sent_to"] == own and first.json()["subject"].startswith("[Test] ")
    assert again.json()["message_id"] == first.json()["message_id"]
    assert [m["to"] for m in mailbox.sent] == [own]  # once, and only to the caller


async def test_preview_and_a_dry_run_import_write_nothing(net: Net, seed: Seeder) -> None:
    admin = await _admin(seed)
    await _published(net, admin)
    before = await seed.actions(admin.tenant_id)
    preview = await net.call(
        "POST", f"{BASE}/reminder/preview", admin, body={"source": "published", "width": 390}
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["findings"] == []
    assert "accrued" not in preview.json()["html"].lower()
    bundle = {
        "dry_run": True,
        "bundle": [
            {
                "key": "reminder",
                "subject": "Pay $3,200 now",
                "blocks": DRAFT["blocks"],
                "cta_label": "Open documents",
                "cta_target": "documents",
            }
        ],
    }
    report = await net.call("POST", f"{BASE}/import", admin, body=bundle)
    assert report.status_code == 200, report.text
    result = report.json()["results"][0]
    assert result["change"] == "refused"
    assert {"code": "amount", "block_id": "subject", "variable": None} in result["findings"]
    assert await seed.actions(admin.tenant_id) == before
    applied = await net.call("POST", f"{BASE}/import", admin, body={**bundle, "dry_run": False})
    assert applied.status_code == 422 and applied.json()["detail"] == "template_lint_failed"
    stale = await net.call("POST", f"{BASE}/import", admin, body=bundle, mfa=False)
    assert stale.status_code == 403
