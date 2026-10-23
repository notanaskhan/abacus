import type { ClientRowOut } from "@abacus/api-client";
import {
  Button,
  DASH,
  DEFAULT_TZ,
  Icon,
  type IndexChip,
  type IndexColumn,
  IndexList,
  type ListEnvelope,
  Menu,
  type MenuItem,
  Pill,
  RegistryStatus,
  SubLine,
  type ViewState,
  count,
  date,
  sameDay,
  status,
  time,
  toast,
} from "@abacus/ui";
import { type JSX, useState } from "react";
import { useCan } from "../../app-core/can";
import { useNow } from "../../app-core/clock";
import { PLANNED_VISIBLE } from "../../app-core/planned";
import { useSession } from "../../app-core/session";
import {
  CLIENT_STATUSES,
  type ClientFilters,
  DEFAULT_CLIENT_FILTERS,
  KIND_WORDS,
  activityWords,
  isClientKind,
  isClientStatus,
  isNarrowed,
  isServiceLine,
  useClients,
} from "../../domain/clients";
import { COPY } from "./copy";

// CLI-01 · Clients index (P-07-T12; docs/screens/CLI-01.md). T1 over `GET /v1/clients`: five split
// filter chips (Status │ Active is the amber active chip), search, the firm's client count in the
// pane header (DEC-47), the ledger rows newest activity first, "Load more" for the next keyset
// page, and a row ··· menu. Each artboard is its data:
//
//   a  Status │ Active: "184 clients", the 16 named clients, "Load more" (Grace Holloway)
//   b  Service line │ Audit: Northwind, Granite Peak, Lakeshore, "Showing 3"
//   c  Lena Park, walled from Ashford: Ashford is simply absent; nothing says so (DEC-43)
//   d  "Schwab" matches nothing: "No clients match 'Schwab'." and Clear filters
//   e  the list never answers: 8 skeleton rows
//   f  a firm with no clients: "No clients yet." with + New client and Import…
//
// Every outbound target (CLI-02, CLI-04, CLI-06, ENG-01, ENG-03, BND-02, INB-04) is planned: those
// controls are hidden in production and disabled with their "Opens …" hint elsewhere.

export interface CLI01Props {
  filters: ClientFilters;
  onFilters: (next: ClientFilters) => void;
}

/** "9:12 AM" today, else "Sep 12", then " · " and the event's words when it has any. */
export function activityText(row: ClientRowOut, now: Date, tz: string): string {
  const at = row.last_activity_at;
  if (at == null) return DASH;
  const when = sameDay(at, now, { tz }) ? time(at, { tz }) : date(at, { now, tz });
  const words = activityWords(row.last_activity_event_type);
  return words === null ? when : `${when} · ${words}`;
}

/** The screen with its own filters: the route's page and the gallery's artboard. `initial` is what
 * an artboard opens on (b: Service line │ Audit; d: the search "Schwab"). */
export function ClientsIndex({ initial = {} }: { initial?: Partial<ClientFilters> }): JSX.Element {
  const [filters, setFilters] = useState<ClientFilters>(() => ({
    ...DEFAULT_CLIENT_FILTERS,
    ...initial,
  }));
  return <CLI01 filters={filters} onFilters={setFilters} />;
}

export function CLI01({ filters, onFilters }: CLI01Props): JSX.Element {
  const now = useNow();
  const tz = useSession().tz ?? DEFAULT_TZ;
  const list = useClients(filters);
  const canIntake = useCan("client.intake");

  const pages = list.data?.pages ?? [];
  const first = pages[0];
  const last = pages[pages.length - 1];
  const items = pages.flatMap((p) => p.items);
  const facets = first?.facets ?? {};
  const narrowed = isNarrowed(filters);
  const set = (patch: Partial<ClientFilters>): void => {
    onFilters({ ...filters, ...patch });
  };
  const clear = (): void => {
    onFilters(DEFAULT_CLIENT_FILTERS);
  };

  let state: ViewState;
  if (list.isError) state = { kind: "error", retry: () => void list.refetch() };
  else if (first === undefined) state = { kind: "loading" };
  else if (first.total === 0 && !narrowed) state = { kind: "empty" };
  else if (items.length === 0) {
    const q = filters.q.trim();
    state = {
      kind: "filtered-empty",
      ...(q === "" ? {} : { query: q, title: COPY.noMatch(q) }),
      clear,
    };
  } else state = { kind: "ready" };

  const envelope: ListEnvelope<ClientRowOut> | undefined =
    first === undefined
      ? undefined
      : {
          items,
          next_cursor: last?.next_cursor ?? null,
          total: first.total,
          counts: first.counts ?? {},
          facets,
        };

  const options = (key: string, word: (value: string, label: string) => string = (_v, l) => l) =>
    (facets[key] ?? []).map((f) => ({ value: f.value, label: word(f.value, f.label) }));
  const partners = new Map((facets.partner ?? []).map((f) => [f.value, f.label]));

  const chips: IndexChip[] = [
    {
      key: "kind",
      label: COPY.chips.type,
      icon: "building-2",
      options: options("kind", (v, l) => (isClientKind(v) ? KIND_WORDS[v] : l)),
      value: filters.kind,
      placeholder: COPY.chips.all,
    },
    {
      key: "office",
      label: COPY.chips.office,
      icon: "map-pin",
      options: options("office"),
      value: filters.office,
      placeholder: COPY.chips.allOffices,
    },
    {
      key: "partner",
      label: COPY.chips.partner,
      icon: "circle-user-round",
      options: options("partner"),
      value: filters.partner,
      placeholder: COPY.chips.all,
    },
    {
      key: "serviceLine",
      label: COPY.chips.serviceLine,
      icon: "briefcase",
      options: (["tax", "audit", "cas", "advisory"] as const).map((line) => ({
        value: line,
        label: COPY.services[line],
      })),
      value: filters.serviceLine,
      placeholder: COPY.chips.all,
    },
    {
      key: "status",
      label: COPY.chips.status,
      icon: "circle-check",
      options: CLIENT_STATUSES.map((code) => ({
        value: code,
        label: status("client", code).label,
      })),
      value: filters.status,
      placeholder: COPY.chips.all,
    },
  ];

  const onChip = (key: string, value: string | null): void => {
    if (key === "kind") set({ kind: isClientKind(value) ? value : null });
    else if (key === "office") set({ office: value });
    else if (key === "partner") set({ partner: value });
    else if (key === "serviceLine") set({ serviceLine: isServiceLine(value) ? value : null });
    else if (key === "status") set({ status: isClientStatus(value) ? value : null });
  };

  const copyId = async (row: ClientRowOut): Promise<void> => {
    try {
      await globalThis.navigator.clipboard.writeText(row.id);
    } catch {
      // A browser without clipboard access still gets the toast's confirmation of the action.
    }
    toast.show({ kind: "success", text: COPY.toast.copied });
  };

  const menuFor = (row: ClientRowOut): MenuItem[][] => {
    const planned: MenuItem[] = PLANNED_VISIBLE
      ? [
          // CLI-02, INB-04 and ENG-03 are planned (docs/screens/CLI-01.md, Links).
          { label: COPY.menu.open, disabled: true, onSelect: () => undefined },
          { label: COPY.menu.message, disabled: true, onSelect: () => undefined },
          { label: COPY.menu.newEngagement, disabled: true, onSelect: () => undefined },
        ]
      : [];
    const own: MenuItem[] = [{ label: COPY.menu.copyId, onSelect: () => void copyId(row) }];
    return planned.length === 0 ? [own] : [planned, own];
  };

  const columns: IndexColumn<ClientRowOut>[] = [
    {
      key: "client",
      header: COPY.columns.client,
      cell: (r) => (
        <span className="flex min-w-0 flex-col">
          <span className="truncate font-medium">{r.name}</span>
          {r.descriptor != null && <SubLine>{r.descriptor}</SubLine>}
        </span>
      ),
    },
    {
      key: "type",
      header: COPY.columns.type,
      width: 190,
      cell: (r) => (
        <span className="flex items-center gap-[6px]">
          {r.kind !== null && <Pill variant="neutral">{KIND_WORDS[r.kind]}</Pill>}
          {r.is_attest_client && (
            <Pill variant="tag" size="micro">
              {COPY.attest}
            </Pill>
          )}
        </span>
      ),
    },
    {
      key: "entities",
      header: COPY.columns.entities,
      width: 70,
      align: "right",
      cell: (r) => count(r.entity_count),
    },
    {
      key: "services",
      header: COPY.columns.services,
      width: 150,
      cell: (r) => (
        <span className="flex items-center gap-[4px]">
          {r.service_lines.map((line) => (
            <Pill key={line} variant="tag" size="outline">
              {COPY.services[line]}
            </Pill>
          ))}
        </span>
      ),
    },
    {
      key: "office",
      header: COPY.columns.office,
      width: 90,
      cell: (r) => <span className="text-ink-2">{r.office_name ?? DASH}</span>,
    },
    {
      key: "partner",
      header: COPY.columns.partner,
      width: 64,
      cell: (r) => {
        const initials = r.relationship_partner_initials;
        if (initials == null) return DASH;
        const name =
          r.relationship_partner_id == null ? undefined : partners.get(r.relationship_partner_id);
        return name === undefined ? (
          <span className="text-ink-2">{initials}</span>
        ) : (
          <abbr title={name} className="text-ink-2 no-underline">
            {initials}
          </abbr>
        );
      },
    },
    {
      key: "portal",
      header: COPY.columns.portal,
      width: 110,
      cell: (r) => (
        <RegistryStatus object="invitation" code={r.portal_status} context="portal_pill" />
      ),
    },
    {
      key: "open",
      header: COPY.columns.openRequests,
      width: 100,
      align: "right",
      cell: (r) => <OpenRequests row={r} />,
    },
    {
      key: "activity",
      header: COPY.columns.lastActivity,
      width: 230,
      cell: (r) => (
        <span className="block whitespace-normal text-meta text-ink-3 line-clamp-2">
          {activityText(r, now, tz)}
        </span>
      ),
    },
    {
      key: "menu",
      header: "",
      width: 36,
      cell: (r) => (
        <Menu
          label={COPY.menu.label(r.name)}
          align="end"
          sections={menuFor(r)}
          trigger={
            <button
              type="button"
              aria-label={COPY.menu.label(r.name)}
              onClick={(e) => {
                e.stopPropagation();
              }}
              className="flex size-[24px] items-center justify-center rounded-pill text-ink-3 hover:bg-nested"
            >
              <Icon name="ellipsis" size={14} />
            </button>
          }
        />
      ),
    },
  ];

  // CLI-06 (single and bulk) is planned: the buttons render for `client.intake` holders, disabled
  // with their hint, and not at all in production.
  const intake = canIntake && PLANNED_VISIBLE;
  const importButton = (
    <Button variant="secondary" icon="upload" disabled title={COPY.importHint}>
      {COPY.import}
    </Button>
  );
  const newButton = (
    <Button variant="primary" icon="plus" disabled title={COPY.newClientHint}>
      {COPY.newClient}
    </Button>
  );

  const countText =
    first === undefined
      ? undefined
      : narrowed
        ? COPY.showing(count(first.total))
        : COPY.count(count(first.total));

  return (
    <div data-screen="CLI-01" className="flex min-h-0 flex-1 flex-col">
      <IndexList<ClientRowOut>
        title={COPY.title}
        noun={COPY.noun}
        state={state}
        envelope={envelope}
        columns={columns}
        rowKey={(r) => r.id}
        twoLine={() => true}
        chips={chips}
        onChip={onChip}
        {...(narrowed ? { onClear: clear } : {})}
        query={filters.q}
        searchPlaceholder={COPY.search}
        onQuery={(q) => {
          set({ q });
        }}
        {...(countText === undefined ? {} : { countText })}
        {...(intake
          ? {
              actions: (
                <>
                  {importButton}
                  {newButton}
                </>
              ),
            }
          : {})}
        {...(list.hasNextPage
          ? {
              footer: (
                <Button
                  variant="secondary"
                  size="sm"
                  loading={list.isFetchingNextPage}
                  onClick={() => void list.fetchNextPage()}
                >
                  {COPY.loadMore}
                </Button>
              ),
            }
          : {})}
        empty={{
          icon: "building-2",
          title: COPY.empty.title,
          body: COPY.empty.body,
          ...(intake
            ? {
                action: (
                  <span className="flex items-center gap-[8px]">
                    {newButton}
                    {importButton}
                  </span>
                ),
              }
            : {}),
        }}
      />
    </div>
  );
}

function OpenRequests({ row }: { row: ClientRowOut }): JSX.Element {
  if (row.binder_draft_only === true) {
    return <span className="text-dense text-ink-3">{COPY.binderDraft}</span>;
  }
  const n = row.open_request_count;
  if (n == null || n === 0) {
    return <span className="text-ink-4">{COPY.none}</span>;
  }
  return <span className="tabular-nums">{count(n)}</span>;
}
