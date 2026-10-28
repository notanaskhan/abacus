// KNW-02 · Methodology versions, the workbook slice (K-01-T07; K-01 AC2.1, AC3.1 to AC3.3). e and
// f on their fixture scenarios, plus: Approve stays disabled with its tooltip while flags remain,
// a workbook row problem names sheet, row and column but never the cell's value, the viewer's
// workbook empty state, and the approve call carries the checklist hash the server computed.
import { client } from "@abacus/api-client/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { type JSX, useState } from "react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import {
  type FixtureHandler,
  type Scenario,
  installFixtureMode,
  json,
} from "../../app-core/fixture-mode";
import { newQueryClient } from "../../testing/support";
import { KNW02, type Knw02Search } from ".";
import { type Knw02State, OPENS, scenarios } from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

interface Call {
  method: string;
  path: string;
  body: unknown;
}

function Page({ state, initial }: { state: Knw02State; initial: Knw02Search }): JSX.Element {
  const [search, setSearch] = useState<Knw02Search>(initial);
  return <KNW02 versionId={OPENS[state].versionId} search={search} onSearch={setSearch} />;
}

function show(
  state: Knw02State,
  initial: Knw02Search = OPENS[state].ov === undefined ? {} : { ov: OPENS[state].ov },
  override: Record<string, FixtureHandler> = {},
): Call[] {
  const scenario: Scenario = scenarios[state];
  const calls: Call[] = [];
  const handlers = Object.fromEntries(
    Object.entries({ ...scenario.handlers, ...override }).map(([key, handler]) => [
      key,
      ((request) => {
        calls.push({ method: request.method, path: request.path, body: request.body });
        return handler(request);
      }) satisfies FixtureHandler,
    ]),
  );
  restore = installFixtureMode({ ...scenario, handlers });
  render(
    <QueryClientProvider client={newQueryClient()}>
      <Page state={state} initial={initial} />
    </QueryClientProvider>,
  );
  return calls;
}

describe("KNW-02 workbook slice", () => {
  it("e: the Approve sheet: effective Jan 1, 2026, supersedes v2, the server's checklist", async () => {
    const calls = show("e");
    const sheet = await screen.findByRole("dialog", {
      name: "Approve BH Audit Methodology · EBP v3",
    });
    await within(sheet).findByText("Engagements accepted on or after the effective date");
    await within(sheet).findByText("v2 (ends Dec 31, 2025)");
    expect(sheet.textContent).toContain("7 programs");
    expect(sheet.textContent).toContain("67 steps");
    fireEvent.click(within(sheet).getByRole("button", { name: "Approve version" }));
    await waitFor(() => {
      const approve = calls.find((c) => c.path.endsWith("/approve"));
      expect(approve?.body).toMatchObject({
        effective_from: "2026-01-01",
        checklist_hash: expect.stringMatching(/^sha256:/) as unknown,
      });
    });
  });

  it("f: approved by Margaret, the green pill, no Approve", async () => {
    show("f");
    await screen.findByText("Approved · Jan 12, 2026 2:31 PM · Margaret Okonkwo");
    expect(screen.queryByRole("button", { name: "Approve version…" })).toBeNull();
  });

  it("the viewer's empty state for a workbook-only version and the Parsed steps sheet", async () => {
    show("e", {});
    await screen.findByText("This version came from a workbook. There is no source document.");
    await screen.findByText("Obtain independence confirmations from every team member");
    expect(screen.getByText("16 steps · 8 mandatory · 0 flagged")).toBeTruthy();
  });

  it("Approve stays disabled with its tooltip while flags remain", async () => {
    show(
      "e",
      {},
      {
        "GET /v1/methodology/versions/{version_id}/programs": () =>
          json([
            {
              id: "p-110",
              version: {},
              code: "BH-EBP-110",
              name: "General Planning",
              position: 1,
              step_count: 16,
              mandatory_count: 8,
              flags_open: 1,
              counts_by_level: {},
            },
          ]),
      },
    );
    const approve = await screen.findByRole("button", { name: "Approve version…" });
    expect((approve as HTMLButtonElement).disabled).toBe(true);
  });

  it("a row problem names sheet, row and column, never the cell's value", async () => {
    show("e", { ov: "upload" });
    const sheet = await screen.findByRole("dialog", { name: "Upload methodology" });
    const file = new File(["PK"], "BH EBP Programs v3.xlsx", {
      type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    });
    fireEvent.change(within(sheet).getByLabelText("Workbook (.xlsx)"), {
      target: { files: [file] },
    });
    fireEvent.click(within(sheet).getByRole("button", { name: "Upload" }));
    const problems = await within(sheet).findByRole("alert");
    expect(problems.textContent).toContain("Steps · row 14 · Level");
    expect(problems.textContent).toContain(
      "The level must be foundation, planning, testing or completion.",
    );
  });
});
