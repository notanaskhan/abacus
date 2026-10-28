// CLI-06 · New client / prospect intake (P-07-T49, P-07-T54; docs/screens/CLI-06.md). One test per
// artboard a–i on its fixture scenario, and the acceptances: "Scenarios a to f, h and i pass with
// axe and Create and start acceptance lands on CLI-07" (T49) and "Scenario g passes with axe and
// the toast reads 210 records imported, 2 skipped, 0 new clients" (T54; axe:
// e2e/screens/CLI-06.spec.ts, Playwright). Also: Next validates each step, step rows jump only to
// finished steps, a person records screening, a manager clears a hit, the import foots
// (204 + 8 + 0 = 212; 212 − 2 = 210), nothing below 90% merges without a person, and the AVOID
// list.
import { client } from "@abacus/api-client/client";
import { toastStore } from "@abacus/ui";
import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import {
  type FixtureHandler,
  type Scenario,
  installFixtureMode,
} from "../../app-core/fixture-mode";
import { renderRoutes } from "../../testing/support";
import { toImport } from "../../domain/clients";
import { buildClients } from "../../fixtures/seed/clients";
import { CLI06, type Cli06Target } from ".";
import { COPY } from "./copy";
import {
  type Cli06State,
  DRAFT_ID,
  IMPORT_ID,
  OPENS,
  STATES,
  freshScenario,
  importRows,
} from "./scenarios";

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
  body: unknown;
  query: URLSearchParams;
}

function install(scenario: Scenario): Call[] {
  const calls: Call[] = [];
  const handlers = Object.fromEntries(
    Object.entries(scenario.handlers).map(([key, handler]) => [
      key,
      ((request) => {
        calls.push({
          method: request.method,
          path: request.path,
          body: request.body,
          query: request.query,
        });
        return handler(request);
      }) satisfies FixtureHandler,
    ]),
  );
  restore = installFixtureMode({ ...scenario, handlers });
  return calls;
}

function show(state: Cli06State, onNavigate?: (t: Cli06Target) => void): Call[] {
  const calls = install(freshScenario(state));
  const opens = OPENS[state];
  renderRoutes([
    {
      path: "/",
      component: () => (
        <CLI06
          draftId={DRAFT_ID}
          step={opens.step}
          {...(opens.problems === undefined ? {} : { problems: opens.problems })}
          screened={opens.screened === true}
          {...(opens.bulk === undefined
            ? {}
            : {
                mode: "bulk" as const,
                importId: opens.bulk.importId,
                importStep: opens.bulk.step,
              })}
          {...(onNavigate === undefined ? {} : { onNavigate })}
        />
      ),
    },
  ]);
  return calls;
}

function next(): void {
  fireEvent.click(screen.getByRole("button", { name: "Next" }));
}

describe("CLI-06 artboards", () => {
  it("has a scenario for every artboard, the bulk import's g among them", () => {
    expect(STATES).toEqual(["a", "b", "c", "d", "e", "f", "g", "h", "i"]);
  });

  it("a: four names searched, No conflicts, screening recorded by a person", async () => {
    show("a");
    expect(await screen.findByText(COPY.conflicts.none)).toBeTruthy();
    expect(screen.getByText(/^Searched 4 names across every client/)).toBeTruthy();
    expect(screen.getByText("Same family · not adverse")).toBeTruthy();
    expect(screen.getAllByText(/ · Recorded by /)).toHaveLength(3);
  });

  it("b: the dedupe card recommends adding the estate under Walter Thornbury", async () => {
    show("b");
    expect(await screen.findByText(COPY.dedupe.match(96, "Walter Thornbury"))).toBeTruthy();
    const radio = screen.getByRole("radio", { name: COPY.dedupe.recommended });
    expect(radio.getAttribute("aria-checked")).toBe("true");
  });

  it("c: the decedent and the executor, and the fiduciary disclosure rule", async () => {
    show("c");
    expect(
      await screen.findByText(
        COPY.relationships.decedent("Walter Thornbury", "Estate of Walter Thornbury"),
      ),
    ).toBeTruthy();
    expect(screen.getByText(COPY.relationships.executor("Paul Thornbury"))).toBeTruthy();
    expect(screen.getByText(COPY.relationships.note)).toBeTruthy();
  });

  it("d: Paul Thornbury, executor", async () => {
    show("d");
    expect(await screen.findByDisplayValue("Paul Thornbury")).toBeTruthy();
    expect(screen.getByDisplayValue("paul.thornbury@thornburylaw.com")).toBeTruthy();
  });

  it("e: the services, Form 706 among them", async () => {
    show("e");
    const box = await screen.findByRole("checkbox", { name: "Form 706" });
    expect(box.getAttribute("aria-checked")).toBe("true");
    expect(
      screen.getByRole("checkbox", { name: "Estate Form 1041" }).getAttribute("aria-checked"),
    ).toBe("true");
  });

  it("f: Create & start acceptance lands on CLI-07 (Prospect only)", async () => {
    const onNavigate = vi.fn();
    const calls = show("f", onNavigate);
    fireEvent.click(await screen.findByRole("button", { name: COPY.review.createStart }));
    await waitFor(() => {
      expect(onNavigate).toHaveBeenCalled();
    });
    const target = onNavigate.mock.calls[0]?.[0] as Cli06Target;
    expect(target.screen).toBe("CLI-07");
    const commit = calls.find((c) => c.path.endsWith("/commit"));
    expect(commit?.body).toEqual({ start_acceptance: true });
  });

  it("f: Create lands on CLI-02", async () => {
    const onNavigate = vi.fn();
    show("f", onNavigate);
    fireEvent.click(await screen.findByRole("button", { name: COPY.review.create }));
    await waitFor(() => {
      expect((onNavigate.mock.calls[0]?.[0] as Cli06Target | undefined)?.screen).toBe("CLI-02");
    });
  });

  it("h: a counterparty to review, cleared as not adverse by Samuel Ito", async () => {
    const calls = show("h");
    expect(await screen.findByText("Harborline Trust Company")).toBeTruthy();
    expect(screen.queryByText(COPY.conflicts.none)).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: COPY.conflicts.clear }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.change(within(dialog).getByRole("textbox"), {
      target: { value: "Custodian only; no adverse interest." },
    });
    fireEvent.click(within(dialog).getByRole("button", { name: COPY.conflicts.clearConfirm }));
    await waitFor(() => {
      expect(calls.some((c) => c.path.endsWith("/clear"))).toBe(true);
    });
  });

  it("i: Date of death empty says why", async () => {
    show("i");
    expect(await screen.findByText("Required for Form 706 due date")).toBeTruthy();
  });

  it("i: Next on Services stops and jumps to Entity details with the reason", async () => {
    install(freshScenario("i"));
    renderRoutes([{ path: "/", component: () => <CLI06 draftId={DRAFT_ID} step="services" /> }]);
    await screen.findByRole("checkbox", { name: "Form 706" });
    next();
    expect(await screen.findByText("Required for Form 706 due date")).toBeTruthy();
    expect(screen.getByDisplayValue("Estate of Walter Thornbury")).toBeTruthy();
  });
});

describe("CLI-06 steps", () => {
  it("rows jump only to finished steps", async () => {
    show("c");
    await screen.findByText(COPY.relationships.note);
    fireEvent.click(screen.getByText(COPY.steps.review));
    expect(screen.queryByRole("button", { name: COPY.review.create })).toBeNull();
    fireEvent.click(screen.getByText(COPY.steps.entity));
    expect(await screen.findByDisplayValue("Estate of Walter Thornbury")).toBeTruthy();
  });

  it("Next saves and validates the step before moving on", async () => {
    const calls = show("b");
    await screen.findByText(COPY.dedupe.match(96, "Walter Thornbury"));
    next();
    expect(await screen.findByText(COPY.relationships.note)).toBeTruthy();
    expect(calls.some((c) => c.method === "PATCH")).toBe(true);
    expect(calls.some((c) => c.path.endsWith("/validate"))).toBe(true);
  });
});

describe("CLI-06 avoid", () => {
  it("no automated screening result: each list waits for a person", async () => {
    show("h");
    await screen.findByText("Harborline Trust Company");
    expect(screen.getAllByRole("button", { name: COPY.conflicts.record })).toHaveLength(3);
    expect(document.body.innerHTML).not.toMatch(/gradient|lorem/i);
  });
});

describe("CLI-06 g · bulk import", () => {
  const run = COPY.import.run;

  it("g: the tallies, the eight to review, rows 7 and 8 skipped, Import 210 records", async () => {
    show("g");
    expect(
      await screen.findByText("CCH Axcess Tax · client list · 212 records · pulled 2:04 PM"),
    ).toBeTruthy();
    const strip = screen.getByRole("list", { name: COPY.import.tally.label });
    expect(within(strip).getByText(COPY.import.tally.matched)).toBeTruthy();
    expect(within(strip).getByText("204")).toBeTruthy();
    expect(within(strip).getByText("8")).toBeTruthy();
    expect(within(strip).getByText("0")).toBeTruthy();
    const table = screen.getByRole("table", { name: COPY.import.table });
    expect(within(table).getAllByRole("row")).toHaveLength(9); // the heading and eight rows
    expect(within(table).getByText("Harbourview Dental Properties LP")).toBeTruthy();
    expect(within(table).getByText("84%")).toBeTruthy();
    const seven = screen.getByRole("tablist", {
      name: COPY.import.decisionLabel("Harbourview Dental Properties LP"),
    });
    expect(within(seven).getByRole("tab", { name: "Skip" }).getAttribute("aria-selected")).toBe(
      "true",
    );
    expect(screen.getByRole("button", { name: run(210) })).toBeTruthy();
  });

  it("g foots: 204 + 8 + 0 = 212 and 212 − 2 = 210; every match is a seed client", () => {
    const rows = importRows();
    expect(rows).toHaveLength(212);
    const review = rows.filter((r) => (r.score ?? 1) < 0.9);
    expect(rows.length - review.length).toBe(204);
    expect(review).toHaveLength(8);
    expect(review.map((r) => r.row_no)).toEqual([7, 8, 10, 15, 30, 33, 34, 38]);
    expect(rows.filter((r) => r.best_match_client_id == null)).toHaveLength(0);
    const counts = { rows: 212, matched: 204, to_review: 8, new: 0 };
    expect(counts.matched + counts.to_review + counts.new).toBe(counts.rows);
    expect(toImport(counts, review)).toBe(210);
    const names = new Set(
      buildClients().map((c) =>
        c.name === "Estate of Walter Thornbury" ? "Walter Thornbury" : c.name,
      ),
    );
    expect(rows.filter((r) => !names.has(r.best_match_name ?? ""))).toHaveLength(0);
    expect(new Set(rows.map((r) => r.display_name)).size).toBe(212);
  });

  it("an undecided row is left out of the count: it is skipped at the run (DEC-643)", () => {
    const counts = { rows: 212, matched: 204, to_review: 8, new: 0 };
    const review = importRows().filter((r) => (r.score ?? 1) < 0.9);
    const undecided = review.map((r, i) => (i === 2 ? { ...r, decision: null } : r));
    expect(toImport(counts, undecided)).toBe(209);
  });

  it("a person's decision is saved as made: row 7 merged into its match", async () => {
    const calls = show("g");
    const seven = await screen.findByRole("tablist", {
      name: COPY.import.decisionLabel("Harbourview Dental Properties LP"),
    });
    fireEvent.click(within(seven).getByRole("tab", { name: "Merge" }));
    await waitFor(() => {
      expect(calls.some((c) => c.method === "PUT" && c.path.endsWith("/decision"))).toBe(true);
    });
    const put = calls.find((c) => c.method === "PUT");
    expect(put?.body).toMatchObject({ decision: "merge" });
    expect((put?.body as { merge_client_id?: string }).merge_client_id).toBeTruthy();
    expect(await screen.findByRole("button", { name: run(211) })).toBeTruthy();
  });

  it("Import 210 records runs once, says Importing 210 records…, then toasts the counts", async () => {
    const calls = show("g");
    fireEvent.click(await screen.findByRole("button", { name: run(210) }));
    expect(await screen.findByText(COPY.import.progress(210))).toBeTruthy();
    expect(calls.filter((c) => c.path.endsWith("/run"))).toHaveLength(1);
    const text = COPY.import.toast(210, 2, 0);
    expect(text).toBe("210 records imported · 2 skipped · 0 new clients");
    await waitFor(
      () => {
        expect(toastStore.list().some((t) => t.text === text)).toBe(true);
      },
      { timeout: 4000 },
    );
    expect(screen.getByText(text)).toBeTruthy();
    expect(screen.queryByRole("button", { name: run(210) })).toBeNull();
  });

  it("uploading a file maps its headings, then reviews the duplicates", async () => {
    const calls = install(freshScenario("g"));
    renderRoutes([{ path: "/", component: () => <CLI06 mode="bulk" /> }]);
    const input = await screen.findByLabelText(COPY.import.choose, { selector: "input" });
    const file = new File(
      ["Client ID,Client Name\r\nBH10001,Northwind Robotics, Inc.\r\n"],
      "list.csv",
      {
        type: "text/csv",
      },
    );
    fireEvent.change(input, { target: { files: [file] } });
    expect(await screen.findByText(COPY.import.chosen("list.csv"))).toBeTruthy();
    next();
    expect(await screen.findByRole("table", { name: COPY.import.mapTitle })).toBeTruthy();
    expect(screen.getByText("Client Name")).toBeTruthy();
    expect(screen.getByText(COPY.import.fields.client_name ?? "")).toBeTruthy();
    const upload = calls.find((c) => c.method === "POST" && c.path === "/v1/client-imports");
    expect(upload?.query.get("filename")).toBe("list.csv");
    expect(upload?.query.get("source")).toBe("cch_axcess_tax_export");
    next();
    expect(await screen.findByRole("table", { name: COPY.import.table })).toBeTruthy();
  });

  it("a file the import can't read says why", async () => {
    const scenario = freshScenario("g");
    install({
      ...scenario,
      handlers: {
        ...scenario.handlers,
        "POST /v1/client-imports": () =>
          new Response(
            JSON.stringify({ detail: "import_file_invalid", facts: { reason: "not_cch_export" } }),
            { status: 422, headers: { "Content-Type": "application/json" } },
          ),
      },
    });
    renderRoutes([{ path: "/", component: () => <CLI06 mode="bulk" /> }]);
    const input = await screen.findByLabelText(COPY.import.choose, { selector: "input" });
    fireEvent.change(input, { target: { files: [new File(["Name\r\nX\r\n"], "x.csv")] } });
    await screen.findByText(COPY.import.chosen("x.csv"));
    next();
    expect(await screen.findByText(COPY.import.fileErrors.not_cch_export ?? "")).toBeTruthy();
  });

  it("the header switches between a single client and the bulk import", async () => {
    show("b");
    await screen.findByText(COPY.dedupe.match(96, "Walter Thornbury"));
    fireEvent.click(screen.getByRole("tab", { name: COPY.mode.bulk }));
    expect(await screen.findByRole("button", { name: COPY.import.choose })).toBeTruthy();
    expect(screen.getByText(COPY.import.steps.review)).toBeTruthy();
  });

  it("nothing below 90% is merged without a person; g's import id is the scenario's", () => {
    const below = importRows().filter((r) => (r.score ?? 1) < 0.9);
    expect(below.every((r) => r.decided_by != null)).toBe(true);
    expect(OPENS.g.bulk?.importId).toBe(IMPORT_ID);
  });
});
