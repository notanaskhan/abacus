import type { AuditCockpitOut } from "@abacus/api-client";
import { type CockpitDock, type DockView, EmptyState } from "@abacus/ui";
import type { ReactNode } from "react";
import { AUDIT_MESSAGES } from "./messages";

// The cockpit's dock host (A-01-T06; AUD-02, AUD-03; DV-2): the tabs the projection offers (Agent,
// Viewer), each holding what its owner mounts. The Agent tab is the v1 engagement-agent activity,
// read-only, until P-09 mounts `AgentDockHost` here; when the data boundary refuses AI for the firm
// it reads DF-04's "AI isn't available for real client data yet". The Viewer tab holds SHL-08
// (P-03). Notes stays hidden until A-06.

type DockTab = NonNullable<AuditCockpitOut["dock_tabs"]>[number];

const VIEW: Record<DockTab, DockView> = { agent: "Agent", viewer: "Viewer" };

export interface DockHostOptions {
  /** The open tab (`?dock=`); the first offered tab when absent or not offered. */
  tab?: DockTab;
  onTab?: (tab: DockTab) => void;
  /** What the Agent tab holds: the activity list (v1) or P-09's run pane. */
  agent?: ReactNode;
  /** What the Viewer tab holds: SHL-08 on the selected document. */
  viewer?: ReactNode;
  /** The data boundary refuses AI for this firm (DF-04): the Agent tab says so. */
  aiUnavailable?: boolean;
  /** A C6 engagement run is executing: the live dot (DV-11). */
  live?: boolean;
  /** The header's right cluster ("Pause agent" menu; P-09's "Sign off run" with its capability). */
  action?: ReactNode;
}

/** The RecordCockpit `dock` for an audit, or undefined when the projection offers no tab. */
export function dockHost(
  cockpit: Pick<AuditCockpitOut, "dock_tabs">,
  options: DockHostOptions = {},
): CockpitDock | undefined {
  const tabs = cockpit.dock_tabs ?? [];
  const first = tabs[0];
  if (first === undefined) return undefined;
  const tab = options.tab !== undefined && tabs.includes(options.tab) ? options.tab : first;
  const byView = new Map(tabs.map((t) => [VIEW[t], t]));
  const body =
    tab === "agent" ? (
      options.aiUnavailable === true ? (
        <EmptyState icon="sparkles" title={AUDIT_MESSAGES.aiUnavailable} />
      ) : (
        options.agent
      )
    ) : (
      options.viewer
    );
  return {
    view: VIEW[tab],
    views: tabs.map((t) => VIEW[t]),
    onView: (view) => {
      const picked = byView.get(view);
      if (picked !== undefined) options.onTab?.(picked);
    },
    ...(options.live === true ? { live: true } : {}),
    ...(options.action === undefined ? {} : { action: options.action }),
    children: (
      <div data-audit-dock={tab} className="flex min-h-0 flex-1 flex-col">
        {body}
      </div>
    ),
  };
}
