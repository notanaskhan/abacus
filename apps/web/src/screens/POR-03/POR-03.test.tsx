// POR-03 · Documents (R-01-T06 part 1, R-01-T10 part 2). One test per artboard on its fixture
// scenario (a–i, motion, c2, M), the contract's acceptance and AVOID lines, and the tasks'
// acceptance: T06 "Scenario tests for a, c, e, f, g and h pass with axe clean and no firm status
// word, agent name or bell in the DOM" (axe runs in e2e/screens/POR-03.spec.ts, Playwright); T10
// "All twelve POR-03 states render from fixtures and … Claire's three-file drop reproduces c and d
// with the outcome announced in a live region".
import { client } from "@abacus/api-client/client";
import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import {
  type FixtureHandler,
  type Scenario,
  installFixtureMode,
  json,
} from "../../app-core/fixture-mode";
import { renderRoutes } from "../../testing/support";
import { PortalDocuments } from ".";
import { ARTBOARD as ALL_ARTBOARDS, scenarios as all } from "../../fixtures/scenarios/POR-03";
import { FELD_DROP } from "../../fixtures/seed/portal-documents";
import { type Por03State, STATES, scenarios } from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

interface Seen {
  calls: { method: string; path: string; body: unknown }[];
}

function show(
  state: Por03State,
  options: { still?: boolean; over?: Record<string, FixtureHandler> } = {},
): Seen {
  const seen: Seen = { calls: [] };
  const scenario: Scenario = {
    ...all[state],
    handlers: { ...all[state].handlers, ...options.over },
  };
  const handlers = Object.fromEntries(
    Object.entries(scenario.handlers).map(([key, handler]) => [
      key,
      ((request) => {
        seen.calls.push({ method: request.method, path: request.path, body: request.body });
        return handler(request);
      }) satisfies FixtureHandler,
    ]),
  );
  restore = installFixtureMode({ ...scenario, handlers });
  const board = ALL_ARTBOARDS[state];
  renderRoutes([
    {
      path: "/",
      component: () => (
        <PortalDocuments
          binderId={board.binderId}
          mobile={board.mobile === true}
          hold={{
            ...(board.uploads === undefined ? {} : { uploads: board.uploads }),
            ...(board.ignoreOpenOn === undefined ? {} : { ignoreOpenOn: board.ignoreOpenOn }),
            ...(board.dragging === undefined ? {} : { dragging: board.dragging }),
            ...(board.motion === undefined ? {} : { motion: board.motion }),
            ...(board.dropBatch === undefined ? {} : { dropBatch: board.dropBatch }),
            ...(options.still === true ? { still: true } : {}),
          }}
        />
      ),
    },
  ]);
  return seen;
}

async function row(title: string): Promise<HTMLElement> {
  const text = await screen.findByText(title);
  const el = text.closest<HTMLElement>("[data-request]");
  if (el === null) throw new Error(`no row ${title}`);
  return el;
}

const FIRM_WORDS = [
  /Accrued/,
  /\bAgent\b/,
  /Uploaded – needs review/,
  /Received ✓/,
  /In review/,
  /confidence/i,
  /Matched \d+%/,
  /Pending incorporation/,
];

function noFirmWords(): void {
  const text = document.body.textContent;
  for (const word of FIRM_WORDS) expect(text).not.toMatch(word);
  const labels = [...document.querySelectorAll("[aria-label],[title],[alt],[placeholder]")]
    .flatMap((el) => ["aria-label", "title", "alt", "placeholder"].map((a) => el.getAttribute(a)))
    .join(" ");
  for (const word of FIRM_WORDS) expect(labels).not.toMatch(word);
  // No bell (DEC-58 d).
  expect(screen.queryByRole("button", { name: /notification/i })).toBeNull();
  expect(document.querySelector("[data-icon='bell']")).toBeNull();
}

describe("POR-03 artboards (part 1)", () => {
  it("defines a, c, e, f, g and h as Claire Feld at E0", () => {
    expect(STATES).toEqual(expect.arrayContaining(["a", "c", "e", "f", "g", "h"]));
    for (const s of ["a", "c", "e", "f", "g", "h"] as const) {
      expect(scenarios[s].persona).toBe("claire-feld");
      expect(scenarios[s].clock).toBe("2026-09-14T09:24:00-05:00");
    }
  });

  it("POR-03a default: two requests open (Intake 2), two files uploading", async () => {
    show("a");
    expect(await screen.findByText("Form 1095-C From Mercer Hill Health")).toBeTruthy();
    const open = document.querySelectorAll("[data-open-request]");
    expect(open).toHaveLength(2);
    expect(screen.getAllByRole("button", { name: /^Ignore / })).toHaveLength(2);
    expect(screen.getAllByText("Received by email Aug 3")).toHaveLength(2);
    expect(screen.getByText("Jonah uploaded Aug 5")).toBeTruthy();
    expect(screen.getByText("You uploaded Aug 7")).toBeTruthy();
    expect(
      screen.getByText(
        "Brightwater Hale prepares this K-1 and adds it for you. Nothing to upload.",
      ),
    ).toBeTruthy();
    expect(screen.getByText("Uploading 2 files…")).toBeTruthy();
    expect(screen.getByText("Feld_2025_Estimated_Payments.pdf")).toBeTruthy();
    expect(screen.getByText("Feld_2025_IT2105_Confirmations.pdf")).toBeTruthy();
    const done = screen.getByRole("button", { name: "Mark as Done" });
    expect(done.getAttribute("data-ready")).toBe("false");
    expect(screen.getByRole("button", { name: "Upload something else" })).toBeTruthy();
    noFirmWords();
  });

  it("POR-03a ticks the rail by the rule and lists the closed 2024 binder", async () => {
    show("a");
    await screen.findByText("Form 1095-C From Mercer Hill Health");
    const rail = screen.getByRole("listbox", { name: /categor/i });
    const ticked = within(rail)
      .getAllByRole("option")
      .filter((o) => o.getAttribute("data-done") === "true")
      .map((o) => o.textContent);
    expect(ticked).toEqual([
      "Personal & Household Information",
      "Income Sources",
      "Home & Property",
      "Charitable & Donations",
    ]);
    fireEvent.click(screen.getByRole("button", { name: /2025 Binder/ }));
    const menu = screen.getByRole("menu", { name: "Binder" });
    expect(within(menu).getByRole("menuitemradio", { name: "2024 Binder (closed)" })).toBeTruthy();
  });

  it("POR-03c: the estimated payments read Suggested — Brightwater Hale will confirm", async () => {
    show("c");
    const est = await row(
      "2025 federal (1040-ES) and New York (IT-2105) estimated payment confirmations",
    );
    expect(within(est).getByText("Feld_2025_Estimated_Payments.pdf")).toBeTruthy();
    expect(within(est).getByText("Feld_2025_IT2105_Confirmations.pdf")).toBeTruthy();
    expect(within(est).getByText("You uploaded Sep 14")).toBeTruthy();
    expect(within(est).getByText("Suggested — Brightwater Hale will confirm")).toBeTruthy();
    expect(within(est).queryByText("Matched to this request")).toBeNull();
    expect(document.querySelectorAll("[data-open-request]")).toHaveLength(1);
    expect(screen.getByRole("button", { name: "Mark as Done" }).getAttribute("data-ready")).toBe(
      "false",
    );
    noFirmWords();
  });

  it("POR-03e: marked done, the green-tint banner with Undo, and Undo reaches the server", async () => {
    const seen = show("e");
    expect(
      await screen.findByText("Marked done Sep 14 · Brightwater Hale will review your documents"),
    ).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Undo" }));
    await waitFor(() => {
      expect(seen.calls.some((c) => c.path.endsWith("/mark-done/undo"))).toBe(true);
    });
    noFirmWords();
  });

  it("POR-03f: Ignore holds the three reasons and a note; choosing one ignores with its code", async () => {
    const seen = show("f");
    const menu = await screen.findByRole("menu", { name: "Ignore" });
    const reasons = within(menu)
      .getAllByRole("menuitem")
      .map((b) => b.textContent);
    expect(reasons).toEqual([
      "Not applicable this year",
      "Already sent another way",
      "I don’t have this",
    ]);
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "No 1095-C this year." } });
    fireEvent.click(within(menu).getByRole("menuitem", { name: "Already sent another way" }));
    await waitFor(() => {
      const call = seen.calls.find((c) => c.path.endsWith("/ignore"));
      expect(call?.body).toEqual({ reason: "sent_another_way", note: "No 1095-C this year." });
    });
    const form = await row("Form 1095-C From Mercer Hill Health");
    expect(within(form).getByRole("button", { name: "Undo" })).toBeTruthy();
    noFirmWords();
  });

  it("POR-03g: returned by the firm, red-tint, with Kevin Osei's note and Upload…", async () => {
    show("g");
    const form = await row("Form 1095-C From Mercer Hill Health");
    const pill = within(form).getByText("Returned · wrong year");
    expect(pill.className).toContain("bg-red-tint");
    expect(
      within(form).getByText("This is the 2024 form. We need the 2025 Form 1095-C. — Kevin Osei"),
    ).toBeTruthy();
    expect(within(form).getByText("Feld_1095C_2024.pdf")).toBeTruthy();
    expect(within(form).getByRole("button", { name: "Upload…" })).toBeTruthy();
    noFirmWords();
  });

  it("POR-03h: nothing requested — You’re all caught up.", async () => {
    show("h");
    expect(await screen.findByText("You’re all caught up.")).toBeTruthy();
    expect(screen.getByText("Brightwater Hale hasn’t requested anything new.")).toBeTruthy();
    noFirmWords();
  });
});

describe("POR-03 behaviour", () => {
  it("Withdraw asks with the DF-15 line and withdraws Claire's own unaccepted file", async () => {
    const seen = show("a");
    const gifts = await row("2025 donation receipts and acknowledgment letters");
    fireEvent.click(
      within(gifts).getByRole("button", { name: "Withdraw Feld_2025_Donations.pdf" }),
    );
    expect(
      screen.getByText(
        "Withdraw this file? Brightwater Hale’s team won’t use it. It’s kept securely for 30 days, then erased.",
      ),
    ).toBeTruthy();
    fireEvent.click(screen.getByRole("menuitem", { name: "Withdraw file" }));
    await waitFor(() => {
      expect(seen.calls.some((c) => c.path.endsWith("/withdraw"))).toBe(true);
    });
  });

  it("no Withdraw on an emailed or another contact's file", async () => {
    show("a");
    const w2 = await row("2025 W-2 From Mercer Hill Health");
    expect(within(w2).queryByRole("button", { name: /^Withdraw/ })).toBeNull();
    const halvard = await row("2025 Consolidated 1099 From Halvard Securities (Acct ••3318)");
    expect(within(halvard).queryByRole("button", { name: /^Withdraw/ })).toBeNull();
  });

  it("Mark as Done turns olive once nothing is open, then marks the binder with a banner", async () => {
    // c2's data (part 2's artboard): the emailed 1095-C filed, nothing open.
    const seen = show("c2");
    const done = await screen.findByRole("button", { name: "Mark as Done" });
    expect(done.getAttribute("data-ready")).toBe("true");
    fireEvent.click(done);
    expect(
      await screen.findByText("Marked done Sep 14 · Brightwater Hale will review your documents"),
    ).toBeTruthy();
    await waitFor(() => {
      expect(seen.calls.some((c) => c.path.endsWith("/mark-done"))).toBe(true);
    });
  });

  it("the closed 2024 binder opens read-only", async () => {
    show("a");
    await screen.findByText("Form 1095-C From Mercer Hill Health");
    fireEvent.click(screen.getByRole("button", { name: /2025 Binder/ }));
    fireEvent.click(screen.getByRole("menuitemradio", { name: "2024 Binder (closed)" }));
    await waitFor(() => {
      expect(screen.queryByText("Form 1095-C From Mercer Hill Health")).toBeNull();
    });
    expect(screen.queryByRole("button", { name: "Mark as Done" })).toBeNull();
    expect(screen.queryByRole("button", { name: /^Ignore / })).toBeNull();
    expect(screen.queryByRole("button", { name: "Upload…" })).toBeNull();
  });
});

describe("POR-03 AVOID", () => {
  it("no red on a requested row; only Returned uses red-tint", async () => {
    show("a");
    await screen.findByText("Form 1095-C From Mercer Hill Health");
    for (const el of document.querySelectorAll<HTMLElement>('[data-status="req"]')) {
      const classes = [el, ...el.querySelectorAll<HTMLElement>("*")]
        .map((x) => x.getAttribute("class") ?? "")
        .join(" ");
      expect(classes).not.toMatch(/\b(bg|text)-red/);
    }
  });

  it("no checkboxes and no confidence percentages", async () => {
    show("c");
    await screen.findByText("Suggested — Brightwater Hale will confirm");
    expect(screen.queryAllByRole("checkbox")).toHaveLength(0);
    expect(document.body.textContent).not.toMatch(/\d+%/);
  });
});

describe("POR-03 artboards (part 2, R-01-T10)", () => {
  const SORTED = "2 files matched a request. 1 file sent to Brightwater Hale to sort.";
  const ESTIMATES =
    "2025 federal (1040-ES) and New York (IT-2105) estimated payment confirmations";

  it("all twelve states are fixture scenarios with their personas", () => {
    expect(STATES).toEqual(["a", "motion", "b", "c", "c2", "d", "e", "f", "g", "h", "i", "M"]);
    expect(scenarios.i.persona).toBe("dana-kowalski");
    expect(scenarios.c2.clock).toBe("2026-09-14T09:12:00-05:00");
    for (const s of STATES.filter((x) => x !== "i")) {
      expect(scenarios[s].persona).toBe("claire-feld");
    }
  });

  it("POR-03b drop target: three files over the list, the well on --nested with the espresso ring", async () => {
    show("b");
    await screen.findByText("Form 1095-C From Mercer Hill Health");
    const well = document.querySelector<HTMLElement>("[data-part='well']");
    expect(well?.getAttribute("data-over")).toBe("true");
    expect(well?.className).toMatch(/bg-nested/);
    expect(well?.className).toMatch(/inset-ring-espresso/);
    const stack = document.querySelector<HTMLElement>("[data-part='drag-stack']");
    expect(stack?.textContent).toContain("Feld_2025_Estimated_Payments.pdf");
    expect(stack?.textContent).toContain("Feld_2025_IT2105_Confirmations.pdf");
    expect(stack?.textContent).toContain("Scan_0914.pdf");
    expect(screen.getByText("Drop to sort into your binder")).toBeTruthy();
  });

  it("POR-03 motion: the packet and '3 files', then the rows rise 135ms apart into c and d", async () => {
    show("motion");
    await screen.findByText("Form 1095-C From Mercer Hill Health");
    const stack = document.querySelector<HTMLElement>("[data-part='drag-stack']");
    expect(stack?.textContent).toContain("3 files");
    await waitFor(
      () => {
        expect(document.querySelector("[data-part='drag-stack']")).toBeNull();
      },
      { timeout: 3000 },
    );
    const rows = [...document.querySelectorAll<HTMLElement>("[data-request]")];
    expect(rows.length).toBeGreaterThan(2);
    expect(rows.every((r) => r.classList.contains("motion-reveal"))).toBe(true);
    expect(rows.slice(0, 3).map((r) => r.style.animationDelay)).toEqual(["0ms", "135ms", "270ms"]);
    expect(await screen.findByText("Scan_0914.pdf")).toBeTruthy();
    await waitFor(() => {
      expect(document.querySelector("[data-part='sort-live']")?.textContent).toBe(SORTED);
    });
  });

  it("POR-03 motion under ?static=1 (and reduced motion) opens on the sorted frame, still", async () => {
    show("motion", { still: true });
    expect(await screen.findByText("Scan_0914.pdf")).toBeTruthy();
    expect(document.querySelector("[data-part='drag-stack']")).toBeNull();
    expect(document.querySelector(".motion-reveal")).toBeNull();
    const est = await row(ESTIMATES);
    expect(within(est).getByText("Suggested — Brightwater Hale will confirm")).toBeTruthy();
  });

  it("POR-03c from drop polling: the batch is read until settled and the outcome is announced", async () => {
    const seen = show("c");
    const est = await row(ESTIMATES);
    expect(within(est).getByText("Suggested — Brightwater Hale will confirm")).toBeTruthy();
    await waitFor(() => {
      expect(document.querySelector("[data-part='sort-live']")?.textContent).toBe(SORTED);
    });
    const live = document.querySelector("[data-part='sort-live']");
    expect(live?.getAttribute("role")).toBe("status");
    expect(live?.getAttribute("aria-live")).toBe("polite");
    expect(seen.calls.some((c) => c.path.startsWith("/v1/portal/drops/"))).toBe(true);
    const rail = screen.getByRole("listbox", { name: /categor/i });
    const ticked = within(rail)
      .getAllByRole("option")
      .filter((o) => o.getAttribute("data-done") === "true")
      .map((o) => o.textContent);
    expect(ticked).toContain("Other Activity");
    expect(ticked).not.toContain("Health & Medical");
    noFirmWords();
  });

  // Mark as Done turning olive on c2 is part 1's test ("Mark as Done turns olive once nothing is
  // open"), which then marks the binder in the scenario's handlers.
  it("POR-03c2: the 9:12 AM email filed to the 1095-C; nothing left open", async () => {
    show("c2");
    const form = await row("Form 1095-C From Mercer Hill Health");
    expect(within(form).getByText("Feld_1095C_2025.pdf")).toBeTruthy();
    expect(within(form).getByText("Received by email Sep 14")).toBeTruthy();
    expect(within(form).queryByRole("button", { name: /Withdraw/ })).toBeNull();
    expect(document.querySelectorAll("[data-open-request]")).toHaveLength(0);
    const rail = screen.getByRole("listbox", { name: /categor/i });
    const ticked = within(rail)
      .getAllByRole("option")
      .filter((o) => o.getAttribute("data-done") === "true")
      .map((o) => o.textContent);
    expect(ticked).toHaveLength(6);
    expect(ticked).toContain("Health & Medical");
  });

  it("POR-03d: Scan_0914.pdf matched no request — Brightwater Hale will sort this", async () => {
    show("d");
    const card = await screen.findByRole("group", { name: "Brightwater Hale will sort this" });
    expect(within(card).getByText("Scan_0914.pdf")).toBeTruthy();
    expect(
      within(card).getByText(
        "We couldn’t tell which request this belongs to. Your team will file it.",
      ),
    ).toBeTruthy();
    expect(within(card).queryByText(/\d+\s?%/)).toBeNull();
    noFirmWords();
  });

  it("POR-03i audit variant: Dana's own requests in folder bands with discs", async () => {
    show("i");
    expect(await screen.findByText("Employee census file — 2025")).toBeTruthy();
    expect(screen.getByRole("button", { name: /PY2025 Audit requests/ })).toBeTruthy();
    expect(
      screen.getByText("Some requests go to Keystone, Harborline, PayGrid and Summit directly."),
    ).toBeTruthy();
    const census = screen.getByRole("group", { name: "Census & Payroll" });
    expect(within(census).getByText("1 of 4")).toBeTruthy();
    expect(within(census).getByText("You uploaded Sep 2")).toBeTruthy();
    expect(within(census).getByText("Due Sep 18")).toBeTruthy();
    expect(within(census).getAllByRole("img", { name: "To do" })).toHaveLength(3);
    expect(within(census).getAllByRole("img", { name: "Done" })).toHaveLength(1);
    expect(
      within(screen.getByRole("group", { name: "Plan documents" })).getByText("0 of 1"),
    ).toBeTruthy();
    expect(
      within(screen.getByRole("group", { name: "Compliance" })).getByText("0 of 1"),
    ).toBeTruthy();
    expect(screen.getAllByRole("button", { name: /^Upload… / })).toHaveLength(5);
    expect(screen.queryByRole("button", { name: /^Ignore / })).toBeNull();
    expect(screen.getByText("3 open")).toBeTruthy();
    expect(screen.getAllByText("1 open")).toHaveLength(2);
    // Only Dana's own requests; the delegated organisations are named, never their requests.
    expect(document.querySelectorAll("[data-request]")).toHaveLength(6);
    expect(screen.queryByText(/Keystone Retirement Services/)).toBeNull();
    noFirmWords();
  });

  it("POR-03-M mobile 390: '2 to do', tap to upload or take a photo, Mark as Done sticky", async () => {
    show("M");
    expect(await screen.findByText("2 to do")).toBeTruthy();
    expect(document.querySelector("[data-variant='portal-mobile']")).not.toBeNull();
    expect(screen.getByRole("button", { name: "Tap to upload or take a photo" })).toBeTruthy();
    const input = document.querySelector<HTMLInputElement>("input[type='file']");
    expect(input?.accept).toContain("image/heic");
    expect(input?.accept).toContain("image/jpeg");
    const footer = document.querySelector("[data-portal='mobile-footer']");
    expect(
      within(footer as HTMLElement).getByRole("button", { name: "Mark as Done" }),
    ).toBeTruthy();
    const bar = screen.getByRole("navigation", { name: "Portal" });
    expect(
      within(bar).getByRole("button", { name: "Documents" }).getAttribute("aria-current"),
    ).toBe("page");
    noFirmWords();
  });

  it("DEC-463: at 390 the audit variant keeps its other-parties note and a row opens its request", async () => {
    restore = installFixtureMode(all.i);
    const opened: string[] = [];
    renderRoutes([
      {
        path: "/",
        component: () => (
          <PortalDocuments
            binderId={ALL_ARTBOARDS.i.binderId}
            mobile
            onOpenRequest={(id) => {
              opened.push(id);
            }}
          />
        ),
      },
    ]);
    expect(await screen.findByText("Employee census file — 2025")).toBeTruthy();
    expect(
      screen.getByText("Some requests go to Keystone, Harborline, PayGrid and Summit directly."),
    ).toBeTruthy();
    const open = screen.getByRole("button", { name: /^W-3 for 2025/ });
    fireEvent.click(open);
    expect(opened).toEqual([open.closest("[data-request]")?.getAttribute("data-request")]);
    expect(screen.queryByText(/Keystone Retirement Services/)).toBeNull();
    noFirmWords();
  });

  it("R-01-T10 acceptance: Claire's three-file drop posts one batch, polls it and announces c and d", async () => {
    const seen = show("a", {
      over: {
        "POST /v1/portal/binders/{binder_id}/drops": () =>
          json({ batch_id: FELD_DROP.batch_id, file_id: FELD_DROP.files[0]?.file_id }, 202),
        "GET /v1/portal/drops/{batch_id}": ({ params }) =>
          params.batch_id === FELD_DROP.batch_id ? json(FELD_DROP) : json({ detail: "x" }, 404),
      },
    });
    await screen.findByText("Form 1095-C From Mercer Hill Health");
    const well = document.querySelector<HTMLElement>("[data-part='well']");
    const files = [
      "Feld_2025_Estimated_Payments.pdf",
      "Feld_2025_IT2105_Confirmations.pdf",
      "Scan_0914.pdf",
    ].map((name) => new File(["%PDF-1.7"], name, { type: "application/pdf" }));
    fireEvent.drop(well as HTMLElement, { dataTransfer: { files, types: ["Files"] } });
    await waitFor(() => {
      expect(document.querySelector("[data-part='sort-live']")?.textContent).toBe(SORTED);
    });
    const posts = seen.calls.filter((c) => c.method === "POST" && c.path.endsWith("/drops"));
    expect(posts).toHaveLength(3);
    expect(seen.calls.some((c) => c.path.startsWith("/v1/portal/drops/"))).toBe(true);
    expect(await screen.findByText("Scan_0914.pdf")).toBeTruthy();
  });

  it("a drop the policy refuses names the file and the limit, in the C-20 grammar", async () => {
    show("a", {
      over: {
        "POST /v1/portal/binders/{binder_id}/drops": () => json({ detail: "file_too_large" }, 413),
      },
    });
    await screen.findByText("Form 1095-C From Mercer Hill Health");
    const well = document.querySelector<HTMLElement>("[data-part='well']");
    const big = new File(["x"], "Scan_big.pdf", { type: "application/pdf" });
    fireEvent.drop(well as HTMLElement, { dataTransfer: { files: [big], types: ["Files"] } });
    const list = await screen.findByRole("list", { name: "Files not uploaded" });
    expect(
      within(list).getByText(
        "Scan_big.pdf is larger than 50 MB. Send a smaller copy or split it into parts.",
      ),
    ).toBeTruthy();
    expect(list.querySelector(".text-red-ink, .bg-red-tint")).toBeNull();
  });
});
