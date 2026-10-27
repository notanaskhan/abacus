// KNW-01's category registry (K-01-T04; KNW-01 revision R2, addendum §4): the CategoryList order,
// each category's label, its icon tile's tone and glyph, and the words a usage count reads in. A
// category's cards and count come from its provider; one without a provider shows no count.

import type { KnowledgeItemOut } from "@abacus/api-client";
import type { IconName } from "@abacus/ui";

export type KnowledgeCategory = KnowledgeItemOut["category"];
export type UsageKind = NonNullable<KnowledgeItemOut["usage_kind"]>;

/** The tile fill tokens: espresso, olive, clay, ochre, brick (the five category colours). */
export type Tone = "espresso" | "olive" | "clay" | "ochre" | "brick";

export const TONE_FILL: Readonly<Record<Tone, string>> = {
  espresso: "bg-espresso",
  olive: "bg-green",
  clay: "bg-clay",
  ochre: "bg-amber",
  brick: "bg-red",
};

export interface CategoryDef {
  key: KnowledgeCategory;
  label: string;
  tone: Tone;
  icon: IconName;
}

/** All · then these, in the addendum's order. */
export const CATEGORIES: readonly CategoryDef[] = [
  {
    key: "engagement_templates",
    label: "Engagement templates",
    tone: "espresso",
    icon: "layout-template",
  },
  { key: "methodology", label: "Methodology", tone: "espresso", icon: "notebook-text" },
  { key: "frameworks", label: "Frameworks", tone: "olive", icon: "shield-check" },
  { key: "firm_standards", label: "Firm standards", tone: "olive", icon: "list-checks" },
  { key: "skills", label: "Skills", tone: "clay", icon: "graduation-cap" },
  { key: "notes", label: "Notes", tone: "ochre", icon: "sticky-note" },
  { key: "pbc_templates", label: "Templates", tone: "clay", icon: "file-text" },
  { key: "research", label: "Research & positions", tone: "ochre", icon: "scale" },
  { key: "content_packs", label: "Content packs", tone: "brick", icon: "package" },
  { key: "agent_instructions", label: "Agent instructions", tone: "brick", icon: "sparkles" },
];

export function categoryDef(key: KnowledgeCategory): CategoryDef {
  const found = CATEGORIES.find((c) => c.key === key);
  if (found === undefined) throw new Error(`unknown knowledge category ${key}`);
  return found;
}

const plural = (n: number, one: string, many: string): string => (n === 1 ? one : many);

/** "Used by 14 engagements", "Applied to 38 returns", "Used by 22 closes", "Used by: My Agents". */
export function usageWords(kind: UsageKind, n: number | null): string | null {
  if (kind === "agents") return "Used by: My Agents";
  if (n === null) return null;
  const count = String(n);
  switch (kind) {
    case "engagements":
      return `Used by ${count} ${plural(n, "engagement", "engagements")}`;
    case "returns":
      return `Applied to ${count} ${plural(n, "return", "returns")}`;
    case "closes":
      return `Used by ${count} ${plural(n, "close", "closes")}`;
    case "audits":
      return `Used by ${count} ${plural(n, "audit", "audits")}`;
  }
}
