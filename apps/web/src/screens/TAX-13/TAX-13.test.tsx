// T-03-T11 (TASK-3324): TAX-13 in fixture mode. Row: "TAX-13a, b and c render in fixture mode with
// tallies footing, no dollar signs in cells and Thornbury's Prepare 4768 action disabled with the gate
// to clear."
import { client } from "@abacus/api-client/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { type FixtureRequest, installFixtureMode, json } from "../../app-core/fixture-mode";
import { tax13SheetOverlay } from "../../fixtures/scenarios/TAX-13";
import { tax13FiledForm, tax13SeasonE } from "../../fixtures/seed/tax13";
import { newQueryClient } from "../../testing/support";
import { Extensions, type ExtensionsProps } from "./Extensions";
import { type Tax13State, scenarios } from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

function show(state: Tax13State, props: Partial<ExtensionsProps> = {}): void {
  restore = installFixtureMode(scenarios[state]);
  render(
    <QueryClientProvider client={newQueryClient()}>
      <Extensions taxYear={2025} {...props} />
    </QueryClientProvider>,
  );
}

const drawn = (selector: string): Promise<HTMLElement> =>
  waitFor(
    () => {
      const found = document.querySelector<HTMLElement>(selector);
      expect(found).not.toBeNull();
      return found as HTMLElement;
    },
    { timeout: 6000 },
  );

const count = (tile: string): number =>
  Number(document.querySelector(`[data-tile='${tile}'] span:last-child`)?.textContent);

describe("TAX-13", () => {
  it("a: the tallies foot, 79 + 82 = 161", async () => {
    show("a");
    await drawn("[data-tax13='extensions'] tbody tr");
    expect(count("open") + count("filed")).toBe(count("extended"));
    expect(count("extended")).toBe(161);
    expect(count("likely")).toBe(2);
  });

  it("a: no dollar signs in cells, and tomorrow's due is urgent", async () => {
    show("a");
    const table = await drawn("[data-tax13='extensions']");
    await waitFor(() => {
      expect(table.textContent).toContain("Ridgeline Property Partners");
    });
    expect(table.textContent).not.toContain("$");
    const row = document.querySelector("[data-client^='Ridgeline']");
    expect(row?.querySelector("[data-due='urgent']")?.textContent).toContain("1 day");
    expect(row?.querySelector("[data-col='paid']")?.textContent).toContain("IL 28,044");
  });

  it("b: Q3 installments foot to 5 due, with Resend on those awaiting", async () => {
    show("b", { tab: "estimates", taxYear: 2026 });
    const table = await drawn("[data-tax13='estimates'] tbody tr");
    expect(table).toBeTruthy();
    expect(count("paid") + count("scheduled") + count("confirmation_requested")).toBe(
      count("due"),
    );
    expect(count("not_required")).toBe(2);
    expect(document.querySelectorAll("[data-tax13='estimates'] button")).toHaveLength(2);
  });

  it("c: Thornbury's Prepare 4768… is disabled with the gate; Lakeshore's is enabled", async () => {
    show("c", { segment: "likely" });
    await drawn("[data-client='Lakeshore Literacy Alliance']");
    const thornbury = document.querySelector("[data-client='Estate of Walter Thornbury']");
    const blocked = thornbury?.querySelector("[data-blocked]");
    expect(blocked?.getAttribute("data-blocked")).toContain("G1 and G3");
    expect(blocked?.querySelector("button")?.hasAttribute("disabled")).toBe(true);
    const lakeshore = document.querySelector("[data-client='Lakeshore Literacy Alliance']");
    const prepare = Array.from(lakeshore?.querySelectorAll("button") ?? []).find((b) =>
      b.textContent.includes("Prepare 8868"),
    );
    expect(prepare?.hasAttribute("disabled")).toBe(false);
  });
});

const button = (name: string): HTMLButtonElement | undefined =>
  [...document.querySelectorAll("button")].find((b) => b.textContent === name);

const sheetFooter = (name: string): Promise<HTMLButtonElement> =>
  waitFor(
    () => {
      const found = button(name);
      expect(found).toBeDefined();
      expect(found?.hasAttribute("disabled")).toBe(false);
      return found as HTMLButtonElement;
    },
    { timeout: 6000 },
  );

describe("T-03-T16: TAX-13 d and e", () => {
  it("d: one click labelled Send confirmation requests makes one call for three clients", async () => {
    const asked = vi.fn((r: { body: unknown }) => {
      const ids = (r.body as { return_ids: string[] }).return_ids;
      return json({
        extensions: [],
        checks: [],
        approved_payment_ids: ids,
        confirmation_request_item_ids: ids,
      });
    });
    const scenario = {
      ...scenarios.d,
      handlers: {
        ...scenarios.d.handlers,
        "POST /v1/tax/extensions:approve-and-request": asked,
      },
    };
    restore = installFixtureMode(scenario);
    render(
      <QueryClientProvider client={newQueryClient()}>
        <Extensions taxYear={2025} ov={tax13SheetOverlay} />
      </QueryClientProvider>,
    );
    await drawn("[data-extend-row]");
    expect(document.querySelectorAll("[data-extend-row]")).toHaveLength(3);
    const send = await sheetFooter("Send confirmation requests");
    send.click();
    await waitFor(
      () => {
        expect(asked).toHaveBeenCalledOnce();
      },
      { timeout: 6000 },
    );
    const body = asked.mock.calls[0]?.[0].body as {
      return_ids: string[];
      payments: { jurisdiction: string; amount: string; form?: string | null }[];
      send_confirmations: boolean;
    };
    expect(body.return_ids).toHaveLength(3);
    expect(body.send_confirmations).toBe(true);
    // Feld's federal payment as typed, and NY as proposed.
    expect(body.payments.map((p) => [p.jurisdiction, p.amount])).toContainEqual(["NY", "6000"]);
    expect(body.payments.filter((p) => p.jurisdiction === "federal")).toHaveLength(3);
  });

  it("d: each row shows its figures, and an edit below the target says so in words", async () => {
    restore = installFixtureMode(scenarios.d);
    render(
      <QueryClientProvider client={newQueryClient()}>
        <Extensions taxYear={2025} ov={tax13SheetOverlay} />
      </QueryClientProvider>,
    );
    const input = await waitFor(
      () => {
        const found = document.querySelector<HTMLInputElement>(
          "input[aria-label='Payment with extension for Elena Varga']",
        );
        expect(found).not.toBeNull();
        return found as HTMLInputElement;
      },
      { timeout: 6000 },
    );
    const card = input.closest("[data-extend-row]");
    expect(card?.querySelector("[data-field='projected']")?.textContent).toBe("3,900");
    expect(card?.querySelector("[data-field='target']")?.textContent).toContain("3,510");
    expect(card?.querySelector("[data-check]")?.textContent).toContain(
      "3,400 + 500 = 3,900 · meets the 90% target",
    );
    fireEvent.change(input, { target: { value: "100" } });
    await waitFor(() => {
      expect(card?.querySelector("[data-check='below']")?.textContent).toContain(
        "below the 90% target",
      );
    });
  });

  it("d: no reviewer function offers Submit for approval, never the send", async () => {
    restore = installFixtureMode(scenarios["not-allowed"]);
    render(
      <QueryClientProvider client={newQueryClient()}>
        <Extensions taxYear={2025} ov={tax13SheetOverlay} />
      </QueryClientProvider>,
    );
    await drawn("[data-extend-row]");
    await sheetFooter("Submit for approval");
    expect(button("Send confirmation requests")).toBeUndefined();
  });

  it("e: Varga reads Rejected with IND-031-04 in text; Feld reads Filed", async () => {
    show("e");
    await drawn("[data-client='Elena Varga']");
    const varga = document.querySelector("[data-client='Elena Varga'] [data-col='ack']");
    expect(varga?.textContent).toContain("Rejected");
    expect(varga?.querySelector("[data-reject-code]")?.textContent).toBe("IND-031-04");
    expect(
      document.querySelector("[data-client='Jonah & Claire Feld'] [data-col='ack']")?.textContent,
    ).toBe("Filed");
    expect(count("acks_pending")).toBe(1);
    expect(count("extended")).toBe(149);
  });

  it("e: Mark filed needs the filed form, and sends the line's version in If-Match", async () => {
    const patched = vi.fn((r: FixtureRequest) => {
      expect(r.body).toBeTruthy();
      return json(tax13SeasonE().items[0]);
    });
    const scenario = {
      ...scenarios.e,
      handlers: { ...scenarios.e.handlers, "PATCH /v1/tax/extensions/{extension_id}": patched },
    };
    restore = installFixtureMode(scenario);
    render(
      <QueryClientProvider client={newQueryClient()}>
        <Extensions taxYear={2025} />
      </QueryClientProvider>,
    );
    await drawn("[data-client^='Estate of Walter Thornbury']");
    const open = (await waitFor(() => {
      const found = document.querySelector(
        "[data-client^='Estate of Walter Thornbury'] [data-col='filed'] button",
      );
      expect(found).not.toBeNull();
      return found;
    })) as HTMLButtonElement;
    open.click();
    await waitFor(
      () => {
        expect(document.querySelector("[data-mark-filed]")).not.toBeNull();
      },
      { timeout: 6000 },
    );
    expect(button("Mark filed")?.hasAttribute("disabled")).toBe(true);
    const chooser = await screen.findByRole("button", { name: /^Filed form/ });
    chooser.focus();
    fireEvent.keyDown(chooser, { key: "ArrowDown" });
    fireEvent.click(await screen.findByRole("menuitemradio", { name: /Form 4868 confirmation/ }));
    (await sheetFooter("Mark filed")).click();
    await waitFor(
      () => {
        expect(patched).toHaveBeenCalledOnce();
      },
      { timeout: 6000 },
    );
    const call = patched.mock.calls[0]?.[0];
    expect(
      (call?.body as { filed_form_evidence_version_id: string }).filed_form_evidence_version_id,
    ).toBe(tax13FiledForm.id);
  });
});

describe("T-03-T11: Open in Excel", () => {
  it("fetches the view's workbook and hands it to the browser", async () => {
    const created = vi.fn(() => "blob:tax13");
    Object.assign(URL, { createObjectURL: created, revokeObjectURL: vi.fn() });
    show("a");
    const button = await waitFor(
      () => {
        const found = [...document.querySelectorAll("button")].find(
          (b) => b.textContent === "Open in Excel",
        );
        expect(found).toBeDefined();
        return found as HTMLButtonElement;
      },
      { timeout: 6000 },
    );
    button.click();
    await waitFor(() => {
      expect(created).toHaveBeenCalledOnce();
    });
  });
});
