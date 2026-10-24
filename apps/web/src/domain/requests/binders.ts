// Binders (P-06 §5.2, L3): the BND-01 list read and the row actions, over the generated client
// only. The filters are BND-01's search params; the server applies them after `visible()`, so a
// walled binder is absent from rows, tiles and totals and nothing here counts what it cannot see.

import type { BinderRowOut, BinderStatus, ListPageBinderRowOut } from "@abacus/api-client";
import {
  createBinderMutation,
  duplicateBinderMutation,
  listBindersOptions,
  listEngagementsOptions,
  publishBinderMutation,
  staffOptions,
  undoPublishBinderMutation,
  unpublishBinderMutation,
  workItemsOptions,
} from "@abacus/api-client/query";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

export type ClientActivity = "any" | "none_30_days";

/** BND-01's search params (P-06 §5.1); a tile sets `status`. */
export interface BinderFilters {
  service: string | null;
  season: string | null;
  office: string | null;
  preparer: string | null;
  activity: ClientActivity;
  status: BinderStatus | null;
  q: string;
}

export const BINDER_STATUSES: readonly BinderStatus[] = [
  "draft",
  "published",
  "unpublished",
  "complete",
  "closed",
];

export function isBinderStatus(v: unknown): v is BinderStatus {
  return typeof v === "string" && (BINDER_STATUSES as readonly string[]).includes(v);
}

/** The tax season a firm works in on `today` (YYYY-MM-DD): returns for the year before. */
export function currentSeason(today: string): string {
  return `TY${String(Number(today.slice(0, 4)) - 1)}`;
}

/** What BND-01 opens on: Service │ Tax returns and the current season, nothing else narrowed. */
export function defaultBinderFilters(today: string): BinderFilters {
  return {
    service: "tax_returns",
    season: currentSeason(today),
    office: null,
    preparer: null,
    activity: "any",
    status: null,
    q: "",
  };
}

/** BND-01's filters in the URL (P-06-T16; DV-15): only what differs from the defaults, so
 * `/binders` is the default view and a shared link reopens the same list. */
export interface BinderSearch {
  service?: string;
  season?: string;
  office?: string;
  preparer?: string;
  client_activity?: "none_30_days";
  status?: BinderStatus;
  q?: string;
}

const SEARCH_KEYS = ["service", "season", "office", "preparer", "q"] as const;

export function validateBinderSearch(search: Record<string, unknown>): BinderSearch {
  const found: BinderSearch = {};
  for (const key of SEARCH_KEYS) {
    const value = search[key];
    if (typeof value === "string" && value !== "") found[key] = value;
  }
  if (search.client_activity === "none_30_days") found.client_activity = "none_30_days";
  const status = search.status;
  if (typeof status === "string" && isBinderStatus(status)) found.status = status;
  return found;
}

export function binderFiltersOf(search: BinderSearch, today: string): BinderFilters {
  const base = defaultBinderFilters(today);
  return {
    service: search.service ?? base.service,
    season: search.season ?? base.season,
    office: search.office ?? null,
    preparer: search.preparer ?? null,
    activity: search.client_activity ?? "any",
    status: search.status ?? null,
    q: search.q ?? "",
  };
}

export function binderSearchOf(filters: BinderFilters, today: string): BinderSearch {
  const base = defaultBinderFilters(today);
  return {
    ...(filters.service !== base.service && filters.service !== null
      ? { service: filters.service }
      : {}),
    ...(filters.season !== base.season && filters.season !== null
      ? { season: filters.season }
      : {}),
    ...(filters.office === null ? {} : { office: filters.office }),
    ...(filters.preparer === null ? {} : { preparer: filters.preparer }),
    ...(filters.activity === "none_30_days" ? { client_activity: "none_30_days" as const } : {}),
    ...(filters.status === null ? {} : { status: filters.status }),
    ...(filters.q.trim() === "" ? {} : { q: filters.q }),
  };
}

function queryOf(f: BinderFilters) {
  return {
    ...(f.service === null ? {} : { service: f.service }),
    ...(f.season === null ? {} : { season: f.season }),
    ...(f.office === null ? {} : { office: f.office }),
    ...(f.preparer === null ? {} : { preparer: f.preparer }),
    client_activity: f.activity,
    ...(f.status === null ? {} : { status: f.status }),
    ...(f.q.trim() === "" ? {} : { q: f.q.trim() }),
  };
}

/** `GET /v1/binders`: rows, the tiles' `counts` (over the filters minus the tile) and facets. */
export function useBinders(filters: BinderFilters) {
  return useQuery({ ...listBindersOptions({ query: queryOf(filters) }), retry: false });
}

/** Seat holders, for the Prep initials and the "by {person}" of a row. */
export function useStaffNames(): ReadonlyMap<string, string> {
  const { data } = useQuery({ ...staffOptions(), retry: false });
  return new Map((data?.members ?? []).map((m) => [m.user_id, m.display_name]));
}

/** "Kevin Osei" → "KO". */
export function initialsOf(name: string): string {
  const words = name.split(/\s+/).filter((w) => w !== "");
  const first = words[0]?.charAt(0) ?? "";
  const last = words.length > 1 ? (words[words.length - 1]?.charAt(0) ?? "") : "";
  return `${first}${last}`.toUpperCase();
}

/** Whether the server lets this person take `action` on the row. */
export function rowAllows(row: BinderRowOut, action: string): boolean {
  return (row.allowed_actions ?? []).includes(action);
}

function useRefreshBinders(): () => void {
  const queryClient = useQueryClient();
  return () => {
    void queryClient.invalidateQueries({
      predicate: (q) => (q.queryKey[0] as { _id?: string } | undefined)?._id === "listBinders",
    });
  };
}

/** A fresh Idempotency-Key per publish (P-36). */
function idempotencyKey(): string {
  return globalThis.crypto.randomUUID();
}

/** Row ··· actions: publish (with its 10-second Undo), unpublish with a reason, duplicate as pt n. */
export function useBinderActions() {
  const refresh = useRefreshBinders();
  const publish = useMutation({ ...publishBinderMutation(), onSuccess: refresh });
  const undo = useMutation({ ...undoPublishBinderMutation(), onSuccess: refresh });
  const unpublish = useMutation({ ...unpublishBinderMutation(), onSuccess: refresh });
  const duplicate = useMutation({ ...duplicateBinderMutation(), onSuccess: refresh });
  return {
    publish: (binderId: string) =>
      publish.mutateAsync({
        path: { binder_id: binderId },
        headers: { "Idempotency-Key": idempotencyKey() },
      }),
    undoPublish: (binderId: string) => undo.mutateAsync({ path: { binder_id: binderId } }),
    unpublish: (binderId: string, reason: string) =>
      unpublish.mutateAsync({ path: { binder_id: binderId }, body: { reason } }),
    duplicate: (binderId: string) => duplicate.mutateAsync({ path: { binder_id: binderId } }),
  };
}

export type BinderKind = BinderRowOut["kind"];

/** The binder kind a work item takes: an organizer for a return, PBC for assurance, close intake. */
export function kindForWorkItem(kind: string): BinderKind {
  if (kind === "assurance") return "pbc";
  if (kind === "close") return "close_intake";
  return "organizer";
}

/** "+ New binder": the engagements and work items to choose from, and the create call. */
export function useNewBinder(engagementId: string | null) {
  const refresh = useRefreshBinders();
  const engagements = useQuery({ ...listEngagementsOptions(), retry: false });
  const items = useQuery({
    ...workItemsOptions({ path: { engagement_id: engagementId ?? "" } }),
    enabled: engagementId !== null,
    retry: false,
  });
  const create = useMutation({ ...createBinderMutation(), onSuccess: refresh });
  return { engagements, items, create };
}

export type BinderPage = ListPageBinderRowOut;
