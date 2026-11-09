// POR-09 · Deliverables (R-02-T17). One test per artboard (a, a2, b, c, d, e, f) on its fixture
// scenario, the flag-off state and the 390 layout. Every figure is the API's; Approve renders only
// when the latest version lists it and sends what was seen; release stays the firm's.
import { client } from "@abacus/api-client/client";
import { toastStore } from "@abacus/ui";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { type FixtureHandler, type Scenario, installFixtureMode } from "../../app-core/fixture-mode";
import { newQueryClient } from "../../testing/support";
import { POR09 } from ".";
import { COPY } from "./copy";
import { FLAG_OFF, OPENING, type Por09State, scenarios } from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
  if (URL.createObjectURL === undefined) {
    Object.assign(URL, { createObjectURL: () => "blob:page", revokeObjectURL: () => undefined });
  }
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
  toastStore.clear();
});

interface Seen {
  calls: { method: string; path: string; body: unknown; key: string | null }[];
}

function show(scenario: Scenario, opening: Record<string, unknown> = {}, mobile = false): Seen {
  const seen: Seen = { calls: [] };
  const handlers = Object.fromEntries(
    Object.entries(scenario.handlers).map(([key, handler]) => [
      key,
      ((request) => {
        seen.calls.push({
          method: request.method,
          path: request.path,
          body: request.body,
          key: request.headers?.get("Idempotency-Key") ?? null,
        });
        return handler(request);
      }) satisfies FixtureHandler,
    ]),
  );
  restore = installFixtureMode({ ...scenario, handlers });
  render(
    <QueryClientProvider client={newQueryClient()}>
      <POR09 {...opening} mobile={mobile} />
    </QueryClientProvider>,
  );
  return seen;
}

const at = (state: Por09State, mobile = false): Seen =>
  show(scenarios[state], OPENING[state] ?? {}, mobile);

describe("POR-09 deliverables", () => {
  it("a: the draft for review, page 2 of 14, the watermark and Dana's comment with the reply", async () => {
    at("a");
    expect(await screen.findByText("Financial statements — draft v3")).toBeTruthy();
    expect(screen.getByText("Draft for review")).toBeTruthy();
    expect(screen.getByText("2 / 14")).toBeTruthy();
    expect(document.querySelector("[data-watermark='draft']")).not.toBeNull();
    expect(await screen.findByText("Keystone calls these participant loans. Can the note say both?")).toBeTruthy();
    expect(screen.getByText(/Note 5 will read/)).toBeTruthy();
    expect(screen.getByText("Comments · 2")).toBeTruthy();
    expect(screen.getByText("Coming next")).toBeTruthy();
    expect(screen.getByText("At release · expected Oct 9")).toBeTruthy();
    // v3 does not list approve: no Approve control on an older draft
    expect(screen.queryByRole("button", { name: COPY.approve })).toBeNull();
  });

  it("the pager and zoom move over the server's pages", async () => {
    at("a");
    await screen.findByText("2 / 14");
    fireEvent.click(screen.getByRole("button", { name: COPY.next }));
    expect(screen.getByText("3 / 14")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: COPY.previous }));
    fireEvent.click(screen.getByRole("button", { name: COPY.previous }));
    expect(screen.getByText("1 / 14")).toBeTruthy();
    expect((screen.getByRole("button", { name: COPY.previous }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: COPY.zoomIn }));
    fireEvent.click(screen.getByRole("button", { name: COPY.fit }));
  });

  it("a2: the confirm approves the latest draft with the hash that was seen", async () => {
    const seen = at("a2");
    expect(await screen.findByText(COPY.approveTitle)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: COPY.approveConfirm }));
    await waitFor(() => {
      expect(seen.calls.some((c) => c.method === "POST" && c.path.endsWith("/versions/4/approve"))).toBe(true);
    });
    const post = seen.calls.find((c) => c.method === "POST");
    expect(post?.body).toEqual({ seen_hash: expect.any(String) as string });
    expect(post?.key).not.toBeNull();
  });

  it("b: approved by you, the watermark stays until release", async () => {
    at("b");
    expect(await screen.findByText(COPY.approvedNote)).toBeTruthy();
    expect(document.querySelector("[data-watermark='draft']")).not.toBeNull();
    expect(screen.queryByRole("button", { name: COPY.approve })).toBeNull();
  });

  it("c: final documents, no watermark, Download", async () => {
    at("c");
    expect(await screen.findByRole("button", { name: COPY.download })).toBeTruthy();
    expect(document.querySelector("[data-watermark='draft']")).toBeNull();
    expect(screen.getAllByText("Final").length).toBeGreaterThanOrEqual(2);
  });

  it("d: Meera's role union shows only her released K-1", async () => {
    at("d");
    expect(await screen.findByText("My K-1s")).toBeTruthy();
    expect(screen.getByText("Released Sep 15")).toBeTruthy();
    expect(await screen.findByText(COPY.k1Added)).toBeTruthy();
    expect(screen.getByText("468,008")).toBeTruthy();
    expect(screen.getByText("228,000")).toBeTruthy();
    expect(screen.queryByText(/Pell Street/)).toBeNull();
  });

  it("e: Copperleaf's package carries the AR-C 70 legend (fixture only)", async () => {
    at("e");
    expect(await screen.findByText(COPY.legend)).toBeTruthy();
    expect(screen.getByText("Waiting for approval")).toBeTruthy();
  });

  it("f: nothing delivered yet", async () => {
    at("f");
    expect(await screen.findByText(COPY.empty)).toBeTruthy();
    expect(screen.getByText(COPY.emptyBody)).toBeTruthy();
  });

  it("flag off: the designed state, never a 404 page", async () => {
    show(FLAG_OFF);
    expect(await screen.findByText(COPY.flagOff)).toBeTruthy();
  });

  it("390: Approve stays sticky at the bottom", async () => {
    at("a2", true);
    await screen.findByText(COPY.approveTitle);
    expect(document.querySelector("[data-sticky-approve]")).not.toBeNull();
  });

  it("no word on the screen is the product's, the agent's or materiality", async () => {
    at("a");
    await screen.findByText("Financial statements — draft v3");
    const text = document.body.textContent ?? "";
    expect(text).not.toMatch(/Accrued|agent|materiality/i);
  });
});
