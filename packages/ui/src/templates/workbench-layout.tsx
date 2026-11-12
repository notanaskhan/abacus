// T4 · Workbench chat frame (F-07-T02; handoff T4; SPEC-652 AC-1). Toolbar 46 is the shell's; this
// draws the tabsbar 60 with a −10 bottom margin (centred Segmented Sessions · Agents · Connect) and
// the two panes at y106–848 (742 tall): the session list 358 wide at x12 and the chat flex (1008 at
// 1440 × 900) at x380. The T4f variant (WB-06) narrows the list to 320. Data comes through props;
// the template never fetches. A restricted or switched-off view keeps the frame and shows no data.
import type { JSX, ReactNode } from "react";
import { cn } from "../cn";
import { Segmented } from "../components/tabs";
import type { ReadOnlyReason } from "../components/view-state";
import { RestrictedState } from "../components/view-state";

export type WorkbenchTab = "sessions" | "agents" | "connect";
export const WORKBENCH_TABS: readonly { key: WorkbenchTab; label: string }[] = [
  { key: "sessions", label: "Sessions" },
  { key: "agents", label: "Agents" },
  { key: "connect", label: "Connect" },
];
/** Tier D geometry at 1440 × 900 (handoff T4). */
export const WORKBENCH_GEOMETRY = {
  tabsbar: 60,
  tabsbarMargin: -10,
  panesTop: 106,
  panesHeight: 742,
  list: 358,
  listAgentDetail: 320,
  listX: 12,
  chatX: 380,
  chat: 1008,
  gap: 10,
} as const;

export interface WorkbenchLayoutProps {
  tab: WorkbenchTab;
  list: ReactNode;
  chat: ReactNode;
  variant?: "chat" | "agent_detail";
  /** `restricted` and `flag-off` keep the frame and draw no list or chat content. */
  viewState?: "ready" | "restricted" | "flag-off";
  restrictedReason?: ReadOnlyReason;
  onTab?: (tab: WorkbenchTab) => void;
  className?: string;
}

export function WorkbenchLayout({
  tab,
  list,
  chat,
  variant = "chat",
  viewState = "ready",
  restrictedReason = "walled",
  onTab,
  className,
}: WorkbenchLayoutProps): JSX.Element {
  const g = WORKBENCH_GEOMETRY;
  const listWidth = variant === "agent_detail" ? g.listAgentDetail : g.list;
  const active = WORKBENCH_TABS.find((t) => t.key === tab)?.label ?? "Sessions";
  const closed = viewState !== "ready";
  return (
    <div
      data-template="T4"
      data-variant={variant}
      data-view-state={viewState}
      className={cn("flex min-h-0 flex-1 flex-col bg-shell", className)}
    >
      <div
        data-tabsbar
        style={{ height: g.tabsbar, marginBottom: g.tabsbarMargin }}
        className="flex items-center justify-center"
      >
        <Segmented
          label="Workbench"
          options={WORKBENCH_TABS.map((t) => t.label)}
          active={active}
          onChange={(label) => {
            const next = WORKBENCH_TABS.find((t) => t.label === label);
            if (next) onTab?.(next.key);
          }}
        />
      </div>
      <div
        data-panes
        style={{ padding: "10px 12px 12px", gap: g.gap, height: g.panesHeight + 22 }}
        className="flex"
      >
        <section
          aria-label={variant === "agent_detail" ? "Agents" : "Sessions"}
          data-pane="list"
          style={{ width: listWidth, height: g.panesHeight }}
          className="flex shrink-0 flex-col overflow-hidden rounded-[12px] bg-card shadow-e1"
        >
          {closed ? null : list}
        </section>
        <section
          aria-label={variant === "agent_detail" ? "Agent" : "Chat"}
          data-pane="chat"
          style={{ height: g.panesHeight }}
          className="flex min-w-0 flex-1 flex-col overflow-hidden rounded-[12px] bg-card shadow-e1"
        >
          {viewState === "restricted" ? (
            <RestrictedState reason={restrictedReason} />
          ) : viewState === "flag-off" ? (
            <RestrictedState reason="flag_off" />
          ) : (
            chat
          )}
        </section>
      </div>
    </div>
  );
}
