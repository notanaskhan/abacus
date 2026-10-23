// Clients (P-07 §5, L3): the CLI-01 list read over the generated client only. The filters are
// CLI-01's search params; the server applies them after `visible(scope=client)`, so a walled
// client is absent from rows, counts, facets and `total`, and nothing here counts what it cannot
// see (INV-3, DEC-43). `q` is a list parameter over the resource's own columns and is never logged.

import type { ClientRowOut, ClientStatus, ListClientsData } from "@abacus/api-client";
import { listClientsInfiniteOptions } from "@abacus/api-client/query";
import { useInfiniteQuery } from "@tanstack/react-query";

export type ClientKind = NonNullable<ClientRowOut["kind"]>;
export type ServiceLine = ClientRowOut["service_lines"][number];

export const CLIENT_KINDS: readonly ClientKind[] = [
  "household",
  "business",
  "plan_sponsor",
  "nonprofit",
  "trust_family",
];
export const SERVICE_LINES: readonly ServiceLine[] = ["tax", "audit", "cas", "advisory"];
export const CLIENT_STATUSES: readonly ClientStatus[] = [
  "prospect",
  "active",
  "inactive",
  "former",
];

/** CLI-01's search params (P-07 §5): `kind`, `office`, `partner`, `service_line`, `status`, `q`. */
export interface ClientFilters {
  kind: ClientKind | null;
  office: string | null;
  partner: string | null;
  serviceLine: ServiceLine | null;
  status: ClientStatus | null;
  q: string;
}

/** What CLI-01 opens on: Status │ Active, nothing else narrowed (a). */
export const DEFAULT_CLIENT_FILTERS: ClientFilters = {
  kind: null,
  office: null,
  partner: null,
  serviceLine: null,
  status: "active",
  q: "",
};

/** The first page CLI-01a draws: the 16 most recently active clients, then "Load more". */
export const CLIENT_PAGE_SIZE = 16;

export function isClientKind(v: unknown): v is ClientKind {
  return typeof v === "string" && (CLIENT_KINDS as readonly string[]).includes(v);
}

export function isServiceLine(v: unknown): v is ServiceLine {
  return typeof v === "string" && (SERVICE_LINES as readonly string[]).includes(v);
}

export function isClientStatus(v: unknown): v is ClientStatus {
  return typeof v === "string" && (CLIENT_STATUSES as readonly string[]).includes(v);
}

/** True when a chip or the search narrows the list past the default (b, d): the header then
 * reads "Showing n" instead of the firm's client count. */
export function isNarrowed(f: ClientFilters): boolean {
  return (
    f.kind !== null ||
    f.office !== null ||
    f.partner !== null ||
    f.serviceLine !== null ||
    f.status !== DEFAULT_CLIENT_FILTERS.status ||
    f.q.trim() !== ""
  );
}

function queryOf(f: ClientFilters): NonNullable<ListClientsData["query"]> {
  return {
    ...(f.kind === null ? {} : { kind: f.kind }),
    ...(f.office === null ? {} : { office_id: f.office }),
    ...(f.partner === null ? {} : { partner_id: f.partner }),
    ...(f.serviceLine === null ? {} : { service_line: f.serviceLine }),
    ...(f.status === null ? {} : { status: f.status }),
    ...(f.q.trim() === "" ? {} : { q: f.q.trim() }),
    sort: "last_activity",
    facets: true,
    limit: CLIENT_PAGE_SIZE,
  };
}

/** `GET /v1/clients`, keyset-paged: "Load more" appends the next page; there are no page
 * numbers (P-07 Story 1.1). */
export function useClients(filters: ClientFilters) {
  return useInfiniteQuery({
    ...listClientsInfiniteOptions({ query: queryOf(filters) }),
    // The first page is the query key's own params: an empty page object (the generated
    // queryFn reads a null page param as an object and fails on it).
    initialPageParam: {},
    getNextPageParam: (last) => last.next_cursor ?? undefined,
    retry: false,
  });
}
