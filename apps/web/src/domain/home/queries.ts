// HOME-01's reads (I-01 §5.2), through the generated client only: `GET /v1/home`, and the one count
// source `GET /v1/human-gates/counts` with the list beside it. Polled every 60 s and on focus,
// fresh for 10 s (DEC-23: no SSE in I-01). Every gate mutation (snooze, reassign, an owner's
// decide) invalidates the counts and the list together, so the badge, header and summary move as
// one (`invalidateGates`).

import {
  homeOptions,
  humanGateCountsOptions,
  humanGateListOptions,
} from "@abacus/api-client/query";
import { type QueryClient, useQuery } from "@tanstack/react-query";

export const HOME_POLL_MS = 60_000;
export const HOME_STALE_MS = 10_000;
const POLL = {
  refetchInterval: HOME_POLL_MS,
  staleTime: HOME_STALE_MS,
  refetchOnWindowFocus: true,
};

function office(officeId: string | null): { query?: { office_id: string } } {
  return officeId === null ? {} : { query: { office_id: officeId } };
}

export function useHome(officeId: string | null) {
  return useQuery({ ...homeOptions(office(officeId)), ...POLL });
}

/** The one count source: the header, the summary line and the Approvals badge read this. */
export function useGateCounts(officeId: string | null) {
  return useQuery({ ...humanGateCountsOptions(office(officeId)), ...POLL });
}

/** What waits on the viewer (the rows); the list filters by office on the client until the
 * list's own `office_id` filter lands (I-01-T07). */
export function useWaitingOnYou() {
  return useQuery({
    ...humanGateListOptions({ query: { assignee: "me", limit: 200 } }),
    ...POLL,
  });
}

export async function invalidateGates(client: QueryClient): Promise<void> {
  // Partial keys: every office's counts, every list page and every home read.
  await Promise.all(
    ["humanGateCounts", "humanGateList", "home"].map((id) =>
      client.invalidateQueries({ queryKey: [{ _id: id }] }),
    ),
  );
}
