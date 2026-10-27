// The Home segmented control (DF-39; HOME-01 R2): My work · Approvals n · Deadlines · Capacity ·
// Insights. Only Approvals carries a count, and it is the counts endpoint's `total` (the badge
// rule, DF-25). Deadlines, Capacity and Insights are planned screens: shown in dev, fixture and
// gallery builds, hidden in production (chapter 04 §2.1 rule 4); Insights also needs its
// entitlement (DEC-55).

import type { SegmentsOut } from "@abacus/api-client";
import { Segmented, type TabOption } from "@abacus/ui";
import type { JSX } from "react";
import { PLANNED_VISIBLE } from "../../app-core/planned";

export const HOME_SEGMENTS = {
  label: "Home",
  myWork: "My work",
  approvals: "Approvals",
  deadlines: "Deadlines",
  capacity: "Capacity",
  insights: "Insights",
} as const;

export function homeSegmentOptions(
  total: number | undefined,
  segments: SegmentsOut | undefined,
  plannedVisible: boolean = PLANNED_VISIBLE,
): TabOption[] {
  const shown = (state: SegmentsOut["deadlines"] | undefined): boolean =>
    state === "available" || (state === "planned" && plannedVisible);
  return [
    { label: HOME_SEGMENTS.myWork },
    { label: HOME_SEGMENTS.approvals, ...(total === undefined ? {} : { count: total }) },
    ...(shown(segments?.deadlines) ? [{ label: HOME_SEGMENTS.deadlines }] : []),
    ...(shown(segments?.capacity) ? [{ label: HOME_SEGMENTS.capacity }] : []),
    ...(shown(segments?.insights) ? [{ label: HOME_SEGMENTS.insights }] : []),
  ];
}

export function HomeSegmented({
  total,
  segments,
  active = HOME_SEGMENTS.myWork,
  onChange,
}: {
  total: number | undefined;
  segments: SegmentsOut | undefined;
  active?: string;
  onChange?: (label: string) => void;
}): JSX.Element {
  return (
    <Segmented
      label={HOME_SEGMENTS.label}
      options={homeSegmentOptions(total, segments)}
      active={active}
      {...(onChange === undefined ? {} : { onChange })}
    />
  );
}
