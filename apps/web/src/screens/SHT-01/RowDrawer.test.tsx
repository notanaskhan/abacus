// K-03-T22 (TASK-9028; DEC-6033): SHT-01 e, the row drawer, against a real router on memory
// history. Row acceptance: "SHT-01e renders SURL-05 word for word with two citation chips that
// open SHL-07, Adopt (L1) opens ?ov=signoff:sheet_row:<id>:L1, and the drawer survives reload and
// closes on Back."
import { client } from "@abacus/api-client/client";
import { QueryClientProvider } from "@tanstack/react-query";
import {
  Outlet,
  RouterProvider,
  createMemoryHistory,
  createRootRoute,
  createRoute,
  createRouter,
} from "@tanstack/react-router";
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { type FixtureHandler, installFixtureMode, json } from "../../app-core/fixture-mode";
import { OverlayHost } from "../../app-core/overlay-host";
import { decodeOverlays } from "../../app-core/overlays";
import "../../routes/firm/sheets"; // registers `row` and `signoff`
import { rowDrawer } from "../../fixtures/seed/sheets-sh1";
import { newQueryClient } from "../../testing/support";
import { COPY as C } from "./copy";
import { SHT01 } from "./index";
import { DRAWER_ROW_KEY, SHEET_ID, scenarios } from "./scenarios";

const AUDIT = "00000000-0000-4000-8000-0000000000a2";
const SHEET_PATH = `/audits/${AUDIT}/sheets/${SHEET_ID}`;
const WHY =
  "Invoice FRF-30418 is dated June 29, 2026 and bills June inbound freight. It was paid on July 22 and posted in July, so it was not in accounts payable at June 30. I suggest Improperly excluded. $68,400 is above clearly trivial ($7,750) and below performance materiality ($116,250).";
let restore: (() => void) | null = null;

beforeAll(() => {
  client.setConfig({ baseUrl: "http://localhost" });
});

afterEach(() => {
  cleanup();
  restore?.();
  restore = null;
});

function mount(at: string, over: Record<string, FixtureHandler> = {}) {
  const base = scenarios.e;
  restore = installFixtureMode({ ...base, handlers: { ...base.handlers, ...over } });
  const root = createRootRoute({
    component: () => (
      <>
        <Outlet />
        <OverlayHost />
      </>
    ),
  });
  const page = createRoute({
    getParentRoute: () => root,
    path: "/audits/$auditId/sheets/$sheetId",
    component: () => <SHT01 auditId={AUDIT} sheetId={SHEET_ID} />,
  });
  const history = createMemoryHistory({ initialEntries: [at] });
  const router = createRouter({ routeTree: root.addChildren([page]), history });
  render(
    <QueryClientProvider client={newQueryClient()}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return { history, router };
}

type Mounted = ReturnType<typeof mount>;
const layers = ({ router }: Mounted) =>
  decodeOverlays((router.state.location.search as Record<string, unknown>)["ov"]);

async function drawer(): Promise<HTMLElement> {
  return screen.findByRole("dialog", { name: `${DRAWER_ROW_KEY} · Front Range Freight Co.` });
}

describe("SHT-01 e · row drawer", () => {
  it("SHT-01e acceptance: renders SURL-05 word for word with two citation chips that open SHL-07", async () => {
    mount(`${SHEET_PATH}?ov=row:${DRAWER_ROW_KEY}`);
    const d = await drawer();
    const details = await within(d).findByText("Payment");
    const facts = details.closest<HTMLElement>('[data-sht01="details"]');
    if (facts === null) throw new Error("no details card");
    for (const [k, v] of [
      ["Payment", "ACH · Jul 22, 2026 · $68,400.00"],
      ["Invoice", "FRF-30418 · Jun 29, 2026"],
      ["Service", "June inbound freight"],
      ["Recorded in", "Jul 2026 (FY2027 period 1)"],
      ["In 6/30 AP aging", "No"],
    ] as const) {
      expect(within(facts).getByText(k)).toBeTruthy();
      expect(within(facts).getByText(v)).toBeTruthy();
    }
    expect(within(facts).getByText("Improperly excluded")).toBeTruthy();
    const why = d.querySelector<HTMLElement>('[data-sht01="why"]');
    expect(why?.textContent).toContain(WHY);
    const chips = await waitFor(() => {
      const found = d.querySelectorAll<HTMLElement>('[data-sht01="citations"] [data-cited]');
      expect(found).toHaveLength(2);
      return found;
    });
    expect(chips[0]?.textContent).toBe("FRF-30418.pdf · p.1");
    expect(chips[1]?.textContent).toBe("NetSuite bill FRF-30418 · posting period Jul 2026");
    // A chip opens SHL-07's card on its source.
    const first = chips[0];
    if (first === undefined) throw new Error("no chip");
    fireEvent.click(first);
    await waitFor(() => {
      expect(first.hasAttribute("data-pinned")).toBe(true);
    });
    const card = await waitFor(() => {
      const found = document.querySelector<HTMLElement>('[data-cite="card"]');
      if (found === null) throw new Error("no SHL-07 card");
      return found;
    });
    expect(card.textContent).toContain("FRF-30418.pdf");
  });

  it("SHT-01e acceptance: Adopt (L1) opens ?ov=signoff:sheet_row:<id>:L1", async () => {
    const mounted = mount(`${SHEET_PATH}?ov=row:${DRAWER_ROW_KEY}`);
    const d = await drawer();
    const adopt = await within(d).findByRole("button", { name: C.drawer.adopt });
    await waitFor(() => {
      expect(adopt.hasAttribute("disabled")).toBe(false);
    });
    fireEvent.click(adopt);
    await waitFor(() => {
      expect(layers(mounted)).toContainEqual({
        key: "signoff",
        args: ["sheet_row", rowDrawer().row.row_id, "L1"],
      });
    });
    expect(within(d).getByRole("button", { name: C.drawer.raiseException })).toBeTruthy();
  });

  it("SHT-01e acceptance: the drawer survives reload and closes on Back", async () => {
    // Opened from the sheet: the row's key pushes `?ov=row:SURL-05`.
    const mounted = mount(SHEET_PATH);
    const { history } = mounted;
    const open = await screen.findByRole("button", { name: `Open ${DRAWER_ROW_KEY}` });
    fireEvent.click(open);
    await drawer();
    expect(layers(mounted)).toEqual([{ key: "row", args: [DRAWER_ROW_KEY] }]);
    act(() => {
      history.back();
    });
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).toBeNull();
    });
    cleanup();
    restore?.();
    restore = null;
    // A reload of the drawer's URL draws it again.
    mount(`${SHEET_PATH}?ov=row:${DRAWER_ROW_KEY}`);
    expect(await drawer()).toBeTruthy();
  });

  it("tabs: the run on Agents, the invoice on Evidence, none on To-dos", async () => {
    mount(`${SHEET_PATH}?ov=row:${DRAWER_ROW_KEY}`);
    const d = await drawer();
    await within(d).findByText("Payment");
    fireEvent.click(within(d).getByRole("tab", { name: C.drawer.tabs.agents }));
    expect(
      await within(d).findByText("Unrecorded liabilities tester · finished Sep 28, 4:52 PM"),
    ).toBeTruthy();
    fireEvent.click(within(d).getByRole("tab", { name: C.drawer.tabs.evidence }));
    expect(await within(d).findByText("FRF-30418.pdf")).toBeTruthy();
    fireEvent.click(within(d).getByRole("tab", { name: C.drawer.tabs.requests }));
    expect(await within(d).findByText(C.drawer.noRequests)).toBeTruthy();
    fireEvent.click(within(d).getByRole("tab", { name: C.drawer.tabs.todos }));
    expect(await within(d).findByText(C.drawer.noTodos)).toBeTruthy();
  });

  it("locked: a signed-off row offers neither Adopt nor Raise exception", async () => {
    const locked = { ...rowDrawer(), row: { ...rowDrawer().row, locked: true } };
    mount(`${SHEET_PATH}?ov=row:${DRAWER_ROW_KEY}`, {
      "GET /v1/sheets/{sheet_id}/rows/{row_id}": () => json(locked),
    });
    const d = await drawer();
    await within(d).findByText("Payment");
    expect(within(d).queryByRole("button", { name: C.drawer.adopt })).toBeNull();
    expect(within(d).queryByRole("button", { name: C.drawer.raiseException })).toBeNull();
  });

  it("not found: a row out of the reader's walls reads as the error", async () => {
    mount(`${SHEET_PATH}?ov=row:${DRAWER_ROW_KEY}`, {
      "GET /v1/sheets/{sheet_id}/rows/{row_id}": () => json({ detail: "not_found" }, 404),
    });
    const d = await drawer();
    expect(await within(d).findByText(C.drawer.notFound)).toBeTruthy();
  });

  it("no agent-owned control approves, signs off, releases, sends or posts", async () => {
    mount(`${SHEET_PATH}?ov=row:${DRAWER_ROW_KEY}`);
    const d = await drawer();
    await within(d).findByText("Payment");
    for (const word of ["Approve", "Sign off", "Release", "Send", "Post"]) {
      expect(within(d).queryByRole("button", { name: new RegExp(`^${word}`) })).toBeNull();
    }
  });
});
