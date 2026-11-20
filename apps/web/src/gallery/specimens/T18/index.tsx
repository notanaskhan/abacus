// T18 Sheet, the template board (F-08-T08 carry; TASK-8843; docs/screens/T18.md; handoff T18 a–i):
// SheetLayout on the handoff's placeholder content only ("Key · Name · Status · Notes", bands
// SECTION A (2) and SECTION B (1)), registered for /components/screens/T18?st=a…i so the parity
// and axe suite (e2e/specimens/f08-t18.spec.ts) can reach every state. The kit computes nothing.
//   a default · b cockpit with the 330 dock (scrolls sideways, select and Key frozen)
//   c filtered (Filter · 2, filter row, Clear) · d the agent column's menu · e agent column running
//   f the O2 480 row drawer · g locked rows · h empty · i loading
import {
  SheetLayout,
  type SheetGridColumn,
  type SheetGridRow,
  type SheetLayoutProps,
  type SheetSection,
} from "@abacus/ui";
import { type JSX, useState } from "react";
import type { FixtureParams } from "../../fixture-mode";

export const T18_STATES = ["a", "b", "c", "d", "e", "f", "g", "h", "i"] as const;
export type T18State = (typeof T18_STATES)[number];

const COLUMNS: SheetGridColumn[] = [
  { key: "key", type: "text", label: "Key", width: 96, frozen: true },
  { key: "name", type: "text", label: "Name", width: 220 },
  { key: "status", type: "single_select", label: "Status", width: 120 },
  { key: "notes", type: "agent", label: "Notes", width: 220, agent: { name: "Notes" } },
];
const SECTIONS: SheetSection[] = [
  { key: "a", title: "Section A", count: 2 },
  { key: "b", title: "Section B", count: 1 },
];

function rows(locked: boolean): SheetGridRow[] {
  const r = (key: string, sectionKey: string): SheetGridRow => ({
    key,
    sectionKey,
    locked: locked && sectionKey === "a",
    cells: {
      key: { value: key, state: "human" },
      name: { value: "—", state: "human" },
      status: { value: "—", state: "human" },
      notes: { value: "—", state: "suggested" },
    },
  });
  return [r("A-1", "a"), r("A-2", "a"), r("B-1", "b")];
}

function boardProps(state: T18State, onSignOff: (key: string) => void): SheetLayoutProps {
  const base: SheetLayoutProps = {
    variant: state === "b" ? "cockpit" : "full",
    view: state === "h" ? "empty" : state === "i" ? "loading" : "ready",
    toolbar: {
      view: "Default view",
      filters: state === "c" ? 2 : 0,
      search: "",
      onSearch: () => undefined,
      ...(state === "c" ? { onClearFilters: () => undefined } : {}),
    },
    grid: {
      label: "Sheet",
      columns: COLUMNS,
      sections: SECTIONS,
      rows: rows(state === "g"),
      status: {
        rows: 3,
        exceptions: 0,
        view: "Default",
        ...(state === "e" ? { agentRunning: true } : {}),
      },
      viewer: { kind: "human", name: "Ana Cruz" },
      ...(state === "c" ? { filterRow: true } : {}),
    },
    onOpenSignOff: (target) => onSignOff(String(target)),
    ...(state === "b" ? { dock: <aside aria-label="Dock" className="h-full w-[330px]" /> } : {}),
    ...(state === "h" ? { onAddRow: () => undefined } : {}),
  };
  if (state === "f") {
    return {
      ...base,
      drawer: {
        rowKey: "A-1",
        title: "A-1",
        tab: "Details",
        onTab: () => undefined,
        onClose: () => undefined,
        slots: {},
      },
    };
  }
  return base;
}

export function T18Artboard({ params }: { params: FixtureParams }): JSX.Element {
  const state: T18State = T18_STATES.find((s) => s === params.st) ?? "a";
  const [signOff, setSignOff] = useState<string | null>(null);
  return (
    <div
      data-artboard={state}
      data-template="T18"
      {...(signOff === null ? {} : { "data-opened-sign-off": signOff })}
    >
      <div className="relative h-[860px] w-[1400px] bg-shell">
        <SheetLayout {...boardProps(state, setSignOff)} />
      </div>
    </div>
  );
}
