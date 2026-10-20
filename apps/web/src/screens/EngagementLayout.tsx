import { AiExclusionControl } from "./AiClientData";
import {
  agentOptions,
  aiExclusionOptions,
  engagementGraphOptions,
} from "@abacus/api-client/query";
import { ChevronDown, ChevronLeft, Skeleton, StatusPill, cn } from "@abacus/ui";
import { useQuery } from "@tanstack/react-query";
import { Link, Outlet } from "@tanstack/react-router";
import { type JSX, useEffect, useRef, useState } from "react";
import { Tabs } from "../shell/Tabs";
import { AgentControls } from "./AgentActivity";
import { IndependenceBanner } from "./MyConfirmations";

/** An engagement's record header and tabs (TASK-092): one compact row (back, title, client,
 * state, period, the agent control) over a segmented tab track. */
export function EngagementLayout({ engagementId }: { engagementId: string }): JSX.Element {
  const graph = useQuery(engagementGraphOptions({ path: { engagement_id: engagementId } }));
  const e = graph.data?.engagement;
  const params = { engagementId };
  return (
    <div className="flex flex-col gap-3">
      <header className="flex min-h-[42px] flex-wrap items-center gap-x-3 gap-y-2">
        <Link
          to="/"
          className="flex h-[29px] items-center gap-1 rounded-[7px] bg-card pr-3 pl-2 text-[13px] text-ink-2 shadow-e1 hover:bg-nav-fill hover:text-ink hover:no-underline"
        >
          <ChevronLeft aria-hidden="true" className="size-3.5" />
          Engagements
        </Link>
        {e === undefined ? (
          <Skeleton className="h-[18px] w-72" />
        ) : (
          <div className="flex min-w-0 flex-wrap items-center gap-x-2.5 gap-y-1">
            <h1 className="truncate text-[15px] font-medium tracking-[-0.012em]">{e.name}</h1>
            {e.client_name !== e.name && (
              <span className="truncate text-[15px] text-ink-2">{e.client_name}</span>
            )}
            <StatusPill tone={e.status === "archived" ? "neutral" : "success"}>
              {e.status === "archived" ? "Archived" : "Active"}
            </StatusPill>
            <span className="text-[12.5px] text-ink-3 tabular-nums">
              {e.fiscal_period_start} – {e.fiscal_period_end}
            </span>
          </div>
        )}
        <span className="flex-1" />
        <AgentMenu engagementId={engagementId} />
      </header>
      <IndependenceBanner engagementId={engagementId} />
      <Tabs
        label="Engagement"
        items={[
          { label: "Overview", to: "/engagements/$engagementId", params, exact: true },
          { label: "Requests", to: "/engagements/$engagementId/requests", params },
          { label: "Review", to: "/engagements/$engagementId/review", params },
          { label: "Fieldwork", to: "/engagements/$engagementId/fieldwork", params },
          { label: "Findings", to: "/engagements/$engagementId/findings", params },
          { label: "Map", to: "/engagements/$engagementId/map", params },
          { label: "People", to: "/engagements/$engagementId/people", params },
          { label: "Activity", to: "/engagements/$engagementId/activity", params },
          { label: "Setup", to: "/engagements/$engagementId/setup", params },
        ]}
      />
      <Outlet />
    </div>
  );
}

/** One control for the engagement's agent: its state on a chip, and pause / resume and the
 * partner's "AI off for this engagement" in a popover. */
function AgentMenu({ engagementId }: { engagementId: string }): JSX.Element | null {
  const path = { path: { engagement_id: engagementId } };
  const agent = useQuery({ ...agentOptions(path), retry: false });
  const exclusion = useQuery({ ...aiExclusionOptions(path), retry: false });
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const onDown = (ev: MouseEvent): void => {
      if (box.current !== null && !box.current.contains(ev.target as Node)) setOpen(false);
    };
    const onKey = (ev: KeyboardEvent): void => {
      if (ev.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);
  const a = agent.data;
  if (a === undefined && exclusion.data === undefined) return null;
  const excluded = exclusion.data?.excluded === true;
  const paused = a !== undefined && (a.paused_at != null || a.firm_paused_at != null);
  const on = a?.enabled === true && !paused && !excluded;
  const label = excluded
    ? "AI off"
    : a === undefined || !a.enabled
      ? "Agent off"
      : paused
        ? "Agent paused"
        : "Agent on";
  return (
    <div ref={box} className="relative">
      <button
        type="button"
        aria-expanded={open}
        aria-haspopup="dialog"
        onClick={() => {
          setOpen((o) => !o);
        }}
        className="flex h-[29px] items-center gap-1.5 rounded-[7px] bg-card pr-2.5 pl-3 text-[13px] shadow-e1 hover:bg-nav-fill"
      >
        <span
          aria-hidden="true"
          className={cn(
            "size-1.5 rounded-full",
            on ? "bg-green" : excluded ? "bg-red" : "bg-amber",
          )}
        />
        {label}
        <ChevronDown aria-hidden="true" className="size-3 text-ink-3" />
      </button>
      {open && (
        <div
          role="dialog"
          aria-label="Agent"
          className="absolute top-[calc(100%+8px)] right-0 z-20 flex w-[380px] flex-col gap-3 rounded-pane bg-card p-3.5 shadow-pop"
        >
          <AgentControls engagementId={engagementId} />
          <AiExclusionControl engagementId={engagementId} />
          <p className="text-[11.5px] leading-[1.45] text-ink-3">
            The agent proposes; your team decides. Pausing stops its scheduled work on this
            engagement.
          </p>
        </div>
      )}
    </div>
  );
}
