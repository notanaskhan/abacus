// AnalyticsLayout T21 (F-08-T14; TASK-8846; F-08 §D; handoff T21 a–g; R8 "every number traces";
// INV-3; DEC-5845): the analytics frame. Subbar 42 (title; the Home segmented — My work ·
// Approvals · Deadlines · Capacity · Insights — in `home`, or in `record` the record's own subbar
// slot; scope chips, amber when narrowed), a tabs bar 44 (the screen's tabs; in `record` the
// audience segmented Preparer · Reviewer · Client and a milestone slot), the KPI row (4–6 tiles
// share the width), and a 12-column card grid (gap 10) of ChartCards whose footers always state the
// basis, naming the scope when a chip narrows it. `view`: ready · loading (tiles and card bodies
// pulse, headers and footers real) · flag-off (the designed state, never a 404) · restricted
// (names and counts only; `LockedName` opens nothing). The layout fetches and computes nothing.
import type { JSX, ReactNode } from "react";
import { ChartKpiTile } from "../charts/card";
import type { KpiTileProps } from "../charts/types";
import { cn } from "../cn";
import { Segmented } from "../components/tabs";
import { FlagOffState } from "../components/view-state";
import { Icon } from "../icons";

export const HOME_SEGMENTS = [
  "My work",
  "Approvals",
  "Deadlines",
  "Capacity",
  "Insights",
] as const;
export const AUDIENCES = ["Preparer", "Reviewer", "Client"] as const;
export const ANALYTICS_GEOMETRY = {
  subbar: 42,
  tabs: 44,
  tile: 72,
  gap: 10,
  columns: 12,
} as const;

export interface ScopeChip {
  key: string;
  label: string;
  icon?: "calendar-range" | "map-pin" | "layers";
  /** A narrowed scope reads amber (T21b). */
  narrowed: boolean;
  onClick?: () => void;
}

export interface AnalyticsCard {
  key: string;
  /** Columns of 12 (6 is half the grid). */
  span: number;
  /** A ChartCard (its footer states the basis); in `loading` the layout draws the pulse. */
  card: ReactNode;
  /** The header and footer stay real while loading. */
  title: string;
  basis: string;
}

export type AnalyticsView = "ready" | "loading" | "flag-off" | "restricted";

export interface AnalyticsLayoutProps {
  variant: "home" | "record";
  title: string;
  /** `record`: the record's subbar (title, context, status). */
  recordSubbar?: ReactNode;
  scope: readonly ScopeChip[];
  tabs: readonly string[];
  activeTab: string;
  onTab?: (tab: string) => void;
  audience?: (typeof AUDIENCES)[number];
  onAudience?: (a: (typeof AUDIENCES)[number]) => void;
  milestone?: ReactNode;
  tiles: readonly KpiTileProps[];
  cards: readonly AnalyticsCard[];
  view?: AnalyticsView;
  /** The entitlement's key for the flag-off state ("insights"). */
  flag?: string;
}

/** T21f: a name the viewer may count but not open (Lock 11 ink-4; no link, no button). */
export function LockedName({ name }: { name: string }): JSX.Element {
  return (
    <span data-locked-name="" className="inline-flex items-center gap-[4px] text-ink-2">
      <Icon name="lock" size={12} label="Locked" className="text-ink-4" />
      {name}
    </span>
  );
}

function Pulse({ h }: { h: number }): JSX.Element {
  return (
    <div aria-hidden className="animate-pulse rounded-[8px] bg-nested" style={{ height: h }} />
  );
}

export function AnalyticsLayout({
  variant,
  title,
  recordSubbar,
  scope,
  tabs,
  activeTab,
  onTab,
  audience,
  onAudience,
  milestone,
  tiles,
  cards,
  view = "ready",
  flag = "insights",
}: AnalyticsLayoutProps): JSX.Element {
  if (view === "flag-off") {
    return (
      <div data-template="T21" data-view="flag-off" className="flex min-h-0 flex-1 flex-col">
        <FlagOffState flag={flag} label="Insights" />
      </div>
    );
  }
  const loading = view === "loading";
  return (
    <div
      data-template="T21"
      data-variant={variant}
      data-view={view}
      className="flex min-h-0 flex-1 flex-col"
    >
      <div
        style={{ height: ANALYTICS_GEOMETRY.subbar }}
        className="relative flex flex-none items-center gap-[8px] px-[12px]"
      >
        {variant === "record" ? (
          (recordSubbar ?? <span className="text-[15px] font-medium text-ink">{title}</span>)
        ) : (
          <>
            <span className="text-[15px] font-medium text-ink">{title}</span>
            <span className="absolute left-1/2 -translate-x-1/2">
              <Segmented label="Home" options={[...HOME_SEGMENTS]} active="Insights" />
            </span>
          </>
        )}
        <span className="ml-auto flex gap-[6px]">
          {scope.map((c) => (
            <button
              key={c.key}
              type="button"
              data-scope={c.key}
              data-narrowed={c.narrowed ? "true" : undefined}
              onClick={c.onClick}
              className={cn(
                "inline-flex h-[29px] items-center gap-[6px] rounded-full px-[10px] text-[12.5px] shadow-e1",
                c.narrowed ? "bg-amber-tint text-amber-ink" : "bg-card text-ink-2",
              )}
            >
              {c.icon ? <Icon name={c.icon} size={14} /> : null}
              {c.label}
            </button>
          ))}
        </span>
      </div>
      <div
        style={{ height: ANALYTICS_GEOMETRY.tabs }}
        className="flex flex-none items-center justify-center gap-[10px] px-[12px]"
      >
        <Segmented
          size="small"
          label={title}
          options={[...tabs]}
          active={activeTab}
          {...(onTab ? { onChange: onTab } : {})}
        />
        {variant === "record" ? (
          <>
            <Segmented
              size="small"
              label="Audience"
              options={[...AUDIENCES]}
              active={audience ?? "Preparer"}
              {...(onAudience
                ? { onChange: (a: string) => { onAudience(a as (typeof AUDIENCES)[number]); } }
                : {})}
            />
            {milestone}
          </>
        ) : null}
      </div>
      <div
        data-kpi-row=""
        className="grid flex-none gap-[8px] px-[12px] pt-[10px]"
        style={{
          gridTemplateColumns: `repeat(${String(Math.max(tiles.length, 1))}, minmax(0, 1fr))`,
        }}
      >
        {tiles.map((t) =>
          loading ? (
            <div
              key={t.label}
              data-tile-loading=""
              className="rounded-pane bg-card px-[14px] py-[10px] shadow-e1"
              style={{ height: ANALYTICS_GEOMETRY.tile }}
            >
              <p className="text-kpi-label text-ink-3 uppercase">{t.label}</p>
              <Pulse h={28} />
            </div>
          ) : (
            <ChartKpiTile key={t.label} {...t} />
          ),
        )}
      </div>
      <div
        data-card-grid=""
        className="grid min-h-0 flex-1 auto-rows-min grid-cols-12 gap-[10px] overflow-auto p-[12px]"
      >
        {cards.map((c) => (
          <div
            key={c.key}
            style={{
              gridColumn: `span ${String(Math.min(Math.max(c.span, 1), 12))} / span ${String(Math.min(Math.max(c.span, 1), 12))}`,
            }}
          >
            {loading ? (
              <section
                aria-label={c.title}
                data-card-loading=""
                className="flex flex-col rounded-pane bg-card shadow-e1"
              >
                <header className="flex h-[44px] items-center border-b border-hair px-[14px] text-body font-medium text-ink">
                  {c.title}
                </header>
                <div className="p-[14px]">
                  <Pulse h={160} />
                </div>
                <footer className="flex h-[28px] items-center border-t border-hair px-[14px] text-meta text-ink-3">
                  {c.basis}
                </footer>
              </section>
            ) : (
              c.card
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
