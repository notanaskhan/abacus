"""Q-05-T11 (TASK-8713; SPEC-711 AC-21, AC-22; DEC-5709): eligibility is the later of the policy's
expiry and the object's observed retain-until, never while held or inside an unlocked archive;
an object shared with a version that is not eligible stays out of the batch; the batch is the
assembly's quarter."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from abacus.modules.evidence.eligibility import VersionFacts, eligible_at, quarter_ref, select

NOW = datetime(2026, 9, 8, 14, 0, tzinfo=UTC)
PAST = datetime(2026, 1, 1, tzinfo=UTC)
FUTURE = datetime(2027, 1, 1, tzinfo=UTC)


def _f(
    key: str | None = None,
    *,
    policy: datetime | None = PAST,
    observed: datetime | None = None,
    held: bool = False,
    unlocked: bool = False,
    client: UUID | None = None,
) -> VersionFacts:
    return VersionFacts(
        uuid4(),
        key or str(uuid4()),
        "v1",
        "client_document",
        client or uuid4(),
        policy,
        observed,
        held,
        unlocked,
    )


def test_ac_eligible_at_is_the_later_of_policy_and_observed_lock() -> None:
    assert eligible_at(_f(policy=PAST, observed=FUTURE)) == FUTURE
    assert eligible_at(_f(policy=FUTURE, observed=PAST)) == FUTURE
    assert eligible_at(_f(policy=None, observed=PAST)) is None


def test_ac_never_while_held_or_inside_an_unlocked_archive() -> None:
    chosen = select([_f(held=True), _f(unlocked=True), _f()], NOW)
    assert len(chosen.items) == 1
    assert chosen.held == 1


def test_ac_a_shared_object_with_a_non_eligible_version_stays_out() -> None:
    shared = "objects/abc"
    chosen = select([_f(shared), _f(shared, policy=FUTURE), _f()], NOW)
    assert len(chosen.items) == 1
    assert chosen.shared_excluded == 1
    assert all(f.object_key != shared for f in chosen.items)


def test_ac_the_batch_counts_former_clients_and_names_its_quarter() -> None:
    a, b = uuid4(), uuid4()
    chosen = select([_f(client=a), _f(client=a), _f(client=b)], NOW)
    assert (len(chosen.items), chosen.clients) == (3, 2)
    assert quarter_ref(NOW) == "2026-Q3"
