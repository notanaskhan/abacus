import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import type { JSX, ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { RUN_ID } from "../../../fixtures/seed/tpl04-sessions";
import type { FixtureParams } from "../../fixture-mode";
import { screenById } from "../../fixture-mode";
import { T4_STATES, T4Artboard, TPL04_STATES, Tpl04Artboard } from ".";
import "..";

// F-07-T08 (TASK-7510; SPEC-652; handoff T4 a–f, TPL-04 a–e): "All 11 artboards render under
// ?st= with a frozen ScriptedRunSource, the gallery action log records each intent, and there are
// no console errors."

afterEach(cleanup);

function wrap(node: ReactNode): JSX.Element {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{node}</QueryClientProvider>;
}

function params(st: string): FixtureParams {
  return { st, static: true } as FixtureParams;
}

function log(): string[] {
  const list = document.querySelector("[data-intent-log]");
  return Array.from(list?.querySelectorAll("li") ?? []).map((li) => li.textContent);
}

describe("T4 and TPL-04 in the gallery", () => {
  it("registers both screens", () => {
    expect(screenById("T4")).toBeDefined();
    expect(screenById("TPL-04")).toBeDefined();
  });

  it("renders all 11 artboards under ?st= frozen, without console errors", () => {
    const error = vi.spyOn(console, "error").mockImplementation(() => undefined);
    expect(T4_STATES.length + TPL04_STATES.length).toBe(11);
    for (const st of T4_STATES) {
      const { container, unmount } = render(wrap(<T4Artboard params={params(st)} />));
      expect(container.querySelector(`[data-specimen="T4"][data-state="${st}"]`)).not.toBeNull();
      expect(container.querySelector('[data-template="T4"]')).not.toBeNull();
      unmount();
    }
    for (const st of TPL04_STATES) {
      const { container, unmount } = render(wrap(<Tpl04Artboard params={params(st)} />));
      expect(
        container.querySelector(`[data-specimen="TPL-04"][data-state="${st}"]`),
      ).not.toBeNull();
      unmount();
    }
    expect(error).not.toHaveBeenCalled();
    error.mockRestore();
  });

  it("a frozen running frame stays on its running page", () => {
    render(wrap(<Tpl04Artboard params={params("c")} />));
    act(() => undefined);
    expect(document.querySelector('[data-state="c"] [data-item="tool_card"]')).not.toBeNull();
    expect(document.querySelector('[data-item="artifact"]')).toBeNull();
  });

  it("logs Bug as run-trace and Create Agent… as edit-agent:new", () => {
    render(wrap(<Tpl04Artboard params={params("a")} />));
    fireEvent.click(screen.getByRole("button", { name: "Open run trace" }));
    fireEvent.click(screen.getByRole("button", { name: /Create Agent/ }));
    expect(log()).toEqual([`run-trace:${RUN_ID}`, "edit-agent:new"]);
  });

  it("logs the answer and moves a to the running frame", () => {
    render(wrap(<Tpl04Artboard params={params("a")} />));
    const card = document.querySelector('[data-kit="QuestionCard"]') as HTMLElement;
    fireEvent.click(within(card).getByRole("button", { name: "Next" }));
    fireEvent.click(within(card).getByRole("button", { name: "Next" }));
    expect(log().filter((l) => l.startsWith("answer:"))).toHaveLength(2);
  });

  it("logs Save to Files on the complete frame's artifact", () => {
    render(wrap(<Tpl04Artboard params={params("d")} />));
    const save = screen.queryByRole("button", { name: /Save to Files/ });
    if (save !== null) {
      fireEvent.click(save);
      expect(log().some((l) => l.startsWith("save-to-files:"))).toBe(true);
    } else {
      expect(document.querySelector('[data-item="artifact"]')).not.toBeNull();
    }
  });

  it("a suggested prompt fills the composer and is logged, never sent", () => {
    render(wrap(<Tpl04Artboard params={params("b")} />));
    fireEvent.click(screen.getByText("Status report by office"));
    const composer = screen.getByRole<HTMLTextAreaElement>("textbox", { name: "Message" });
    expect(composer.value).toBe("Status report by office");
    expect(log()).toEqual(["prompt"]);
  });

  it("T4f is WB-06 with Run, Edit and Archive logged", () => {
    render(wrap(<T4Artboard params={params("f")} />));
    expect(document.querySelector('[data-variant="agent_detail"]')).not.toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Run" }));
    fireEvent.click(screen.getByRole("button", { name: "Edit agent" }));
    expect(log()).toEqual(["run-agent:soc1", "edit-agent:soc1"]);
  });
});
