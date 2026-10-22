import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AgentText, sanitiseAgentText } from "../agent-text";
import { HUMAN_VERBS, actorFromAudit, formatActor } from "./actor";
import {
  AgentFilledMarker,
  adoptSuggestion,
  editSuggestion,
  suggestionLines,
  type Suggestion,
} from "./agent-filled";
import { HumanAction } from "./human-action";

// F-05-T30 acceptance: "HumanAction refuses to render for an agent actor, formatActor yields
// 'X via Agent' and 'Policy: name vN', and AgentText logic is unchanged."

afterEach(cleanup);

const HANNAH = { kind: "human", name: "Hannah Leclerc" } as const;
const AGENT = { kind: "agent" } as const;

describe("formatActor", () => {
  it("names a person, a person via the agent, a policy, the agent and the system", () => {
    expect(formatActor(HANNAH)).toBe("Hannah Leclerc");
    expect(formatActor({ kind: "agent_assisted", person: "Hannah Leclerc" })).toBe(
      "Hannah Leclerc via Agent",
    );
    expect(formatActor({ kind: "policy", name: "BH AJE thresholds", version: 2 })).toBe(
      "Policy: BH AJE thresholds v2",
    );
    expect(formatActor(AGENT)).toBe("Accrued Agent");
    expect(formatActor({ kind: "system" })).toBe("System");
  });

  it("reads an audit row's actor: an agent row with a person is that person via the agent", () => {
    expect(formatActor(actorFromAudit("agent", "Samuel Ito"))).toBe("Samuel Ito via Agent");
    expect(formatActor(actorFromAudit("agent", null))).toBe("Accrued Agent");
    expect(formatActor(actorFromAudit("human", "Priya Raman"))).toBe("Priya Raman");
    expect(formatActor(actorFromAudit("system", null))).toBe("System");
  });
});

describe("HumanAction (INV-1)", () => {
  it("renders the verb for a named person", () => {
    render(<HumanAction verb="Approve" object="Document" actor={HANNAH} />);
    const button = screen.getByRole("button", { name: "Approve Document" });
    expect(button.getAttribute("data-human-verb")).toBe("Approve");
  });

  it("refuses to render for the agent, a policy or the system", () => {
    for (const verb of HUMAN_VERBS) {
      const { container, unmount } = render(
        <>
          <HumanAction verb={verb} actor={AGENT} />
          <HumanAction verb={verb} actor={{ kind: "policy", name: "Auto-post", version: 1 }} />
          <HumanAction verb={verb} actor={{ kind: "system" }} />
        </>,
      );
      expect(container.innerHTML).toBe("");
      unmount();
    }
  });

  it("a control that opens a dialog ends in an ellipsis", () => {
    render(<HumanAction verb="Sign off" actor={HANNAH} opensDialog />);
    expect(screen.getByRole("button", { name: "Sign off…" })).toBeTruthy();
  });
});

describe("AgentText", () => {
  it("keeps its sanitising logic and reads text-para ink-2, marked as the agent's", () => {
    const hostile = "Paid‮ late​\n\n\n\nok";
    render(<AgentText text={hostile} />);
    const p = screen.getByText(/Paid/);
    expect(p.textContent).toBe(sanitiseAgentText(hostile));
    expect(p.textContent).toBe("Paid late\n\nok");
    expect(p.className).toContain("text-para");
    expect(p.className).toContain("text-ink-2");
    expect(p.getAttribute("data-actor")).toBe("agent");
  });

  it("a caller's classes still win", () => {
    render(<AgentText text="Quote" inline className="text-ink" />);
    const span = screen.getByText("Quote");
    expect(span.className).toContain("text-ink");
    expect(span.className).not.toContain("text-ink-2");
  });
});

describe("AgentFilledMarker (C-31)", () => {
  const suggested: Suggestion = {
    state: "suggested",
    value: "Improperly excluded",
    cites: ["Invoice FRF-30418 · Jun 29, 2026", "Payment · Jul 22, 2026"],
  };

  it("a suggestion is ink-2, says who suggested it, and offers Adopt to a person", () => {
    const onAdopt = vi.fn();
    render(
      <AgentFilledMarker
        suggestion={suggested}
        viewer={HANNAH}
        onAdopt={onAdopt}
        exception
        open
      />,
    );
    expect(screen.getByText("Improperly excluded").parentElement?.className).toContain(
      "text-ink-2",
    );
    expect(screen.getByRole("tooltip").textContent).toContain(
      "Suggested by Accrued Agent · 2 citations · not yet adopted",
    );
    fireEvent.click(screen.getByRole("button", { name: "Adopt" }));
    expect(onAdopt).toHaveBeenCalledOnce();
    expect(screen.getByRole("img", { name: "Exception" })).toBeTruthy();
  });

  it("never offers Adopt when the viewer is not a person", () => {
    render(<AgentFilledMarker suggestion={suggested} viewer={AGENT} open />);
    expect(screen.queryByRole("button", { name: "Adopt" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Edit" })).toBeNull();
  });

  it("adopted reads ink with an olive atom and names the person", () => {
    const adopted = adoptSuggestion(suggested, HANNAH, "Oct 1");
    render(<AgentFilledMarker suggestion={adopted} viewer={HANNAH} open />);
    expect(
      screen.getByRole("img", { name: "Adopted agent value" }).getAttribute("class"),
    ).toContain("text-green");
    expect(screen.getByRole("tooltip").textContent).toContain("Adopted by Hannah Leclerc · Oct 1");
  });

  it("the agent cannot adopt or edit", () => {
    expect(() => adoptSuggestion(suggested, AGENT, "Oct 1")).toThrow(/cannot adopt/);
    expect(() => editSuggestion(suggested, "Properly excluded", AGENT, "Oct 1")).toThrow(
      /cannot edit/,
    );
  });

  it("an edit keeps the agent's value as `was`; picking it back re-adopts", () => {
    const edited = editSuggestion(suggested, "Properly excluded", HANNAH, "Oct 2");
    expect(edited).toMatchObject({
      state: "edited",
      value: "Properly excluded",
      was: "Improperly excluded",
    });
    expect(suggestionLines(edited).line).toBe(
      "Edited by Hannah Leclerc · was Improperly excluded",
    );
    const back = editSuggestion(edited, "Improperly excluded", HANNAH, "Oct 3");
    expect(back.state).toBe("adopted");
  });

  it("running, input and empty use their own words", () => {
    const { rerender } = render(
      <AgentFilledMarker
        suggestion={{ state: "running", value: "", ask: "Conclusion run" }}
        viewer={HANNAH}
      />,
    );
    expect(screen.getByText("Running…")).toBeTruthy();
    rerender(<AgentFilledMarker suggestion={{ state: "input", value: "" }} viewer={HANNAH} />);
    expect(screen.getByText("Needs input")).toBeTruthy();
    rerender(<AgentFilledMarker suggestion={{ state: "empty", value: "" }} viewer={HANNAH} />);
    expect(screen.getByText("—")).toBeTruthy();
  });
});
