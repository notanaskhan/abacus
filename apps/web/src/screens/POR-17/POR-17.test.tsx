// POR-17 live (TASK-8355): the respondent page on fixture-mode handlers. The expired and answered
// views, the open request (the authorization quoted, the balance foots), the difference computed
// exactly as the respondent types, and Submit gated on a choice, the verified email (the CSRF
// value the verify answer carries) and the attestation; the receipt is state b.
import type { RespondentRequestOut } from "@abacus/api-client";
import { client } from "@abacus/api-client/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { type FixtureHandler, installFixtureMode, json } from "../../app-core/fixture-mode";
import { newQueryClient } from "../../testing/support";
import { POR17, differenceOf } from ".";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});
let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

// The handoff's POR-17a request (spec.md): Summit Trail, Granite Peak's three invoices.
const REQUEST: RespondentRequestOut = {
  as_of: "2026-06-30",
  authorization_text:
    "Our auditors, Brightwater Hale LLP, are auditing our financial statements for the year ended June 30, 2026. Please confirm directly to them the balance you owed us at that date. This is not a request for payment.",
  authorized_by: "Luis Ferrante, Chief Financial Officer",
  authorized_on: "2026-09-18",
  balance_per_client: "412600.00",
  client_accounts: [],
  client_name: "Granite Peak Outdoor Supply, Inc.",
  firm_name: "Brightwater Hale LLP",
  invoices: [
    { number: "INV-26-1841", invoice_date: "2026-05-28", amount: "138200.00" },
    { number: "INV-26-1907", invoice_date: "2026-06-12", amount: "151750.00" },
    { number: "INV-26-1966", invoice_date: "2026-06-26", amount: "122650.00" },
  ],
  list_every_account: false,
  reference: "C2",
  respondent_org: "Summit Trail Outfitters",
  type: "accounts_receivable",
};
const VIEW = "GET /v1/confirm/{token}";

function show(handlers: Record<string, FixtureHandler>) {
  const posted: { path: string; body: unknown; csrf: string | null }[] = [];
  const wrapped = Object.fromEntries(
    Object.entries(handlers).map(([k, h]) => [
      k,
      ((r) => {
        posted.push({ path: r.path, body: r.body, csrf: r.headers?.get("X-Abacus-CSRF") ?? null });
        return h(r);
      }) satisfies FixtureHandler,
    ]),
  );
  restore = installFixtureMode({ state: "a", handlers: wrapped });
  render(
    <QueryClientProvider client={newQueryClient()}>
      <POR17 token="t0k3n" />
    </QueryClientProvider>,
  );
  return posted;
}

describe("POR-17", () => {
  it("d: an expired link says so, naming no firm (DV-7)", async () => {
    show({ [VIEW]: () => json({ state: "expired" }) });
    expect(await screen.findByText("This confirmation link has expired")).toBeTruthy();
    expect(screen.queryByText(/Brightwater/)).toBeNull();
  });

  it("e: an answered link gives the date it was answered", async () => {
    show({ [VIEW]: () => json({ state: "answered", answered_on: "2026-09-25" }) });
    expect(
      await screen.findByText("This confirmation was already answered on September 25, 2026."),
    ).toBeTruthy();
  });

  it("a: the request quotes the authorization and the invoices foot to the balance", async () => {
    show({ [VIEW]: () => json({ state: "open", request: REQUEST }) });
    expect(
      await screen.findByText(
        "Please confirm the amount you owed Granite Peak Outdoor Supply, Inc. at June 30, 2026",
      ),
    ).toBeTruthy();
    expect(screen.getByText(REQUEST.authorization_text)).toBeTruthy();
    expect(screen.getByText("$412,600.00")).toBeTruthy();
    expect(screen.getByText("412,600.00")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Submit response" })).toHaveProperty(
      "disabled",
      true,
    );
  });

  it("c: the difference is computed exactly (286,900 − 282,600 = 4,300)", () => {
    expect(differenceOf("286900.00", "282600")).toBe("4300.00");
    expect(differenceOf("0.10", "0.30")).toBe("-0.20");
    expect(differenceOf("412600.00", "")).toBeNull();
    expect(differenceOf("412600.00", "abc")).toBeNull();
  });

  it("b: agree, verify the email, attest and submit; the CSRF value rides the submit", async () => {
    const posted = show({
      [VIEW]: () => json({ state: "open", request: REQUEST }),
      "POST /v1/confirm/{token}/code": () => json({ accepted: true }, 202),
      "POST /v1/confirm/{token}/code/verify": () =>
        new Response(JSON.stringify({ verified: true }), {
          status: 200,
          headers: { "Content-Type": "application/json", "X-Abacus-CSRF": "c5rf" },
        }),
      "POST /v1/confirm/{token}/response": () =>
        json(
          {
            agrees: true,
            difference: "0.00",
            receipt_id: "r1",
            reference: "C2",
            respondent_balance: null,
            submitted_at: "2026-09-25T16:12:00Z",
            verified_email: "r.imholt@example.com",
          },
          201,
        ),
    });
    fireEvent.click(
      await screen.findByRole("button", { name: "The balance agrees with our records" }),
    );
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Rachel Imholt" } });
    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "r.imholt@example.com" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send code" }));
    const boxes = await screen.findAllByRole("textbox", { name: /digit/i });
    fireEvent.paste(boxes[0] as HTMLElement, { clipboardData: { getData: () => "123456" } });
    fireEvent.click(
      await screen.findByRole("switch", {
        name: "I confirm this response is accurate and that I'm authorized to give it.",
      }),
    );
    const submit = screen.getByRole("button", { name: "Submit response" });
    await waitFor(() => {
      expect(submit).toHaveProperty("disabled", false);
    });
    fireEvent.click(submit);
    expect(
      await screen.findByText("Thank you — your response was sent to Brightwater Hale LLP"),
    ).toBeTruthy();
    const sent = posted.find((p) => p.path.endsWith("/response"));
    expect(sent?.csrf).toBe("c5rf");
    expect(sent?.body).toMatchObject({
      agrees: true,
      attestation: true,
      respondent_name: "Rachel Imholt",
    });
  });
});
