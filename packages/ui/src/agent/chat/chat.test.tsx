// F-07-T02 (SPEC-652 AC-1 to AC-3; handoff T4a–f). Acceptance: "T4a to T4f frames render from props
// with Tier D geometry (list 358, chat 1008, panes 742 tall) and every meta line comes from
// formatActor."
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { type Actor, formatActor } from "../../attribution/actor";
import { WORKBENCH_GEOMETRY, WorkbenchLayout } from "../../templates/workbench-layout";
import { ChatHeader } from "./chat-header";
import { type SessionRow, SessionList, sessionMeta } from "./session-list";

afterEach(cleanup);

const hannah: Actor = { kind: "human", name: "Hannah Leclerc" };
const viaAgent: Actor = { kind: "agent_assisted", person: "Hannah Leclerc" };
const ROWS: SessionRow[] = [
  {
    id: "s1",
    title: "TY2025 season progress by office",
    owner: hannah,
    last_at: "2026-09-14T14:21:00Z",
    state: "awaiting_answer",
    needs_answer: true,
    running: false,
    locked: false,
  },
  {
    id: "s2",
    title: "Season Progress Reporter",
    owner: viaAgent,
    last_at: "2026-09-14T14:00:00Z",
    state: "running",
    needs_answer: false,
    running: true,
    locked: false,
  },
  {
    id: "s3",
    title: "Copperleaf questions",
    owner: hannah,
    last_at: "2026-09-14T13:10:00Z",
    state: "live",
    needs_answer: false,
    running: false,
    locked: true,
  },
];

describe("WorkbenchLayout (T4)", () => {
  it.each(["chat", "agent_detail"] as const)("%s draws the Tier D frame", (variant) => {
    render(<WorkbenchLayout tab="sessions" variant={variant} list={<p>list</p>} chat={<p>chat</p>} />);
    const list = document.querySelector("[data-pane='list']") as HTMLElement;
    const chat = document.querySelector("[data-pane='chat']") as HTMLElement;
    expect(list.style.width).toBe(
      `${String(variant === "chat" ? WORKBENCH_GEOMETRY.list : WORKBENCH_GEOMETRY.listAgentDetail)}px`,
    );
    expect(list.style.height).toBe("742px");
    expect(chat.style.height).toBe("742px");
    const bar = document.querySelector("[data-tabsbar]") as HTMLElement;
    expect([bar.style.height, bar.style.marginBottom]).toEqual(["60px", "-10px"]);
    const g = WORKBENCH_GEOMETRY;
    expect(g.listX + g.list + g.gap).toBe(g.chatX); // list 358 at x12, chat at x380
    expect(g.chatX + g.chat + g.listX).toBe(1400); // chat 1008 wide in the 1400 window
  });

  it("the tabs are Sessions · Agents · Connect and emit the tab", () => {
    const onTab = vi.fn();
    render(<WorkbenchLayout tab="sessions" onTab={onTab} list={null} chat={null} />);
    fireEvent.click(screen.getByRole("tab", { name: "Agents" }));
    expect(onTab).toHaveBeenCalledWith("agents");
  });

  it("restricted keeps the frame and draws no list or chat content (INV-3)", () => {
    render(
      <WorkbenchLayout
        tab="sessions"
        viewState="restricted"
        list={<p>LIST-SECRET</p>}
        chat={<p>CHAT-SECRET 224 returns</p>}
      />,
    );
    expect(document.body.textContent).not.toContain("SECRET");
    expect(document.body.textContent).not.toContain("224");
    expect(document.querySelector("[data-pane='chat']")).not.toBeNull();
  });
});

describe("SessionList", () => {
  it("every meta line comes from formatActor; none names the agent as an owner", () => {
    render(<SessionList rows={ROWS} selectedId="s1" still />);
    const metas = [...document.querySelectorAll("[data-meta]")].map((m) => m.textContent ?? "");
    expect(metas[0]).toBe(`9:21 AM · ${formatActor(hannah)}`);
    expect(metas[1]).toBe("9:00 AM · Hannah Leclerc via Agent");
    expect(metas.every((m) => !m.includes("· Accrued Agent"))).toBe(true);
    expect(sessionMeta(ROWS[0] as SessionRow)).toBe(metas[0]);
  });

  it("row 1 shows the awaiting dot, row 2 the spinner, row 3 says locked", () => {
    render(<SessionList rows={ROWS} still />);
    expect(screen.getByRole("img", { name: "Awaiting your answer" })).toBeTruthy();
    expect(document.querySelector("[data-session='s2'] [role='status'], [data-session='s2'] svg")).not.toBeNull();
    expect(document.querySelector("[data-session='s3'][data-locked='true']")?.textContent).toContain("Locked");
  });

  it("a search that matches nothing shows filtered-empty with Clear search", () => {
    const onQuery = vi.fn();
    render(<SessionList rows={ROWS} query="K-3" onQuery={onQuery} />);
    expect(screen.queryByRole("list", { name: "Sessions" })).toBeNull();
    expect(document.body.textContent).toContain("K-3");
  });

  it("selecting a row emits its id", () => {
    const onSelect = vi.fn();
    render(<SessionList rows={ROWS} onSelect={onSelect} />);
    fireEvent.click(document.querySelector("[data-session='s3']") as HTMLElement);
    expect(onSelect).toHaveBeenCalledWith("s3");
  });
});

describe("ChatHeader", () => {
  it("draws the title and the owner from formatActor and emits each intent", () => {
    const intents = { onOpenTrace: vi.fn(), onRename: vi.fn(), onDelete: vi.fn(), onCreateAgent: vi.fn() };
    render(<ChatHeader title="TY2025 season progress by office" owner={hannah} live still {...intents} />);
    expect(document.querySelector("[data-owner]")?.textContent).toBe("Hannah Leclerc");
    fireEvent.click(screen.getByRole("button", { name: "Open run trace" }));
    fireEvent.click(screen.getByRole("button", { name: "Rename session" }));
    fireEvent.click(screen.getByRole("button", { name: "Delete session" }));
    fireEvent.click(screen.getByRole("button", { name: /Create Agent…/ }));
    for (const fn of Object.values(intents)) expect(fn).toHaveBeenCalledOnce();
  });

  it("a locked session disables every action", () => {
    render(<ChatHeader title="Copperleaf questions" owner={hannah} live={false} locked />);
    for (const b of screen.getAllByRole("button")) expect((b as HTMLButtonElement).disabled).toBe(true);
  });
});
