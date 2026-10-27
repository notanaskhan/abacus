// KNW-01's reads through the generated client only (K-01-T03's contract): the catalog cards with
// their status counts and category facets, the review queue and the change log.

import {
  knowledgeChangeLogOptions,
  knowledgeItemsOptions,
  knowledgeReviewQueueOptions,
} from "@abacus/api-client/query";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import type { KnowledgeCategory } from "./categories";

export interface CatalogFilters {
  category: KnowledgeCategory | null;
  status: "published" | "draft" | "superseded" | null;
  q: string;
}

export function useKnowledgeItems(filters: CatalogFilters) {
  const query = {
    ...(filters.category === null ? {} : { category: filters.category }),
    ...(filters.status === null ? {} : { status: filters.status }),
    ...(filters.q.trim() === "" ? {} : { q: filters.q.trim() }),
    limit: 200,
  };
  return useQuery({ ...knowledgeItemsOptions({ query }), placeholderData: keepPreviousData });
}

export function useReviewQueue() {
  return useQuery(knowledgeReviewQueueOptions());
}

export function useChangeLog(enabled: boolean) {
  return useQuery({ ...knowledgeChangeLogOptions({ query: { limit: 200 } }), enabled });
}
