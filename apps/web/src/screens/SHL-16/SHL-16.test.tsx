// SHL-16 · Checkpoint diff drawer (P-04-T43). One test per frame (a–f) on its fixture scenario and
// the acceptance: "SHL-16a-f match their artboards at Tier C, and Restore always creates a new
// checkpoint in the UI." Tier C (pixels) is the visual suite's; here the content and the writes.
import { client } from "@abacus/api-client/client";
import { toastStore } from "@abacus/ui";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { type FixtureHandler, installFixtureMode } from "../../app-core/fixture-mode";
import { newQueryClient } from "../../testing/support";
import { CheckpointDrawer } from ".";
import { COPY } from "./copy";
import { OPENS, STATES, type Shl16State, scenarios } from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
  toastStore.clear();
});

interface Call {
  method: string;
  path: string;
  query: string;
  body: unknown;
}

function show(state: Shl16State): Call[] {
  const calls: Call[] = [];
  const scenario = scenarios[state];
  const handlers = Object.fromEntries(
    Object.entries(scenario.handlers).map(([key, handler]) => [
      key,
      ((request) => {
        calls.push({
          method: request.method,
          path: request.path,
          query: request.query.toString(),
          body: request.body,
        });
        return handler(request);
      }) satisfies FixtureHandler,
    ]),
  );
  restore = installFixtureMode({ ...scenario, handlers });
  const open = OPENS[state];
  render(
    <QueryClientProvider client={newQueryClient()}>
      <CheckpointDrawer
        target={{ type: open.type, id: open.id }}
        {...(open.seq === undefined ? {} : { initialSeq: open.seq })}
        {...(open.dialog === undefined ? {} : { initialDialog: open.dialog })}
        open
        onOpenChange={() => undefined}
      />
    </QueryClientProvider>,
  );
  return calls;
}

const card = (seq: number): HTMLElement | null =>
  document.querySelector<HTMLElement>(`[data-checkpoint="${String(seq)}"]`);

describe("SHL-16", () => {
  it("builds a to f, and the import variant ia, ib and ie (P-04-T47)", () => {
    expect(STATES).toEqual(["a", "b", "c", "d", "e", "f", "ia", "ib", "ie"]);
  });

  it("a: Checkpoint 6 proposed and expanded with steps, the diff, the tie and Approve", async () => {
    const calls = show("a");
    await waitFor(() => {
      expect(card(6)?.hasAttribute("data-open")).toBe(true);
    });
    expect(within(card(6) as HTMLElement).getByText("Proposed")).toBeTruthy();
    expect(within(card(5) as HTMLElement).getByText(COPY.current)).toBeTruthy();
    expect(await screen.findByText("Analyzed the drafted return")).toBeTruthy();
    expect(screen.getByText("Skipped creating worksheet")).toBeTruthy();
    const diff = screen.getByRole("table", { name: "Field diff" });
    expect(within(diff).getAllByRole("row")).toHaveLength(1 + 4 + 1);
    expect(within(diff).getByText(COPY.tie)).toBeTruthy();
    expect(screen.getByText(COPY.approveNote(6))).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /Approve checkpoint/u }));
    await waitFor(() => {
      expect(calls.some((c) => c.method === "POST" && c.path.endsWith("/approve"))).toBe(true);
    });
    const post = calls.find((c) => c.path.endsWith("/approve"));
    expect(post?.body).toHaveProperty("seen_hash");
  });

  it("b: approved; Current moves to Checkpoint 6 with Approved · Samuel Ito", async () => {
    show("b");
    await waitFor(() => {
      expect(card(6)).not.toBeNull();
    });
    expect(within(card(6) as HTMLElement).getByText(COPY.current)).toBeTruthy();
    expect(within(card(6) as HTMLElement).getByText(/^Approved · Samuel Ito · /u)).toBeTruthy();
    expect(within(card(5) as HTMLElement).queryByText(COPY.current)).toBeNull();
  });

  it("c: Checkpoint 3 selected; Restore… only; restoring creates a new checkpoint", async () => {
    const calls = show("c");
    expect(await screen.findByText("Self-check: 0 errors, 2 warnings")).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Approve checkpoint/u })).toBeNull();
    expect((await screen.findAllByText(COPY.restoreDialog.title(3))).length).toBeGreaterThan(0);
    expect(screen.getByText(COPY.restoreDialog.body(3, 7))).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: COPY.restoreDialog.restore }));
    await waitFor(() => {
      expect(calls.some((c) => c.method === "POST" && c.path.endsWith("/restore"))).toBe(true);
    });
    await waitFor(() => {
      expect(toastStore.list().map((t) => t.text)).toContain(COPY.toasts.restored(7));
    });
    expect(calls.filter((c) => ["PATCH", "DELETE"].includes(c.method))).toEqual([]);
  });

  it("d: Checkpoint 5 named Before K-1 treatment, star filled, its name field open", async () => {
    show("d");
    const field = await screen.findByRole("textbox", { name: COPY.renameLabel(5) });
    expect((field as HTMLInputElement).value).toBe("Before K-1 treatment");
    expect(
      within(card(5) as HTMLElement)
        .getByRole("button", { name: COPY.unstar })
        .getAttribute("aria-pressed"),
    ).toBe("true");
  });

  it("e: rejected with the reason line", async () => {
    show("e");
    expect(await screen.findByText("Rejected")).toBeTruthy();
    expect(screen.getByText("Samuel Ito · reason: Wait for final K-1")).toBeTruthy();
  });

  it("f: no checkpoints yet, with Save checkpoint…", async () => {
    show("f");
    expect(await screen.findByText(COPY.emptyTitle)).toBeTruthy();
    expect(screen.getByText(COPY.emptyBody)).toBeTruthy();
    expect(screen.getByRole("button", { name: COPY.save })).toBeTruthy();
  });

  it("the filter asks the server for Agent only", async () => {
    const calls = show("a");
    const filter = await screen.findByRole("button", { name: COPY.filter });
    filter.focus();
    fireEvent.keyDown(filter, { key: "ArrowDown" });
    fireEvent.click(await screen.findByText(COPY.filters.agent));
    await waitFor(() => {
      expect(
        calls.some((c) => c.path === "/v1/checkpoints" && c.query.includes("filter=agent")),
      ).toBe(true);
    });
  });
});
