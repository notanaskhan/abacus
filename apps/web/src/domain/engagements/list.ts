// The engagements index (P-07 §5, L3; docs/contracts/engagements-v2.md §3): ENG-01's filters and
// `GET /v1/engagements/index` over the generated client only. The server computes the tiles
// (`counts`, minus the selected tile), the segments (`facets.service_line`) and the summary over
// one `visible()` predicate; the screen adds nothing up.

import type {
  EngagementIndexData,
  EngagementIndexRowOut,
  EngagementStatus,
} from "@abacus/api-client";
import { engagementIndexInfiniteOptions } from "@abacus/api-client/query";
import { useInfiniteQuery } from "@tanstack/react-query";

export type EngagementLine = EngagementIndexRowOut["service_line"];
export type EngagementQuery = NonNullable<EngagementIndexData["query"]>;
export type NextDueWindow = NonNullable<EngagementQuery["next_due"]>;
export type EngagementPeriod = NonNullable<EngagementQuery["period"]>;

export const ENGAGEMENT_LINES: readonly EngagementLine[] = ["tax", "audit", "cas", "advisory"];

/** The seven tiles, in the screen's order; `declined` is never a tile. */
export const ENGAGEMENT_TILES: readonly EngagementStatus[] = [
  "prospect",
  "accepted",
  "contracted",
  "active",
  "on_hold",
  "delivered",
  "archived",
];

export interface EngagementFilters {
  line: EngagementLine | null;
  tile: EngagementStatus | null;
  office: string | null;
  partner: string | null;
  letter: "not_signed" | "signed" | null;
  nextDue: NextDueWindow | null;
  period: EngagementPeriod;
  client: string | null;
  q: string;
}

export const DEFAULT_ENGAGEMENT_FILTERS: EngagementFilters = {
  line: null,
  tile: null,
  office: null,
  partner: null,
  letter: null,
  nextDue: null,
  period: "current",
  client: null,
  q: "",
};

export function isEngagementLine(v: string | null | undefined): v is EngagementLine {
  return v != null && (ENGAGEMENT_LINES as readonly string[]).includes(v);
}

export function isEngagementTile(v: string | null | undefined): v is EngagementStatus {
  return v != null && (ENGAGEMENT_TILES as readonly string[]).includes(v);
}

/** Anything but the default view (the segment is a view, not a filter). */
export function isNarrowedIndex(f: EngagementFilters): boolean {
  return (
    f.tile !== null ||
    f.office !== null ||
    f.partner !== null ||
    f.letter !== null ||
    f.nextDue !== null ||
    f.period !== "current" ||
    f.client !== null ||
    f.q.trim() !== ""
  );
}

function queryOf(f: EngagementFilters): EngagementQuery {
  const q = f.q.trim();
  return {
    ...(f.line === null ? {} : { service_line: f.line }),
    ...(f.tile === null ? {} : { tile: f.tile }),
    ...(f.office === null ? {} : { office_id: f.office }),
    ...(f.partner === null ? {} : { partner_id: f.partner }),
    ...(f.letter === null ? {} : { letter: f.letter }),
    ...(f.nextDue === null ? {} : { next_due: f.nextDue }),
    ...(f.period === "current" ? {} : { period: f.period }),
    ...(f.client === null ? {} : { client_id: f.client }),
    ...(q === "" ? {} : { q }),
  };
}

/** `GET /v1/engagements/index`, keyset-paged ("Load more" appends the next page). */
export function useEngagementIndex(filters: EngagementFilters) {
  return useInfiniteQuery({
    ...engagementIndexInfiniteOptions({ query: queryOf(filters) }),
    initialPageParam: {},
    getNextPageParam: (last) => last.next_cursor ?? undefined,
    retry: false,
  });
}
