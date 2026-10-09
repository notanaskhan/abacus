/** The API's engagement type (SPEC-024 Q5). */
export type EngagementType = "audit" | "review" | "compilation" | "agreed_upon_procedures";

/** SPEC-024 Q5: the US engagement types (AICPA), in plain words. */
export const ENGAGEMENT_TYPES: [EngagementType, string][] = [
  ["audit", "Audit"],
  ["review", "Review"],
  ["compilation", "Compilation"],
  ["agreed_upon_procedures", "Agreed-upon procedures"],
];

export function typeLabel(type: string): string {
  return ENGAGEMENT_TYPES.find(([value]) => value === type)?.[1] ?? type;
}
