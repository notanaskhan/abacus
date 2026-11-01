// POR-13 · My K-1s (T-02-T27). One test per artboard (a–f) on its fixture scenario; every read
// in the OpenAPI schema; no state shows a draft, a full TIN or another recipient's amounts; the
// reduced shell has one nav item; nothing is written until a person sends a change.
import { client } from "@abacus/api-client/client";
import { toastStore } from "@abacus/ui";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import {
  type FixtureHandler,
  type Scenario,
  installFixtureMode,
} from "../../app-core/fixture-mode";
import { validateResponse } from "../../fixtures/schema-check";
import {
  type Por13Variant,
  portalK1Detail,
  portalK1Expected,
  portalK1Rows,
} from "../../fixtures/seed/portal-k1s";
import { newQueryClient } from "../../testing/support";
import { POR13 } from ".";
import { COPY } from "./copy";
import { OPENING, type Por13State, STATES, scenarios } from "./scenarios";

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

interface Seen {
  calls: { method: string; path: string; body: unknown }[];
}

function show(state: Por13State, override: Record<string, FixtureHandler> = {}): Seen {
  const seen: Seen = { calls: [] };
  const scenario: Scenario = scenarios[state];
  const handlers = Object.fromEntries(
    Object.entries({ ...scenario.handlers, ...override }).map(([key, handler]) => [
      key,
      ((request) => {
        seen.calls.push({ method: request.method, path: request.path, body: request.body });
        return handler(request);
      }) satisfies FixtureHandler,
    ]),
  );
  restore = installFixtureMode({ ...scenario, handlers });
  const opening = OPENING[state];
  render(
    <QueryClientProvider client={newQueryClient()}>
      <POR13 {...(opening === undefined ? {} : { opening })} />
    </QueryClientProvider>,
  );
  return seen;
}

const writes = (seen: Seen) => seen.calls.filter((c) => c.method !== "GET");

function noLeaks(): void {
  const text = document.body.textContent;
  expect(text).not.toMatch(/pre-release|Accrued/i);
  expect(text).not.toMatch(/\d{3}-\d{2}-\d{4}|\d{2}-\d{7}/); // never a full TIN
}

describe("POR-13 My K-1s", () => {
  it("covers a–f", () => {
    expect(STATES).toEqual(["a", "b", "c", "d", "e", "f"]);
  });

  it("every read is in the schema", () => {
    const variants: Por13Variant[] = [
      "nora_released",
      "pell_expected",
      "pell_released",
      "nora_amended",
      "meera_expected",
    ];
    for (const v of variants) {
      expect(validateResponse("GET", "/v1/portal/k1s", portalK1Rows(v))).toEqual([]);
      expect(validateResponse("GET", "/v1/portal/k1s/expected", portalK1Expected(v))).toEqual([]);
      for (const row of portalK1Rows(v)) {
        expect(
          validateResponse("GET", "/v1/portal/k1s/{package_id}", portalK1Detail(v, row.id)),
        ).toEqual([]);
      }
    }
  });

  it("a · Nora's released K-1: boxes, the total rule, documents and her masked TIN", async () => {
    const seen = show("a");
    expect(
      await screen.findByText("Calloway Family Trust — 2025 Schedule K-1 (Form 1041)"),
    ).toBeTruthy();
    expect(await screen.findByText("40,000")).toBeTruthy();
    expect(screen.getByText("120,000")).toBeTruthy();
    expect(screen.getByText("96,000")).toBeTruthy();
    expect(screen.getByText("160,000")).toBeTruthy();
    expect(screen.getByText(COPY.distributions(2025))).toBeTruthy();
    expect(screen.getByText("Released Sep 29")).toBeTruthy();
    expect(screen.getByRole("button", { name: /Schedule K-1 \(Form 1041\) — PDF/ })).toBeTruthy();
    expect(screen.getByRole("button", { name: /IL Schedule K-1/ })).toBeTruthy();
    expect(await screen.findByText("•••-••-5512")).toBeTruthy();
    expect(screen.getByText(COPY.details.onFile)).toBeTruthy();
    noLeaks();
    expect(writes(seen)).toEqual([]);
  });

  it("b · not released yet: who issues it and by when, no amounts and no documents", async () => {
    show("b");
    expect(
      await screen.findByText("Ridgeline Property Partners, LP — 2025 Schedule K-1 (Form 1065)"),
    ).toBeTruthy();
    expect(screen.getByText("Not released yet")).toBeTruthy();
    expect(screen.getByText(/^Expected by Sep 15, 2026/)).toBeTruthy();
    expect(screen.getByText(COPY.k3Title)).toBeTruthy();
    expect(screen.queryByRole("table")).toBeNull();
    expect(screen.queryByRole("button", { name: COPY.downloadAll })).toBeNull();
    noLeaks();
  });

  it("c · Pell Street's released Ridgeline K-1 and Download all", async () => {
    const seen = show("c");
    expect(await screen.findByText("400,270")).toBeTruthy();
    expect(screen.getByText("5,980")).toBeTruthy();
    expect(screen.getByText("2,015")).toBeTruthy();
    expect(screen.getByText("180,000")).toBeTruthy();
    expect(screen.getByText(COPY.k3Included)).toBeTruthy();
    expect(screen.getByRole("button", { name: /State K-1s — IL, CO, NY \(3\)/ })).toBeTruthy();
    expect(screen.getByRole("button", { name: /Partner letter/ })).toBeTruthy();
    // Nora's figures never show to Pell Street.
    expect(screen.queryByText("40,000")).toBeNull();
    noLeaks();
    fireEvent.click(screen.getByRole("button", { name: COPY.downloadAll }));
    await waitFor(() => {
      expect(seen.calls.some((c) => c.path.endsWith("/download"))).toBe(true);
    });
    expect(writes(seen)).toEqual([]);
  });

  it("d · the taxpayer-ID sheet asks for a signed W-9, never a typed number", async () => {
    show("d");
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText(COPY.tinSheet.upload)).toBeTruthy();
    expect(within(dialog).getByText(COPY.tinSheet.helper)).toBeTruthy();
    expect(within(dialog).queryByRole("textbox")).toBeNull();
  });

  it("d · the chosen file goes up as the recipient's own upload, W-9 or W-8", async () => {
    const seen = show("d");
    const dialog = await screen.findByRole("dialog");
    const send = within(dialog).getByRole("button", { name: COPY.tinSheet.submit });
    expect(send).toHaveProperty("disabled", true);
    fireEvent.click(within(dialog).getByRole("radio", { name: COPY.tinSheet.w8 }));
    const input = dialog.querySelector("input[type=file]");
    const file = new File(["%PDF-1.7"], "w8-signed.pdf", { type: "application/pdf" });
    fireEvent.change(input as HTMLInputElement, { target: { files: [file] } });
    fireEvent.click(within(dialog).getByRole("button", { name: COPY.tinSheet.submit }));
    await waitFor(() => {
      expect(writes(seen).map((c) => c.path)).toEqual([
        expect.stringMatching(/\/details-changes:upload$/),
      ]);
    });
  });

  it("e · the amended K-1 over the struck, superseded one", async () => {
    show("e");
    expect(await screen.findByText("Superseded (amended K-1)")).toBeTruthy();
    expect(screen.getByText(/^Amended 2025 K-1 · /)).toBeTruthy();
    const struck = screen
      .getAllByText("Calloway Family Trust — 2025 Schedule K-1 (Form 1041)")
      .filter((el) => el.className.includes("line-through"));
    expect(struck).toHaveLength(1);
  });

  it("f · Meera's role union: the full shell with the banner", async () => {
    show("f");
    expect(await screen.findByText(COPY.roleUnion)).toBeTruthy();
    expect(
      await screen.findByText("Ridgeline Property Partners, LP — 2025 Schedule K-1 (Form 1065)"),
    ).toBeTruthy();
    noLeaks();
  });

  it("a K-1-only person's shell has one nav item", async () => {
    show("a");
    await screen.findByText("40,000");
    const nav = screen.getAllByRole("navigation")[0];
    expect(nav).toBeTruthy();
    if (nav !== undefined) {
      expect(
        within(nav)
          .getAllByRole("button")
          .map((l) => l.textContent),
      ).toEqual([COPY.active]);
    }
  });

  it("an address change goes to the firm to check", async () => {
    const seen = show("a");
    await screen.findByText("40,000");
    const update = screen.getAllByRole("button", { name: COPY.details.update });
    fireEvent.click(update[update.length - 1] as HTMLElement);
    const dialog = await screen.findByRole("dialog");
    const boxes = within(dialog).getAllByRole("textbox");
    fireEvent.change(boxes[0] as HTMLElement, { target: { value: "100 Lake St" } });
    fireEvent.change(boxes[2] as HTMLElement, { target: { value: "Evanston" } });
    fireEvent.change(boxes[4] as HTMLElement, { target: { value: "60201" } });
    fireEvent.click(within(dialog).getByRole("button", { name: COPY.addressSheet.submit }));
    await waitFor(() => {
      expect(writes(seen).map((c) => c.path)).toHaveLength(1);
    });
    expect((writes(seen)[0]?.body as { kind: string }).kind).toBe("address");
  });

  it("DV-12 · with a published disclosure, Download all asks first; agreeing records consent, then downloads", async () => {
    const disclosure = {
      id: "0d1e2f30-0000-4000-8000-000000000001",
      version_no: 1,
      body: "Synthetic disclosure, paragraph one.\n\nParagraph two.",
      imported_at: "2026-09-01T12:00:00Z",
    };
    const seen = show("c", {
      "GET /v1/portal/k1-furnishing-disclosure": () => Response.json(disclosure),
    });
    await screen.findByText("400,270");
    await waitFor(() => {
      expect(seen.calls.some((c) => c.path.endsWith("/k1-furnishing-disclosure"))).toBe(true);
    });
    fireEvent.click(screen.getByRole("button", { name: COPY.downloadAll }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText("Paragraph two.")).toBeTruthy();
    expect(seen.calls.some((c) => c.path.endsWith("/download"))).toBe(false);
    fireEvent.click(within(dialog).getByRole("button", { name: COPY.consent.agree }));
    await waitFor(() => {
      expect(seen.calls.some((c) => c.path.endsWith("/download"))).toBe(true);
    });
    const consent = writes(seen).find((c) => c.path.endsWith("/e-furnishing-consent"));
    expect(consent?.body).toEqual({ decision: "given", disclosure_version_id: disclosure.id });
  });

  it("DV-12 · declining records the decline and downloads nothing", async () => {
    const seen = show("c", {
      "GET /v1/portal/k1-furnishing-disclosure": () =>
        Response.json({
          id: "0d1e2f30-0000-4000-8000-000000000001",
          version_no: 1,
          body: "Synthetic disclosure.",
          imported_at: "2026-09-01T12:00:00Z",
        }),
    });
    await screen.findByText("400,270");
    await waitFor(() => {
      expect(seen.calls.some((c) => c.path.endsWith("/k1-furnishing-disclosure"))).toBe(true);
    });
    fireEvent.click(screen.getByRole("button", { name: COPY.downloadAll }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.click(within(dialog).getByRole("button", { name: COPY.consent.decline }));
    await waitFor(() => {
      expect(writes(seen).map((c) => (c.body as { decision?: string }).decision)).toEqual([
        "declined",
      ]);
    });
    expect(seen.calls.some((c) => c.path.endsWith("/download"))).toBe(false);
  });
});
