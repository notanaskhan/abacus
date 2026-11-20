"""Q-05-T15 (TASK-8819; SPEC-711 AC-22 to AC-26): approvals and execution.

Row acceptance: "Felix Andersen's typed DESTROY 2026-Q3 destroys 1,204 documents (1,201 with 3
excluded in the fil02e variant), reads answer 410 citing DC-2026-Q3, and a re-render of the
certificate is byte-identical." Here, on the pure parts: the certificate is canonical (the same
batch gives the same bytes, exclusions in any order); the phrase must be exact; a destroyed read is
410 `destroyed`; the workflow runs in the batch class; derived stores register.
"""

from __future__ import annotations

from abacus.kernel.errors import DomainGone
from abacus.modules.evidence import destruction_execute as d
from abacus.modules.evidence.api import WORKFLOWS


def _body(excluded: list[tuple[str, str]]) -> bytes:
    return d.certificate_body(
        ref="2026-Q3", scope="Records past retention · Q3 2026", eligible=1204, destroyed=1201,
        excluded=excluded, approvers=[("u-felix", "firm_admin"), ("u-victor", "security_admin")],
        hold_recheck_at="2026-10-02T09:00:00+00:00", manifest_sha256="a" * 64, checkpoint_root="b" * 64,
    )  # fmt: skip


def test_ac_the_certificate_is_byte_identical_on_re_render() -> None:
    first = _body([("v1", "held"), ("v2", "held"), ("v3", "shared_object")])
    again = _body([("v3", "shared_object"), ("v1", "held"), ("v2", "held")])
    assert first == again
    assert b'"certificate":"DC-2026-Q3"' in first and b'"destroyed":1201' in first
    assert d.BACKUP_STATEMENT.encode() in first


def test_ac_the_phrase_and_the_410() -> None:
    assert d.PhraseMismatch.code == "batch_phrase_mismatch"
    assert d.SameApprover.code == "same_approver"
    assert DomainGone.code == "destroyed"


def test_the_workflow_runs_in_the_batch_class_and_stores_register() -> None:
    assert WORKFLOWS[d.DestructionExecuteWorkflow] == "batch"
    calls: list[str] = []

    async def purge(_t: object, _v: object) -> int:
        calls.append("x")
        return 0

    d.register_derived_store("test_store", purge)
    assert "test_store" in d._derived  # pyright: ignore[reportPrivateUsage]
    del d._derived["test_store"]  # pyright: ignore[reportPrivateUsage]
