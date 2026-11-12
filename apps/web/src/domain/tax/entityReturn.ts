// T-05-T28 (TASK-7520; T-05 §5.1, F1): the entity return's tabs and slugs. A 1065 opens on its Agent
// tab (TXP-00); a 1040 or 1041 keeps TAX-02. Group A is the reviewer's order; Review's Group B
// lists the review sheets, of which four are P1 (T-06): planned, hidden in production by the flag
// and drawn "Not built yet" in fixture builds. A slug that is not the form's redirects to Agent.

export const ENTITY_FORMS: ReadonlySet<string> = new Set(["1065"]);

export const GROUP_A = ["agent", "issues", "workpaper", "review", "intake", "activity"] as const;
export type EntityTab = (typeof GROUP_A)[number];

export const GROUP_B = [
  "summary",
  "financials",
  "fixed-assets",
  "m1-m3",
  "schedule-m2",
  "schedule-k",
  "capital",
  "basis",
  "states",
] as const;
export type ReviewTab = (typeof GROUP_B)[number];
export const P1_REVIEW: ReadonlySet<ReviewTab> = new Set([
  "fixed-assets",
  "m1-m3",
  "basis",
  "states",
]);

export const TAB_LABEL: Readonly<Record<EntityTab | ReviewTab, string>> = {
  agent: "Agent",
  issues: "Issues",
  workpaper: "Workpaper",
  review: "Review",
  intake: "Intake",
  activity: "Activity",
  summary: "Summary",
  financials: "Financials",
  "fixed-assets": "Fixed Assets",
  "m1-m3": "M-1/M-3",
  "schedule-m2": "Schedule M-2",
  "schedule-k": "Schedule K",
  capital: "Capital Accounts",
  basis: "Basis",
  states: "States",
};

/** The screen each section opens (the manifest's IDs). */
export const SCREEN_OF: Readonly<Partial<Record<EntityTab | ReviewTab, string>>> = {
  agent: "TXP-00",
  issues: "TXP-10",
  workpaper: "TXP-11",
  intake: "TAX-03",
  activity: "TAX-07",
  summary: "TXP-01",
  financials: "TXP-02",
  "schedule-k": "TXP-05",
  capital: "TXP-07",
};

export function isEntityForm(form: string | null | undefined): boolean {
  return form != null && ENTITY_FORMS.has(form);
}

export interface Section {
  tab: EntityTab;
  review?: ReviewTab;
}

/** A path's section for an entity return, or null (the caller redirects to Agent). */
export function sectionOf(slug: string | undefined, review?: string): Section | null {
  if (slug === undefined || slug === "") return { tab: "agent" };
  if (!(GROUP_A as readonly string[]).includes(slug)) return null;
  const tab = slug as EntityTab;
  if (tab !== "review") return review === undefined ? { tab } : null;
  if (review === undefined || review === "") return { tab, review: "summary" };
  return (GROUP_B as readonly string[]).includes(review)
    ? { tab, review: review as ReviewTab }
    : null;
}

/** The path segment(s) after `/tax-returns/$returnId` for a section. */
export function slugOf(section: Section): string {
  if (section.tab === "agent") return "";
  if (section.tab === "review") return `/review/${section.review ?? "summary"}`;
  return `/${section.tab}`;
}
