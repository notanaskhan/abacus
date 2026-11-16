import type { ConnectCatalogOut, ConnectTileOut } from "@abacus/api-client";
import {
  connectCatalogOptions,
  connectFirmMutation,
  connectInterestMutation,
  connectPersonalMutation,
} from "@abacus/api-client/query";
import {
  AboutCard,
  Button,
  CatalogBadge,
  type CatalogBadgeState,
  CatalogCard,
  CatalogGrid,
  CatalogLayout,
  CatalogSkeletonCard,
  CategoryList,
  EmptyState,
  ErrorState,
  ICON_NAMES,
  Icon,
  type IconName,
  Picker,
  Pill,
  SearchField,
  type ToolbarProps,
  cn,
  status as statusWord,
  toast,
} from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, useId, useState } from "react";
import { PLANNED_VISIBLE } from "../../app-core/planned";
import { hrefOf, to } from "../../routes/to";
import { RevealStepUp } from "../../domain/audits";
import { COPY } from "./copy";

// WB-10 · Workbench › Connect (W-01-T12; SPEC-659 AC-1 to AC-9, AC-31; docs/screens/WB-10.md).
// T5 CatalogLayout inside the Workbench tabsbar (Sessions · Agents · Connect): the 358 side (search,
// the About card, the Categories list with catalogue-total counts, Build on Accrued) beside the grid
// (status Picker, "Integrations", search; three columns of C-14 tiles). Everything a tile says is the
// API's: its honest status (AC-4), who connected it, its blocked reason and its allowed actions. A
// firm tile the viewer may not enable keeps its Enable focusable with `aria-disabled` and states the
// reason through `aria-describedby` (AC-6); Notify me is idempotent (AC-31). Details… opens WB-11
// (`?ov=connection:<key>`), planned until W-01-T15.
//
//   a  Felix at E0: 53 = 9 + 38 + 6      d  Hannah: Enable disabled, "Felix Andersen manages…"
//   b  ERP: 8                             e  Google Workspace connecting (staging)
//   c  Connected: 9                       f  Aug 17: CCH Needs reauth, Reconnect (staging)
//   g  "Karbon": 1, counts unchanged      h  E2: 55 = 9 + 40 + 6     i  GRC: Drata, Vanta

export type Wb10Status = "connected" | "available" | "coming_soon";
const ALL = "all";
const STATUSES: readonly Wb10Status[] = ["connected", "available", "coming_soon"];
const TONE_FILL: Readonly<Record<string, string>> = {
  espresso: "bg-espresso",
  olive: "bg-green",
  clay: "bg-clay",
  ochre: "bg-amber",
  brick: "bg-red",
};

export interface WB10Initial {
  category?: string | null;
  status?: Wb10Status | null;
  q?: string;
}

export interface WB10Props {
  toolbar?: ToolbarProps;
  height?: number;
  initial?: WB10Initial;
  /** The Workbench tabsbar's other tabs (the routes'). */
  onTab?: (tab: "sessions" | "agents") => void;
}

/** The catalogue's category glyph, when the icon set has it (content is data, AC-5). */
function iconOf(name: string): IconName {
  return (ICON_NAMES as readonly string[]).includes(name) ? (name as IconName) : "plug";
}

function badgeOf(tile: ConnectTileOut): CatalogBadgeState | null {
  const code = tile.status;
  if (
    code === "available" ||
    code === "connected" ||
    code === "connecting" ||
    code === "coming_soon"
  ) {
    return { object: "integration", code };
  }
  return null;
}

function Tile({ tile }: { tile: ConnectTileOut }): JSX.Element {
  const client = useQueryClient();
  const reasonId = useId();
  const [notified, setNotified] = useState(false);
  const personal = tile.kind === "personal";
  const word = statusWord("integration", tile.status);
  const refresh = (): void =>
    void client.invalidateQueries({ queryKey: [{ _id: "connectCatalog" }] });
  const go = (url: string | null | undefined): void => {
    if (url) window.location.assign(url);
    refresh();
  };
  const [stepUp, setStepUp] = useState(false);
  const failed = (error: unknown): void => {
    // AC-7: Enable and Reconnect ask a fresh second factor; only that refusal steps up.
    if (isStepUp(error)) setStepUp(true);
    else toast.show({ kind: "error", text: COPY.connectFailed });
  };
  const firm = useMutation({
    ...connectFirmMutation(),
    onSuccess: (r) => {
      go(r.authorise_url);
    },
    onError: failed,
  });
  const mine = useMutation({
    ...connectPersonalMutation(),
    onSuccess: (r) => {
      go(r.authorise_url);
    },
    onError: failed,
  });
  const interest = useMutation({
    ...connectInterestMutation(),
    onSuccess: () => {
      setNotified(true);
    },
    onError: failed,
  });
  const key = { "Idempotency-Key": `wb10-${tile.key}-${crypto.randomUUID()}` };
  const may = (a: ConnectTileOut["allowed_actions"][number]): boolean =>
    tile.allowed_actions.includes(a);
  const canConnect = personal
    ? may("integration.connect_personal")
    : may("integration.connect_firm");
  const badge = badgeOf(tile);
  let action: JSX.Element | null = null;
  if (tile.status === "coming_soon") {
    action = may("integration.interest") ? (
      <Button
        variant="secondary"
        size="sm"
        disabled={notified || interest.isPending}
        onClick={() => {
          interest.mutate({ path: { key: tile.key }, headers: key });
        }}
      >
        {notified ? COPY.notified : COPY.notifyMe}
      </Button>
    ) : null;
  } else if (
    tile.status === "available" ||
    tile.status === "needs_reauth" ||
    tile.status === "needs_attention"
  ) {
    const label =
      tile.status === "available" ? (personal ? COPY.connect : COPY.enable) : COPY.reconnect;
    const blocked = !canConnect || tile.blocked_reason !== null;
    action = (
      <Button
        variant={tile.status === "available" ? "secondary" : "primary"}
        size="sm"
        aria-disabled={blocked || undefined}
        {...(blocked && tile.blocked_reason !== null ? { "aria-describedby": reasonId } : {})}
        onClick={() => {
          if (blocked) return;
          (personal ? mine : firm).mutate({ path: { key: tile.key }, headers: key });
        }}
      >
        {label}
      </Button>
    );
  } else if (PLANNED_VISIBLE) {
    action = (
      <Button variant="secondary" size="sm" disabled title={COPY.notBuilt}>
        {COPY.details}
      </Button>
    );
  }
  const by =
    tile.status === "connected" && personal
      ? COPY.connectedAsYou
      : tile.connected_by_label !== null
        ? COPY.connectedBy(tile.connected_by_label)
        : null;
  return (
    <CatalogCard
      label={`${tile.name}, ${word.label}`}
      height={212}
      still={tile.status === "coming_soon"}
    >
      <div
        data-connect-tile={tile.status}
        data-key={tile.key}
        className="flex items-start justify-between gap-[8px]"
      >
        <span
          aria-hidden="true"
          data-icon-tile={tile.tone}
          className={cn(
            "flex size-[34px] flex-none items-center justify-center rounded-tile text-on-dark shadow-lift",
            TONE_FILL[tile.tone] ?? "bg-espresso",
          )}
        >
          <Icon name={iconOf(tile.icon)} size={17} />
        </span>
        {badge !== null ? (
          <CatalogBadge state={badge} />
        ) : (
          <Pill variant={word.variant ?? "neutral"} size="outline">
            {word.label}
          </Pill>
        )}
      </div>
      <p title={tile.name} className="mt-[10px] truncate text-tab font-medium tracking-[-0.012em]">
        {tile.name}
      </p>
      <p className="mt-[4px] line-clamp-2 text-cell text-ink-2">{tile.description}</p>
      <p className="mt-[3px] truncate text-meta text-ink-3">
        {by === null ? tile.auth_line : `${tile.auth_line} · ${by}`}
      </p>
      {tile.blocked_reason !== null && (
        <p
          id={reasonId}
          data-blocked-reason=""
          className="mt-[6px] line-clamp-2 text-meta text-ink-3"
        >
          {tile.blocked_reason}
        </p>
      )}
      {action !== null && <div className="mt-auto pt-[8px]">{action}</div>}
      <RevealStepUp open={stepUp} onOpenChange={setStepUp} />
    </CatalogCard>
  );
}

/** A refusal for a stale second factor: 403 with `facts.reason` `mfa_required`. */
export function isStepUp(error: unknown): boolean {
  if (typeof error !== "object" || error === null) return false;
  const facts = (error as { facts?: { reason?: unknown } }).facts;
  return facts?.reason === "mfa_required";
}

function Grid({
  q,
  page,
  pending,
  failed,
  onRetry,
}: {
  q: string;
  page: ConnectCatalogOut | undefined;
  pending: boolean;
  failed: boolean;
  onRetry: () => void;
}): JSX.Element {
  if (failed) return <ErrorState noun="integrations" onRetry={onRetry} />;
  if (pending || page === undefined) {
    return (
      <CatalogGrid label={COPY.grid} busy>
        {[0, 1, 2, 3, 4, 5].map((i) => (
          <CatalogSkeletonCard key={i} height={212} />
        ))}
      </CatalogGrid>
    );
  }
  if (page.items.length === 0) {
    return (
      <EmptyState icon="search" title={q.trim() === "" ? COPY.empty : COPY.noMatch(q.trim())} />
    );
  }
  return (
    <CatalogGrid label={COPY.grid}>
      {page.items.map((tile) => (
        <Tile key={tile.key} tile={tile} />
      ))}
    </CatalogGrid>
  );
}

function BuildOnAccrued({ page }: { page: ConnectCatalogOut | undefined }): JSX.Element | null {
  const rows = (page?.build_on_accrued ?? []).filter((r) => !r.planned || PLANNED_VISIBLE);
  if (rows.length === 0) return null;
  return (
    <section aria-label={COPY.buildOnAccrued} className="m-[10px] flex flex-col gap-[6px]">
      <p className="text-meta text-ink-3">{COPY.buildOnAccrued}</p>
      {rows.map((row) =>
        row.key === "workflow_sync" && !row.planned ? (
          // ADM-08, live: Workflow status sync (the screen contract's Links).
          <a
            key={row.key}
            href={hrefOf(to.ADM08())}
            className="rounded-control px-[8px] py-[4px] text-cell text-ink hover:bg-hover"
          >
            {row.label}
          </a>
        ) : (
          <Button key={row.key} variant="ghost" size="sm" disabled title={COPY.notBuilt}>
            {row.label}
          </Button>
        ),
      )}
    </section>
  );
}

export function WB10({ toolbar, height, initial = {}, onTab }: WB10Props): JSX.Element {
  const [category, setCategory] = useState<string | null>(initial.category ?? null);
  const [status, setStatus] = useState<Wb10Status | null>(initial.status ?? null);
  const [q, setQ] = useState(initial.q ?? "");
  const query = {
    ...(category === null
      ? {}
      : { category: category as NonNullable<ConnectTileOut["categories"]>[number] }),
    ...(status === null ? {} : { status }),
    ...(q.trim() === "" ? {} : { q: q.trim() }),
  };
  const catalogue = useQuery(connectCatalogOptions({ query }));
  const page = catalogue.data;
  const counts = page?.counts;
  const statusOptions = [
    { value: ALL, label: counts === undefined ? COPY.all : `${COPY.all} ${String(counts.all)}` },
    ...STATUSES.map((s) => ({
      value: s,
      label:
        counts === undefined
          ? statusWord("integration", s).label
          : `${statusWord("integration", s).label} ${String(counts[s])}`,
    })),
  ];
  return (
    <CatalogLayout
      {...(toolbar === undefined
        ? { bare: true, toolbar: { nav: [], active: "Workbench", firm: "" } }
        : { toolbar: { ...toolbar, active: "Workbench" }, embedded: true })}
      {...(height === undefined ? {} : { height })}
      tabs={{
        label: COPY.tabs.label,
        options: [COPY.tabs.sessions, COPY.tabs.agents, COPY.tabs.connect],
        active: COPY.tabs.connect,
        onChange: (label) => {
          if (label === COPY.tabs.sessions) onTab?.("sessions");
          else if (label === COPY.tabs.agents) onTab?.("agents");
        },
      }}
      side={{
        search: (
          <SearchField
            label={COPY.search}
            placeholder={COPY.search}
            value={q}
            onChange={setQ}
            className="w-auto flex-1"
          />
        ),
        about: <AboutCard icon="plug" title={COPY.about.title} body={COPY.about.body} />,
        categories: (
          <>
            <CategoryList
              label={COPY.categories}
              selected={category ?? ALL}
              onSelect={(key) => {
                setCategory(key === ALL ? null : key);
              }}
              categories={[
                {
                  key: ALL,
                  label: COPY.all,
                  ...(counts === undefined ? {} : { count: counts.all }),
                },
                ...(page?.categories ?? []).map((c) => ({
                  key: c.code,
                  label: c.label,
                  description: c.description,
                  count: c.count,
                })),
              ]}
            />
            <BuildOnAccrued page={page} />
          </>
        ),
      }}
      grid={{
        title: COPY.grid,
        left: (
          <Picker
            label={COPY.status}
            variant="white"
            options={statusOptions}
            value={status ?? ALL}
            onChange={(value) => {
              setStatus(value === ALL ? null : (value as Wb10Status));
            }}
          />
        ),
        right: (
          <SearchField
            label={COPY.search}
            placeholder={COPY.search}
            value={q}
            onChange={setQ}
            className="w-[220px]"
          />
        ),
        body: (
          <Grid
            q={q}
            page={page}
            pending={catalogue.isPending}
            failed={catalogue.isError}
            onRetry={() => void catalogue.refetch()}
          />
        ),
      }}
    />
  );
}
