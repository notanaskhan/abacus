// W-02-T16 (TASK-7911; docs/screens/WB-02.md; SPEC-653 AC-C1–C5, AC-A1–A5): "WB-02 a-f pass in
// Vitest with axe clean, and a citation click opens SHL-08 with the region lit." Data is the
// server's (the fixture stands in for it).
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { attachedContext, contextOptions, FIRM_WIDE, PICKED } from "../../fixtures/seed/workbench";
import { COPY } from "./copy";
import { type GroundedAnswer, WB02View, answerOf } from ".";

afterEach(cleanup);

const ANSWER: GroundedAnswer = {
  question: "Why did contributions receivable go from $0 at 1/1/2025 to $48,600 at 12/31/2025?",
  blocks: {
    version: 1,
    parts: [{ kind: "paragraph", text: "Contributions receivable moved." }],
  } as never,
  facts: {},
  cites: {},
  sources: [
    {
      id: "c1",
      n: 1,
      title: "PayGrid Contribution Detail 2025.xlsx",
      loc: "pay date 12/26/2025",
      evidenceVersionId: "ev-1",
      matchId: "m-1",
    },
    {
      id: "c2",
      n: 2,
      title: "Keystone Account Balances PY2025.xlsx",
      loc: "deposit 1/9/2026",
      evidenceVersionId: "ev-2",
      matchId: "m-2",
    },
  ],
  nothingWritten: true,
  controlLink: true,
  controlAuditId: "aud-northwind",
};

describe("WB-02 New session", () => {
  it("a: the blank session, firm-wide read-only, four suggested prompts", () => {
    render(<WB02View list={null} context={FIRM_WIDE} />);
    expect(screen.getByText(COPY.title)).toBeTruthy();
    expect(screen.getByText(COPY.firmWide)).toBeTruthy();
    expect(screen.getByText("Status report on open engagements")).toBeTruthy();
  });

  it("f: a prompt fills the composer and sends nothing; the chip stays firm-wide", () => {
    const onDraft = vi.fn();
    const onSend = vi.fn();
    render(<WB02View list={null} context={FIRM_WIDE} onDraft={onDraft} onSend={onSend} />);
    fireEvent.click(screen.getByText("Status report on open engagements"));
    expect(onDraft).toHaveBeenCalled();
    expect(onSend).not.toHaveBeenCalled();
    expect(screen.getByText(COPY.firmWide)).toBeTruthy();
  });

  it("b: the picker lists only the server's rows, never Copperleaf, with 3 selected", () => {
    render(
      <WB02View
        list={null}
        pickerOpen
        options={contextOptions("client_record")}
        picked={new Set(PICKED)}
      />,
    );
    expect(screen.getByText("Northwind Robotics 401(k) Plan")).toBeTruthy();
    expect(screen.queryByText(/Copperleaf/)).toBeNull();
    expect(screen.getByText(COPY.pickerFooter)).toBeTruthy();
    expect(screen.getByText(COPY.selected(3))).toBeTruthy();
  });

  it("c: adding draws a skeleton card per record", () => {
    render(<WB02View list={null} adding={[...PICKED]} />);
    expect(screen.getAllByLabelText(COPY.loadingCard).length).toBeGreaterThanOrEqual(3);
  });

  it("d: the cards read code's summary lines and the chips remove", () => {
    const onRemove = vi.fn();
    render(<WB02View list={null} context={attachedContext()} onRemove={onRemove} />);
    expect(screen.getByText("24 requests · 12 received · 3 files in use")).toBeTruthy();
    expect(screen.queryByText(COPY.firmWide)).toBeNull();
    fireEvent.click(screen.getByLabelText(COPY.remove("PBC · 12 of 24")));
    expect(onRemove).toHaveBeenCalled();
  });

  it("e: the answer's sources open SHL-08; Internal Control opens AUD-09; the code line", () => {
    const onOpenSource = vi.fn();
    const onOpenControl = vi.fn();
    render(
      <WB02View
        list={null}
        context={attachedContext()}
        answer={ANSWER}
        onOpenSource={onOpenSource}
        onOpenControl={onOpenControl}
      />,
    );
    fireEvent.click(screen.getByText(/\[1\] PayGrid Contribution Detail 2025\.xlsx/));
    expect(onOpenSource).toHaveBeenCalledWith(expect.objectContaining({ matchId: "m-1" }));
    fireEvent.click(screen.getByText(COPY.controlLink));
    expect(onOpenControl).toHaveBeenCalledWith("aud-northwind");
    expect(screen.getByText(COPY.readOnlyLine)).toBeTruthy();
  });

  it("answerOf reads the code line from the turn's notice", () => {
    const items = [
      {
        id: "1",
        seq: 1,
        kind: "user_message",
        actor_kind: "human",
        created_at: "",
        payload: { body: "Q?" },
      },
      {
        id: "2",
        seq: 2,
        kind: "agent_blocks",
        actor_kind: "agent",
        created_at: "",
        payload: { blocks: { version: 1, parts: [] } },
      },
      {
        id: "3",
        seq: 3,
        kind: "notice",
        actor_kind: "system",
        created_at: "",
        payload: { code: "nothing_written" },
      },
    ] as never;
    const a = answerOf(items);
    expect(a?.question).toBe("Q?");
    expect(a?.nothingWritten).toBe(true);
    expect(a?.controlLink).toBe(false);
  });

  it("answerOf takes the Internal Control link's audit from the blocks' entity_ref", () => {
    const parts = [
      { kind: "p", segments: [{ kind: "text", text: "Contributions tie." }] },
      { kind: "entity_ref", record_type: "audit", record_id: "aud-1" },
    ];
    const items = [
      { id: "1", seq: 1, kind: "user_message", actor_kind: "human", created_at: "", payload: {} },
      {
        id: "2",
        seq: 2,
        kind: "agent_blocks",
        actor_kind: "agent",
        created_at: "",
        payload: { blocks: { version: 1, parts } },
      },
    ] as never;
    const a = answerOf(items);
    expect(a?.controlLink).toBe(true);
    expect(a?.controlAuditId).toBe("aud-1");
  });
});
