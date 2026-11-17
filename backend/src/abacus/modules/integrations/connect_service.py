"""Connect, reconnect and disconnect (W-01-T08; C20 v2; SPEC-659 AC-10 to AC-16, AC-24 to
AC-26; red).

- **Start** (`connect_firm`, fresh MFA; `connect_personal`, the caller's own): the tile must be
  listed and honest for this firm (a port for the key and mode, `connect_ports.port_for`), its
  prerequisite scope granted (409 `prerequisite_scope_missing`), and not paused or a file bridge
  (OQ-3, OQ-9: no Reconnect). A firm app (client-authorised) is connected at once: no OAuth, no
  secret (AC-16). Otherwise a single-use state is minted: only its SHA-256 is stored, with the
  PKCE verifier sealed under the tenant key bound to that hash, for ten minutes (AC-11); the
  install reads `connecting` (a reconnect keeps its status until it completes).
- **Complete**: the state is spent first, in its own unit of work, by `UPDATE … WHERE spent_at
  IS NULL AND expires_at > now AND user_id = the caller` (AC-12): a replayed, expired or other
  person's state is 409 `invalid_state` and nothing else happens. The code is exchanged through
  the port; a declined grant is 409 `connect_declined`. The token is sealed (the only copy), the
  install connected with who and when, the granted scopes and the consent version; one
  `integration_events` row and an audit event naming the person. Neither the code nor the state
  is logged or stored.
- **Disconnect** (firm: the typed name, 422 `confirm_name_mismatch`; `seen_version`, 409
  `stale_version`; fresh MFA. Personal: the caller's own only, else 404): a best-effort remote
  revoke, then the secret erased and the install disconnected, with its event and audit (AC-24 to
  AC-26). A firm app's disable (a client-authorised row) suspends every live client connection
  of its provider in the same unit of work (`connections.api.suspend_for_firm_app`: "Needs
  reauth", secret retired, one audit row each; AC-25, OQ-5, DEC-5083) and reports the count; new
  POR-16 starts refuse 409 `firm_app_disabled` until it is enabled again.
- **Membership end** (`membership.deactivated`): every personal install of the person is
  disconnected and its secret deleted (AC-13).
"""

from __future__ import annotations

import base64
import hashlib
import secrets
from dataclasses import dataclass
from datetime import timedelta
from typing import Final, Literal, cast
from uuid import UUID

from sqlalchemy import delete, func, insert, select, update

from abacus.kernel.clock import system_now
from abacus.kernel.config import settings
from abacus.kernel.crypto import open_sealed, seal
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import NotFound
from abacus.kernel.uow import Ref, Target, UnitOfWork, uow
from abacus.kernel.uow.relay import OutboxEvent
from abacus.modules.connections.api import suspend_for_firm_app
from abacus.modules.identity.api import AuthContext, Resource, authorise, is_synthetic_firm
from abacus.modules.integrations.connect_catalog import (
    WorkbenchRow,
    firm_installs,
    honest_listing,
    published_row,
)
from abacus.modules.integrations.connect_errors import (
    ConfirmNameMismatch,
    ConnectDeclined,
    IntegrationNotAvailable,
    InvalidState,
    PrerequisiteScopeMissing,
    StaleVersion,
)
from abacus.modules.integrations.connect_ports import port_for
from abacus.modules.integrations.kill_switch import ensure_not_paused
from abacus.modules.integrations.models import (
    FirmIntegration,
    IntegrationEvent,
    IntegrationOAuthState,
    UserIntegration,
)
from abacus.modules.integrations.ports import ConnectMode, ConnectPort, ConnectRefused
from abacus.modules.integrations.secrets import (
    TARGET,
    USER_TARGET,
    erase_secret,
    erase_user_secret,
    open_secret,
    open_user_secret,
    store_secret,
    store_user_secret,
)

STATE_TTL: Final = timedelta(minutes=10)
STATE_PURGE: Final = timedelta(hours=24)
CALLBACK_PATH: Final = "/workbench/connect/callback"
ScopeKind = Literal["firm", "user"]


@dataclass(frozen=True)
class Started:
    status: Literal["connecting", "connected"]
    authorise_url: str | None


@dataclass(frozen=True)
class Disconnected:
    key: str
    suspended_client_connections: int


def redirect_uri() -> str:
    return f"{settings().app_base_url.rstrip('/')}{CALLBACK_PATH}"


def state_hash(state: str) -> str:
    return hashlib.sha256(state.encode()).hexdigest()


def pkce_pair() -> tuple[str, str]:
    """The verifier (kept sealed) and its S256 challenge (sent)."""
    verifier = secrets.token_urlsafe(48)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return verifier, base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def _verifier_binding(digest: str) -> str:
    return f"oauth_state:{digest}"


def _mode(row: WorkbenchRow, install_mode: str | None) -> ConnectMode:
    if row.ownership_mode == "personal":
        return "personal"
    if row.ownership_mode == "client_authorised":
        return "firm_app"
    return "file_bridge" if install_mode == "file_bridge" else "token"


async def _event(
    tx: UnitOfWork,
    tenant_id: UUID,
    kind: str,
    scope: ScopeKind,
    install_id: UUID,
    key: str,
    actor: UUID | None,
) -> None:
    await tx.session.execute(
        insert(IntegrationEvent).values(
            tenant_id=tenant_id,
            install_kind=scope,
            install_id=install_id,
            catalog_key=key,
            kind=kind,
            at=system_now(),
            actor_user_id=actor,
        )
    )


async def _port(ctx: AuthContext, row: WorkbenchRow, mode: ConnectMode) -> ConnectPort:
    synthetic = await is_synthetic_firm(ctx.tenant)
    port = port_for(row.key, mode, synthetic=synthetic)
    if port is None or honest_listing(row, synthetic=synthetic) != "available":
        raise IntegrationNotAvailable
    return port


async def _mint(
    tx: UnitOfWork, ctx: AuthContext, key: str, scope: ScopeKind, purpose: str
) -> tuple[str, str]:
    """A fresh state and challenge; only the state's hash and the sealed verifier are stored."""
    # 0890: spent or expired states go after a day (the app's delete grant), when one is minted.
    await tx.session.execute(
        delete(IntegrationOAuthState).where(
            IntegrationOAuthState.created_at < func.now() - STATE_PURGE
        )
    )
    state = secrets.token_urlsafe(32)
    digest = state_hash(state)
    verifier, challenge = pkce_pair()
    sealed = await seal(ctx.tenant_id, verifier.encode("ascii"), _verifier_binding(digest))
    await tx.session.execute(
        insert(IntegrationOAuthState).values(
            state_sha256=digest,
            tenant_id=ctx.tenant_id,
            user_id=ctx.user_id,
            catalog_key=key,
            scope_kind=scope,
            purpose=purpose,
            pkce_verifier_sealed=sealed,
            # The transaction's start on the database's clock: never later than `created_at`
            # (`clock_timestamp()`, evaluated first), so 0890's ten-minute CHECK always holds.
            expires_at=func.now() + STATE_TTL,
        )
    )
    return state, challenge


async def start_firm(ctx: AuthContext, key: str) -> Started:
    """Enable, Reconnect or enable a firm app (the route authorised `connect_firm`, fresh MFA)."""
    row = await published_row(ctx, key)
    if row.ownership_mode == "personal":
        raise NotFound("integration")
    await ensure_not_paused(ctx.tenant_id, key)  # W-01-T07 rest (DEC-5433)
    async with tenant_session(ctx.tenant) as session:
        firm = await firm_installs(session)
    install = firm.get(key)
    if row.prerequisite is not None:
        needed = firm.get(row.prerequisite["key"])
        if needed is None or row.prerequisite["scope"] not in needed.granted_scopes:
            raise PrerequisiteScopeMissing(facts={"key": row.prerequisite["key"]})
    # A live install reconnects from Needs reauth or Needs attention, or retries a connect it
    # started; connected has nothing to do, and paused hides Reconnect (OQ-9).
    if install is not None and install.status in ("connected", "paused"):
        raise IntegrationNotAvailable(facts={"status": install.status})
    mode = _mode(row, install.mode if install else None)
    if mode == "file_bridge":
        raise IntegrationNotAvailable(facts={"mode": "file_bridge"})  # OQ-3: no Reconnect
    port = await _port(ctx, row, mode)
    async with uow(ctx.tenant) as tx:
        if mode == "firm_app":
            install_id = await tx.session.scalar(
                insert(FirmIntegration)
                .values(
                    tenant_id=ctx.tenant_id,
                    catalog_key=key,
                    status="connected",
                    mode="firm_app",
                    created_by=ctx.user_id,
                    status_changed_at=system_now(),
                    connected_by=ctx.user_id,
                    connected_at=system_now(),
                    consent_version=row.consent_version,
                )
                .returning(FirmIntegration.id)
            )
            install_id = cast(UUID, install_id)
            await _event(tx, ctx.tenant_id, "connected", "firm", install_id, key, ctx.user_id)
            tx.record("integration.connected", target=Target(TARGET, install_id))
            return Started("connected", None)
        purpose = "connect"
        if install is None:
            created = await tx.session.scalar(
                insert(FirmIntegration)
                .values(
                    tenant_id=ctx.tenant_id,
                    catalog_key=key,
                    status="connecting",
                    mode="token",
                    created_by=ctx.user_id,
                    status_changed_at=system_now(),
                )
                .returning(FirmIntegration.id)
            )
            install_id = cast(UUID, created)
        else:
            install_id = install.id
            purpose = "connect" if install.status == "connecting" else "reconnect"
        state, challenge = await _mint(tx, ctx, key, "firm", purpose)
        await _event(tx, ctx.tenant_id, "connect_started", "firm", install_id, key, ctx.user_id)
        tx.record("integration.connect_started", target=Target(TARGET, install_id), after=Ref(n=1))
    return Started(
        "connecting",
        port.authorise_url(state=state, code_challenge=challenge, redirect_uri=redirect_uri()),
    )


async def start_personal(ctx: AuthContext, key: str) -> Started:
    """Connect "acting as you" (the route authorised `connect_personal` for the caller)."""
    row = await published_row(ctx, key)
    if row.ownership_mode != "personal":
        raise NotFound("integration")
    await ensure_not_paused(ctx.tenant_id, key)  # W-01-T07 rest (DEC-5433)
    port = await _port(ctx, row, "personal")
    async with uow(ctx.tenant) as tx:
        found = (
            await tx.session.execute(
                select(UserIntegration)
                .where(
                    UserIntegration.user_id == ctx.user_id,
                    UserIntegration.catalog_key == key,
                    UserIntegration.status != "disconnected",
                )
                .with_for_update()
            )
        ).scalar_one_or_none()
        if found is not None and found.status in ("connected", "paused"):
            raise IntegrationNotAvailable(facts={"status": found.status})
        if found is None:
            created = await tx.session.scalar(
                insert(UserIntegration)
                .values(
                    tenant_id=ctx.tenant_id,
                    user_id=ctx.user_id,
                    catalog_key=key,
                    status="connecting",
                    status_changed_at=system_now(),
                )
                .returning(UserIntegration.id)
            )
            install_id = cast(UUID, created)
            purpose = "connect"
        else:
            install_id = found.id
            purpose = "connect" if found.status == "connecting" else "reconnect"
        state, challenge = await _mint(tx, ctx, key, "user", purpose)
        await _event(tx, ctx.tenant_id, "connect_started", "user", install_id, key, ctx.user_id)
        tx.record(
            "integration.connect_started",
            target=Target(USER_TARGET, install_id),
            after=Ref(n=1),
        )
    return Started(
        "connecting",
        port.authorise_url(state=state, code_challenge=challenge, redirect_uri=redirect_uri()),
    )


@dataclass(frozen=True)
class _Spent:
    key: str
    scope: ScopeKind
    purpose: str
    verifier: str


async def _spend(ctx: AuthContext, state: str) -> _Spent | None:
    """Spend the state in its own unit of work (AC-12): once, unexpired, the caller's."""
    digest = state_hash(state)
    async with uow(ctx.tenant) as tx:
        row = (
            await tx.session.execute(
                update(IntegrationOAuthState)
                .where(
                    IntegrationOAuthState.state_sha256 == digest,
                    IntegrationOAuthState.spent_at.is_(None),
                    IntegrationOAuthState.expires_at > func.clock_timestamp(),
                    IntegrationOAuthState.user_id == ctx.user_id,
                )
                .values(spent_at=system_now())
                .returning(
                    IntegrationOAuthState.catalog_key,
                    IntegrationOAuthState.scope_kind,
                    IntegrationOAuthState.purpose,
                    IntegrationOAuthState.pkce_verifier_sealed,
                )
            )
        ).first()
        tx.record(
            "integration.oauth_state_spent" if row else "integration.oauth_state_refused",
            target=Target("firm", ctx.tenant_id),
            after=Ref(spent=1 if row else 0),
        )
    if row is None:
        return None
    key, scope, purpose, sealed = row
    verifier = await open_sealed(ctx.tenant_id, sealed, _verifier_binding(digest))
    return _Spent(str(key), cast(ScopeKind, scope), str(purpose), verifier.decode("ascii"))


async def complete(ctx: AuthContext, state: str, code: str) -> str:
    """The OAuth callback: the key it connected."""
    spent = await _spend(ctx, state)
    if spent is None:
        raise InvalidState
    if spent.scope == "firm":
        # Security review (S46): the person must still hold the firm action, with fresh MFA, when
        # the provider calls back; a state minted before their role or session changed is spent.
        await authorise(ctx, "integration.connect_firm", Resource.firm(ctx.tenant_id))
    # W-01-T07 rest (DEC-5433): a pause set after the start stops the code exchange too.
    await ensure_not_paused(ctx.tenant_id, spent.key)
    row = await published_row(ctx, spent.key)
    mode: ConnectMode = "personal" if spent.scope == "user" else "token"
    port = await _port(ctx, row, mode)
    try:
        grant = await port.exchange_code(
            code=code, code_verifier=spent.verifier, redirect_uri=redirect_uri()
        )
    except ConnectRefused:
        raise ConnectDeclined from None
    kind = "reconnected" if spent.purpose == "reconnect" else "connected"
    now = system_now()
    facts = {
        "status": "connected",
        "status_reason_code": None,
        "status_changed_at": now,
        "connected_at": now,
        "token_renews_at": grant.renews_at,
        "granted_scopes": list(grant.scopes),
        "consent_version": row.consent_version,
    }
    async with uow(ctx.tenant) as tx:
        if spent.scope == "firm":
            install = (
                await tx.session.execute(
                    select(FirmIntegration)
                    .where(
                        FirmIntegration.catalog_key == spent.key,
                        FirmIntegration.status != "disconnected",
                    )
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if install is None:
                raise InvalidState  # disconnected meanwhile
            await erase_secret(tx, install.id)
            await store_secret(tx, ctx.tenant_id, install.id, grant.secret)
            await tx.session.execute(
                update(FirmIntegration)
                .where(FirmIntegration.id == install.id)
                .values(**facts, connected_by=ctx.user_id, version=FirmIntegration.version + 1)
            )
            await _event(tx, ctx.tenant_id, kind, "firm", install.id, spent.key, ctx.user_id)
            tx.record(f"integration.{kind}", target=Target(TARGET, install.id))
        else:
            mine = (
                await tx.session.execute(
                    select(UserIntegration)
                    .where(
                        UserIntegration.user_id == ctx.user_id,
                        UserIntegration.catalog_key == spent.key,
                        UserIntegration.status != "disconnected",
                    )
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if mine is None:
                raise InvalidState
            await erase_user_secret(tx, mine.id)
            await store_user_secret(tx, ctx.tenant_id, mine.id, grant.secret)
            await tx.session.execute(
                update(UserIntegration)
                .where(UserIntegration.id == mine.id)
                .values(**facts, version=UserIntegration.version + 1)
            )
            await _event(tx, ctx.tenant_id, kind, "user", mine.id, spent.key, ctx.user_id)
            tx.record(f"integration.{kind}", target=Target(USER_TARGET, mine.id))
    return spent.key


async def _revoke_remote(port: ConnectPort | None, secret: bytes | None) -> None:
    """Best effort (AC-24): a provider outage never keeps a secret alive here."""
    if port is None or secret is None:
        return
    try:
        await port.revoke(secret)
    except Exception:
        return


async def disconnect_firm(
    ctx: AuthContext, key: str, confirm_name: str, seen_version: int
) -> Disconnected:
    """The typed-name disconnect (the route authorised `disconnect_firm`, fresh MFA)."""
    row = await published_row(ctx, key)
    if confirm_name.strip() != row.name:
        raise ConfirmNameMismatch
    async with tenant_session(ctx.tenant) as session:
        install = (await firm_installs(session)).get(key)
    if install is None:
        raise NotFound("firm_integration")
    if install.version != seen_version:
        raise StaleVersion(facts={"version": install.version})
    secret = await open_secret(ctx.tenant, install.id)
    mode = _mode(row, install.mode)
    suspended = 0
    async with uow(ctx.tenant) as tx:
        done = await tx.session.scalar(
            update(FirmIntegration)
            .where(FirmIntegration.id == install.id, FirmIntegration.version == seen_version)
            .values(
                status="disconnected",
                status_reason_code="disconnected_by_person",
                status_changed_at=system_now(),
                version=FirmIntegration.version + 1,
            )
            .returning(FirmIntegration.id)
        )
        if done is None:
            raise StaleVersion
        await erase_secret(tx, install.id)
        if mode == "firm_app" and row.connector_provider is not None:
            # AC-25: the firm's client connections of the provider stop syncing (Needs reauth).
            suspended = await suspend_for_firm_app(tx, ctx.tenant_id, row.connector_provider)
        await _event(tx, ctx.tenant_id, "disconnected", "firm", install.id, key, ctx.user_id)
        tx.record(
            "integration.disconnected",
            target=Target(TARGET, install.id),
            after=Ref(n=suspended),
        )
    # Security review (S46): the remote revoke runs only after the local disconnect committed, with
    # the copy opened before the erase; a refused or stale request never revokes a live grant.
    synthetic = await is_synthetic_firm(ctx.tenant)
    await _revoke_remote(port_for(key, mode, synthetic=synthetic), secret)
    return Disconnected(key, suspended)


async def disconnect_personal(ctx: AuthContext, key: str) -> Disconnected:
    """The caller's own personal install only (AC-26): anyone else's is 404."""
    async with tenant_session(ctx.tenant) as session:
        mine = (
            await session.execute(
                select(UserIntegration).where(
                    UserIntegration.user_id == ctx.user_id,
                    UserIntegration.catalog_key == key,
                    UserIntegration.status != "disconnected",
                )
            )
        ).scalar_one_or_none()
    if mine is None:
        raise NotFound("integration")
    secret = await open_user_secret(ctx.tenant, mine.id)
    async with uow(ctx.tenant) as tx:
        await _end_personal(tx, ctx.tenant_id, mine.id, key, ctx.user_id, "disconnected_by_person")
    synthetic = await is_synthetic_firm(ctx.tenant)
    await _revoke_remote(port_for(key, "personal", synthetic=synthetic), secret)
    return Disconnected(key, 0)


async def _end_personal(
    tx: UnitOfWork, tenant_id: UUID, install_id: UUID, key: str, actor: UUID | None, reason: str
) -> None:
    await tx.session.execute(
        update(UserIntegration)
        .where(UserIntegration.id == install_id)
        .values(
            status="disconnected",
            status_reason_code=reason,
            status_changed_at=system_now(),
            version=UserIntegration.version + 1,
        )
    )
    await erase_user_secret(tx, install_id)
    await _event(tx, tenant_id, "disconnected", "user", install_id, key, actor)
    tx.record("integration.disconnected", target=Target(USER_TARGET, install_id), after=Ref(n=1))


async def membership_ended(event: OutboxEvent) -> None:
    """AC-13: a deactivated person's personal installs are disconnected and their secrets
    deleted, in the firm's own unit of work."""
    raw = event.payload.get("user_id")
    if not isinstance(raw, str):
        return
    user_id = UUID(raw)
    tenant = TenantContext(event.tenant_id, "system", "integrations:membership_ended")
    async with tenant_session(tenant) as session:
        live = (
            await session.execute(
                select(UserIntegration.id, UserIntegration.catalog_key).where(
                    UserIntegration.user_id == user_id, UserIntegration.status != "disconnected"
                )
            )
        ).all()
    if not live:
        return
    async with uow(tenant) as tx:
        for install_id, key in live:
            await _end_personal(
                tx, event.tenant_id, install_id, str(key), None, "membership_ended"
            )
