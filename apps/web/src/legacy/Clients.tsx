import type { EngagementSummaryOut, OverdueCountOut } from "@abacus/api-client";
import {
  getEngagementOptions,
  listEngagementsOptions,
  overdueWaitingOptions,
} from "@abacus/api-client/query";
import {
  Alert,
  Badge,
  type Column,
  DataTable,
  EmptyState,
  Skeleton,
  StatusPill,
} from "@abacus/ui";
import { useQueries, useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "@tanstack/react-router";
import { type JSX, useState } from "react";
import { errorMessage } from "../api";
import { typeLabel } from "./engagementTypes";

// SPEC-303 (TASK-304): the clients index (CLI-01) and the client record (CLI-02), joined in the
// screen from the engagements the person can already see (walls apply), so a client appears only
// through a visible engagement.

export type ClientRow = {
  id: string;
  name: string;
  entities: { id: string; name: string; engagements: EngagementSummaryOut[] }[];
  active: number;
  overdue: number;
  latestYearEnd: string;
};

/** Pure: group engagements by client, newest year end first inside each entity. */
export function groupClients(
  engagements: EngagementSummaryOut[],
  overdue: OverdueCountOut[] = [],
): ClientRow[] {
  const late = new Map(overdue.map((o) => [o.engagement_id, o.count]));
  const byClient = new Map<string, ClientRow>();
  for (const e of engagements) {
    let client = byClient.get(e.client_id);
    if (client === undefined) {
      client = {
        id: e.client_id,
        name: e.client_name,
        entities: [],
        active: 0,
        overdue: 0,
        latestYearEnd: "",
      };
      byClient.set(e.client_id, client);
    }
    let entity = client.entities.find((x) => x.id === e.client_entity_id);
    if (entity === undefined) {
      entity = { id: e.client_entity_id, name: e.client_entity_name, engagements: [] };
      client.entities.push(entity);
    }
    entity.engagements.push(e);
    if (e.status === "active") client.active += 1;
    client.overdue += late.get(e.id) ?? 0;
    if (e.fiscal_period_end > client.latestYearEnd) client.latestYearEnd = e.fiscal_period_end;
  }
  for (const client of byClient.values()) {
    client.entities.sort((a, b) => a.name.localeCompare(b.name));
    for (const entity of client.entities)
      entity.engagements.sort((a, b) => b.fiscal_period_end.localeCompare(a.fiscal_period_end));
  }
  return [...byClient.values()].sort((a, b) => a.name.localeCompare(b.name));
}

type Filter = "active" | "all";

export function Clients(): JSX.Element {
  const engagements = useQuery(listEngagementsOptions());
  const overdue = useQuery({ ...overdueWaitingOptions(), retry: false });
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<Filter>("active");
  if (engagements.isPending) return <Skeleton className="h-64" />;
  if (engagements.isError)
    return <Alert title="Couldn't load clients">{errorMessage(engagements.error)}</Alert>;
  const all = groupClients(engagements.data, overdue.data ?? []);
  const needle = search.trim().toLowerCase();
  const rows = all.filter(
    (c) =>
      (filter === "all" || c.active > 0) &&
      (needle === "" ||
        `${c.name} ${c.entities.map((e) => e.name).join(" ")}`.toLowerCase().includes(needle)),
  );
  const columns: Column<ClientRow>[] = [
    {
      key: "name",
      header: "Client",
      cell: (c) => (
        <span className="flex flex-col">
          <span className="font-medium">{c.name}</span>
          <span className="text-[11.5px] text-ink-3">
            {c.entities.length === 1
              ? c.entities[0]?.name
              : `${String(c.entities.length)} entities`}
          </span>
        </span>
      ),
      sortValue: (c) => c.name,
    },
    {
      key: "active",
      header: "Active engagements",
      align: "right",
      cell: (c) => <span className="tabular-nums">{c.active}</span>,
      sortValue: (c) => c.active,
    },
    {
      key: "overdue",
      header: "Overdue client items",
      align: "right",
      cell: (c) =>
        c.overdue > 0 ? (
          <Badge tone="warning">{c.overdue}</Badge>
        ) : (
          <span className="text-ink-4">—</span>
        ),
      sortValue: (c) => c.overdue,
    },
    {
      key: "year",
      header: "Latest year end",
      cell: (c) => <span className="tabular-nums">{c.latestYearEnd}</span>,
      sortValue: (c) => c.latestYearEnd,
    },
  ];
  return (
    <section
      aria-labelledby="clients-heading"
      className="flex flex-col overflow-hidden rounded-pane bg-card shadow-e2"
    >
      <div className="flex min-h-[50px] flex-wrap items-center gap-2 border-b-[0.5px] border-hair px-4 py-2">
        <h1 id="clients-heading" className="text-[15px] font-medium tracking-[-0.012em]">
          Clients
        </h1>
        <span className="text-[12.5px] text-ink-3 tabular-nums">{rows.length}</span>
        <span className="flex-1" />
        <input
          aria-label="Search clients"
          value={search}
          placeholder="Search clients and entities"
          onChange={(e) => {
            setSearch(e.target.value);
          }}
          className="h-[30px] w-[240px] rounded-tile border-0 bg-nested px-2.5 text-[13px] inset-shadow-hair focus:bg-card"
        />
        <div
          role="group"
          aria-label="Status"
          className="flex gap-0.5 rounded-tile bg-nested p-0.5"
        >
          {(
            [
              ["active", "With active work"],
              ["all", "All"],
            ] as const
          ).map(([key, label]) => (
            <button
              key={key}
              type="button"
              aria-pressed={filter === key}
              onClick={() => {
                setFilter(key);
              }}
              className={`rounded-[var(--radius-control)] px-2.5 py-1 text-[12.5px] ${filter === key ? "bg-card font-medium shadow-e1" : "text-ink-2"}`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>
      {rows.length === 0 ? (
        <EmptyState title={all.length === 0 ? "No clients yet" : "No clients match"}>
          {all.length === 0
            ? "Clients appear here once you're on one of their engagements."
            : "Try another search or show all clients."}
        </EmptyState>
      ) : (
        <DataTable
          label="Clients"
          rows={rows}
          columns={columns}
          rowKey={(c) => c.id}
          onRowClick={(c) => {
            void navigate({ to: "/clients/$clientId", params: { clientId: c.id } });
          }}
        />
      )}
    </section>
  );
}

const ROLE: Record<string, string> = {
  engagement_partner: "Partner",
  manager: "Manager",
  senior: "Senior",
  staff: "Staff",
  reviewer: "EQR",
};

export function ClientRecord({ clientId }: { clientId: string }): JSX.Element {
  const engagements = useQuery(listEngagementsOptions());
  const overdue = useQuery({ ...overdueWaitingOptions(), retry: false });
  const client = groupClients(engagements.data ?? [], overdue.data ?? []).find(
    (c) => c.id === clientId,
  );
  const active = (client?.entities ?? [])
    .flatMap((x) => x.engagements)
    .filter((e) => e.status === "active");
  const details = useQueries({
    queries: active.map((e) => ({
      ...getEngagementOptions({ path: { engagement_id: e.id } }),
      retry: false,
    })),
  });
  if (engagements.isPending) return <Skeleton className="h-64" />;
  if (engagements.isError)
    return <Alert title="Couldn't load the client">{errorMessage(engagements.error)}</Alert>;
  if (client === undefined)
    return (
      <Alert title="Client not found">
        It doesn't exist, or you're not on any of its engagements.{" "}
        <Link to="/clients">All clients</Link>
      </Alert>
    );
  const team = new Map<string, { name: string; roles: Set<string> }>();
  for (const d of details) {
    for (const m of d.data?.team ?? []) {
      const seen = team.get(m.user_id) ?? { name: m.display_name, roles: new Set<string>() };
      seen.roles.add(ROLE[m.role] ?? m.role);
      team.set(m.user_id, seen);
    }
  }
  const stats: [string, string | number][] = [
    ["Entities", client.entities.length],
    ["Active engagements", client.active],
    ["Overdue client items", client.overdue],
    ["Latest year end", client.latestYearEnd],
  ];
  return (
    <div className="flex flex-col gap-3">
      <header className="flex flex-col gap-3 rounded-pane bg-card p-4 shadow-e2">
        <div className="flex items-center gap-2 text-[12.5px] text-ink-3">
          <Link to="/clients" className="text-ink-3 hover:text-ink">
            Clients
          </Link>
          <span aria-hidden="true">›</span>
        </div>
        <h1 className="text-[20px] font-medium tracking-[-0.02em]">{client.name}</h1>
        <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {stats.map(([label, value]) => (
            <div key={label} className="rounded-nested bg-shell px-3 py-2.5">
              <dt className="text-[11.5px] text-ink-3">{label}</dt>
              <dd className="text-[15px] font-medium tabular-nums">{value}</dd>
            </div>
          ))}
        </dl>
      </header>
      <div className="grid gap-3 lg:grid-cols-[1fr_300px]">
        <div className="flex flex-col gap-3">
          {client.entities.map((entity) => (
            <section
              key={entity.id}
              aria-label={entity.name}
              className="flex flex-col overflow-hidden rounded-pane bg-card shadow-e2"
            >
              <div className="flex min-h-[46px] items-center gap-2 border-b-[0.5px] border-hair px-4">
                <h2 className="text-[14px] font-medium">{entity.name}</h2>
                <span className="text-[12px] text-ink-3 tabular-nums">
                  {entity.engagements.length}
                </span>
              </div>
              <ul className="divide-y-[0.5px] divide-hair">
                {entity.engagements.map((e) => (
                  <li key={e.id}>
                    <Link
                      to="/engagements/$engagementId"
                      params={{ engagementId: e.id }}
                      className="flex items-center gap-3 px-4 py-2.5 text-[13px] text-ink hover:bg-sel-bg hover:no-underline"
                    >
                      <span className="flex-1 font-medium">{e.name}</span>
                      <span className="text-ink-3">{typeLabel(e.type)}</span>
                      <span className="w-[180px] text-ink-3 tabular-nums">
                        {`${e.fiscal_period_start} – ${e.fiscal_period_end}`}
                      </span>
                      <StatusPill tone={e.status === "active" ? "success" : "neutral"}>
                        {e.status === "active" ? "Active" : "Archived"}
                      </StatusPill>
                    </Link>
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>
        <aside
          aria-labelledby="team-heading"
          className="flex h-fit flex-col gap-2 rounded-pane bg-card p-4 shadow-e2"
        >
          <h2 id="team-heading" className="text-[14px] font-medium">
            Team on active work
          </h2>
          {details.some((d) => d.isPending) ? (
            <Skeleton className="h-16" />
          ) : team.size === 0 ? (
            <p className="text-[12.5px] text-ink-3">No active engagements.</p>
          ) : (
            <ul className="flex flex-col gap-1.5 text-[13px]">
              {[...team.values()]
                .sort((a, b) => a.name.localeCompare(b.name))
                .map((m) => (
                  <li key={m.name} className="flex justify-between gap-2">
                    <span>{m.name}</span>
                    <span className="text-ink-3">{[...m.roles].join(", ")}</span>
                  </li>
                ))}
            </ul>
          )}
        </aside>
      </div>
    </div>
  );
}
