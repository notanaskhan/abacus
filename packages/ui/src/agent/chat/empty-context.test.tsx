// F-07-T07 (TASK-7509; handoff T4a, T4f, TPL-04b). Acceptance: "T4a, T4f and TPL-04b render from
// props, a suggested prompt fills the composer without sending, and the picker shows only items L3
// passes in."
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { WorkbenchLayout } from "../../templates/workbench-layout";
import { AgentDetail } from "./agent-detail";
import { ContextPicker } from "./context-picker";
import {
  ContextChips,
  type ContextItem,
  EMPTY_SESSION_COPY,
  EmptySession,
  type SuggestedPrompt,
} from "./empty-session";
import { ChatThread } from "./thread";

afterEach(cleanup);

// T4a's four cards, verbatim.
const PROMPTS: SuggestedPrompt[] = [
  {
    id: "p1",
    title: "Which TY2025 returns are still in review?",
    detail: "Grouped by reviewer, oldest first",
  },
  {
    id: "p2",
    title: "What’s still missing from Northwind’s PBC list?",
    detail: "Open requests by owner",
  },
  {
    id: "p3",
    title: "Summarize the Copperleaf August close",
    detail: "Progress, open issues and what’s late",
  },
  {
    id: "p4",
    title: "Which notices need a response this week?",
    detail: "Response dates across all clients",
  },
];

function NewSession({ onSend }: { onSend: (body: string) => void }) {
  const [draft, setDraft] = useState<{ text: string; nonce: number } | null>(null);
  return (
    <ChatThread
      items={[]}
      draft={draft}
      onSend={onSend}
      empty={
        <EmptySession
          prompts={PROMPTS}
          onPick={(text) => setDraft((d) => ({ text, nonce: (d?.nonce ?? 0) + 1 }))}
        />
      }
      above={<ContextChips attached={[]} onAdd={vi.fn()} />}
    />
  );
}

describe("EmptySession (T4a, TPL-04b)", () => {
  it("renders the copy and the 2 × 2 prompts from props", () => {
    render(<EmptySession prompts={PROMPTS} onPick={vi.fn()} />);
    expect(screen.getByRole("heading", { name: "New session" })).toBeTruthy();
    expect(screen.getByText(EMPTY_SESSION_COPY.body)).toBeTruthy();
    expect(screen.getAllByRole("listitem")).toHaveLength(4);
    expect(screen.getByText("Grouped by reviewer, oldest first")).toBeTruthy();
  });

  it("a suggested prompt fills the composer without sending", () => {
    const onSend = vi.fn();
    render(<NewSession onSend={onSend} />);
    fireEvent.click(screen.getByText("Summarize the Copperleaf August close"));
    const composer = screen.getByRole("textbox", { name: "Message" }) as HTMLTextAreaElement;
    expect(composer.value).toBe("Summarize the Copperleaf August close");
    expect(onSend).not.toHaveBeenCalled();
    fireEvent.keyDown(composer, { key: "Enter" });
    expect(onSend).toHaveBeenCalledWith("Summarize the Copperleaf August close");
  });

  it("shows the three context chips above the composer", () => {
    const onAdd = vi.fn();
    render(<ContextChips attached={[]} onAdd={onAdd} />);
    for (const label of ["Client record", "Documents", "Workpapers"]) {
      expect(screen.getByRole("button", { name: label })).toBeTruthy();
    }
    fireEvent.click(screen.getByRole("button", { name: "Documents" }));
    expect(onAdd).toHaveBeenCalledWith("documents");
  });
});

describe("ContextPicker (O1 380)", () => {
  const FELD: ContextItem = {
    id: "c1",
    kind: "client_record",
    label: "Jonah & Claire Feld",
    detail: "Household · Brooklyn, NY",
  };
  const W2: ContextItem = {
    id: "d1",
    kind: "documents",
    label: "Claire_Feld_2025_W2_MercerHill.pdf",
  };

  it("lists only the items L3 passes in, with attached and loading states", () => {
    const onAttach = vi.fn();
    const onDetach = vi.fn();
    render(
      <ContextPicker
        trigger={<button type="button">Context</button>}
        forceState="open"
        items={{ client_record: [FELD], documents: [W2] }}
        attached={new Set(["d1"])}
        loading={new Set(["workpapers"])}
        onAttach={onAttach}
        onDetach={onDetach}
      />,
    );
    const rows = screen.getAllByRole("menuitemcheckbox");
    expect(rows.map((r) => r.getAttribute("data-item"))).toEqual(["c1", "d1"]);
    expect(rows[1]?.getAttribute("aria-checked")).toBe("true");
    expect(screen.getByText("Loading…")).toBeTruthy();
    fireEvent.click(rows[0]!);
    expect(onAttach).toHaveBeenCalledWith(FELD);
    fireEvent.click(rows[1]!);
    expect(onDetach).toHaveBeenCalledWith(W2);
  });

  it("opens on one kind from its chip", () => {
    render(
      <ContextPicker
        trigger={<button type="button">Context</button>}
        forceState="open"
        kind="documents"
        items={{ client_record: [FELD], documents: [W2] }}
        attached={new Set()}
        onAttach={vi.fn()}
        onDetach={vi.fn()}
      />,
    );
    expect(screen.queryByText("Jonah & Claire Feld")).toBeNull();
    expect(screen.getByText("Claire_Feld_2025_W2_MercerHill.pdf")).toBeTruthy();
  });
});

describe("AgentDetail (T4f, WB-06)", () => {
  function T4f() {
    return (
      <WorkbenchLayout
        tab="agents"
        variant="agent_detail"
        list={<div />}
        chat={
          <AgentDetail
            name="SOC 1 Coverage Check"
            provenance="Published by Accrued"
            icon="panels-top-left"
            purpose="Check that each service organization’s SOC 1 report and bridge letter cover the full plan year."
            meta="Audit · Installed Aug 3 by Grace Holloway"
            facts={[
              {
                label: "Schedule",
                value: "Weekdays at 9:00 AM, on audits in Planning or Fieldwork",
              },
              {
                label: "Reads",
                value: "SOC 1 reports, bridge letters and the Service Organizations workpaper",
              },
              {
                label: "Changes",
                value: "Raises an issue only after a manager answers. It never edits a workpaper",
              },
              { label: "Asks", value: "The engagement manager, when coverage has a gap" },
            ]}
            runs={[
              {
                id: "r1",
                title: "Northwind Robotics 401(k) Plan",
                meta: "Today 9:00 AM · Waiting on Hannah Leclerc",
                state: "waiting",
              },
              {
                id: "r2",
                title: "Northwind Robotics 401(k) Plan",
                meta: "Sep 11 · Paycrest bridge letter still outstanding",
                state: "done",
              },
            ]}
            onRun={vi.fn()}
          />
        }
      />
    );
  }

  it("renders the frame from props in the 320 variant", () => {
    const { container } = render(<T4f />);
    expect(container.querySelector('[data-variant="agent_detail"]')).not.toBeNull();
    expect(screen.getByText("Published by Accrued")).toBeTruthy();
    expect(screen.getByText("Recent runs")).toBeTruthy();
    expect(container.querySelectorAll("[data-run]")).toHaveLength(2);
    expect(screen.getByRole("button", { name: "Run" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Archive agent" })).toBeTruthy();
  });

  it("renders no human-only verb on the agent's controls", () => {
    render(<T4f />);
    for (const verb of ["Approve", "Sign off", "Release", "Send", "Post", "Decide"]) {
      expect(screen.queryByRole("button", { name: new RegExp(`^${verb}`, "i") })).toBeNull();
    }
  });
});
