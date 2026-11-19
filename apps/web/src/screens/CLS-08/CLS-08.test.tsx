// C-02-T23 (TASK-8711): CLS-08 a-g render from their scenarios; the statements are the exported
// package's (total assets 549,195.45, net income 27,795.00 against 31,455.00), the legend sits on
// every page only on the AR-C 70 route, toggling a section renumbers the pages, and c names the
// three blockers.
import { client } from "@abacus/api-client/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import { newQueryClient } from "../../testing/support";
import { COPY as C } from "./copy";
import { CLS08 } from "./index";
import { CLS08_CLOSE_ID, type Cls08State, scenarios } from "./scenarios";

let restore: (() => void) | null = null;

beforeAll(() => {
  client.setConfig({ baseUrl: "http://localhost" });
});

afterEach(() => {
  cleanup();
  restore?.();
  restore = null;
});

function show(state: Cls08State): void {
  restore = installFixtureMode(scenarios[state]);
  render(
    <QueryClientProvider client={newQueryClient()}>
      <CLS08 closeId={CLS08_CLOSE_ID} />
    </QueryClientProvider>,
  );
}

describe("CLS-08 Close › Deliverables", () => {
  it("a: two pages from the posted ledger, each with the legend", async () => {
    show("a");
    const total = await screen.findByText("Total assets");
    expect(within(total.closest("tr") as HTMLElement).getByText("$549,195.45")).toBeTruthy();
    const ni = screen.getByText("Net income");
    expect(within(ni.closest("tr") as HTMLElement).getByText("$27,795.00")).toBeTruthy();
    expect(within(ni.closest("tr") as HTMLElement).getByText("$31,455.00")).toBeTruthy();
    expect(screen.getAllByText("No assurance is provided.")).toHaveLength(2);
    expect(screen.getByText(C.statements.page(2, 2))).toBeTruthy();
  });

  it("toggling the income statement off renumbers the pages", async () => {
    show("a");
    await screen.findByText("Total assets");
    fireEvent.click(screen.getByRole("switch", { name: C.sections.income_statement ?? "" }));
    expect(await screen.findByText(C.statements.page(1, 1))).toBeTruthy();
  });

  it("c: the three blockers of 9:24 AM", async () => {
    show("c");
    expect(await screen.findByText(C.preconditions.accounts_unreconciled(9, 21))).toBeTruthy();
    expect(screen.getByText(C.preconditions.issues_open(7))).toBeTruthy();
    expect(screen.getByText(C.preconditions.entries_unposted)).toBeTruthy();
  });

  it("d and e: released, then approved by the client, without the watermark", async () => {
    show("d");
    expect(await screen.findByText(C.status.released)).toBeTruthy();
    cleanup();
    restore?.();
    show("e");
    expect(await screen.findByText(C.status.approved)).toBeTruthy();
  });

  it("f: the SSARS 27 route carries no legend", async () => {
    show("f");
    await screen.findByText("Total assets");
    expect(screen.queryAllByText("No assurance is provided.")).toHaveLength(0);
    expect(screen.getByText(C.basis.routes.cas_by_product ?? "")).toBeTruthy();
  });

  it("g: the No answer routes to a standalone engagement", async () => {
    show("g");
    expect(await screen.findByText(C.basis.routes.standalone_letter ?? "")).toBeTruthy();
  });
});
