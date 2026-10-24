import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { PortalBrandProvider } from "../brand/portal-brand";
import { BRIGHTWATER_BRAND } from "../specimens/portal";
import { RequestRowsSpecimen, T7Specimen, Tpl07Specimen } from "../specimens/requests";
import {
  RequestDocuments,
  RequestRail,
  useRequestBinder,
  type RequestBinderProps,
} from "./binder";
import {
  CATEGORIES,
  type RequestItem,
  type RequestSectionData,
  applyUpload,
  categoryState,
  doneButton,
  keep,
  naText,
  route,
  rowView,
  satisfied,
} from "./types";

// F-05-T36 acceptance: "TPL-07a shows exactly two open requests, the drop target uses the 2px
// espresso ring, Mark as Done turns olive in 260 ms, and no red marks a missing item." Plus the
// C-16 rules (request-rows-types.ts) and the kit's behaviour: filter, category, Ignore with a
// reason and Undo, Remove, Reply, the blocked Mark as Done.

afterEach(cleanup);

function board(container: HTMLElement, id: string): HTMLElement {
  const el = container.querySelector<HTMLElement>(`[data-artboard="${id}"]`);
  if (el === null) throw new Error(`no artboard ${id}`);
  return el;
}

describe("TPL-07 (Claire Feld's 2025 Binder)", () => {
  it("TPL-07a shows exactly two open requests, matching Intake 2", () => {
    const { container } = render(<Tpl07Specimen />);
    const a = board(container, "tpl-07a");
    const open = a.querySelectorAll("[data-open-request]");
    expect(open).toHaveLength(2);
    expect([...open].map((el) => el.getAttribute("data-request"))).toEqual(["aca", "est"]);
    expect(within(a).getAllByRole("button", { name: /^Ignore / })).toHaveLength(2);
    expect(within(a).getAllByRole("button", { name: "Upload…" })).toHaveLength(2);
    expect(within(a).getByText("Uploading 2 files…")).toBeTruthy();
  });

  it("no red marks a missing item", () => {
    const { container } = render(<Tpl07Specimen />);
    for (const row of container.querySelectorAll<HTMLElement>('[data-status="req"]')) {
      const classes = [row, ...row.querySelectorAll<HTMLElement>("*")]
        .map((el) => el.getAttribute("class") ?? "")
        .join(" ");
      // The Trash2 hover is red, and only a returned file is; a requested row has neither.
      expect(classes).not.toMatch(/\b(bg|text)-red/);
    }
  });

  it("the drop target uses the 2px espresso ring on the nested fill (TPL-07b)", () => {
    const { container } = render(<Tpl07Specimen />);
    const well = board(container, "tpl-07b").querySelector('[data-part="well"]');
    expect(well?.getAttribute("data-over")).toBe("true");
    expect(well?.className).toContain("inset-ring-2");
    expect(well?.className).toContain("inset-ring-espresso");
    expect(well?.className).toContain("bg-nested");
    expect(board(container, "tpl-07b").querySelector('[data-part="drag-stack"]')).not.toBeNull();
    const plain = board(container, "tpl-07a").querySelector('[data-part="well"]');
    expect(plain?.getAttribute("data-over")).toBe("false");
    expect(plain?.className).not.toContain("inset-ring-espresso");
  });

  it("Mark as Done is tonal while requests are open and olive over 260 ms when all are in", () => {
    const { container } = render(<Tpl07Specimen />);
    const blocked = within(board(container, "tpl-07a")).getByRole("button", {
      name: "Mark as Done",
    });
    expect(blocked.getAttribute("data-ready")).toBe("false");
    expect(blocked.getAttribute("aria-disabled")).toBe("true");
    expect(blocked.hasAttribute("disabled")).toBe(false);
    expect(blocked.className).toContain("bg-chip");
    expect(blocked.title).toBe("2 requests still open");
    const ready = within(board(container, "tpl-07d")).getByRole("button", {
      name: "Mark as Done",
    });
    expect(ready.getAttribute("data-ready")).toBe("true");
    expect(ready.className).toContain("bg-green");
    expect(ready.className).toContain("duration-[260ms]");
    fireEvent.click(ready);
    expect(within(board(container, "tpl-07d")).getByRole("status").textContent).toContain(
      "Marked done Sep 14 · Brightwater Hale will review your documents",
    );
  });

  it("TPL-07c: the matched estimated payments give Other Activity its tick", () => {
    const { container } = render(<Tpl07Specimen />);
    const c = board(container, "tpl-07c");
    expect(within(c).getByText("Matched to this request")).toBeTruthy();
    const other = within(c).getByRole("option", { name: /Other Activity/ });
    expect(other.getAttribute("data-done")).toBe("true");
    const health = within(c).getByRole("option", { name: /Health & Medical/ });
    expect(health.getAttribute("data-done")).toBe("false");
  });

  it("TPL-07e reads You're all caught up; TPL-07f holds the three reasons open", () => {
    const { container } = render(<Tpl07Specimen />);
    expect(within(board(container, "tpl-07e")).getByText("You’re all caught up.")).toBeTruthy();
    expect(
      within(board(container, "tpl-07e")).getByText(
        "Brightwater Hale hasn’t requested anything new.",
      ),
    ).toBeTruthy();
    const menu = within(board(container, "tpl-07f")).getByRole("menu", { name: "Ignore" });
    expect(
      within(menu)
        .getAllByRole("menuitem")
        .map((i) => i.textContent),
    ).toEqual(["Not applicable this year", "Already sent another way", "I don’t have this"]);
  });

  it("TPL-07-M: the 390 binder says 2 to do, with a 44 Upload… target on each open request", () => {
    const { container } = render(<Tpl07Specimen />);
    const m = board(container, "tpl-07-m");
    expect(within(m).getByText("2 to do")).toBeTruthy();
    const uploads = within(m).getAllByRole("button", { name: /^Upload… / });
    expect(uploads).toHaveLength(2);
    for (const u of uploads) expect(u.className).toContain("h-[44px]");
    expect(m.querySelector('[data-shell="mobile-tab-bar"]')).not.toBeNull();
  });

  it("never names the product", () => {
    const { container } = render(<Tpl07Specimen />);
    expect(container.textContent).not.toMatch(/accrued/i);
  });
});

describe("T7 (the template's artboards)", () => {
  it("T7a: every request is open; T7d: Income Sources is complete; T7f is empty", () => {
    const { container } = render(<T7Specimen />);
    expect(board(container, "t7a").querySelectorAll("[data-open-request]")).toHaveLength(9);
    const income = within(board(container, "t7d")).getByRole("option", { name: /Income Sources/ });
    expect(income.getAttribute("data-done")).toBe("true");
    const home = within(board(container, "t7d")).getByRole("option", { name: /Home & Property/ });
    expect(home.getAttribute("data-done")).toBe("false");
    expect(within(board(container, "t7f")).getByText("You’re all caught up.")).toBeTruthy();
  });

  it("T7b shows the uploads with their bars and the follow-up; T7e is ready", () => {
    const { container } = render(<T7Specimen />);
    const b = board(container, "t7b");
    expect(
      within(b)
        .getAllByRole("progressbar")
        .map((p) => p.getAttribute("aria-valuenow")),
    ).toEqual(["68", "31"]);
    expect(within(b).getByText("Needs follow-up")).toBeTruthy();
    expect(within(b).getByRole("button", { name: "Reply…" })).toBeTruthy();
    expect(
      within(board(container, "t7e"))
        .getByRole("button", { name: "Mark as Done" })
        .getAttribute("data-ready"),
    ).toBe("true");
  });

  it("T7g: one 720 pane, no rail, and the header reads Upload…", () => {
    const { container } = render(<T7Specimen />);
    const g = board(container, "t7g");
    expect(g.querySelector('[data-portal="rail"]')).toBeNull();
    expect(g.querySelector('[data-portal="main"]')?.className).toContain("w-[720px]");
    expect(within(g).getAllByRole("button", { name: "Upload…" }).length).toBeGreaterThan(0);
    expect(within(g).getByText("Accepted by Brightwater Hale · Aug 9")).toBeTruthy();
  });

  it("the row-state sheet renders each status", () => {
    render(<RequestRowsSpecimen />);
    expect(screen.getByText("Marked not applicable")).toBeTruthy();
    expect(screen.getAllByText(/Brightwater Hale prepares this K-1/)).toHaveLength(1);
  });
});

// ---- The rules ----------------------------------------------------------------------------------

const SECTIONS: readonly RequestSectionData[] = [
  { key: "w2", category: "income", title: "W-2s", icon: "banknote" },
  { key: "give", category: "charity", title: "Charitable gifts", icon: "hand-heart" },
  { key: "other", category: "other", title: "Other documents you uploaded", icon: "ellipsis" },
];
const REQ = (
  id: string,
  st: RequestItem["st"],
  extra: Partial<RequestItem> = {},
): RequestItem => ({
  id,
  sec: "w2",
  title: id,
  st,
  req: "Sep 8",
  ...extra,
});

describe("C-16 rules", () => {
  it("satisfied: uploaded, accepted, not applicable and firm-provided", () => {
    expect(
      ["up", "acc", "na", "firm"].every((st) => satisfied(REQ("a", st as RequestItem["st"]))),
    ).toBe(true);
    expect(["req", "fu", "ret"].some((st) => satisfied(REQ("a", st as RequestItem["st"])))).toBe(
      false,
    );
  });

  it("keep: Requested hides only extras; Uploaded is up or accepted; category narrows", () => {
    const extra = REQ("x", "up", { extra: true, sec: "other" });
    expect(keep(extra, "requested", null, SECTIONS)).toBe(false);
    expect(keep(extra, "all", null, SECTIONS)).toBe(true);
    expect(keep(REQ("a", "acc"), "uploaded", null, SECTIONS)).toBe(true);
    expect(keep(REQ("a", "fu"), "uploaded", null, SECTIONS)).toBe(false);
    expect(keep(REQ("a", "fu"), "fu", null, SECTIONS)).toBe(true);
    expect(keep(REQ("a", "req"), "requested", "charity", SECTIONS)).toBe(false);
  });

  it("categoryState: done, none and forced", () => {
    const items = [REQ("a", "up"), REQ("b", "req", { sec: "give" })];
    expect(categoryState("income", items, SECTIONS)).toEqual({ done: true, none: false });
    expect(categoryState("charity", items, SECTIONS)).toEqual({ done: false, none: false });
    expect(categoryState("edu", items, SECTIONS)).toEqual({ done: false, none: true });
    expect(categoryState("personal", items, SECTIONS, ["personal"])).toEqual({
      done: true,
      none: false,
    });
  });

  it("doneButton counts open requests and ignores extras", () => {
    const items = [REQ("a", "req"), REQ("b", "fu"), REQ("x", "req", { extra: true })];
    expect(doneButton(items, false)).toMatchObject({ ready: false, open: 2, ariaDisabled: true });
    expect(doneButton([REQ("a", "up")], false)).toMatchObject({
      ready: true,
      ariaDisabled: false,
    });
    expect(doneButton([REQ("a", "up")], true).label).toBe("Marked as Done");
  });

  it("naText leaves out the default reason and quotes the note", () => {
    expect(naText(REQ("a", "na", { reason: "Not applicable this year" }))).toBe(
      "Marked not applicable",
    );
    expect(naText(REQ("a", "na", { reason: "Already sent another way", naNote: "Mailed" }))).toBe(
      "Marked not applicable · Already sent another way · “Mailed”",
    );
  });

  it("rowView: Trash2 only on the client's own upload; Ignore only on a requested row", () => {
    expect(rowView(REQ("a", "up", { on: "Aug 7" }), "Brightwater Hale").trash).toBe(true);
    expect(
      rowView(REQ("a", "up", { upText: "Jonah uploaded Aug 5" }), "Brightwater Hale").trash,
    ).toBe(false);
    expect(rowView(REQ("a", "req"), "Brightwater Hale").ignore).toBe(true);
    expect(rowView(REQ("a", "acc", { on: "Aug 9" }), "Brightwater Hale").accepted).toBe(
      "Accepted by Brightwater Hale · Aug 9",
    );
  });

  it("route: exact name first, then the keyword table, else null; a second file appends", () => {
    const all = [
      REQ("est", "req", { fname: "Feld_2025_Estimated_Payments.pdf" }),
      REQ("aca", "req"),
    ];
    expect(route("feld_2025_estimated_payments.pdf", all)?.id).toBe("est");
    expect(route("scan_1095-c.pdf", all, [["1095-c", "aca"]])?.id).toBe("aca");
    expect(route("unknown.pdf", all)).toBeNull();
    const once = applyUpload(all[0] as RequestItem, "a.pdf", "Sep 14");
    expect(once).toMatchObject({ st: "up", file: "a.pdf", on: "Sep 14", matched: true });
    expect(applyUpload(once, "b.pdf", "Sep 14").files).toEqual(["a.pdf", "b.pdf"]);
  });

  it("the nine categories, in order", () => {
    expect(CATEGORIES.map((c) => c.label)).toEqual([
      "Personal & Household Information",
      "Income Sources",
      "Home & Property",
      "Health & Medical",
      "Education & Student",
      "Retirement",
      "Charitable & Donations",
      "Business & Self-Employment",
      "Other Activity",
    ]);
  });
});

// ---- Behaviour ----------------------------------------------------------------------------------

const ITEMS: readonly RequestItem[] = [
  REQ("w2", "up", { title: "2025 W-2 From Mercer Hill Health", file: "W2.pdf", on: "Aug 3" }),
  REQ("gift", "req", { sec: "give", title: "Receipts for gifts of $250 or more" }),
  REQ("int", "fu", { title: "2025 Form 1099-INT", file: "INT.pdf", note: "This one shows 2024." }),
];

function Binder(props: Partial<RequestBinderProps>): React.JSX.Element {
  const binder = useRequestBinder({
    firm: "Brightwater Hale",
    today: "Sep 14",
    binder: "2025 Binder",
    viewer: { kind: "human", name: "Claire Feld" },
    requests: ITEMS,
    sections: SECTIONS,
    ...props,
  });
  return (
    <PortalBrandProvider brand={BRIGHTWATER_BRAND}>
      <RequestRail binder={binder} />
      <RequestDocuments binder={binder} />
    </PortalBrandProvider>
  );
}

describe("the binder's behaviour", () => {
  it("Ignore with a reason marks it not applicable, with the note; Undo reopens it", () => {
    const onIgnore = vi.fn();
    const onUndoIgnore = vi.fn();
    render(<Binder onIgnore={onIgnore} onUndoIgnore={onUndoIgnore} />);
    fireEvent.click(
      screen.getByRole("button", { name: "Ignore Receipts for gifts of $250 or more" }),
    );
    const menu = screen.getByRole("menu", { name: "Ignore" });
    expect(document.activeElement).toBe(within(menu).getAllByRole("menuitem")[0]);
    fireEvent.change(screen.getByRole("textbox", { name: "Add a note (optional)" }), {
      target: { value: "Mailed" },
    });
    fireEvent.click(within(menu).getByRole("menuitem", { name: "Already sent another way" }));
    expect(onIgnore).toHaveBeenCalledWith("gift", "Already sent another way", "Mailed");
    expect(
      screen.getByText("Marked not applicable · Already sent another way · “Mailed”"),
    ).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Undo" }));
    expect(onUndoIgnore).toHaveBeenCalledWith("gift");
    expect(
      screen.getByRole("button", { name: "Ignore Receipts for gifts of $250 or more" }),
    ).toBeTruthy();
  });

  it("a menu closes on Escape and returns focus to its trigger", () => {
    render(<Binder />);
    const trigger = screen.getByRole("button", {
      name: "Ignore Receipts for gifts of $250 or more",
    });
    fireEvent.click(trigger);
    fireEvent.keyDown(screen.getByRole("menu", { name: "Ignore" }), { key: "Escape" });
    expect(screen.queryByRole("menu", { name: "Ignore" })).toBeNull();
    expect(document.activeElement).toBe(trigger);
  });

  it("Remove returns the request to requested", () => {
    const onRemove = vi.fn();
    render(<Binder onRemove={onRemove} />);
    fireEvent.click(screen.getByRole("button", { name: "Remove W2.pdf" }));
    fireEvent.click(screen.getByRole("menuitem", { name: "Remove file" }));
    expect(onRemove).toHaveBeenCalledWith("w2");
    expect(document.querySelector('[data-request="w2"]')?.getAttribute("data-status")).toBe("req");
  });

  it("Reply sends with Cmd or Ctrl Enter and reads You replied", () => {
    const onReply = vi.fn();
    render(<Binder onReply={onReply} />);
    fireEvent.click(screen.getByRole("button", { name: "Reply…" }));
    const box = screen.getByRole("textbox", { name: "Reply to Brightwater Hale" });
    expect(document.activeElement).toBe(box);
    expect(screen.getByRole("button", { name: "Send" }).hasAttribute("disabled")).toBe(true);
    // Send is a human verb (INV-1): the reply goes out through HumanAction for the viewer.
    expect(screen.getByRole("button", { name: "Send" }).getAttribute("data-human-verb")).toBe(
      "Send",
    );
    fireEvent.change(box, { target: { value: "Uploading the 2025 form now." } });
    fireEvent.keyDown(box, { key: "Enter", metaKey: true });
    expect(onReply).toHaveBeenCalledWith("int", "Uploading the 2025 form now.");
    expect(screen.getByText("You replied Sep 14")).toBeTruthy();
  });

  it("a blocked Mark as Done says how many are open and marks nothing", () => {
    const onBlocked = vi.fn();
    const onMarkDone = vi.fn();
    render(<Binder onBlocked={onBlocked} onMarkDone={onMarkDone} />);
    fireEvent.click(screen.getByRole("button", { name: "Mark as Done" }));
    expect(onBlocked).toHaveBeenCalledWith(2);
    expect(onMarkDone).not.toHaveBeenCalled();
    expect(screen.queryByRole("status")).toBeNull();
  });

  it("the Show filter and a category narrow the list; a second click clears", () => {
    render(<Binder />);
    fireEvent.click(screen.getByRole("button", { name: "Show · Requested" }));
    fireEvent.click(screen.getByRole("menuitemradio", { name: "Needs follow-up" }));
    expect(document.querySelectorAll("[data-request]")).toHaveLength(1);
    fireEvent.click(screen.getByRole("button", { name: "Show · Needs follow-up" }));
    fireEvent.click(screen.getByRole("menuitemradio", { name: "All" }));
    const charity = screen.getByRole("option", { name: /Charitable & Donations/ });
    fireEvent.click(charity);
    expect(charity.getAttribute("aria-selected")).toBe("true");
    expect(document.querySelectorAll("[data-request]")).toHaveLength(1);
    fireEvent.click(charity);
    expect(document.querySelectorAll("[data-request]")).toHaveLength(3);
  });

  it("the CategoryRail moves with the arrows, Home and End", () => {
    render(<Binder />);
    const options = screen.getAllByRole("option");
    act(() => {
      (options[0] as HTMLElement).focus();
    });
    fireEvent.keyDown(options[0] as HTMLElement, { key: "ArrowDown" });
    expect(document.activeElement).toBe(options[1]);
    fireEvent.keyDown(options[1] as HTMLElement, { key: "End" });
    expect(document.activeElement).toBe(options[8]);
    fireEvent.keyDown(options[8] as HTMLElement, { key: "Enter" });
    expect(options[8]?.getAttribute("aria-selected")).toBe("true");
  });

  it("dropped files go out with no request; a live drag rings the well", () => {
    const onFiles = vi.fn();
    const { container } = render(<Binder onFiles={onFiles} />);
    const well = container.querySelector<HTMLElement>('[data-part="well"]') as HTMLElement;
    const file = new File(["x"], "Feld_2025_Donations.pdf");
    fireEvent.dragOver(well, { dataTransfer: { types: ["Files"], files: [file] } });
    expect(well.getAttribute("data-over")).toBe("true");
    fireEvent.drop(well, { dataTransfer: { types: ["Files"], files: [file] } });
    expect(onFiles).toHaveBeenCalledWith([file], null);
    expect(well.getAttribute("data-over")).toBe("false");
  });
});

// R-01-T06: the portal's own screens withdraw an unaccepted upload (DF-15, ADR P-31), mark a
// code-rule link as suggested (DEC-58 a) and draw a closed binder read-only.
describe("the portal's opt-ins (R-01-T06)", () => {
  it("withdraw says Withdraw with the 30-day line", () => {
    const onRemove = vi.fn();
    render(<Binder withdraw onRemove={onRemove} />);
    fireEvent.click(screen.getByRole("button", { name: "Withdraw W2.pdf" }));
    expect(screen.getByRole("menu", { name: "Withdraw" })).toBeTruthy();
    expect(
      screen.getByText(
        "Withdraw this file? Brightwater Hale’s team won’t use it. It’s kept securely for 30 days, then erased.",
      ),
    ).toBeTruthy();
    expect(screen.queryByText(/Remove this file/)).toBeNull();
    fireEvent.click(screen.getByRole("menuitem", { name: "Withdraw file" }));
    expect(onRemove).toHaveBeenCalledWith("w2");
  });

  it("a suggested link reads Suggested — the firm will confirm, never Matched", () => {
    expect(
      rowView(
        REQ("e", "up", { file: "E.pdf", on: "Sep 14", matched: true, suggested: true }),
        "Brightwater Hale",
      ),
    ).toMatchObject({ matched: false, suggested: "Suggested — Brightwater Hale will confirm" });
    expect(
      rowView(REQ("e", "up", { file: "E.pdf", matched: true }), "Brightwater Hale").suggested,
    ).toBeNull();
  });

  it("a read-only binder offers no upload, Ignore, Withdraw or Mark as Done", () => {
    render(<Binder readOnly />);
    expect(screen.queryByRole("button", { name: "Upload…" })).toBeNull();
    expect(screen.queryByRole("button", { name: /^Ignore / })).toBeNull();
    expect(screen.queryByRole("button", { name: /^(Remove|Withdraw) / })).toBeNull();
    expect(screen.queryByRole("button", { name: "Mark as Done" })).toBeNull();
    expect(screen.queryByRole("button", { name: /Reply/ })).toBeNull();
  });
});
