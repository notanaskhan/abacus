// The close shell (C-01-T12; CLS-02 spec.md lines 19–20 and the R2 revision): the record bar's
// words and the close tabs, verbatim from the handoff. The status and tally words come from the
// registry (`close`, `close_flag`, `close_tally`; C-01-T03), never from here.

export const TAB_SLUGS = ["overview", "intake", "accounts", "review", "deliverables"] as const;
export type CloseTab = (typeof TAB_SLUGS)[number];

export const COPY = {
  record: "Close",
  back: "‹ Back",
  tabs: {
    overview: "Overview",
    intake: "Intake",
    accounts: "Accounts",
    review: "Review",
    deliverables: "Deliverables",
  } satisfies Record<CloseTab, string>,
  tabsLabel: "Close",
  flagLabel: "Closes",
} as const;

export function isCloseTab(value: unknown): value is CloseTab {
  return typeof value === "string" && (TAB_SLUGS as readonly string[]).includes(value);
}
