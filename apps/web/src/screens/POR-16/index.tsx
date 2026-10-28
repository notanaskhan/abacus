import type {
  ConsentCopyOut,
  PortalConnectionCardOut,
  PortalConnectionDetailOut,
} from "@abacus/api-client";
import {
  connectionDetailOptions,
  disconnectConnectionMutation,
  listEntityConnectionsOptions,
  listEntityConnectionsQueryKey,
  retryConnectionMutation,
  startConnectionMutation,
} from "@abacus/api-client/query";
import {
  Button,
  DEFAULT_TZ,
  Dialog,
  Drawer,
  DrawerCard,
  EmptyState,
  ICON_NAMES,
  Icon,
  type IconName,
  Pane,
  PortalBrandProvider,
  PortalLayout,
  RegistryStatus,
  SheetModal,
  Spinner,
  Tag,
  Toggle,
  cn,
  date,
  time,
  toast,
  usePortalBrand,
} from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, useId, useState } from "react";
import { useNow } from "../../app-core/clock";
import { brandOf, useBranding, usePortalToolbar } from "../../domain/portal";
import { COPY } from "./copy";

// POR-16 · Connections (A-02-T18; A-02 §2.1, §3.9, §3.10; C20 v1). T7 reduced (one 720 pane under
// the PortalToolbar) and the 390 page, over `GET /v1/portal/entities/{entity}/connections`. The
// client, not the firm, authorises access to the entity's ledger, bank and card feeds and sales
// platforms. Each artboard is its data (fixtures/scenarios/POR-16.ts):
//
//   a  QuickBooks Online, Front Range Bank ••4410 and Square connected; American Express ••1009
//      needs reauth; Shopify and a payroll provider not connected
//   b  the consent sheet over a: "Reconnect American Express", will and won't, the authorization
//      toggle gating Continue
//   c  9:30 AM, back from the provider: the card is connecting
//   d  9:31 AM: "reconnected by Tess Moreno · Sep 14, 9:31 AM"
//   e  Wed Mar 4, 2026: QuickBooks' first connect, its read-only disclosure (DF-19)
//   f  the disconnect dialog on QuickBooks
//   g  Square's last sync failed Sep 13, with Try again
//
// Every status word is the C2 registry's (`integration`, the portal's wording); every ledger card
// offers Export instead beside Connect (ADR-108); no write scope or copy appears (DF-19); tiles
// are Lucide glyphs on a category colour, never a vendor's logo or colours. Sign-in happens on the
// provider's site: the portal never asks for a password. White label: the firm's name comes from
// the branding, never the product's (DEC-01).

export interface POR16Props {
  /** The client entity; the portal's chosen scope when it is an entity. */
  entityId?: string;
  mobile?: boolean;
  /** Presentation only (the gallery): the 1400 window or the 390 phone. */
  frame?: boolean;
  /** The consent sheet open on arrival, by catalogue key (b, e). */
  sheet?: string;
  /** The disconnect dialog open on arrival, by catalogue key (f). */
  dialog?: string;
  /** Where the provider's sign-in URL goes; the page leaves for it (fixtures stay in the app). */
  onAuthorise?: (url: string, card: PortalConnectionCardOut) => void;
  /** The back chip: Home until POR-12 (A-02 §11.2 Q4); the browser's back without it. */
  onBack?: () => void;
  /** A start refused for a stale second factor (`mfa_required`): sign in again, then return. */
  onStepUp?: () => void;
  /** "Export instead": the open trial-balance request's guided steps (ADR-108). */
  onExportInstead?: () => void;
}

const TONE_FILL: Readonly<Record<PortalConnectionCardOut["tone"], string>> = {
  olive: "bg-green",
  espresso: "bg-espresso",
  clay: "bg-clay",
  ochre: "bg-amber",
};

const KNOWN: ReadonlySet<string> = new Set(ICON_NAMES);

/** The catalogue's glyph ("BookOpen" or "book-open") as a registry icon; a glyph the kit has no
 * drawing for shows the store glyph, never a vendor's mark. */
export function glyphOf(icon: string): IconName {
  const kebab = icon
    .replace(/([a-z0-9])([A-Z])/g, "$1-$2")
    .replace(/_/g, "-")
    .toLowerCase();
  return KNOWN.has(kebab) ? (kebab as IconName) : "store";
}

/** The provider's sign-in URL may only be HTTPS, or this app's own origin (the server also
 * holds it to the egress allowlist). Never a `javascript:` or other scheme. */
export function safeSignIn(url: string): boolean {
  try {
    const parsed = new URL(url, window.location.origin);
    return parsed.protocol === "https:" || parsed.origin === window.location.origin;
  } catch {
    return false;
  }
}

function key(card: PortalConnectionCardOut): string {
  return card.connection_id ?? card.catalog_key;
}

function idempotency(): { "Idempotency-Key": string } {
  return { "Idempotency-Key": crypto.randomUUID() };
}

function GlyphTile({
  card,
  size = 34,
}: {
  card: PortalConnectionCardOut;
  size?: 34 | 64 | 88;
}): JSX.Element {
  return (
    <span
      aria-hidden="true"
      data-glyph={glyphOf(card.icon)}
      className={cn(
        "flex flex-none items-center justify-center text-on-dark shadow-lift",
        size === 34 ? "size-[34px] rounded-tile" : "rounded-window",
        size === 64 && "size-[64px]",
        size === 88 && "size-[88px]",
        TONE_FILL[card.tone],
      )}
    >
      <Icon name={glyphOf(card.icon)} size={size === 34 ? 17 : 22} />
    </span>
  );
}

/** The bento relationship header: the firm's tile and the books' tile joined by the sync glyph. */
function Relationship({ firm, mobile }: { firm: string; mobile: boolean }): JSX.Element {
  const tile = mobile ? "size-[64px]" : "size-[88px]";
  const initials = firm
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() ?? "")
    .join("");
  return (
    <div data-relationship="" className="m-[12px] rounded-pane bg-shell p-[20px] text-center">
      <div className="relative mx-auto flex w-fit items-center gap-[24px]">
        <span
          aria-hidden="true"
          className={cn(
            "flex items-center justify-center rounded-window bg-card text-tab font-medium text-espresso shadow-e2",
            tile,
          )}
        >
          {initials}
        </span>
        <span
          aria-hidden="true"
          className="absolute left-1/2 top-1/2 flex size-[40px] -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full bg-surface-deep text-ink-2 shadow-e1"
        >
          <Icon name="refresh-cw" size={16} />
        </span>
        <span
          aria-hidden="true"
          className={cn(
            "flex items-center justify-center rounded-window bg-espresso text-on-dark",
            tile,
          )}
        >
          <Icon name="book-open" size={22} />
        </span>
      </div>
      <p className="mt-[12px] text-para text-ink-2">{COPY.relationship(firm)}</p>
    </div>
  );
}

interface CardLineProps {
  card: PortalConnectionCardOut;
  firm: string;
  now: Date;
  connecting: boolean;
  retrying: boolean;
  onRetry: () => void;
}

/** The card's 12px detail line, from the card's facts in the handoff's grammar. */
function DetailLine({
  card,
  firm,
  now,
  connecting,
  retrying,
  onRetry,
}: CardLineProps): JSX.Element | null {
  const day = (iso: string, withYear = false): string =>
    date(iso, { now, tz: DEFAULT_TZ, withYear });
  const at = (iso: string): string => time(iso, { tz: DEFAULT_TZ });
  if (connecting || card.status === "connecting") {
    return (
      <p className="text-cell text-ink-3">
        <Spinner size={12} label={COPY.connecting} />
      </p>
    );
  }
  const parts: string[] = [];
  if (card.status === "needs_attention" && card.last_failed_at) {
    return (
      <p className="text-cell text-ink-3">
        {COPY.syncFailed(day(card.last_failed_at))} ·{" "}
        {card.allowed_actions?.includes("retry") ? (
          <Button
            variant="link"
            size="sm"
            disabled={retrying}
            onClick={onRetry}
            aria-label={`${COPY.tryAgain}: ${card.display_label ?? card.name}`}
          >
            {COPY.tryAgain}
          </Button>
        ) : null}
      </p>
    );
  }
  if (card.status === "connected" && card.connected_by && card.connected_at) {
    if (card.reconnected) {
      return (
        <p className="text-cell text-ink-3">
          {COPY.reconnectedBy(
            card.connected_by.display_name,
            `${day(card.connected_at)}, ${at(card.connected_at)}`,
          )}
        </p>
      );
    }
    parts.push(COPY.connectedBy(card.connected_by.display_name, day(card.connected_at, true)));
  } else if (card.helper) {
    parts.push(card.helper);
  }
  if (card.status === "connected" && card.last_sync_at)
    parts.push(COPY.lastSync(at(card.last_sync_at)));
  let text = parts.join(" · ");
  if (card.status === "needs_reauth" && card.reauth_requested_at) {
    text = `${text} ${COPY.asked(firm, day(card.reauth_requested_at))}`.trim();
  }
  return text ? <p className="text-cell text-ink-3">{text}</p> : null;
}

interface CardProps extends CardLineProps {
  mobile: boolean;
  onConnect: () => void;
  onDetails: () => void;
  onDisconnect: () => void;
  onExport: () => void;
}

function ConnectionCard(props: CardProps): JSX.Element {
  const { card, mobile, connecting } = props;
  const actions = connecting ? [] : (card.allowed_actions ?? []);
  const title = card.display_label ?? card.name;
  const status = connecting ? "connecting" : card.status;
  const pill = <RegistryStatus object="integration" code={status} client />;
  const full = mobile ? "h-[44px] w-full" : "";
  return (
    <li
      data-connection={card.catalog_key}
      data-status={status}
      aria-label={title}
      className="rounded-pane bg-card px-[16px] py-[14px] shadow-e1"
    >
      <div className={cn("flex gap-[12px]", mobile ? "flex-col" : "items-start")}>
        <div className="flex min-w-0 flex-1 gap-[12px]">
          <GlyphTile card={card} />
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-[8px]">
              <p className="truncate text-tab font-medium">{title}</p>
              {!mobile && pill}
            </div>
            {mobile && <div className="mt-[4px]">{pill}</div>}
            <div className="mt-[2px]">
              <DetailLine {...props} />
            </div>
            {(card.scopes ?? []).length > 0 && (
              <div className="mt-[6px] flex flex-wrap gap-[6px]">
                {(card.scopes ?? []).map((s) => (
                  <Tag key={s.code} data-scope={s.code}>
                    {s.label}
                  </Tag>
                ))}
              </div>
            )}
          </div>
        </div>
        <div className={cn("flex gap-[6px]", mobile ? "flex-col" : "flex-none items-center")}>
          {actions.includes("reconnect") && (
            <Button variant="primary" size="sm" className={full} onClick={props.onConnect}>
              {COPY.reconnect}
            </Button>
          )}
          {actions.includes("connect") && (
            <Button variant="secondary" size="sm" className={full} onClick={props.onConnect}>
              {card.category === "payroll" ? COPY.connectMore : COPY.connect}
            </Button>
          )}
          {actions.includes("export_instead") && (
            <Button variant="secondary" size="sm" className={full} onClick={props.onExport}>
              {COPY.exportInstead}
            </Button>
          )}
          {actions.includes("details") && (
            <Button
              variant="ghost"
              size="sm"
              className={full}
              aria-haspopup="dialog"
              aria-label={`${COPY.details}: ${title}`}
              onClick={props.onDetails}
            >
              {COPY.details}
            </Button>
          )}
          {actions.includes("disconnect") && (
            <Button
              variant="destructive"
              size="sm"
              className={full}
              aria-haspopup="dialog"
              aria-label={`${COPY.disconnect}: ${title}`}
              onClick={props.onDisconnect}
            >
              {COPY.disconnect}
            </Button>
          )}
        </div>
      </div>
    </li>
  );
}

/** The O3 consent sheet: will and won't from the catalogue, the authorization toggle gating
 * Continue (b, e). The person signs in on the provider's site, never here. */
function ConsentSheet({
  consent,
  firm,
  open,
  mobile,
  busy,
  onClose,
  onContinue,
}: {
  consent: ConsentCopyOut;
  firm: string;
  open: boolean;
  mobile: boolean;
  busy: boolean;
  onClose: () => void;
  onContinue: () => void;
}): JSX.Element {
  const [authorized, setAuthorized] = useState(false);
  const toggleId = useId();
  return (
    <SheetModal
      open={open}
      onOpenChange={(next) => {
        if (!next) {
          setAuthorized(false);
          onClose();
        }
      }}
      title={consent.title}
      fullScreen={mobile}
    >
      <div className="flex flex-col gap-[12px] p-[14px]">
        <fieldset className="rounded-pane bg-card p-[14px] shadow-e1">
          <legend className="sr-only">{COPY.will(firm)}</legend>
          <p aria-hidden="true" className="mb-[8px] text-cell font-medium text-ink-2">
            {COPY.will(firm)}
          </p>
          <ul className="flex flex-col gap-[6px]">
            {consent.will.map((line) => (
              <li key={line} className="flex items-start gap-[8px] text-para">
                <Icon name="check" size={13} className="mt-[3px] text-green" />
                {line}
              </li>
            ))}
          </ul>
        </fieldset>
        {consent.wont.length > 0 && (
          <fieldset className="rounded-pane bg-card p-[14px] shadow-e1">
            <legend className="sr-only">{COPY.wont(firm)}</legend>
            <p aria-hidden="true" className="mb-[8px] text-cell font-medium text-ink-2">
              {COPY.wont(firm)}
            </p>
            <ul className="flex flex-col gap-[6px]">
              {consent.wont.map((line) => (
                <li key={line} className="flex items-start gap-[8px] text-para">
                  <Icon name="x" size={13} className="mt-[3px] text-ink-3" />
                  {line}
                </li>
              ))}
            </ul>
          </fieldset>
        )}
        <div className="flex items-start gap-[12px] rounded-pane bg-card p-[14px] shadow-e1">
          <Toggle
            id={toggleId}
            checked={authorized}
            onChange={setAuthorized}
            label={consent.authorization}
          />
          <label htmlFor={toggleId} className="text-para">
            {consent.authorization}
          </label>
        </div>
        <Button
          variant="primary"
          size="md"
          className={mobile ? "h-[44px] w-full" : "self-start"}
          disabled={!authorized || busy}
          aria-describedby={authorized ? undefined : toggleId}
          onClick={onContinue}
        >
          {consent.continue_label}
        </Button>
        {consent.helper && <p className="text-meta text-ink-3">{consent.helper}</p>}
      </div>
    </SheetModal>
  );
}

function DetailsDrawer({
  detail,
  title,
  now,
  onClose,
}: {
  detail: PortalConnectionDetailOut | undefined;
  title: string;
  now: Date;
  onClose: () => void;
}): JSX.Element {
  const card = detail?.card;
  return (
    <Drawer
      open
      onOpenChange={(next) => {
        if (!next) onClose();
      }}
      title={title}
    >
      {card === undefined ? (
        <Spinner size={15} label={COPY.loading} />
      ) : (
        <>
          <DrawerCard className="p-[14px]">
            <p className="text-cell font-medium text-ink-2">{COPY.scopes}</p>
            <div className="mt-[6px] flex flex-wrap gap-[6px]">
              {(card.scopes ?? []).map((s) => (
                <Tag key={s.code}>{s.label}</Tag>
              ))}
            </div>
            {card.connected_by && card.connected_at && (
              <p className="mt-[8px] text-cell text-ink-3">
                {COPY.connectedBy(
                  card.connected_by.display_name,
                  date(card.connected_at, { now, tz: DEFAULT_TZ, withYear: true }),
                )}
              </p>
            )}
          </DrawerCard>
          <DrawerCard className="p-[14px]">
            <p className="text-cell font-medium text-ink-2">{COPY.recent}</p>
            {(detail?.recent_syncs ?? []).length === 0 ? (
              <p className="mt-[6px] text-cell text-ink-3">{COPY.noSyncs}</p>
            ) : (
              <ul className="mt-[6px] flex flex-col gap-[4px]">
                {(detail?.recent_syncs ?? []).map((r) => (
                  <li key={r.sync_run_id} className="flex items-center justify-between text-cell">
                    <span>{date(r.started_at, { now, tz: DEFAULT_TZ })}</span>
                    <span className="text-ink-3">{r.status}</span>
                  </li>
                ))}
              </ul>
            )}
          </DrawerCard>
          {(detail?.activity ?? []).length > 0 && (
            <DrawerCard className="p-[14px]">
              <p className="text-cell font-medium text-ink-2">{COPY.activity}</p>
              <ul className="mt-[6px] flex flex-col gap-[4px]">
                {(detail?.activity ?? []).map((a) => (
                  <li key={`${a.action}:${a.at}`} className="text-cell">
                    {a.text}
                  </li>
                ))}
              </ul>
            </DrawerCard>
          )}
        </>
      )}
    </Drawer>
  );
}

export function POR16({
  entityId,
  mobile = false,
  frame = false,
  sheet,
  dialog,
  onAuthorise,
  onBack,
  onStepUp,
  onExportInstead,
}: POR16Props): JSX.Element | null {
  const now = useNow();
  const brand = usePortalBrand();
  const bar = usePortalToolbar(entityId ?? null);
  const client = useQueryClient();
  const entity = entityId ?? (bar?.scope?.kind === "client_entity" ? bar.scope.id : undefined);
  const path = { entity_id: entity ?? "" };
  const cards = useQuery({
    ...listEntityConnectionsOptions({ path }),
    enabled: entity !== undefined,
    retry: false,
  });
  const [consentFor, setConsentFor] = useState<string | null>(sheet ?? null);
  const [dialogFor, setDialogFor] = useState<string | null>(dialog ?? null);
  const [detailsFor, setDetailsFor] = useState<string | null>(null);
  const [connecting, setConnecting] = useState<ReadonlySet<string>>(new Set());
  const [retrying, setRetrying] = useState<ReadonlySet<string>>(new Set());
  const detail = useQuery({
    ...connectionDetailOptions({ path: { connection_id: detailsFor ?? "" } }),
    enabled: detailsFor !== null,
    retry: false,
  });
  const refresh = (): void => {
    void client.invalidateQueries({ queryKey: listEntityConnectionsQueryKey({ path }) });
  };
  const start = useMutation(startConnectionMutation());
  const retry = useMutation(retryConnectionMutation());
  const disconnect = useMutation(disconnectConnectionMutation());
  if (bar === undefined) return null;
  // The firm's short name ("Brightwater Hale"): the server's, else the portal's branding.
  const firm = cards.data?.firm_display_name ?? brand.portalName ?? brand.name;
  const items = cards.data?.items ?? [];
  const byKey = (k: string | null): PortalConnectionCardOut | undefined =>
    k === null ? undefined : items.find((c) => c.catalog_key === k || c.connection_id === k);
  const failed = (): void => {
    toast.show({ kind: "error", text: COPY.failed });
  };
  const continueTo = (card: PortalConnectionCardOut): void => {
    const consent = card.consent;
    if (consent == null) return;
    start.mutate(
      {
        path: { entity_id: entity ?? "", catalog_key: card.catalog_key },
        body: {
          consent_version: consent.version,
          authorized: true,
          ...(card.status === "needs_reauth" && card.connection_id
            ? { connection_id: card.connection_id }
            : {}),
        },
        headers: idempotency(),
      },
      {
        onSuccess: (started) => {
          setConsentFor(null);
          setConnecting((s) => new Set([...s, key(card)]));
          if (onAuthorise) onAuthorise(started.authorise_url, card);
          else if (safeSignIn(started.authorise_url))
            window.location.assign(started.authorise_url);
          else failed();
        },
        onError: (error: unknown) => {
          if (isStepUp(error) && onStepUp) onStepUp();
          else failed();
        },
      },
    );
  };
  const tryAgain = (card: PortalConnectionCardOut): void => {
    if (!card.connection_id) return;
    setRetrying((s) => new Set([...s, key(card)]));
    retry.mutate(
      { path: { connection_id: card.connection_id }, headers: idempotency() },
      {
        onSuccess: () => {
          toast.show(COPY.retried);
        },
        onError: () => {
          setRetrying((s) => new Set([...s].filter((k) => k !== key(card))));
          failed();
        },
      },
    );
  };
  const confirmDisconnect = (card: PortalConnectionCardOut): void => {
    if (!card.connection_id) return;
    disconnect.mutate(
      {
        path: { connection_id: card.connection_id },
        body: { seen_version: card.version ?? 0 },
        headers: idempotency(),
      },
      {
        onSuccess: () => {
          setDialogFor(null);
          toast.show(COPY.disconnected(card.name));
          refresh();
        },
        onError: failed,
      },
    );
  };
  const exportInstead = (): void => {
    // A-02-T28: the open trial-balance request's guided steps (the portal's Documents); with no
    // page to go to, the team asks when it needs one (ADR-108: connecting is never required).
    if (onExportInstead) onExportInstead();
    else toast.show(COPY.exportNone(firm));
  };

  let body: JSX.Element;
  if (cards.data !== undefined) {
    body =
      items.length === 0 ? (
        <EmptyState icon="link" title={COPY.empty(firm)} />
      ) : (
        <>
          <Relationship firm={firm} mobile={mobile} />
          <ul aria-label={COPY.pane} className="mx-[12px] flex flex-col gap-[8px]">
            {items.map((card) => (
              <ConnectionCard
                key={key(card)}
                card={card}
                firm={firm}
                now={now}
                mobile={mobile}
                connecting={connecting.has(key(card))}
                retrying={retrying.has(key(card))}
                onRetry={() => {
                  tryAgain(card);
                }}
                onConnect={() => {
                  setConsentFor(card.connection_id ?? card.catalog_key);
                }}
                onDetails={() => {
                  setDetailsFor(card.connection_id ?? null);
                }}
                onDisconnect={() => {
                  setDialogFor(card.connection_id ?? card.catalog_key);
                }}
                onExport={exportInstead}
              />
            ))}
          </ul>
          <p className="px-[16px] py-[12px] text-meta text-ink-3">{COPY.footer(firm)}</p>
        </>
      );
  } else if (entity === undefined || (cards.isError && isMissing(cards.error))) {
    body = <EmptyState icon="lock" title={COPY.notAllowed} />;
  } else if (cards.isError) {
    body = (
      <EmptyState
        tone="error"
        icon="circle-alert"
        title={COPY.loadError}
        action={
          <Button variant="secondary" size="sm" onClick={() => void cards.refetch()}>
            {COPY.retryLoad}
          </Button>
        }
      />
    );
  } else {
    body = (
      <div role="status" aria-label={COPY.loading} className="flex flex-col gap-[8px] p-[14px]">
        {[0, 1, 2].map((i) => (
          <div key={i} className="h-[64px] rounded-nested bg-nested" />
        ))}
      </div>
    );
  }
  const consentCard = byKey(consentFor);
  const dialogCard = byKey(dialogFor);
  const detailsCard = byKey(detailsFor);
  const back = (
    <Button
      variant="secondary"
      size="sm"
      icon="chevron-left"
      onClick={() => {
        if (onBack) onBack();
        else window.history.back();
      }}
    >
      {COPY.back}
    </Button>
  );
  const overlays = (
    <>
      {consentCard?.consent != null && (
        <ConsentSheet
          consent={consentCard.consent}
          firm={firm}
          open
          mobile={mobile}
          busy={start.isPending}
          onClose={() => {
            setConsentFor(null);
          }}
          onContinue={() => {
            continueTo(consentCard);
          }}
        />
      )}
      {dialogCard !== undefined && (
        <Dialog
          open
          size="sm"
          onOpenChange={(next) => {
            if (!next) setDialogFor(null);
          }}
          title={COPY.disconnectTitle(dialogCard.name)}
          description={COPY.disconnectBody(firm)}
        >
          <div className="flex justify-end gap-[8px] p-[14px]">
            <Button
              variant="secondary"
              size="md"
              onClick={() => {
                setDialogFor(null);
              }}
            >
              {COPY.cancel}
            </Button>
            <Button
              variant="destructive"
              size="md"
              disabled={disconnect.isPending}
              onClick={() => {
                confirmDisconnect(dialogCard);
              }}
            >
              {COPY.disconnect}
            </Button>
          </div>
        </Dialog>
      )}
      {detailsFor !== null && (
        <DetailsDrawer
          detail={detail.data}
          title={detailsCard?.display_label ?? detailsCard?.name ?? COPY.details}
          now={now}
          onClose={() => {
            setDetailsFor(null);
          }}
        />
      )}
    </>
  );
  return (
    <div data-screen="POR-16" className="flex min-h-0 flex-1 flex-col">
      {mobile ? (
        <PortalLayout
          variant="mobile"
          user={bar.user}
          nav={[]}
          frame={frame}
          {...(frame ? { height: 844 } : {})}
        >
          <div className="overflow-hidden rounded-pane bg-card shadow-e1">
            <div className="flex h-[56px] items-center gap-[8px] px-[12px]">
              {back}
              <h1 className="flex-1 text-center text-tab font-medium">{COPY.pane}</h1>
            </div>
            {body}
          </div>
          {overlays}
        </PortalLayout>
      ) : (
        <PortalLayout
          variant="reduced"
          user={bar.user}
          nav={bar.nav}
          frame={frame}
          {...(frame ? { height: 860 } : {})}
        >
          <Pane title={COPY.pane} titleAlign="center" left={back} width={720}>
            {body}
          </Pane>
          {overlays}
        </PortalLayout>
      )}
    </div>
  );
}

/** A refusal for a stale second factor: 403 with `facts.reason` `mfa_required`. */
export function isStepUp(error: unknown): boolean {
  if (typeof error !== "object" || error === null) return false;
  const facts = (error as { facts?: { reason?: unknown } }).facts;
  return facts?.reason === "mfa_required";
}

function isMissing(error: unknown): boolean {
  return typeof error === "object" && error !== null && "detail" in error;
}

/** The page: the firm's branding first, then the connections under its brand. */
export function PortalConnections(props: POR16Props): JSX.Element | null {
  const branding = useBranding();
  if (branding.data === undefined) return null;
  return (
    <PortalBrandProvider brand={brandOf(branding.data)}>
      <POR16 {...props} />
    </PortalBrandProvider>
  );
}
