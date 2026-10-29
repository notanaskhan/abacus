// P-07-T61 (DEC-822): the Activity tab of CLI-02 and ENG-02 over P-07-T57's routes. Acceptance
// (the task row): "Both Activity tabs render live lines with axe clean." axe runs in Playwright
// (the gallery axe harness covers CLI-02 and ENG-02); here the lines render from the live shape.
import type { AuditEventRow } from "@abacus/api-client";
import { client } from "@abacus/api-client/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { installFixtureMode, json } from "../../app-core/fixture-mode";
import { ADM07_ROWS } from "../../fixtures/seed/audit-log";
import { ACTIVITY_COPY, RecordActivity } from "./RecordActivity";

const NOW = new Date("2026-09-14T15:00:00Z");
const ROWS: readonly AuditEventRow[] = ADM07_ROWS.slice(0, 3);
let restore: (() => void) | undefined;

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

function mount(of: { client: string } | { engagement: string }, rows: readonly AuditEventRow[]) {
  restore = installFixtureMode({
    state: "activity",
    handlers: {
      "GET /v1/clients/{client_id}/activity": () => json({ items: rows, total: rows.length }),
      "GET /v1/engagements/{engagement_id}/record-activity": () =>
        json({ items: rows, total: rows.length }),
    },
  });
  const queries = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queries}>
      <RecordActivity of={of} now={NOW} tz="America/Chicago" />
    </QueryClientProvider>,
  );
}

describe("RecordActivity", () => {
  it.each([[{ client: "c-1" }], [{ engagement: "e-1" }]])(
    "AC: renders the live lines (%o)",
    async (of) => {
      mount(of, ROWS);
      const list = await screen.findByRole("list", { name: ACTIVITY_COPY.label });
      expect(list.querySelectorAll("li")).toHaveLength(ROWS.length);
    },
  );

  it("shows the empty state when the record has no lines", async () => {
    mount({ client: "c-1" }, []);
    expect(await screen.findByText(ACTIVITY_COPY.empty)).toBeTruthy();
  });
});
