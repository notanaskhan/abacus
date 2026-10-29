import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { installDomShims } from "../test-dom";
import { PhaseRow, RecordRail } from "./rail";
import {
  CLOSE_FLOW,
  KvRowView,
  OverviewCard,
  RecordStatePill,
  StatRow,
  StatusDropdownPill,
  recordTone,
} from "./record-kit";
import { type Phase, ROW_MENU, type RailSection } from "./types";

// F-05-T40: the C-03 Rail kit and the C-04 Record kit. "Sub-lines plus discs, never colour alone":
// every phase row names its state in words beside a disc; Begin… is optimistic; collapsed groups
// leave the tab order; ↑↓ walk the visible rows; the record card's state reads in words.

beforeAll(installDomShims);
afterEach(cleanup);

const PLANNING: Phase[] = [
  { id: "tb", title: "Trial Balance", disc: "prepared", pill: { kind: "ready", text: "Ready" } },
  {
    id: "mat",
    title: "Materiality",
    disc: "warn",
    live: { text: "Blocked on a partner decision", tone: "amber" },
  },
  { id: "risk", title: "Risk Assessment", begin: true },
  { id: "ic", title: "Internal Control", disc: "fail", live: { text: "Failed — see run" } },
  { id: "soc", title: "Service Organizations & SOC 1", disc: "run", live: { text: "Running" } },
];

const SECTIONS: RailSection[] = [
  { id: "activity", title: "Activity", nav: true },
  { id: "planning", title: "Planning", phases: PLANNING },
  {
    id: "testing",
    title: "Testing",
    collapsed: true,
    phases: [{ id: "t1", title: "Substantive Testing" }],
  },
];

function rowOf(title: string): HTMLElement {
  const row = screen.getByText(title).closest<HTMLElement>("[data-rail-row]");
  if (row === null) throw new Error(`no row for ${title}`);
  return row;
}

describe("C-03 RecordRail", () => {
  it("names every phase's state in words beside a disc, never colour alone", () => {
    render(<RecordRail sections={SECTIONS} />);
    const words: Record<string, string> = {
      "Trial Balance": "Ready",
      Materiality: "Blocked on a partner decision",
      "Internal Control": "Failed — see run",
      "Service Organizations & SOC 1": "Running",
    };
    for (const [title, word] of Object.entries(words)) {
      const row = rowOf(title);
      expect(within(row).getByRole("img").getAttribute("aria-label")).toBeTruthy();
      expect(within(row).getByText(word)).toBeTruthy();
    }
    // The to-do phase still has its disc, named.
    expect(within(rowOf("Risk Assessment")).getByRole("img", { name: "To do" })).toBeTruthy();
  });

  it("draws a failed title in red ink and a line that wants a person in amber ink", () => {
    render(<RecordRail sections={SECTIONS} />);
    expect(screen.getByText("Internal Control").className).toContain("text-red-ink");
    expect(screen.getByText("Blocked on a partner decision").className).toContain(
      "text-amber-ink",
    );
    expect(screen.getByText("Trial Balance").className).not.toContain("text-red-ink");
  });

  it("is 330 wide with the Overview header, and marks the selected row", () => {
    const { container } = render(
      <RecordRail
        card={{ kind: "audit", title: "Plan", sub: "PY2025", state: "Planning" }}
        sections={SECTIONS}
        selected="tb"
      />,
    );
    const pane = container.querySelector<HTMLElement>('[data-shell="pane"]');
    expect(pane?.style.width).toBe("330px");
    expect(screen.getByRole("heading", { name: "Overview" })).toBeTruthy();
    const tb = within(rowOf("Trial Balance")).getAllByRole("button")[0];
    expect(tb?.getAttribute("aria-current")).toBe("true");
    expect(screen.getByText("Trial Balance").className).toContain("font-medium");
    expect(screen.getByText("Materiality").className).not.toContain("font-medium");
  });

  it("Begin… shows Running at once and calls onBegin; the data then takes over", () => {
    const onBegin = vi.fn();
    const { rerender } = render(<RecordRail sections={SECTIONS} onBegin={onBegin} />);
    fireEvent.click(screen.getByRole("button", { name: "Begin…" }));
    expect(onBegin).toHaveBeenCalledWith(expect.objectContaining({ id: "risk" }));
    const row = rowOf("Risk Assessment");
    expect(row.getAttribute("data-disc")).toBe("run");
    expect(within(row).getByText("Running")).toBeTruthy();
    expect(within(row).queryByRole("button", { name: "Begin…" })).toBeNull();
    // The run reports the phase in progress: the rail follows the data.
    const moved = SECTIONS.map((s) =>
      s.id !== "planning"
        ? s
        : {
            ...s,
            phases: PLANNING.map((p) =>
              p.id === "risk"
                ? {
                    ...p,
                    disc: "half" as const,
                    pill: { kind: "progress" as const, text: "In progress" },
                  }
                : p,
            ),
          },
    );
    rerender(<RecordRail sections={moved} onBegin={onBegin} />);
    expect(rowOf("Risk Assessment").getAttribute("data-disc")).toBe("half");
    expect(within(rowOf("Risk Assessment")).getByText("In progress")).toBeTruthy();
  });

  it("collapses a band: aria-expanded, the group inert, and onToggle", () => {
    const onToggle = vi.fn();
    render(<RecordRail sections={SECTIONS} onToggle={onToggle} />);
    const testing = screen.getByRole("button", { name: "Testing" });
    expect(testing.getAttribute("aria-expanded")).toBe("false");
    const group = document.getElementById(testing.getAttribute("aria-controls") ?? "");
    expect(group?.hasAttribute("inert")).toBe(true);
    fireEvent.click(testing);
    expect(onToggle).toHaveBeenCalledWith("Testing", true);
    expect(testing.getAttribute("aria-expanded")).toBe("true");
    expect(group?.hasAttribute("inert")).toBe(false);
    // A navigating band has no expanded state and calls onNavigate.
    const onNavigate = vi.fn();
    cleanup();
    render(<RecordRail sections={SECTIONS} onNavigate={onNavigate} />);
    const activity = screen.getByRole("button", { name: "Activity" });
    expect(activity.hasAttribute("aria-expanded")).toBe(false);
    fireEvent.click(activity);
    expect(onNavigate).toHaveBeenCalledWith("Activity");
  });

  it("linksTitle puts the links under a collapsing band; tight draws two-line rows at 44", () => {
    const onToggle = vi.fn();
    const links = [
      { id: "client", icon: "user-round" as const, title: "Client", sub: "Northwind" },
    ];
    render(
      <RecordRail
        links={links}
        linksTitle="Overview"
        tight
        sections={SECTIONS}
        onToggle={onToggle}
      />,
    );
    const band = screen.getByRole("button", { name: "Overview" });
    expect(band.getAttribute("aria-expanded")).toBe("true");
    const group = document.getElementById(band.getAttribute("aria-controls") ?? "");
    expect(group?.contains(rowOf("Client"))).toBe(true);
    expect(rowOf("Client").className).toContain("py-[5px]");
    expect(rowOf("Trial Balance").className).toContain("py-[5px]");
    fireEvent.click(band);
    expect(onToggle).toHaveBeenCalledWith("Overview", false);
    expect(group?.hasAttribute("inert")).toBe(true);
    // Without either: no band over the links, and the 48 rows.
    cleanup();
    render(<RecordRail links={links} sections={SECTIONS} />);
    expect(screen.queryByRole("button", { name: "Overview" })).toBeNull();
    expect(rowOf("Client").className).toContain("py-[7px]");
    expect(rowOf("Trial Balance").className).toContain("py-[7px]");
  });

  it("moves focus with ↑ and ↓ across visible rows and bands, skipping a collapsed group", () => {
    render(
      <RecordRail
        links={[{ id: "client", icon: "user-round", title: "Client", sub: "Northwind" }]}
        sections={SECTIONS}
      />,
    );
    const client = screen.getByRole("button", { name: /Client/ });
    client.focus();
    fireEvent.keyDown(client, { key: "ArrowDown" });
    expect(document.activeElement?.textContent).toBe("Activity");
    fireEvent.keyDown(document.activeElement as Element, { key: "ArrowDown" });
    expect(document.activeElement?.textContent).toBe("Planning");
    fireEvent.keyDown(document.activeElement as Element, { key: "ArrowUp" });
    expect(document.activeElement?.textContent).toBe("Activity");
    // From the last visible phase, ↓ reaches the Testing band, not the collapsed row under it.
    const soc = within(rowOf("Service Organizations & SOC 1")).getAllByRole("button")[0];
    soc?.focus();
    fireEvent.keyDown(soc as Element, { key: "ArrowDown" });
    expect(document.activeElement?.textContent).toBe("Testing");
    fireEvent.keyDown(document.activeElement as Element, { key: "ArrowDown" });
    expect(document.activeElement?.textContent).toBe("Testing");
  });

  it("opens a row on click and offers the four row actions in its ··· menu", () => {
    const onOpen = vi.fn();
    const onMenu = vi.fn();
    render(
      <PhaseRow
        phase={PLANNING[0] as Phase}
        onOpen={onOpen}
        onMenu={onMenu}
        menuForceState="open"
      />,
    );
    fireEvent.click(screen.getByText("Trial Balance"));
    expect(onOpen).toHaveBeenCalledWith(expect.objectContaining({ id: "tb" }));
    const items = screen.getAllByRole("menuitem").map((el) => el.textContent);
    expect(items).toEqual([...ROW_MENU]);
    for (const dialog of ["Assign…", "Skip phase…"]) {
      expect(screen.getByRole("menuitem", { name: dialog }).getAttribute("aria-haspopup")).toBe(
        "dialog",
      );
    }
    expect(screen.getByRole("button", { name: "More for Trial Balance" })).toBeTruthy();
  });

  it("indents versions to 30 and uses 13px titles in the outline variant", () => {
    render(
      <RecordRail
        variant="outline"
        sections={[
          {
            id: "f",
            title: "Fieldwork",
            phases: [
              {
                id: "pr",
                title: "Plan Review",
                disc: "done",
                children: [{ id: "v2", title: "Version 2", disc: "done" }],
              },
            ],
          },
        ]}
      />,
    );
    expect(screen.getByRole("heading", { name: "Audit program" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Fieldwork" }).className).toContain("uppercase");
    expect(screen.queryByRole("button", { name: "Fieldwork" })).toBeNull();
    expect(rowOf("Version 2").className).toContain("pl-[30px]");
    expect(screen.getByText("Plan Review").className).toContain("text-body");
  });
});

describe("C-04 Record kit", () => {
  it("tones a state by A7 and always says it in words", () => {
    expect(recordTone("Processing")).toBe("amber");
    expect(recordTone("Filed")).toBe("done");
    expect(recordTone("Ready")).toBe("ready");
    expect(recordTone("Rejected")).toBe("issue");
    expect(recordTone("Not started")).toBe("neutral");
    expect(recordTone("Waiting on inputs")).toBe("muted");
    render(<RecordStatePill state="Filed" />);
    const pill = screen.getByText("Filed");
    expect(pill.getAttribute("data-tone")).toBe("done");
    expect(pill.querySelector("svg")).not.toBeNull(); // the check
  });

  it("draws the overview card recessed and centred with its tile, title, sub and state", () => {
    const { container } = render(
      <OverviewCard
        kind="audit"
        title="Northwind Robotics 401(k) Plan"
        sub="PY2025"
        state="Planning"
      />,
    );
    const card = container.querySelector('[data-record="overview-card"]');
    expect(card?.className).toContain("inset-shadow-hair");
    expect(card?.className).toContain("items-center");
    expect(card?.className).not.toMatch(/\bshadow-e/);
    expect(screen.getByText("Planning").getAttribute("data-tone")).toBe("amber");
  });

  it("offers only the allowed close transitions and reports next and previous", () => {
    const onStatus = vi.fn();
    render(<StatusDropdownPill status="In review" onStatus={onStatus} forceState="open" />);
    const items = screen.getAllByRole("menuitem").map((el) => el.textContent);
    expect(items).toEqual([...(CLOSE_FLOW["In review"] ?? [])]);
    expect(items).not.toContain("Not started");
  });

  it("a person picker reports a different person only", async () => {
    const onAssign = vi.fn();
    render(
      <KvRowView
        row={{ id: "p", label: "Preparer", value: "Raj Malhotra", kind: "person", signed: true }}
        people={["Raj Malhotra", "Priya Raman"]}
        onAssign={onAssign}
      />,
    );
    expect(screen.getByRole("img", { name: "Done" })).toBeTruthy();
    const trigger = screen.getByRole("button", { name: "Preparer: Raj Malhotra" });
    await act(async () => {
      fireEvent.pointerDown(trigger, { button: 0, ctrlKey: false });
      await Promise.resolve();
    });
    fireEvent.click(await screen.findByRole("menuitemradio", { name: "Raj Malhotra" }));
    expect(onAssign).not.toHaveBeenCalled();
    await act(async () => {
      fireEvent.pointerDown(trigger, { button: 0, ctrlKey: false });
      await Promise.resolve();
    });
    fireEvent.click(await screen.findByRole("menuitemradio", { name: "Priya Raman" }));
    expect(onAssign).toHaveBeenCalledWith(expect.objectContaining({ id: "p" }), "Priya Raman");
  });

  it("a stat caption that is overdue reads red ink; the value stays at 15px", () => {
    render(
      <StatRow stat={{ id: "d", value: "4 days", caption: "Past Due (Sep 10)", overdue: true }} />,
    );
    expect(screen.getByText("Past Due (Sep 10)").className).toContain("text-red-ink");
    expect(screen.getByText("4 days").className).toContain("text-title");
  });
});
