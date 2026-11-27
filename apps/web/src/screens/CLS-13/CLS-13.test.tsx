// C-02-T47 (TASK-9025; DEC-6030): CLS-13 a-f and d2 render from their scenarios, whose rows are the
// exported Python scenario's. Row acceptance: "CLS-13a-f and d2 render at Tier C with every TIN
// masked and the vendor-link channel shown unavailable."
import { client } from "@abacus/api-client/client";
import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import {
  type FixtureHandler,
  type Scenario,
  installFixtureMode,
  json,
  never,
} from "../../app-core/fixture-mode";
import { renderRoutes } from "../../testing/support";
import { COPY as C } from "./copy";
import { CLS13 } from "./index";
import { CLS13_ENTITY_ID, type Cls13State, ELENA_ID, scenarios } from "./scenarios";

let restore: (() => void) | null = null;
interface Call {
  method: string;
  path: string;
  body: unknown;
}

beforeAll(() => {
  client.setConfig({ baseUrl: "http://localhost" });
});

afterEach(() => {
  cleanup();
  restore?.();
  restore = null;
});

function show(
  state: Cls13State,
  props: { taxYear?: number; requestOpen?: boolean; expandedVendorId?: string } = {},
  over: Record<string, FixtureHandler> = {},
): Call[] {
  const calls: Call[] = [];
  const base: Scenario = scenarios[state];
  const handlers = Object.fromEntries(
    Object.entries({ ...base.handlers, ...over }).map(([key, handler]) => [
      key,
      ((request) => {
        calls.push({ method: request.method, path: request.path, body: request.body });
        return handler(request);
      }) satisfies FixtureHandler,
    ]),
  );
  restore = installFixtureMode({ ...base, handlers });
  renderRoutes([
    { path: "/", component: () => <CLS13 clientEntityId={CLS13_ENTITY_ID} {...props} /> },
  ]);
  return calls;
}

function vendor(name: string): HTMLElement {
  const row = document.querySelector<HTMLElement>(`[data-vendor="${name}"]`);
  if (row === null) throw new Error(`no vendor ${name}`);
  return row;
}

async function loaded(): Promise<void> {
  await screen.findByText(C.title);
}

describe("CLS-13 1099 / W-9 tracker", () => {
  it("CLS-13a default: twelve vendors, six reportable, two requested, one TIN mismatch", async () => {
    show("a");
    await loaded();
    const tiles = document.querySelector<HTMLElement>('[data-cls13="tiles"]');
    for (const n of ["12", "6", "2", "1", "0"]) expect(tiles?.textContent).toContain(n);
    expect(document.querySelectorAll("[data-vendor]")).toHaveLength(12);
    const larimer = vendor("Larimer Street Properties, LLC");
    expect(within(larimer).getByText("LLC (partnership)")).toBeTruthy();
    expect(within(larimer).getByText("1099-MISC · Box 1 Rents")).toBeTruthy();
    expect(within(larimer).getByText("$78,400.00")).toBeTruthy();
    expect(within(larimer).getByText("••-•••4471")).toBeTruthy();
    expect(
      within(vendor("Sound Electric Contractors, LLC")).getByText("•••-••-6612"),
    ).toBeTruthy();
    expect(within(vendor("Mile High Window Cleaning")).getByText("Requested Sep 11")).toBeTruthy();
    expect(
      within(vendor("Front Range Plumbing Co.")).getByText("Below $2,000 · watch"),
    ).toBeTruthy();
    expect(within(vendor("Elena Ruiz Design")).getByText(C.backup.watch)).toBeTruthy();
    expect(
      within(vendor("Hartwell & Lowe LLP")).getByText("1099-NEC · attorney fees"),
    ).toBeTruthy();
    expect(within(vendor("Hartwell & Lowe LLP")).getByText(C.threshold.attorneyNote)).toBeTruthy();
    const cascade = vendor("Cascade Coffee Importers, Inc.");
    expect(within(cascade).getByText(C.form.card)).toBeTruthy();
    expect(within(cascade).getByText("$41,260.00")).toBeTruthy();
    expect(within(cascade).getByText(C.threshold.card)).toBeTruthy();
    expect(within(vendor("Rocky Ridge Dairy Co.")).getByText(C.threshold.exempt)).toBeTruthy();
    expect(screen.getByRole("button", { name: C.requestW9s(2) })).toBeTruthy();
    const approve = screen.getByRole("button", { name: C.approve });
    expect(approve.hasAttribute("disabled")).toBe(true);
    expect(approve.getAttribute("title")).toBe(C.approveClosed("Jan 11, 2027"));
  });

  it("CLS-13 acceptance: every TIN is masked and no full TIN is ever on the page", async () => {
    show("a");
    await loaded();
    for (const cell of document.querySelectorAll<HTMLElement>("[data-tin]")) {
      const text = cell.textContent;
      expect(text === "—" || /^(••-•••|•••-••-)\d{4}$/.test(text), text).toBe(true);
    }
    expect(document.body.textContent).not.toMatch(/\b\d{2}-\d{7}\b|\b\d{3}-\d{2}-\d{4}\b/);
  });

  it("CLS-13b acceptance: the W-9 request drawer, the vendor-link channel unavailable, a person's send", async () => {
    const calls = show("b", { requestOpen: true });
    const drawer = await screen.findByRole("dialog", { name: C.request.title });
    expect(within(drawer).getByText("Mile High Window Cleaning")).toBeTruthy();
    expect(within(drawer).getByText("$2,640.00")).toBeTruthy();
    expect(within(drawer).getByText("Front Range Plumbing Co.")).toBeTruthy();
    expect(within(drawer).getByText("$1,450.00")).toBeTruthy();
    const link = within(drawer).getByRole("radio", { name: new RegExp(C.request.vendorLink) });
    expect(link.hasAttribute("disabled")).toBe(true);
    expect(within(drawer).getByText(C.request.unavailable)).toBeTruthy();
    expect(within(drawer).getByText(C.request.wording)).toBeTruthy();
    expect(calls.filter((c) => c.method === "POST")).toHaveLength(0);
    fireEvent.click(within(drawer).getByRole("button", { name: C.request.send(2) }));
    await waitFor(() => {
      expect(calls.filter((c) => c.path.endsWith("/w9-requests"))).toHaveLength(1);
    });
    const sent = calls.find((c) => c.path.endsWith("/w9-requests"));
    expect((sent?.body as { channel: string; vendor_ids: string[] }).channel).toBe("portal");
    expect((sent?.body as { vendor_ids: string[] }).vendor_ids).toHaveLength(2);
  });

  it("CLS-13c TIN mismatch: the inline panel and its two actions", async () => {
    show("c", { expandedVendorId: ELENA_ID });
    await loaded();
    const panel = await waitFor(() => {
      const found = document.querySelector<HTMLElement>(`[data-mismatch="${ELENA_ID}"]`);
      if (found === null) throw new Error("no panel");
      return found;
    });
    expect(panel.textContent).toContain(
      "IRS TIN Matching, Aug 28: name/TIN combination does not match.",
    );
    expect(panel.textContent).toContain("Backup withholding at 24% becomes mandatory");
    fireEvent.click(within(panel).getByRole("button", { name: C.mismatch.requestCorrected }));
    const request = await screen.findByRole("dialog", { name: C.request.title });
    expect(within(request).getByText("Elena Ruiz Design")).toBeTruthy();
    expect(within(request).getByRole("button", { name: C.request.send(1) })).toBeTruthy();
    fireEvent.click(within(request).getByRole("button", { name: C.request.cancel }));
    await waitFor(() => {
      expect(screen.queryByRole("dialog", { name: C.request.title })).toBeNull();
    });
    fireEvent.click(within(panel).getByRole("button", { name: C.mismatch.markStarted }));
    const dialog = await screen.findByRole("dialog", { name: C.backupDialog.title });
    const confirm = within(dialog).getByRole("button", { name: C.backupDialog.confirm });
    expect(confirm.hasAttribute("disabled")).toBe(true); // a reason first
  });

  it("CLS-13d January: the December close locked, Approve 1099 batch opens", async () => {
    show("d");
    await loaded();
    const approve = screen.getByRole("button", { name: C.approve });
    expect(approve.hasAttribute("disabled")).toBe(false);
  });

  it("CLS-13d2 filed: six rows Filed · IRIS and the Filed tile reads 6", async () => {
    show("d2");
    await loaded();
    await waitFor(() => {
      expect(screen.getAllByText(C.efile.filed)).toHaveLength(6);
    });
    const tiles = document.querySelector<HTMLElement>('[data-cls13="tiles"]');
    expect(tiles?.textContent).toContain("6");
    expect(screen.getByRole("button", { name: C.approve }).hasAttribute("disabled")).toBe(true);
  });

  it("CLS-13e prior year: five rows Accepted · Jan 29, 2026, no Vendors paid figure", async () => {
    show("e", { taxYear: 2025 });
    await loaded();
    expect(screen.getByText(C.taxYear(2025))).toBeTruthy();
    expect(document.querySelectorAll("[data-vendor]")).toHaveLength(5);
    expect(screen.getAllByText(C.efile.accepted)).toHaveLength(5);
    expect(screen.getAllByText("Jan 29, 2026")).toHaveLength(5);
    expect(within(vendor("Larimer Street Properties, LLC")).getByText("$114,000.00")).toBeTruthy();
    expect(document.querySelector('[data-cls13="vendors-paid-none"]')).not.toBeNull();
    expect(screen.getByText(/threshold \$600 for 2025 payments/)).toBeTruthy();
  });

  it("CLS-13f empty: no vendor payments synced", async () => {
    show("f");
    expect(await screen.findByText(C.empty.title)).toBeTruthy();
    expect(screen.getByRole("button", { name: C.empty.connect })).toBeTruthy();
  });

  it("a vendor opens its drawer with payments by method; card is excluded", async () => {
    show("a");
    await loaded();
    fireEvent.click(
      within(vendor("Cascade Coffee Importers, Inc.")).getByRole("button", {
        name: "Cascade Coffee Importers, Inc.",
      }),
    );
    const drawer = await screen.findByRole("dialog", { name: "Cascade Coffee Importers, Inc." });
    expect(within(drawer).getByText(C.drawer.method.card ?? "Card")).toBeTruthy();
    expect(within(drawer).getByText(C.drawer.excluded)).toBeTruthy();
  });

  it("loading: skeletons while the read is pending", async () => {
    show("a", {}, { "GET /v1/client-entities/{client_entity_id}/information-returns": () => never() });
    await waitFor(() => {
      expect(document.querySelector('[data-screen="CLS-13"][aria-busy="true"]')).not.toBeNull();
    });
  });

  it("error: a failed read offers Retry", async () => {
    show(
      "a",
      {},
      {
        "GET /v1/client-entities/{client_entity_id}/information-returns": () =>
          json({ detail: "boom" }, 500),
      },
    );
    expect(await screen.findByRole("button", { name: C.retry })).toBeTruthy();
  });

  it("not allowed: a walled entity's 404 reads as the error state", async () => {
    show(
      "a",
      {},
      {
        "GET /v1/client-entities/{client_entity_id}/information-returns": () =>
          json({ detail: "not found" }, 404),
      },
    );
    expect(await screen.findByText(C.failedToLoad)).toBeTruthy();
  });

  it("no agent-owned control approves, signs off, releases, sends or posts", async () => {
    show("a");
    await loaded();
    for (const word of ["Sign off", "Release", "Post"]) {
      expect(screen.queryByRole("button", { name: new RegExp(`^${word}`) })).toBeNull();
    }
  });
});
