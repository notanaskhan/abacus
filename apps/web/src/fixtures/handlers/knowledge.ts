// The knowledge catalog in fixture mode (K-01-T04; docs/contracts/knowledge-catalog.md): cards with
// the status counts (category and search applied, status left out) and the category facets
// (status and search applied; a category without a provider is absent: no count, never 0), the
// review queue and the change log. As the API does, a reader who neither manages nor approves
// content gets no Draft card, no queue row and no change-log entry of a draft (AC1.6). Search is
// lexical and case-folded; match ranges are the title's. Typed with the generated client.

import type {
  Facet,
  KnowledgeItemOut,
  ListPageChangeLogEntryOut,
  ListPageKnowledgeItemOut,
  ListPageReviewQueueItemOut,
} from "@abacus/api-client";
import { type FixtureHandler, type FixtureRequest, json } from "../../app-core/fixture-mode";
import { DEFAULT_PERSONA } from "../handlers";
import {
  E0_CATEGORIES,
  KEYWORDS,
  cardNumber,
  changeLog,
  knowledgeItems,
  reviewQueue,
} from "../seed/knowledge";

/** The personas who manage or approve content (`methodology.manage` / `.approve`). */
export const DRAFT_READERS: ReadonlySet<string> = new Set([
  "margaret-okonkwo",
  "daniel-reyes",
  "priya-raman",
  "grace-holloway",
]);

const STATUSES = ["published", "draft", "superseded"] as const;

function ranges(title: string, q: string): { start: number; end: number }[] {
  const hay = title.toLowerCase();
  const needle = q.toLowerCase();
  const out: { start: number; end: number }[] = [];
  if (needle === "" || hay.length !== title.length) return out;
  let at = hay.indexOf(needle);
  while (at !== -1) {
    out.push({ start: at, end: at + needle.length });
    at = hay.indexOf(needle, at + needle.length);
  }
  return out;
}

function found(item: KnowledgeItemOut, q: string): boolean {
  const needle = q.toLowerCase();
  return [item.title, item.subtitle ?? "", ...(KEYWORDS[item.id] ?? [])].some((t) =>
    t.toLowerCase().includes(needle),
  );
}

export function catalogPage(request: FixtureRequest): ListPageKnowledgeItemOut {
  const drafts = DRAFT_READERS.has(request.persona ?? DEFAULT_PERSONA);
  const category = request.query.get("category");
  const status = request.query.get("status");
  const q = (request.query.get("q") ?? "").trim();
  let every = knowledgeItems().filter((i) => drafts || i.status !== "draft");
  if (q !== "") {
    // Title matches first, then what is found by its other words (KNW-01f: cards 8 and 1).
    const hits = every.filter((i) => found(i, q));
    every = [
      ...hits.filter((i) => ranges(i.title, q).length > 0),
      ...hits.filter((i) => ranges(i.title, q).length === 0),
    ];
  }
  const inCategory = every.filter((i) => category === null || i.category === category);
  const counts = Object.fromEntries(
    STATUSES.map((s) => [s, inCategory.filter((i) => i.status === s).length]),
  );
  const byStatus = every.filter((i) => status === null || i.status === status);
  const facets: Facet[] = E0_CATEGORIES.map((c) => ({
    value: c,
    label: c,
    n: byStatus.filter((i) => i.category === c).length,
  }));
  let items = byStatus.filter((i) => category === null || i.category === category);
  if (category !== null && q === "") {
    items = [...items].sort((a, b) => cardNumber(a.id) - cardNumber(b.id));
  }
  return {
    items: items.map((i) => ({ ...i, match: ranges(i.title, q) })),
    next_cursor: null,
    total: items.length,
    total_capped: false,
    counts,
    facets: { category: facets },
  };
}

export function knowledgeHandlers(): Record<string, FixtureHandler> {
  return {
    "GET /v1/knowledge/items": (request) => json(catalogPage(request)),
    "GET /v1/knowledge/review-queue": (request) => {
      const items = DRAFT_READERS.has(request.persona ?? DEFAULT_PERSONA) ? reviewQueue() : [];
      return json({
        items,
        next_cursor: null,
        total: items.length,
        total_capped: false,
        counts: { draft: items.length },
        facets: {},
      } satisfies ListPageReviewQueueItemOut);
    },
    "GET /v1/knowledge/change-log": () => {
      const items = changeLog();
      return json({
        items,
        next_cursor: null,
        total: items.length,
        total_capped: false,
        counts: {},
        facets: {},
      } satisfies ListPageChangeLogEntryOut);
    },
  };
}
