// T-06-T29 (TASK-8751; docs/screens/TXP-03.md; T-06 §3 F1): "Each artboard renders from its
// scenario, and the sign-off dialog requires a note while the roof flag is open." Figures are the
// server's (the fixture stands in for it); the screen sums nothing.
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { TXP03_OPENS, scenarios } from "../../fixtures/scenarios/TXP-03";
import { PARKING_ID, ROOF_ID, fixedAssets } from "../../fixtures/seed/tax-depth-assets";
import { COPY } from "./copy";
import { TXP03, registerRows, tallyItems } from ".";

afterEach(cleanup);

function ask(state: keyof typeof scenarios, route: string, query = "") {
  const handler = scenarios[state].handlers[route];
  if (handler === undefined) throw new Error(`no ${route}`);
  return handler({
    method: "GET",
    path: "/v1/tax-returns/x/fixed-assets",
    params: { return_id: "x" },
    query: new URLSearchParams(query),
    body: null,
    persona: undefined,
  });
}

describe("TXP-03 scenarios answer each artboard's server state", () => {
  it("c resolves the bonus check and e signs the section off", async () => {
    const R = "GET /v1/tax-returns/{return_id}";
    const a = (await (await ask("a", `${R}/fixed-assets`)).json()) as {
      bonus_eligibility: string;
    };
    const c = (await (await ask("c", `${R}/fixed-assets`)).json()) as {
      bonus_eligibility: string;
    };
    expect([a.bonus_eligibility, c.bonus_eligibility]).toEqual(["check", "tie"]);
    const b = (await (await ask("b", `${R}/fixed-assets`, "view=by_property")).json()) as {
      by_property: unknown[];
    };
    expect(b.by_property).toHaveLength(3);
    type Sections = { items: { key: string; signed_levels: string[] }[] };
    const signed = async (st: "a" | "e") =>
      ((await (await ask(st, `${R}/sections`)).json()) as Sections).items.find(
        (i) => i.key === "fixed-assets",
      )?.signed_levels;
    expect(await signed("a")).toEqual([]);
    expect(await signed("e")).toEqual(["l2"]);
  });
});

describe("TXP-03 Fixed Assets", () => {
  it("covers the six artboards, each on its scenario", () => {
    expect(Object.keys(scenarios)).toEqual(["a", "a2", "b", "c", "d", "e"]);
    expect(TXP03_OPENS).toEqual({
      a2: "?asset=_assetId_",
      b: "?view=by_property",
      d: "?view=dispositions",
    });
  });

  it("a: cost 15,752,000, accumulated 2,625,167, the roof Flag and the Larimer Check", () => {
    render(<TXP03 fixedAssets={fixedAssets("register", "e0")} view="register" />);
    const items = tallyItems(fixedAssets("register", "e0"));
    expect(items.find((i) => i.label === COPY.cards.cost)).toMatchObject({ value: "15,752,000" });
    expect(items.find((i) => i.label === COPY.cards.accumulated)).toMatchObject({
      value: "2,625,167",
    });
    expect(items.find((i) => i.label === COPY.cards.bonus)).toMatchObject({
      pill: { text: COPY.check },
    });
    const rows = registerRows(fixedAssets("register", "e0").rows);
    expect(rows.filter((r) => r.kind === "group").map((r) => r.label)).toEqual([
      "Elm Street, Chicago",
      "Larimer Lofts, Denver",
      "Bergen Street, Brooklyn",
    ]);
    expect(rows.find((r) => r.id === ROOF_ID)?.tag).toBe(COPY.flag);
    expect(rows.find((r) => r.id === PARKING_ID)?.cells.check?.value).toBe(COPY.check);
    expect(document.body.textContent).not.toMatch(/\$|QIP/);
  });

  it("a2: the Asset detail drawer shows the bonus date test and a picker choice is a ghost", async () => {
    const onPropose = vi.fn();
    render(
      <TXP03
        fixedAssets={fixedAssets("register", "e0")}
        view="register"
        assetId={PARKING_ID}
        onPropose={onPropose}
        onOpenInvoice={() => undefined}
      />,
    );
    const drawer = screen.getByRole("dialog");
    expect(within(drawer).getByText(COPY.drawer.waiting)).toBeTruthy();
    expect(within(drawer).getByText(COPY.drawer.cutoff("Jan 19, 2025"))).toBeTruthy();
    expect(within(drawer).getByRole("button", { name: COPY.drawer.invoice })).toBeTruthy();
    expect(drawer.querySelector("[data-ghost]")).toBeNull();
    const trigger = within(drawer).getByRole("button", { name: /^Bonus/u });
    trigger.focus();
    fireEvent.keyDown(trigger, { key: "ArrowDown" });
    fireEvent.click(await screen.findByRole("menuitemradio", { name: "40%" }));
    expect(drawer.querySelector("[data-ghost]")?.textContent).toBe(
      COPY.drawer.proposed("40% bonus"),
    );
    fireEvent.click(within(drawer).getByRole("button", { name: COPY.drawer.propose }));
    expect(onPropose).toHaveBeenCalledWith(PARKING_ID, { bonus_pct: "40" });
  });

  it("b: by property, land 3,600,000 and 733,500 to Form 8825", () => {
    render(<TXP03 fixedAssets={fixedAssets("by_property", "e0")} view="by_property" />);
    for (const t of ["169,500", "360,000", "204,000", "3,600,000", "733,500"]) {
      expect(screen.getAllByText(t).length).toBeGreaterThan(0);
    }
  });

  it("c: the bonus check resolves to tie once the contract matches", () => {
    const fa = fixedAssets("register", "bonusResolved");
    expect(tallyItems(fa).find((i) => i.label === COPY.cards.bonus)).toMatchObject({
      tally: "tie",
    });
    render(<TXP03 fixedAssets={fa} view="register" assetId={PARKING_ID} />);
    expect(screen.getByText(COPY.drawer.contract)).toBeTruthy();
  });

  it("d: dispositions is the EmptyState with §1245 and §1250", () => {
    render(<TXP03 fixedAssets={fixedAssets("dispositions", "e0")} view="dispositions" />);
    expect(screen.getByText(COPY.emptyTitle)).toBeTruthy();
    expect(document.body.textContent).toMatch(/§1245 and §1250/);
  });

  it("the sign-off dialog requires a note while the roof flag is open", () => {
    const onSignOff = vi.fn();
    const onSignOffOpen = vi.fn();
    const { rerender } = render(
      <TXP03
        fixedAssets={fixedAssets("register", "e0")}
        view="register"
        onSignOff={onSignOff}
        onSignOffOpen={onSignOffOpen}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: COPY.signOff }));
    expect(onSignOffOpen).toHaveBeenCalledWith(true);
    expect(onSignOff).not.toHaveBeenCalled();
    rerender(
      <TXP03
        fixedAssets={fixedAssets("register", "e0")}
        view="register"
        signOffOpen
        onSignOff={onSignOff}
        onSignOffOpen={onSignOffOpen}
      />,
    );
    const dialog = screen.getByRole("dialog", { name: COPY.signOff });
    const sign = within(dialog).getByRole("button", { name: COPY.signOffDialog.signWithNote });
    expect((sign as HTMLButtonElement).disabled).toBe(true);
    fireEvent.change(within(dialog).getByRole("textbox"), {
      target: { value: "Roof invoice requested; 39-yr kept" },
    });
    fireEvent.click(sign);
    expect(onSignOff).toHaveBeenCalledWith("Roof invoice requested; 39-yr kept");
  });

  it("e: signed off reads ✓ SI and Reviewed · SI, with no Sign off…", () => {
    render(
      <TXP03 fixedAssets={fixedAssets("register", "signedOff")} view="register" signedBy="SI" />,
    );
    expect(screen.getByText("✓ SI")).toBeTruthy();
    expect(screen.getByText("Reviewed · SI")).toBeTruthy();
    expect(screen.queryByRole("button", { name: COPY.signOff })).toBeNull();
  });
});
