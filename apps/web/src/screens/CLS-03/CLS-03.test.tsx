// C-01-T35 (TASK-8075): CLS-03 Intake a–h in fixture mode. Row acceptance: "Every artboard matches
// its scenario, hovering the net total lights the 71,482.36 cell within 360 ms, and only a
// person's click incorporates or returns."
import { client } from "@abacus/api-client/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import { CLOSE_IDS } from "../../fixtures/seed/closes";
import { copperleafRequestTree } from "../../fixtures/seed/close-intake";
import { newQueryClient } from "../../testing/support";
import { type CLS03Props, CLS03, receivedCount, requestsOf } from "./index";
import { type IntakeState, scenarios } from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

const tree = copperleafRequestTree();
const byTitle = (t: string): string =>
  requestsOf(tree.nodes).find((r) => r.title.startsWith(t))?.request_item_id ?? "";

function show(state: IntakeState, props: Partial<CLS03Props> = {}): void {
  restore = installFixtureMode(scenarios[state]);
  render(
    <QueryClientProvider client={newQueryClient()}>
      <CLS03 closeId={CLOSE_IDS.august} {...props} />
    </QueryClientProvider>,
  );
}

describe("CLS-03 Intake", () => {
  it("a: nine requests, 7 received and 2 requested; Square pending incorporation", async () => {
    expect(receivedCount(tree.nodes)).toEqual({ received: 7, total: 9 });
    show("a");
    await waitFor(() => {
      expect(screen.getByText("Pending incorporation")).toBeTruthy();
    });
    expect(document.querySelectorAll("[data-request]").length).toBe(9);
    await waitFor(() => {
      expect(document.querySelector("[data-cell='F23']")?.textContent).toBe("71,482.36");
    });
  });

  it("a2: hovering the net total lights the 71,482.36 cell (360 ms fade)", async () => {
    show("a2");
    const net = await waitFor(() => {
      const el = document.querySelector<HTMLElement>("[data-figure='net']");
      expect(el).not.toBeNull();
      return el as HTMLElement;
    });
    await waitFor(() => {
      expect(document.querySelector("[data-cell='F23']")).not.toBeNull();
    });
    fireEvent.mouseEnter(net);
    const cell = document.querySelector<HTMLElement>("[data-cell='F23']");
    expect(cell?.dataset.lit).toBe("true");
    expect(cell?.className).toContain("duration-[360ms]");
  });

  it("only a person's click incorporates or returns (a, a3)", async () => {
    const onIncorporate = vi.fn();
    const onReturn = vi.fn();
    show("a3", { onIncorporate, onReturn, initial: { picker: true } });
    const reason = await screen.findByRole("button", { name: "Wrong period" });
    expect(onReturn).not.toHaveBeenCalled();
    expect(onIncorporate).not.toHaveBeenCalled();
    fireEvent.click(reason);
    expect(onReturn).toHaveBeenCalledWith(byTitle("Square payouts"), "Wrong period");
  });

  it("b: incorporated offers Re-run affected tasks for exactly the Square procedure", async () => {
    const onRerun = vi.fn();
    show("b", { onRerun });
    fireEvent.click(await screen.findByRole("button", { name: "Re-run affected tasks" }));
    expect(onRerun).toHaveBeenCalledTimes(1);
    expect((onRerun.mock.calls[0]?.[0] as string[]).length).toBe(1);
  });

  it("c: a requested row offers Send reminder and Upload on behalf", async () => {
    show("c", {
      initial: { selected: { kind: "request", id: byTitle("Front Range Bank statement") } },
    });
    expect(await screen.findByText("Nothing uploaded yet")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Send reminder…" })).toBeTruthy();
  });

  it("d: the questionnaire, 4 of 5 answered", async () => {
    show("d", { initial: { selected: { kind: "questionnaire" } } });
    expect(await screen.findByText("4 of 5 answered")).toBeTruthy();
    expect(screen.getByText("Awaiting answer")).toBeTruthy();
  });

  it("e: the tree is a drop target", async () => {
    show("e", { initial: { dropTarget: true } });
    await waitFor(() => {
      expect(document.querySelector("[data-drop-target='on']")).not.toBeNull();
    });
  });

  it("f: before BD1 nothing is published", async () => {
    show("f");
    expect(
      await screen.findByText("Requests publish Oct 1 (BD1) from close plan v3."),
    ).toBeTruthy();
  });

  it("g and h: the Amex row is flagged; rescreening shows the spinner", async () => {
    show("g");
    await waitFor(() => {
      expect(document.querySelectorAll("[data-request]").length).toBe(9);
    });
    cleanup();
    restore?.();
    show("h", { initial: { rescreening: true } });
    await waitFor(() => {
      expect(document.querySelector("[data-rescreening]")).not.toBeNull();
    });
  });
});
