// Firm search (P-02-T10; C15 v1, docs/contracts/c15-search.md): the "Go…" palette's reads over the
// generated client. The search text travels in the POST body only and is never logged or put in
// a query key that leaves the tab; each keystroke's request is debounced (150 ms) and aborted when
// a newer one starts. The server applies walls and `visible()`; nothing here counts what it
// cannot see (DEC-43).

import type { SearchQueryIn, SearchResultsOut } from "@abacus/api-client";
import { firmSearch } from "@abacus/api-client";
import { recentsOptions, recordRecentMutation } from "@abacus/api-client/query";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";

export type SearchGroup = NonNullable<SearchQueryIn["types"]>[number];

export const DEBOUNCE_MS = 150;

export function useDebounced<T>(value: T, ms: number = DEBOUNCE_MS): T {
  const [settled, setSettled] = useState(value);
  useEffect(() => {
    const id = setTimeout(() => {
      setSettled(value);
    }, ms);
    return () => {
      clearTimeout(id);
    };
  }, [value, ms]);
  return settled;
}

/** `POST /v1/search` for the settled text (or `>` agent mode); disabled when there is none. */
export function useFirmSearch(q: string, types: SearchGroup[] | null, enabled: boolean) {
  const text = useDebounced(q);
  return useQuery<SearchResultsOut>({
    // The text stays in this tab's cache only; it is never sent anywhere but the POST body.
    queryKey: ["firmSearch", text, types],
    queryFn: async ({ signal }) => {
      const { data } = await firmSearch({
        body: { q: text, ...(types === null ? {} : { types }), limit_per_group: 5 },
        signal,
        throwOnError: true,
      });
      return data;
    },
    enabled: enabled && (text !== "" || types !== null),
    staleTime: 10_000,
    retry: false,
  });
}

/** `GET /v1/search/recents` when nothing is typed (SHL-02 b). */
export function useRecents(enabled: boolean) {
  return useQuery({ ...recentsOptions({ query: { limit: 5 } }), enabled, retry: false });
}

/** `POST /v1/search/recents` when a record is opened from the palette. */
export function useRecordRecent() {
  const m = useMutation(recordRecentMutation());
  return (object_type: string, object_id: string): void => {
    m.mutate({ body: { object_type, object_id } });
  };
}
