// HOME-05 · Home with Today brief (I-02-T16; docs/screens/HOME-05.md; SPEC-654 §3.9). On the T11
// dashboard: the Today panel docked as a 470 pane at x12 beside HOME-01 (compressed), a Today
// toggle chip, and the collapsed state c with "Open Today ›" where HOME-01 keeps its exact
// geometry. The preference persists in guarded storage. Hovering or focusing a brief row lights
// its HOME-01 rows (two-way: a HOME-01 row lights the brief rows that name it). With
// `today_brief.enabled` off the route draws HOME-01 alone: no chip, no link, no bell entry.
import { Button, Icon } from "@abacus/ui";
import { type JSX, useEffect, useRef, useState } from "react";
import { useOpenHref } from "../../app-core/open";
import {
  readCollapsed,
  useRebuildBrief,
  useTodayBrief,
  writeCollapsed,
} from "../../domain/today";
import { HOME01 } from "../HOME-01";
import { TodayPanel } from "../SHL-23";

export const PANE_WIDTH = 470;
export const COPY = {
  today: "Today",
  openToday: "Open Today",
  collapse: "Collapse Today",
} as const;

/** Light the HOME-01 rows (`[data-gate]`) named by `refs` inside `root`; none clears them. */
export function lightRows(root: HTMLElement | null, refs: readonly string[] | null): void {
  if (root === null) return;
  for (const el of root.querySelectorAll<HTMLElement>("[data-gate]")) {
    const on = refs !== null && refs.includes(el.dataset.gate ?? "");
    if (on) el.setAttribute("data-lit", "true");
    else el.removeAttribute("data-lit");
  }
}

export interface HOME05Props {
  /** Start collapsed regardless of the stored preference (a specimen). */
  initialCollapsed?: boolean;
}

export function HOME05({ initialCollapsed }: HOME05Props): JSX.Element {
  const [collapsed, setCollapsed] = useState(initialCollapsed ?? readCollapsed());
  const brief = useTodayBrief(!collapsed);
  const rebuild = useRebuildBrief();
  const open = useOpenHref();
  const home = useRef<HTMLDivElement>(null);
  const panel = useRef<HTMLDivElement>(null);
  const [lit, setLit] = useState<readonly string[] | null>(null);
  useEffect(() => {
    lightRows(home.current, lit);
  }, [lit]);
  useEffect(() => {
    // The other way: a HOME-01 row hovered lights the brief rows that name it.
    const root = home.current;
    if (root === null) return undefined;
    const enter = (e: Event) => {
      const row = (e.target as HTMLElement | null)?.closest<HTMLElement>("[data-gate]");
      const id = row?.dataset.gate;
      for (const el of panel.current?.querySelectorAll<HTMLElement>("[data-row]") ?? []) {
        if (id !== undefined && el.dataset.row === id) el.setAttribute("data-lit", "true");
        else el.removeAttribute("data-lit");
      }
    };
    root.addEventListener("mouseover", enter);
    root.addEventListener("focusin", enter);
    return () => {
      root.removeEventListener("mouseover", enter);
      root.removeEventListener("focusin", enter);
    };
  }, [collapsed]);
  const toggle = (next: boolean) => {
    setCollapsed(next);
    writeCollapsed(next);
  };
  if (collapsed) {
    return (
      <div data-screen="HOME-05" data-state="c" className="flex min-h-0 flex-1 flex-col">
        <div className="flex h-[32px] flex-none items-center px-[12px]">
          <Button variant="ghost" size="sm" onClick={() => toggle(false)}>
            {COPY.openToday}
            <Icon name="chevron-right" size={12} />
          </Button>
        </div>
        <div ref={home} className="flex min-h-0 flex-1 flex-col">
          <HOME01 />
        </div>
      </div>
    );
  }
  return (
    <div data-screen="HOME-05" data-state="docked" className="flex min-h-0 flex-1 gap-[12px] pl-[12px]">
      <aside
        ref={panel}
        aria-label={COPY.today}
        style={{ width: PANE_WIDTH }}
        className="flex min-h-0 flex-none flex-col rounded-[12px] bg-shell shadow-e1"
      >
        <div className="flex h-[32px] flex-none items-center justify-end px-[8px]">
          <button
            type="button"
            data-chip="today"
            aria-pressed="true"
            onClick={() => toggle(true)}
            className="inline-flex h-[24px] items-center gap-[4px] rounded-pill bg-nested px-[8px] text-[12px] text-ink"
          >
            {COPY.today}
            <Icon name="chevron-left" size={12} />
          </button>
        </div>
        <TodayPanel
          vm={brief.data}
          onOpen={(href) => open(href)}
          onRebuild={() => {
            if (brief.data !== undefined) void rebuild.rebuild(brief.data.brief_date, true);
          }}
          onHighlight={setLit}
        />
      </aside>
      <div ref={home} className="flex min-h-0 min-w-0 flex-1 flex-col">
        <HOME01 />
      </div>
    </div>
  );
}

/** `?ov=today`: the panel as a left drawer x10–480 with no scrim, over any firm route. */
export function TodayDrawer({ onClose }: { onClose: () => void }): JSX.Element {
  const brief = useTodayBrief();
  const rebuild = useRebuildBrief();
  const open = useOpenHref();
  return (
    <div
      role="dialog"
      aria-label={COPY.today}
      data-drawer="today"
      className="fixed bottom-[10px] left-[10px] top-[10px] z-40 flex w-[470px] flex-col rounded-[14px] bg-shell shadow-modal"
      onKeyDown={(e) => {
        if (e.key === "Escape") onClose();
      }}
    >
      <div className="flex h-[32px] flex-none items-center justify-end px-[8px]">
        <Button variant="ghost" size="sm" icon="x" aria-label={COPY.collapse} onClick={onClose} />
      </div>
      <TodayPanel
        vm={brief.data}
        onOpen={(href) => {
          onClose();
          open(href);
        }}
        onRebuild={() => {
          if (brief.data !== undefined) void rebuild.rebuild(brief.data.brief_date, true);
        }}
      />
    </div>
  );
}
