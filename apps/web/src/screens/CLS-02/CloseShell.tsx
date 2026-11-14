import type { CloseSummaryOut } from "@abacus/api-client";
import { closeSummaryOptions } from "@abacus/api-client/query";
import { EmptyState, FlagOffState, type Opt, RecordHeader, Skeleton } from "@abacus/ui";
import { useQuery } from "@tanstack/react-query";
import type { JSX, ReactNode } from "react";
import { useFlag } from "../../app-core/flags";
import { MANIFEST, type Manifest } from "../../routes/manifest";
import { COPY, type CloseTab, TAB_SLUGS, isCloseTab } from "./copy";

// The close shell (C-01-T12; C-01 §5; SPEC-655 AC-7, AC-54): the record bar (42) and the close
// tabs (50) over `GET /v1/closes/{id}`, with the period stepper and the Review count. Each tab's
// body is its screen (CLS-02 to CLS-06, built by their rows); until then the body names its
// screen. Deliverables (CLS-08) is C-02's and renders disabled with its name (DV-6). With
// `closes.engine` off the route shows the C-20 flag-off state inside the frame, never a 404.

export interface CloseShellProps {
  closeId: string;
  tab: CloseTab;
  onTab: (tab: CloseTab) => void;
  onClose: (closeId: string) => void;
  onBack: () => void;
  /** The tab's screen; omitted until its row builds it. */
  children?: ReactNode;
  /** The manifest ID of the screen the body shows (for the planned body). */
  screen: string;
}

const SCREENS: Manifest = MANIFEST;

const TAB_SCREEN: Record<CloseTab, string> = {
  overview: "CLS-02",
  intake: "CLS-03",
  accounts: "CLS-04",
  review: "CLS-06",
  deliverables: "CLS-08",
};

function shiftPeriod(period: string, months: number): string {
  const [y, m] = period.split("-").map(Number) as [number, number];
  const index = y * 12 + (m - 1) + months;
  return `${String(Math.floor(index / 12))}-${String((index % 12) + 1).padStart(2, "0")}`;
}

/** The stepper's periods: the previous and next closes when they exist, around this one. */
export function periodsOf(summary: CloseSummaryOut): string[] {
  return [
    ...(summary.previous_period_close_id ? [shiftPeriod(summary.period, -1)] : []),
    summary.period,
    ...(summary.next_period_close_id ? [shiftPeriod(summary.period, 1)] : []),
  ];
}

export function tabsOf(summary: CloseSummaryOut | undefined): Opt[] {
  return TAB_SLUGS.map((slug): Opt => {
    const label = COPY.tabs[slug];
    if (slug === "review" && summary !== undefined && summary.open_issues > 0) {
      return { label, count: summary.open_issues, bad: true };
    }
    if (SCREENS[TAB_SCREEN[slug]]?.path === null) return { label, disabled: true };
    return label;
  });
}

function PlannedBody({ screen }: { screen: string }): JSX.Element {
  return <EmptyState icon="layers" title={SCREENS[screen]?.name ?? screen} />;
}

export function CloseShell(props: CloseShellProps): JSX.Element {
  const enabled = useFlag("closes.engine") === true;
  const summary = useQuery({
    ...closeSummaryOptions({ path: { close_id: props.closeId } }),
    enabled,
  });
  if (!enabled) {
    return <FlagOffState flag="closes.engine" label={COPY.flagLabel} />;
  }
  const data = summary.data;
  const tabLabel = COPY.tabs[props.tab];
  const header =
    data === undefined ? (
      <div className="flex h-[92px] items-center justify-center">
        <Skeleton className="h-[9px] w-[320px]" />
      </div>
    ) : (
      <RecordHeader
        variant="close"
        title={data.client_name}
        context={COPY.record}
        periods={periodsOf(data)}
        period={data.period}
        onPeriod={(period) => {
          const target =
            period < data.period ? data.previous_period_close_id : data.next_period_close_id;
          if (target) props.onClose(target);
        }}
        tabs={tabsOf(data)}
        activeTab={tabLabel}
        tabsLabel={COPY.tabsLabel}
        onTab={(label) => {
          const slug = TAB_SLUGS.find((s) => COPY.tabs[s] === label);
          if (isCloseTab(slug)) props.onTab(slug);
        }}
        backLabel={COPY.back}
        onBack={props.onBack}
      />
    );
  return (
    <div data-screen={props.screen} className="flex min-h-0 flex-1 flex-col">
      {header}
      <div className="flex min-h-0 flex-1 flex-col">
        {props.children ?? <PlannedBody screen={props.screen} />}
      </div>
    </div>
  );
}
