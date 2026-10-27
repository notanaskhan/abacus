// KNW-01 copy, verbatim from the handoff spec.md and revision.md R2. Card names, versions, owners,
// dates and counts are data, never copy. Strings with no handoff source are marked "undesigned".

export const COPY = {
  tabsLabel: "Knowledge",
  tabs: { library: "Library", review: "Review queue", changes: "Change log" },
  search: "Search knowledge",
  gridSearch: "Search",
  add: "Add to knowledge",
  addMenu: [
    "Upload methodology…",
    "New firm standard…",
    "New template…",
    "New research memo…",
    "New engagement template…",
    "New skill…",
  ],
  about: {
    title: "Knowledge",
    body: (firm: string) =>
      `${firm}’s methodology, standards, templates and positions. Agents work from the published versions here, and every citation points back to them.`,
  },
  categories: "Categories",
  all: "All",
  status: "Status",
  open: "Open",
  review: "Review",
  /** Undesigned: a planned target's hint in dev and fixture builds (chapter 04 §2.1 rule 4). */
  notBuilt: "Not built yet",
  effective: (on: string) => `Effective ${on}`,
  submitted: (on: string) => `submitted ${on}`,
  /** Undesigned: the grid when nothing matches. */
  noMatch: (q: string) => `Nothing in knowledge matches “${q}”.`,
  /** Undesigned: an empty review queue. */
  queueEmpty: "Nothing waiting for review.",
  change: {
    approved: (title: string, who: string) => `${title} approved by ${who}`,
    published: (title: string, who: string) => `${title} published by ${who}`,
    imported: (title: string, who: string) => `${title} imported by ${who}`,
    other: (title: string, who: string) => `${title} · ${who}`,
    /** A platform release of a library agent: "Request Chaser v3 available (Accrued)". */
    available: (title: string) => `${title} available (Accrued)`,
    effective: (on: string) => `effective ${on}`,
    viaAgent: (who: string) => `${who} via Agent`,
  },
} as const;
