// C-02-T23 (TASK-8711): CLS-08 a-g render from their scenarios; the statements are the exported
// package's (total assets 549,195.45, net income 27,795.00 against 31,455.00), the legend sits on
// every page only on the AR-C 70 route, toggling a section renumbers the pages, and c names the
// three blockers.
import { client } from "@abacus/api-client/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
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
  it("a: the statements and the commentary, each page with the legend", async () => {
    show("a");
    const total = await screen.findByText("Total assets");
    expect(within(total.closest("tr") as HTMLElement).getByText("$549,195.45")).toBeTruthy();
    const ni = screen.getByText("Net income");
    expect(within(ni.closest("tr") as HTMLElement).getByText("$27,795.00")).toBeTruthy();
    expect(within(ni.closest("tr") as HTMLElement).getByText("$31,455.00")).toBeTruthy();
    expect(screen.getAllByText("No assurance is provided.")).toHaveLength(3);
    expect(screen.getByText(C.statements.page(3, 3))).toBeTruthy();
  });

  it("toggling the income statement off renumbers the pages", async () => {
    show("a");
    await screen.findByText("Total assets");
    fireEvent.click(screen.getByRole("switch", { name: C.sections.income_statement ?? "" }));
    expect(await screen.findByText(C.statements.page(2, 2))).toBeTruthy();
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

  it("a: the commentary page reads the accepted flux, and Edit changes commentary only", async () => {
    show("a");
    const page = await screen.findByText(/Payroll rose 12\.5% to \$68,910/);
    expect(page.closest("[data-commentary]")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: C.edit }));
    const field = screen.getByLabelText(C.commentaryEdit.label);
    fireEvent.change(field, { target: { value: "Revenue rose 4.5% to $214,600." } });
    fireEvent.click(screen.getByRole("button", { name: C.commentaryEdit.save }));
    expect(await screen.findByText("Revenue rose 4.5% to $214,600.")).toBeTruthy();
    // the figures are untouched by a commentary edit
    expect(screen.getByText("Total assets")).toBeTruthy();
  });

  it("g: the No answer routes to a standalone engagement", async () => {
    show("g");
    expect(await screen.findByText(C.basis.routes.standalone_letter ?? "")).toBeTruthy();
  });

  // C-02-T37 (TASK-8923; DEC-5925): d, e, f and g in full.
  it("CLS-08d released: the pill, who released it and whom approval was asked of, no watermark", async () => {
    show("d");
    expect(await screen.findByText(C.status.released)).toBeTruthy();
    expect(
      screen.getByText(
        C.status.releasedLine("Priya Raman", "4:25 PM", ["Tess Moreno", "Ben Ashby"]),
      ),
    ).toBeTruthy();
    expect(screen.getByText(/approval requested from Tess Moreno and Ben Ashby$/)).toBeTruthy();
    await screen.findByText("Total assets");
    expect(document.querySelector('[data-document="watermark"]')).toBeNull();
    expect(screen.queryByRole("button", { name: C.lockClose })).toBeNull();
  });

  it("CLS-08e approved by client: Tess Moreno's approval and Lock close behind a confirm", async () => {
    show("e");
    expect(await screen.findByText(C.status.approved)).toBeTruthy();
    expect(
      screen.getByText(
        C.status.approvedLine("Tess Moreno", "Sep 15, 8:42 AM", "Priya Raman", "Sep 14, 4:25 PM"),
      ),
    ).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: C.lockClose }));
    const confirm = await screen
      .findByRole("alertdialog", { name: C.lock.title("August 2026") })
      .catch(() => screen.findByRole("dialog", { name: C.lock.title("August 2026") }));
    fireEvent.click(within(confirm).getByRole("button", { name: C.lock.confirm }));
    expect(await screen.findByText(C.status.locked)).toBeTruthy();
    expect(screen.queryByRole("button", { name: C.lockClose })).toBeNull();
  });

  it("CLS-08e: Reopen close… needs a reason before it reopens", async () => {
    show("e");
    fireEvent.click(await screen.findByRole("button", { name: C.lockClose }));
    const confirm = await screen
      .findByRole("alertdialog", { name: C.lock.title("August 2026") })
      .catch(() => screen.findByRole("dialog", { name: C.lock.title("August 2026") }));
    fireEvent.click(within(confirm).getByRole("button", { name: C.lock.confirm }));
    fireEvent.click(await screen.findByRole("button", { name: C.reopen.open }));
    const dialog = await screen.findByRole("dialog", { name: C.reopen.title("August 2026") });
    const go = within(dialog).getByRole("button", { name: C.reopen.confirm });
    expect((go as HTMLButtonElement).disabled).toBe(true);
    fireEvent.change(within(dialog).getByLabelText(C.reopen.reason), {
      target: { value: "A late vendor credit" },
    });
    expect((go as HTMLButtonElement).disabled).toBe(false);
    fireEvent.click(go);
    await waitFor(() => {
      expect(screen.queryByText(C.status.locked)).toBeNull();
    });
    expect(screen.getByRole("button", { name: C.lockClose })).toBeTruthy();
  });

  it("CLS-08f SSARS 27: the CAS by-product route carries no legend or report", async () => {
    show("f");
    await screen.findByText("Total assets");
    expect(screen.queryAllByText("No assurance is provided.")).toHaveLength(0);
    expect(document.querySelector('[data-document="watermark"]')).not.toBeNull();
  });

  it("CLS-08g No answer: the letter governs the legend or report, with Open letter", async () => {
    show("g");
    expect(await screen.findByText(C.basis.legendOrReport)).toBeTruthy();
    expect(screen.getByText(C.basis.perLetter)).toBeTruthy();
    expect(screen.getByText(C.basis.openLetter)).toBeTruthy();
    expect(screen.queryByText(C.basis.report)).toBeNull();
  });

  it("the studio button is a planned link: drawn disabled where planned screens are", async () => {
    show("a");
    await screen.findByText("Total assets");
    const studio = screen.getByRole("button", { name: C.studio.open });
    expect((studio as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByText(C.release_band.studioVersion)).toBeTruthy();
  });
});
