// T-06-T53 (TASK-9030; DEC-6035): TAX-11 a-e from their scenarios, whose pages, values and
// diagnostics are the exported Python scenario's. Row acceptance: "Approve stays disabled with 'n
// blocking diagnostics' until state d, and no control on the screen transmits or files."
import { client } from "@abacus/api-client/client";
import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { installFixtureMode, json } from "../../app-core/fixture-mode";
import { renderRoutes } from "../../testing/support";
import { COPY as C } from "./copy";
import { TAX11 } from "./index";
import { INITIAL, RIDGELINE_RETURN, type Tax11State, scenarios } from "./scenarios";

const opened = vi.hoisted(() => [] as { key: string; args: readonly string[] }[]);
vi.mock("../../app-core/open", () => ({
  useOpenOverlay: () => (ref: { key: string; args: readonly string[] }) => {
    opened.push(ref);
  },
}));

let restore: (() => void) | null = null;

beforeAll(() => {
  client.setConfig({ baseUrl: "http://localhost" });
});

afterEach(() => {
  cleanup();
  restore?.();
  restore = null;
  opened.length = 0;
});

function show(
  state: Tax11State,
  over: Parameters<typeof installFixtureMode>[0]["handlers"] = {},
): void {
  const base = scenarios[state];
  restore = installFixtureMode({ ...base, handlers: { ...base.handlers, ...over } });
  const init = INITIAL[state];
  renderRoutes([
    {
      path: "/",
      component: () => (
        <TAX11
          returnId={RIDGELINE_RETURN}
          {...(init.page === undefined ? {} : { initialPage: init.page })}
          {...(init.k1 === undefined ? {} : { initialK1: init.k1 })}
        />
      ),
    },
  ]);
}

async function approve(): Promise<HTMLElement> {
  return screen.findByRole("button", { name: C.approve });
}

function diagnosticsPane(): HTMLElement {
  const pane = screen.getByRole("region", { name: "Diagnostics" });
  return pane;
}

describe("TAX-11 Form preview with K-1s", () => {
  it("TAX-11a page 1: typed values, the K-1 list ties, two blocking diagnostics block Approve", async () => {
    show("a");
    expect(await screen.findByRole("button", { name: "Form 1065 page 1" })).toBeTruthy();
    const values = await screen.findByRole("region", { name: C.values });
    for (const v of ["Real estate rental", "531110", "••-•••0287", "17,914,500", "5"]) {
      expect(await within(values).findByText(v)).toBeTruthy();
    }
    await waitFor(() => {
      expect(screen.getAllByRole("listitem").some((l) => l.getAttribute("data-k1"))).toBe(true);
    });
    expect(document.querySelectorAll("[data-k1]")).toHaveLength(5);
    expect(document.querySelector('[data-total="tie"]')).not.toBeNull();
    const pane = diagnosticsPane();
    await waitFor(() => {
      expect(
        within(pane).getByText("Σ K-1 Item L does not equal Schedule L line 21"),
      ).toBeTruthy();
    });
    expect(within(pane).getByText("§754 statement not decided")).toBeTruthy();
    expect(within(pane).getByText("Item J: Schedule M-3 attached")).toBeTruthy();
    const button = await approve();
    await waitFor(() => {
      expect(button.hasAttribute("disabled")).toBe(true);
    });
    expect(button.getAttribute("title")).toBe("2 blocking diagnostics");
    expect(screen.getByText("2 blocking diagnostics")).toBeTruthy();
    expect(screen.getByRole("button", { name: C.export }).hasAttribute("disabled")).toBe(true);
  });

  it("TAX-11 a: a typed value opens SHL-09, a diagnostic opens TXP-10, page thumbnails show the placeholders", async () => {
    show("a");
    const values = await screen.findByRole("region", { name: C.values });
    fireEvent.click(await within(values).findByText("17,914,500"));
    expect(opened).toContainEqual({
      key: "provenance",
      args: ["tax_return", RIDGELINE_RETURN, "f"],
    });
    const pane = diagnosticsPane();
    const issue = await waitFor(() => {
      const found = within(pane).getAllByRole("button", { name: "→ issue" });
      expect(found).toHaveLength(3);
      return found;
    });
    expect(issue[0]).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Sch. C (M-3 filers)" }));
    expect(await screen.findByText(C.placeholder)).toBeTruthy();
  });

  it("TAX-11b K-1 · Jonah Feld: the partner is selected and the face points to the K-1 package", async () => {
    show("b");
    expect(await screen.findByText(C.k1Face("Jonah Feld"))).toBeTruthy();
    await waitFor(() => {
      expect(document.querySelector('[data-k1][aria-current="true"]')?.textContent).toContain(
        "Jonah Feld",
      );
    });
    expect(screen.getByRole("button", { name: C.openK1Package })).toBeTruthy();
  });

  it("TAX-11c Schedule K: lines 2, 5, 18a, 19a and 20a with TXP-05's values", async () => {
    show("c");
    const values = await screen.findByRole("region", { name: C.values });
    for (const v of ["1,231,600", "6,200", "600,000"]) {
      expect(await within(values).findByText(v)).toBeTruthy();
    }
    expect(within(values).getAllByText("18,400")).toHaveLength(2);
  });

  it("TAX-11 acceptance: Approve stays disabled with 'n blocking diagnostics' until state d", async () => {
    show("d");
    const button = await approve();
    await waitFor(() => {
      expect(button.hasAttribute("disabled")).toBe(false);
    });
    expect(screen.queryByText(/blocking diagnostic/)).toBeNull();
    fireEvent.click(button);
    expect(opened).toContainEqual({
      key: "signoff",
      args: ["tax_return", RIDGELINE_RETURN, "L4_partner"],
    });
    // Export waits for the approval itself.
    expect(screen.getByRole("button", { name: C.export }).hasAttribute("disabled")).toBe(true);
  });

  it("TAX-11 acceptance: no control on the screen transmits or files", async () => {
    for (const state of ["a", "d"] as const) {
      show(state);
      await approve();
      for (const word of ["Transmit", "File", "E-file", "Submit", "Send"]) {
        expect(screen.queryByRole("button", { name: new RegExp(`^${word}`, "i") })).toBeNull();
      }
      cleanup();
      restore?.();
      restore = null;
    }
  });

  it("TAX-11e loading: the form-rule skeleton while the pages render", async () => {
    show("e");
    await waitFor(() => {
      expect(document.querySelector('[data-screen="TAX-11"][aria-busy="true"]')).not.toBeNull();
    });
  });

  it("error: a failed read offers Retry", async () => {
    show("a", {
      "GET /v1/tax-returns/{return_id}/form-pages": () => json({ detail: "boom" }, 500),
    });
    expect(await screen.findByRole("button", { name: C.retry })).toBeTruthy();
  });
});
