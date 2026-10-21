"""Q-01-T12 / SPEC-050 AC-14 and AC-17: the Temporal payload keyring (P2), written from the spec.

Spec text: "the codec loads several key IDs and one current ID; a payload sealed under a
retired-but-present ID still decodes; removing a key that histories still use is refused by the
rotation runbook (RB-09)". The values reach the process as environment (Secrets Manager injects
them into the task definition), so these tests rotate by changing the environment: public names
only are taken from the code (`payload_codec()`, `PayloadEncryptionCodec`,
`PayloadDecryptionError`, the `ABACUS_TEMPORAL_PAYLOAD_*` settings).
"""

from __future__ import annotations

import json

import pytest
from temporalio.api.common.v1 import Payload

from abacus.kernel.config import settings
from abacus.kernel.crypto.payload_codec import PayloadDecryptionError, PayloadEncryptionCodec
from abacus.kernel.temporal import payload_codec

from .support import KEYRING_V1, KEYRING_V2, afails, fails, use_staging

THIRD = "payload-key-three-Bd7Nw4Xe2Kr9Hs6Ly3Tq-third"
BODY = b'{"workflow": "synthetic-fixture-4417"}'


def payload() -> Payload:
    return Payload(metadata={"encoding": b"json/plain"}, data=BODY)


def keyring(monkeypatch: pytest.MonkeyPatch, keys: dict[str, str], current: str) -> None:
    use_staging(
        monkeypatch,
        ABACUS_TEMPORAL_PAYLOAD_KEYS=json.dumps(keys),
        ABACUS_TEMPORAL_PAYLOAD_CURRENT=current,
    )


async def seal_under(
    monkeypatch: pytest.MonkeyPatch, keys: dict[str, str], current: str
) -> Payload:
    keyring(monkeypatch, keys, current)
    (sealed,) = await payload_codec().encode([payload()])
    return sealed


async def opens(
    monkeypatch: pytest.MonkeyPatch, keys: dict[str, str], current: str, p: Payload
) -> bool:
    keyring(monkeypatch, keys, current)
    try:
        (opened,) = await payload_codec().decode([p])
    except PayloadDecryptionError:
        return False
    assert opened.data == BODY
    return True


# --- the codec ----------------------------------------------------------------------------------


async def test_ac14_sealed_payloads_hide_their_content() -> None:
    codec = PayloadEncryptionCodec({"v1": KEYRING_V1.encode()}, current="v1")
    (sealed,) = await codec.encode([payload()])
    assert BODY not in sealed.data
    assert sealed.metadata != payload().metadata


async def test_ac14_a_codec_holds_several_keys_and_one_current() -> None:
    old = PayloadEncryptionCodec({"v1": KEYRING_V1.encode()}, current="v1")
    rotated = PayloadEncryptionCodec(
        {"v1": KEYRING_V1.encode(), "v2": KEYRING_V2.encode()}, current="v2"
    )
    (under_v1,) = await old.encode([payload()])
    (under_v2,) = await rotated.encode([payload()])
    # A retired-but-present key still opens what it sealed ...
    assert (await rotated.decode([under_v1]))[0].data == BODY
    # ... and the current key is the one that seals: a codec that only has v1 cannot open it.
    with pytest.raises(PayloadDecryptionError):
        await old.decode([under_v2])


async def test_ac14_the_current_key_must_be_in_the_keyring() -> None:
    fails(lambda: PayloadEncryptionCodec({"v1": KEYRING_V1.encode()}, current="v9"))


async def test_ac14_a_payload_altered_in_transit_is_refused() -> None:
    codec = PayloadEncryptionCodec({"v1": KEYRING_V1.encode()}, current="v1")
    (sealed,) = await codec.encode([payload()])
    flipped = bytearray(sealed.data)
    flipped[-1] ^= 0x01
    tampered = Payload(metadata=dict(sealed.metadata), data=bytes(flipped))
    with pytest.raises(PayloadDecryptionError):
        await codec.decode([tampered])


async def test_ac14_a_payload_sealed_under_another_key_is_refused() -> None:
    ours = PayloadEncryptionCodec({"v1": KEYRING_V1.encode()}, current="v1")
    theirs = PayloadEncryptionCodec(
        {"v1": KEYRING_V2.encode()}, current="v1"
    )  # same ID, other secret
    (sealed,) = await theirs.encode([payload()])
    with pytest.raises(PayloadDecryptionError):
        await ours.decode([sealed])


# --- rotation through the environment -----------------------------------------------------------


async def test_ac14_rotation_a_payload_sealed_under_a_retired_but_present_id_still_decodes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    before = await seal_under(monkeypatch, {"v1": KEYRING_V1}, "v1")
    # Add v2 and make it current; v1 stays in the keyring.
    assert await opens(monkeypatch, {"v1": KEYRING_V1, "v2": KEYRING_V2}, "v2", before)


async def test_ac14_rotation_new_payloads_are_sealed_under_the_current_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    after = await seal_under(monkeypatch, {"v1": KEYRING_V1, "v2": KEYRING_V2}, "v2")
    # A process that still only knows v1 cannot open it, so v2 sealed it ...
    assert not await opens(monkeypatch, {"v1": KEYRING_V1}, "v1", after)
    # ... and a process that has dropped v1 can.
    assert await opens(monkeypatch, {"v2": KEYRING_V2}, "v2", after)


async def test_ac14_rotation_a_removed_key_no_longer_decodes_what_it_sealed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The reason RB-09 refuses removing a key that histories still use: the payloads become
    unreadable. The codec itself fails closed."""
    before = await seal_under(monkeypatch, {"v1": KEYRING_V1}, "v1")
    assert not await opens(monkeypatch, {"v2": KEYRING_V2}, "v2", before)


async def test_ac14_three_keys_and_a_middle_current(monkeypatch: pytest.MonkeyPatch) -> None:
    ring = {"v1": KEYRING_V1, "v2": KEYRING_V2, "v3": THIRD}
    sealed_v1 = await seal_under(monkeypatch, {"v1": KEYRING_V1}, "v1")
    sealed_v3 = await seal_under(monkeypatch, {"v3": THIRD}, "v3")
    assert await opens(monkeypatch, ring, "v2", sealed_v1)
    assert await opens(monkeypatch, ring, "v2", sealed_v3)


# --- settings (AC-17): the keyring is required and must be coherent -----------------------------


@pytest.mark.parametrize("name", ["staging", "production"])
def test_ac17_aws_environments_do_not_start_without_a_keyring(
    monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    use_staging(
        monkeypatch,
        without=("ABACUS_TEMPORAL_PAYLOAD_KEYS", "ABACUS_TEMPORAL_PAYLOAD_CURRENT"),
        ABACUS_ENVIRONMENT=name,
    )
    fails(settings)


def test_ac17_a_keyring_without_a_current_id_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    use_staging(monkeypatch, without=("ABACUS_TEMPORAL_PAYLOAD_CURRENT",))
    fails(settings)


def test_ac17_a_current_id_outside_the_keyring_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    keyring(monkeypatch, {"v1": KEYRING_V1}, "v2")
    fails(settings)


async def test_ac17_the_keyring_is_what_staging_seals_with(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sealed = await seal_under(monkeypatch, {"v1": KEYRING_V1}, "v1")
    assert BODY not in sealed.data
    # Not sealable by a codec holding a different secret under the same ID.
    keyring(monkeypatch, {"v1": KEYRING_V2}, "v1")
    await afails(lambda: payload_codec().decode([sealed]))
