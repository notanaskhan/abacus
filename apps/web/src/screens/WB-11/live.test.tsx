// WB-11 live (S47, TASK-8338): the drawer over its host reads GET /v1/integrations/{key} and
// draws only what the API says; Disconnect… needs the typed name and posts the seen version.
// Figures and words are the handoff's WB-11 a and f.
import type { ConnectIntegrationDetailOut } from "@abacus/api-client";
import { client } from "@abacus/api-client/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { ov } from "../../routes/to";
import { newQueryClient } from "../../testing/support";
import { IntegrationLayer } from "./live";

const DETAIL: ConnectIntegrationDetailOut = {
  key: "cch_axcess_tax",
  name: "CCH Axcess Tax",
  status: "connected",
  status_line: null,
  connection: {
    mode: "token",
    auth_mode_label: "Firm connection · access token",
    connected_by: "Felix Andersen",
    connected_at: "2026-01-14T15:12:00Z",
    token_renews_at: "2026-10-12T05:00:00Z",
    last_sync_at: "2026-09-14T14:02:00Z",
    linked_count: null,
    linked_label_code: null,
    mapping_ref: null,
  },
  may_do: {
    read: [
      { label: "Return list and status", gate_label: null, state: "allowed" },
      { label: "Field values", gate_label: null, state: "allowed" },
      { label: "Diagnostics", gate_label: null, state: "allowed" },
      { label: "E-file acknowledgements", gate_label: null, state: "allowed" },
    ],
    write: [],
    never: [],
  },
  health: {
    summary: "Synced",
    events: [{ id: "e1", kind: "synced", at: "2026-09-14T14:02:00Z", label: "Synced", ok: true }],
  },
  dependents: { count: 0, paused: false, items: [] },
  who_can_use: "",
  managed_by: "Felix Andersen",
  consent: null,
  allowed_actions: ["integration.connect_firm", "integration.disconnect_firm"],
  version: 3,
};

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

function serve(detail: ConnectIntegrationDetailOut): Request[] {
  const seen: Request[] = [];
  vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
    const request = input instanceof Request ? input : new Request(String(input));
    seen.push(request.clone());
    const body = request.url.endsWith("/disconnect")
      ? { key: detail.key, status: "disconnected", suspended_client_connections: 0 }
      : detail;
    return Promise.resolve(
      new Response(JSON.stringify(body), { headers: { "content-type": "application/json" } }),
    );
  });
  return seen;
}

function open(): void {
  render(
    <QueryClientProvider client={newQueryClient()}>
      <IntegrationLayer ref={ov.WB11("cch_axcess_tax")} index={0} close={() => undefined} />
    </QueryClientProvider>,
  );
}

describe("WB-11 live drawer", () => {
  it("draws the API's connection, reads and events", async () => {
    serve(DETAIL);
    open();
    const card = await screen.findByLabelText("Connection");
    expect(within(card).getByText("Firm connection · access token")).toBeTruthy();
    expect(within(card).getByText(/Felix Andersen/)).toBeTruthy();
    for (const read of DETAIL.may_do.read) expect(screen.getByText(read.label)).toBeTruthy();
    expect(within(screen.getByLabelText("Health")).getByText(/Synced/)).toBeTruthy();
    expect(screen.queryByLabelText(/Agents using it/)).toBeNull(); // no dependents: not drawn
  });

  it("disconnects only after the typed name, with the seen version", async () => {
    const seen = serve(DETAIL);
    open();
    fireEvent.click(await screen.findByRole("button", { name: "Disconnect…" }));
    const dialog = screen.getByRole("dialog", { name: "Disconnect CCH Axcess Tax?" });
    const confirm = within(dialog).getByRole("button", { name: "Disconnect" });
    expect((confirm as HTMLButtonElement).disabled).toBe(true);
    fireEvent.change(within(dialog).getByRole("textbox"), { target: { value: "CCH Axcess Tax" } });
    fireEvent.click(confirm);
    await waitFor(() => {
      expect(seen.some((r) => r.url.endsWith("/integrations/cch_axcess_tax/disconnect"))).toBe(
        true,
      );
    });
    const posted = seen.find((r) => r.url.endsWith("/disconnect"));
    expect(await posted?.json()).toEqual({ confirm_name: "CCH Axcess Tax", seen_version: 3 });
  });

  it("names who manages it for a viewer without the firm actions (f)", async () => {
    serve({ ...DETAIL, allowed_actions: [] });
    open();
    expect(await screen.findByText("Felix Andersen manages this firm connection.")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Disconnect…" })).toBeNull();
  });
});
