"""R-01-T22 (TASK-1353): the `email_templates` slice, Brightwater Hale's six templates as POR-20's
figures give them ("6 of 6 published · 1 with draft changes"). Opt-in and deterministic, every
kind has a loader handler, it replays after the editor flag, and every seeded version would
publish: its call to action is the key's, its variables are the key's whitelist, and the lint
finds nothing (no amount, TIN, account number or platform name)."""

from __future__ import annotations

from abacus.modules.communications.lint import lint_template
from abacus.modules.communications.render import TemplateContent
from abacus.modules.communications.template_keys import DESIGNED
from abacus.modules.communications.template_service import check_content
from abacus_tools.synthetic.scenarios.brightwater_hale import SCENARIO_HASH, build, loader
from abacus_tools.synthetic.scenarios.brightwater_hale.email_templates import (
    EDITOR_FLAG,
    SLICE,
    TEMPLATES,
    email_template_events,
)
from abacus_tools.synthetic.scenarios.brightwater_hale.people import FIRM_ROLES
from abacus_tools.synthetic.scenarios.brightwater_hale.slices import registered

SLICES = ("audit_core", SLICE)
REGISTRATIONS = {r.key: r for r in DESIGNED}


def test_the_slice_is_registered_opt_in_and_deterministic() -> None:
    assert SLICE in registered()
    assert all(e.slice == "audit_core" for e in build().events)
    assert build().fingerprint() == SCENARIO_HASH
    assert build(slices=SLICES).fingerprint() == build(slices=SLICES).fingerprint()
    assert {e.kind for e in email_template_events()} <= set(loader.HANDLERS)


def test_the_designed_six_at_por20s_versions_by_grace_the_firm_admin() -> None:
    assert {t.key for t in TEMPLATES} == set(REGISTRATIONS)
    versions = {t.key: (t.published, t.draft) for t in TEMPLATES}
    assert versions == {
        "invitation": (3, False),
        "reminder": (3, True),
        "signature_request": (2, False),
        "deliverable_ready": (2, False),
        "confirmation_request": (1, False),
        "reconnect_request": (1, False),
    }
    events = email_template_events()
    assert FIRM_ROLES["GH"] == "firm_admin"
    assert all(e.actor == "GH" for e in events if e.kind != "platform.flag_set")
    assert sum(e.kind == "communications.email_template_published" for e in events) == 12
    assert sum(e.kind == "communications.email_template_draft_saved" for e in events) == 1


def test_the_editor_flag_replays_first() -> None:
    kinds = [e.kind for e in loader.replay_order(build(slices=SLICES).events)]
    flag = next(
        i
        for i, e in enumerate(loader.replay_order(build(slices=SLICES).events))
        if e.kind == "platform.flag_set" and e.data.get("flag") == EDITOR_FLAG
    )
    assert flag < kinds.index("communications.email_template_published")
    assert kinds.index("identity.staff_member_added") < flag


def test_every_seeded_version_would_publish() -> None:
    for template in TEMPLATES:
        registration = REGISTRATIONS[template.key]
        content = TemplateContent.from_json(template.content())
        check_content(content, registration)
        assert lint_template(content, registration) == [], template.key
